"""The admin page's API: everyone's generations, to see and delete; people and their credits; invite codes; and the
banned words. Every endpoint here needs an admin."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.accounts import admin_user
from app.credits import balance
from app.db import SessionDep
from app.generations import GenerationOut
from app.media import MediaStoreDep
from app.models import (
    AssetSource,
    BannedWord,
    CreditEntry,
    CreditKind,
    Generation,
    GenerationInput,
    InviteCode,
    User,
)

router = APIRouter(prefix="/admin", dependencies=[Depends(admin_user)])


class AdminGenerationOut(GenerationOut):
    owner_email: str


class AdminUserOut(BaseModel):
    id: uuid.UUID
    email: str
    is_admin: bool
    balance: int
    generation_count: int
    created_at: datetime


class GrantIn(BaseModel):
    # Negative takes credits back
    amount: int = Field(ge=-100_000, le=100_000)
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None


class InviteIn(BaseModel):
    code: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, to_upper=True, min_length=3, max_length=32, pattern=r"^[A-Za-z0-9-]+$"
        ),
    ]
    credits: int = Field(ge=1, le=100_000)
    max_uses: int = Field(ge=1, le=10_000)
    # Left out, it works until it is used up
    days: int | None = Field(default=None, ge=1, le=365)


class InviteOut(BaseModel):
    code: str
    credits: int
    max_uses: int
    uses: int
    expires_at: datetime | None
    created_at: datetime


class WordIn(BaseModel):
    word: Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=1, max_length=64)]


@router.get("/generations")
def list_generations(session: SessionDep, before: uuid.UUID | None = None, limit: int = 30) -> list[AdminGenerationOut]:
    """Everyone's, newest first. For the next page, pass the id of the last one received as before."""
    query = (
        select(Generation, User.email)
        .join(User, Generation.owner_id == User.id)
        .order_by(Generation.id.desc())
        .limit(min(limit, 100))
    )
    if before is not None:
        query = query.where(Generation.id < before)
    return [
        AdminGenerationOut(**GenerationOut.of(g).model_dump(), owner_email=email) for g, email in session.execute(query)
    ]


@router.delete(
    "/generations/{generation_id}", status_code=status.HTTP_204_NO_CONTENT, responses={404: {"description": "No such"}}
)
def delete_generation(generation_id: uuid.UUID, session: SessionDep, store: MediaStoreDep) -> None:
    """Deletes a generation with its outputs and their files, and the photos and clips uploaded for it that nothing
    else uses. Credits it took stay taken."""
    generation = session.get(Generation, generation_id)
    if generation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such generation")
    uploads = [i.asset for i in generation.inputs if i.asset.source is AssetSource.UPLOAD]
    gone = list(generation.outputs)
    for output in gone:
        session.delete(output)
    session.delete(generation)
    session.flush()
    for upload in uploads:
        if session.scalar(select(func.count()).where(GenerationInput.asset_id == upload.id)) == 0:
            session.delete(upload)
            gone.append(upload)
    session.commit()
    # Files go once the rows are gone, so a failure part way leaves files without rows, never the reverse
    for asset in gone:
        store.delete(asset.storage_key)
        if asset.poster_key is not None:
            store.delete(asset.poster_key)


@router.get("/users")
def list_users(session: SessionDep) -> list[AdminUserOut]:
    """Everyone, newest first, with their balance."""
    balances = (
        select(CreditEntry.user_id, func.sum(CreditEntry.amount).label("balance"))
        .group_by(CreditEntry.user_id)
        .subquery()
    )
    counts = select(Generation.owner_id, func.count().label("generations")).group_by(Generation.owner_id).subquery()
    query = (
        select(User, func.coalesce(balances.c.balance, 0), func.coalesce(counts.c.generations, 0))
        .outerjoin(balances, balances.c.user_id == User.id)
        .outerjoin(counts, counts.c.owner_id == User.id)
        .order_by(User.id.desc())
    )
    return [
        AdminUserOut(
            id=user.id,
            email=user.email,
            is_admin=user.is_admin,
            balance=int(credits),
            generation_count=int(generations),
            created_at=user.created_at,
        )
        for user, credits, generations in session.execute(query)
    ]


@router.post("/users/{user_id}/credits", responses={404: {"description": "No such account"}})
def grant(user_id: uuid.UUID, body: GrantIn, session: SessionDep) -> AdminUserOut:
    """Gives someone credits, or takes them back with a negative amount."""
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such account")
    if body.amount == 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Give or take at least one credit")
    session.add(CreditEntry(user_id=user.id, amount=body.amount, kind=CreditKind.GRANT, note=body.note))
    session.commit()
    count = session.scalar(select(func.count()).where(Generation.owner_id == user.id)) or 0
    return AdminUserOut(
        id=user.id,
        email=user.email,
        is_admin=user.is_admin,
        balance=balance(session, user.id),
        generation_count=count,
        created_at=user.created_at,
    )


@router.get("/invite-codes")
def list_invite_codes(session: SessionDep) -> list[InviteOut]:
    """Newest first, with how many people have used each."""
    uses = (
        select(CreditEntry.invite_code, func.count().label("uses"))
        .where(CreditEntry.invite_code.is_not(None))
        .group_by(CreditEntry.invite_code)
        .subquery()
    )
    query = (
        select(InviteCode, func.coalesce(uses.c.uses, 0))
        .outerjoin(uses, uses.c.invite_code == InviteCode.code)
        .order_by(InviteCode.created_at.desc())
    )
    return [invite_out(invite, int(used)) for invite, used in session.execute(query)]


@router.post("/invite-codes", status_code=status.HTTP_201_CREATED, responses={409: {"description": "Code taken"}})
def create_invite_code(body: InviteIn, session: SessionDep) -> InviteOut:
    expires = None if body.days is None else datetime.now(UTC) + timedelta(days=body.days)
    invite = InviteCode(code=body.code, credits=body.credits, max_uses=body.max_uses, expires_at=expires)
    session.add(invite)
    try:
        session.commit()
    except IntegrityError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, "That code already exists") from error
    return invite_out(invite, 0)


def invite_out(invite: InviteCode, uses: int) -> InviteOut:
    return InviteOut(
        code=invite.code,
        credits=invite.credits,
        max_uses=invite.max_uses,
        uses=uses,
        expires_at=invite.expires_at,
        created_at=invite.created_at,
    )


@router.get("/banned-words")
def list_banned_words(session: SessionDep) -> list[str]:
    """In the order they were added."""
    return list(session.scalars(select(BannedWord.word).order_by(BannedWord.created_at, BannedWord.word)))


@router.post("/banned-words")
def add_banned_word(body: WordIn, session: SessionDep) -> list[str]:
    """Adds a word or phrase, and returns the list. Adding one already there changes nothing."""
    if session.get(BannedWord, body.word) is None:
        session.add(BannedWord(word=body.word))
        session.commit()
    return list_banned_words(session)


@router.delete("/banned-words/{word}")
def remove_banned_word(word: str, session: SessionDep) -> list[str]:
    session.execute(delete(BannedWord).where(BannedWord.word == word.strip().lower()))
    session.commit()
    return list_banned_words(session)
