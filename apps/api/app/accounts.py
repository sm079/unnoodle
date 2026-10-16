"""Accounts: signing up, in and out with an email and a password.

A signed-in browser holds a random token in an httpOnly cookie; the sessions table keeps its SHA-256, so the cookie is
the only copy of the token. Cookies are SameSite=Lax, so another site can't make a signed-in request that changes
anything (the browser leaves the cookie off cross-site POSTs), and the web app reaches the API on the same origin.
"""

import hashlib
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from pydantic import AfterValidator, BaseModel, StringConstraints
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import SessionDep
from app.models import User, UserSession
from app.settings import Settings

COOKIE = "unnoodle_session"
SESSION_LENGTH = timedelta(days=30)
MIN_PASSWORD = 8

hasher = PasswordHasher()
# Checked against when the email has no account, so a wrong email takes as long to refuse as a wrong password and
# the timing doesn't tell which addresses have accounts
UNUSED_HASH = hasher.hash(secrets.token_hex())

# Enough to catch typos; whether the address works is something only an email can prove
EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def normal_email(value: str) -> str:
    if not EMAIL.fullmatch(value):
        raise ValueError("That doesn't look like an email address")
    return value.lower()


Email = Annotated[str, StringConstraints(strip_whitespace=True, max_length=254), AfterValidator(normal_email)]


class SignUpIn(BaseModel):
    email: Email
    # Argon2 takes any length; the cap keeps someone from making the server hash megabytes
    password: Annotated[str, StringConstraints(min_length=MIN_PASSWORD, max_length=256)]


class SignInIn(BaseModel):
    email: Email
    password: Annotated[str, StringConstraints(max_length=256)]


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    is_admin: bool

    @classmethod
    def of(cls, user: User) -> UserOut:
        return cls(id=user.id, email=user.email, is_admin=user.is_admin)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def hash_password(password: str) -> str:
    return hasher.hash(password)


def password_matches(user: User | None, password: str) -> bool:
    """Hashes the password even when there's no account or no password to check it against."""
    stored = user.password_hash if user is not None else None
    try:
        hasher.verify(stored or UNUSED_HASH, password)
    except VerifyMismatchError, InvalidHashError:
        return False
    return stored is not None


def start_session(session: Session, user: User, response: Response, settings: Settings) -> None:
    token = secrets.token_urlsafe(32)
    session.add(UserSession(token_hash=hash_token(token), user=user, expires_at=datetime.now(UTC) + SESSION_LENGTH))
    response.set_cookie(
        COOKIE,
        token,
        max_age=int(SESSION_LENGTH.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=settings.secure_cookies,
    )


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


SettingsDep = Annotated[Settings, Depends(get_settings)]


def current_user(session: SessionDep, token: Annotated[str | None, Cookie(alias=COOKIE)] = None) -> User:
    if token is not None:
        signed_in = session.get(UserSession, hash_token(token))
        if signed_in is not None and signed_in.expires_at > datetime.now(UTC):
            return signed_in.user
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue")


CurrentUser = Annotated[User, Depends(current_user)]


def admin_user(user: CurrentUser) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an admin can change this")
    return user


AdminUser = Annotated[User, Depends(admin_user)]


router = APIRouter(prefix="/auth")


@router.post("/sign-up", status_code=status.HTTP_201_CREATED, responses={409: {"description": "Email taken"}})
def sign_up(body: SignUpIn, response: Response, session: SessionDep, settings: SettingsDep) -> UserOut:
    user = User(email=body.email, password_hash=hash_password(body.password))
    session.add(user)
    try:
        session.flush()
    except IntegrityError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, "There's already an account with that email") from error
    start_session(session, user, response, settings)
    session.commit()
    return UserOut.of(user)


@router.post("/sign-in", responses={401: {"description": "Wrong email or password"}})
def sign_in(body: SignInIn, response: Response, session: SessionDep, settings: SettingsDep) -> UserOut:
    user = session.scalars(select(User).where(User.email == body.email)).first()
    if not password_matches(user, body.password) or user is None:
        # One message for both, so it doesn't say which addresses have accounts
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    if user.password_hash is not None and hasher.check_needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    start_session(session, user, response, settings)
    # Sessions that have run out are cleared now and then, here being as good a time as any
    session.execute(delete(UserSession).where(UserSession.expires_at <= datetime.now(UTC)))
    session.commit()
    return UserOut.of(user)


@router.post("/sign-out", status_code=status.HTTP_204_NO_CONTENT)
def sign_out(
    response: Response, session: SessionDep, token: Annotated[str | None, Cookie(alias=COOKIE)] = None
) -> None:
    if token is not None:
        session.execute(delete(UserSession).where(UserSession.token_hash == hash_token(token)))
        session.commit()
    response.delete_cookie(COOKIE)


@router.get("/me", responses={401: {"description": "Not signed in"}})
def me(user: CurrentUser) -> UserOut:
    return UserOut.of(user)
