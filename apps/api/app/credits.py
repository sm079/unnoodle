"""Credits: what generating costs, and an append-only ledger of every credit given and taken.

There's no payment. Admins grant credits, and invite codes give them to whoever redeems one. Queuing a generation
takes its cost at once, and a generation that fails gives it back, both in the transaction that changes its status,
so a balance never counts a job twice or forgets one. A balance is the sum of someone's entries.

Prices are fixed, so they're the same every time and can be shown before Generate (apps/web/src/lib/credits.ts
mirrors cost_of; change both together). They follow what the GPU spends: a picture takes seconds, a 5 second video
minutes, and each reference clip adds about as much again.

    uv run python -m app.credits grant someone@example.com 100 --note "for the demo"
    uv run python -m app.credits invite WELCOME --credits 50 --uses 20 [--days 14]
    uv run python -m app.credits balance someone@example.com
"""

import argparse
import sys
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, StringConstraints, TypeAdapter, ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.accounts import CurrentUser, Email
from app.db import SessionDep, make_engine
from app.models import CreditEntry, CreditKind, Generation, InviteCode, MediaType, Quality, User
from app.settings import Settings


class Prices(BaseModel):
    # Each picture, by quality
    image: dict[Quality, int]
    # Each 5 seconds of video, by quality
    video_per_5s: dict[Quality, int]
    # Added to a video for each reference clip attached
    per_clip: int


PRICES = Prices(
    image={Quality.LOW: 1, Quality.MEDIUM: 1, Quality.HIGH: 2},
    video_per_5s={Quality.LOW: 10, Quality.MEDIUM: 20, Quality.HIGH: 40},
    per_clip=10,
)


def cost_of(media_type: MediaType, quality: Quality, duration_s: int | None, clips: int) -> int:
    """The credits one generation takes. "How many" queues that many, each charged this."""
    if media_type is MediaType.IMAGE:
        return PRICES.image[quality]
    # Lengths are 5, 10 or 15 seconds; anything else is refused before it is priced
    return PRICES.video_per_5s[quality] * -(-(duration_s or 5) // 5) + PRICES.per_clip * clips


def balance(session: Session, user_id: uuid.UUID) -> int:
    total = session.scalar(select(func.coalesce(func.sum(CreditEntry.amount), 0)).where(CreditEntry.user_id == user_id))
    return int(total or 0)


def locked_balance(session: Session, user_id: uuid.UUID) -> int:
    """The balance, with the account locked until the transaction ends, so two requests at once can't both spend
    the same credits."""
    session.execute(select(User.id).where(User.id == user_id).with_for_update())
    return balance(session, user_id)


def charge(session: Session, generation: Generation) -> None:
    if generation.cost > 0:
        session.add(
            CreditEntry(
                user_id=generation.owner_id,
                amount=-generation.cost,
                kind=CreditKind.CHARGE,
                generation_id=generation.id,
            )
        )


def refund(session: Session, generation: Generation) -> None:
    """Gives back what a failed generation was charged."""
    if generation.cost > 0:
        session.add(
            CreditEntry(
                user_id=generation.owner_id, amount=generation.cost, kind=CreditKind.REFUND, generation_id=generation.id
            )
        )


class CreditsOut(BaseModel):
    balance: int
    prices: Prices


class RedeemIn(BaseModel):
    code: Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, min_length=1, max_length=32)]


router = APIRouter(prefix="/credits")


@router.get("")
def get_credits(user: CurrentUser, session: SessionDep) -> CreditsOut:
    """Your balance, and what things cost."""
    return CreditsOut(balance=balance(session, user.id), prices=PRICES)


@router.post("/redeem", responses={404: {"description": "No such code"}, 409: {"description": "Already redeemed"}})
def redeem(body: RedeemIn, user: CurrentUser, session: SessionDep) -> CreditsOut:
    """Adds an invite code's credits to your balance."""
    # Locked, so the last use of a code can't be taken by two people at once
    invite = session.scalars(select(InviteCode).where(InviteCode.code == body.code).with_for_update()).first()
    if invite is None or (invite.expires_at is not None and invite.expires_at <= datetime.now(UTC)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That code doesn't work")
    used = session.scalar(select(func.count()).where(CreditEntry.invite_code == invite.code)) or 0
    if used >= invite.max_uses:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That code has been used up")
    session.add(CreditEntry(user_id=user.id, amount=invite.credits, kind=CreditKind.INVITE, invite_code=invite.code))
    try:
        session.flush()
    except IntegrityError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, "You've already used that code") from error
    session.commit()
    return CreditsOut(balance=balance(session, user.id), prices=PRICES)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.credits", description="Give credits")
    commands = parser.add_subparsers(dest="command", required=True)
    grant = commands.add_parser("grant", help="give an account credits (negative to take them back)")
    grant.add_argument("email")
    grant.add_argument("amount", type=int)
    grant.add_argument("--note", help="why, for the record")
    invite = commands.add_parser("invite", help="make an invite code")
    invite.add_argument("code")
    invite.add_argument("--credits", type=int, required=True, help="what each person gets")
    invite.add_argument("--uses", type=int, required=True, help="how many people can redeem it")
    invite.add_argument("--days", type=int, help="how long it works (default: until used up)")
    commands.add_parser("balance", help="show an account's balance").add_argument("email")
    args = parser.parse_args(argv)

    with Session(make_engine(Settings().database_url)) as session:
        if args.command == "invite":
            expires = None if args.days is None else datetime.now(UTC) + timedelta(days=args.days)
            session.add(
                InviteCode(code=args.code.upper(), credits=args.credits, max_uses=args.uses, expires_at=expires)
            )
            try:
                session.commit()
            except IntegrityError:
                sys.exit(f"{args.code.upper()} already exists, or its numbers aren't positive")
            print(f"{args.code.upper()} gives {args.credits} credits to up to {args.uses} people")
            return
        try:
            email = TypeAdapter(Email).validate_python(args.email)
        except ValidationError:
            sys.exit(f"{args.email} doesn't look like an email address")
        user = session.scalars(select(User).where(User.email == email)).first()
        if user is None:
            sys.exit(f"There's no account for {email}")
        if args.command == "grant":
            if args.amount == 0:
                sys.exit("Give or take at least one credit")
            session.add(CreditEntry(user_id=user.id, amount=args.amount, kind=CreditKind.GRANT, note=args.note))
            session.commit()
        print(f"{email} has {balance(session, user.id)} credits")


if __name__ == "__main__":
    main()
