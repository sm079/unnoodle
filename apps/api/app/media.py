"""Stored media: uploads and generation outputs, kept on local disk and served under /media to their owners only.

Files are stored under keys like "uploads/<asset id>.png". The key goes in the database, so moving the files later
(to object storage, for instance) changes how keys turn into URLs, not the rows.
"""

import os
import tempfile
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel
from sqlalchemy import or_, select

from app import video
from app.accounts import CurrentUser
from app.db import SessionDep
from app.models import Asset, AssetSource, MediaType, new_id
from app.sharing import visible_asset

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

    @contextmanager
    def writing(self, key: str) -> Iterator[Path]:
        """A temporary path for a tool such as ffmpeg to write to, which becomes the file at key once the block
        finishes. It has the key's extension, which ffmpeg goes by."""
        target = self.path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        handle, name = tempfile.mkstemp(dir=target.parent, suffix=target.suffix)
        os.close(handle)
        try:
            yield Path(name)
            os.replace(name, target)
        finally:
            Path(name).unlink(missing_ok=True)


@dataclass(frozen=True)
class Stored:
    """A file put in the store, with what its Asset row records about it."""

    media_type: MediaType
    storage_key: str
    mime_type: str
    size_bytes: int
    width: int
    height: int
    # Videos only
    duration_s: float | None = None
    poster_key: str | None = None

    def fields(self) -> dict[str, Any]:
        return self.__dict__.copy()


def store_image(store: MediaStore, data: bytes, key_stem: str) -> Stored | None:
    """Stores a PNG, JPEG or WebP image as it is, or returns None if the data isn't one."""
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
    except UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError:
        return None
    if image_format not in IMAGE_FORMATS:
        return None
    mime_type, extension = IMAGE_FORMATS[image_format]
    key = f"{key_stem}.{extension}"
    store.write(key, data)
    return Stored(MediaType.IMAGE, key, mime_type, len(data), width, height)


class ClipTooShort(Exception):
    pass


def store_video(store: MediaStore, data: bytes, key_stem: str, *, clip: bool) -> Stored:
    """Stores a video as MP4 with a poster beside it. A clip to use as a reference is cut to what the video model
    uses of it (see app.video); an output is kept as it is. Raises VideoError if ffmpeg can't read the data."""
    key, poster_key = f"{key_stem}.mp4", f"{key_stem}.jpg"
    with tempfile.TemporaryDirectory() as folder:
        original = Path(folder) / "original"
        original.write_bytes(data)
        if clip:
            found = video.probe(original)
            if found.container not in video.CLIP_CONTAINERS:
                raise video.VideoError(f"{found.container} isn't a clip")
            if found.duration_s < video.SHORTEST_CLIP_S:
                raise ClipTooShort
            with store.writing(key) as cut:
                video.cut_clip(original, cut)
        else:
            video.probe(original)
            store.write(key, data)
    stored = store.path(key)
    with store.writing(poster_key) as still:
        video.poster(stored, still)
    info = video.probe(stored)
    return Stored(
        MediaType.VIDEO,
        key,
        "video/mp4",
        stored.stat().st_size,
        info.width,
        info.height,
        round(info.duration_s, 3),
        poster_key,
    )


def get_media_store(request: Request) -> MediaStore:
    store: MediaStore = request.app.state.media
    return store


MediaStoreDep = Annotated[MediaStore, Depends(get_media_store)]


class AssetOut(BaseModel):
    id: uuid.UUID
    media_type: MediaType
    source: AssetSource
    url: str
    # A still for grids: a video's first frame, or the image itself
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
            thumbnail_url=url if asset.poster_key is None else f"{MEDIA_URL}/{asset.poster_key}",
            width=asset.width,
            height=asset.height,
            duration_s=asset.duration_s,
            created_at=asset.created_at,
        )


router = APIRouter()


@router.post("/assets", status_code=status.HTTP_201_CREATED, responses={422: {"description": "A clip too short"}})
def upload_asset(file: UploadFile, user: CurrentUser, session: SessionDep, store: MediaStoreDep) -> AssetOut:
    """Stores an uploaded photo or video clip, to attach to generations. Clips are cut to their first 15 seconds."""
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, f"Uploads are limited to {MAX_UPLOAD_BYTES >> 20} MB")
    asset_id = new_id()
    key_stem = f"uploads/{asset_id}"
    try:
        stored = store_image(store, data, key_stem) or store_video(store, data, key_stem, clip=True)
    except video.VideoError as error:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Upload a photo (PNG, JPEG or WebP) or a video clip"
        ) from error
    except ClipTooShort as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Clips need to be at least {video.SHORTEST_CLIP_S:g} seconds long",
        ) from error
    asset = Asset(id=asset_id, owner_id=user.id, source=AssetSource.UPLOAD, **stored.fields())
    session.add(asset)
    session.commit()
    return AssetOut.of(asset)


@router.get("/assets")
def list_uploads(user: CurrentUser, session: SessionDep, limit: int = 60) -> list[AssetOut]:
    """Your uploads, newest first: the library the composer attaches from."""
    query = (
        select(Asset)
        .where(Asset.owner_id == user.id, Asset.source == AssetSource.UPLOAD)
        .order_by(Asset.id.desc())
        .limit(min(limit, 200))
    )
    return [AssetOut.of(asset) for asset in session.scalars(query)]


@router.get(MEDIA_URL + "/{key:path}", response_class=FileResponse, responses={404: {"description": "No such file"}})
def get_media(key: str, user: CurrentUser, session: SessionDep, store: MediaStoreDep) -> FileResponse:
    """A stored file or a video's poster, for its owner, or anyone for a demo's. Anyone else gets the same 404 as for
    a file that doesn't exist, so whether it exists isn't given away either."""
    asset = session.scalars(
        select(Asset).where(visible_asset(user), or_(Asset.storage_key == key, Asset.poster_key == key))
    ).first()
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such file")
    media_type = asset.mime_type if key == asset.storage_key else "image/jpeg"
    # A key is never reused for other content, so the browser can keep it, but only for this person (private)
    return FileResponse(
        store.path(key), media_type=media_type, headers={"Cache-Control": "private, max-age=31536000, immutable"}
    )
