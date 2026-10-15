import logging
from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db import SessionDep

logger = logging.getLogger(__name__)

router = APIRouter()


class Health(BaseModel):
    status: Literal["ok", "error"]
    db: Literal["ok", "down"]


@router.get("/health", responses={503: {"model": Health}})
def health(session: SessionDep, response: Response) -> Health:
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.warning("Database check failed", exc_info=True)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return Health(status="error", db="down")
    return Health(status="ok", db="ok")
