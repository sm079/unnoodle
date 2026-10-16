"""Preferences: settings for the whole app, until there are accounts to hold them."""

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import SessionDep
from app.models import Preferences


class PreferencesIn(BaseModel):
    # Left out, a setting stays as it is
    smart_queue: bool | None = None


class PreferencesOut(BaseModel):
    # Quick generations go ahead of long ones in the queue, each long one by ten minutes at most
    smart_queue: bool


router = APIRouter()


@router.get("/preferences")
def get_preferences(session: SessionDep) -> PreferencesOut:
    return PreferencesOut(smart_queue=stored(session).smart_queue)


@router.patch("/preferences")
def update_preferences(body: PreferencesIn, session: SessionDep) -> PreferencesOut:
    preferences = stored(session)
    if body.smart_queue is not None:
        preferences.smart_queue = body.smart_queue
    session.commit()
    return PreferencesOut(smart_queue=preferences.smart_queue)


def stored(session: Session) -> Preferences:
    # The row is made the first time it is needed; until then everything is off
    preferences = session.get(Preferences, 1)
    if preferences is None:
        preferences = Preferences(id=1, smart_queue=False)
        session.add(preferences)
    return preferences
