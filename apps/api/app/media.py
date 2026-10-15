"""Stored media: uploads and generation outputs, kept on local disk and served under /media.

Files are stored under keys like "uploads/<asset id>.png". The key goes in the database, so moving the files later
(to object storage, for instance) changes how keys turn into URLs, not the rows.
"""

import os
import tempfile
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel
from sqlalchemy import select

from app.db import SessionDep
from app.models import Asset, AssetSource, MediaType, new_id

MEDIA_URL = "/media"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

# Pillow format -> (MIME type, file extension)
IMAGE_FORMATS = {"PNG": ("image/png", "png"), "JPEG": ("image/jpeg", "jpg"), "WEBP": ("image/webp", "webp")}

# EXIF orientations that turn the picture a quarter turn, so its width and height swap when shown
QUARTER_TURNS = {5, 6, 7, 8}
EXIF_ORIENTATION = 0x0112


class MediaStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def path(self, key: str) -> Path:
        return self.root / key

    def write(self, key: str, data: bytes) -> None:
        # Written to a temporary file first, so a reader never sees half a file
        target = self.path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as temporary:
            temporary.write(data)
        os.replace(temporary.name, target)


def get_media_store(request: Request) -> MediaStore:
    store: MediaStore = request.app.state.media
    return store


MediaStoreDep = Annotated[MediaStore, Depends(get_media_store)]


class AssetOut(BaseModel):
    id: uuid.UUID
    media_type: MediaType
    source: AssetSource
    url: str
    # A still for grids. The same as url for images.
    thumbnail_url: str
    width: int
    height: int
    # Videos only
    duration_s: float | None
    created_at: datetime

    @classmethod
    def of(cls, asset: Asset) -> AssetOut:
        url = f"{MEDIA_URL}/{asset.storage_key}"
        return cls(
            id=asset.id,
            media_type=asset.media_type,
            source=asset.source,
            url=url,
            thumbnail_url=url,
            width=asset.width,
            height=asset.height,
            duration_s=asset.duration_s,
            created_at=asset.created_at,
        )


router = APIRouter()


@router.post("/assets", status_code=status.HTTP_201_CREATED)
def upload_asset(file: UploadFile, session: SessionDep, store: MediaStoreDep) -> AssetOut:
    """Stores an uploaded image, to attach to generations. Videos come once a workflow takes them."""
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, f"Uploads are limited to {MAX_UPLOAD_BYTES >> 20} MB")
    unsupported = HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Upload a PNG, JPEG or WebP image")
    # The bytes decide what the file is, not its name or the type the client claims
    try:
        # Opening reads only the header; verify catches truncated and corrupt files before ComfyUI meets them. It
        # has to come straight after opening, and leaves the image unusable, hence the second open.
        with Image.open(BytesIO(data)) as image:
            image.verify()
        with Image.open(BytesIO(data)) as image:
            image_format, (width, height) = image.format, image.size
            if image.getexif().get(EXIF_ORIENTATION) in QUARTER_TURNS:
                width, height = height, width
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError) as error:
        raise unsupported from error
    if image_format not in IMAGE_FORMATS:
        raise unsupported
    mime_type, extension = IMAGE_FORMATS[image_format]

    asset_id = new_id()
    key = f"uploads/{asset_id}.{extension}"
    store.write(key, data)
    asset = Asset(
        id=asset_id,
        media_type=MediaType.IMAGE,
        source=AssetSource.UPLOAD,
        storage_key=key,
        mime_type=mime_type,
        size_bytes=len(data),
        width=width,
        height=height,
    )
    session.add(asset)
    session.commit()
    return AssetOut.of(asset)


@router.get("/assets")
def list_uploads(session: SessionDep, limit: int = 60) -> list[AssetOut]:
    """Uploads, newest first: the library the composer attaches from."""
    query = select(Asset).where(Asset.source == AssetSource.UPLOAD).order_by(Asset.id.desc()).limit(min(limit, 200))
    return [AssetOut.of(asset) for asset in session.scalars(query)]
