import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Enum, ForeignKey, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class MediaType(StrEnum):
    IMAGE = "image"
    VIDEO = "video"


class AssetSource(StrEnum):
    UPLOAD = "upload"
    GENERATION = "generation"


class GenerationStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    FAILED = "failed"
    DONE = "done"


class Capability(StrEnum):
    IMAGE_GENERATE = "image.generate"
    IMAGE_EDIT = "image.edit"
    VIDEO_GENERATE = "video.generate"
    VIDEO_REFERENCE = "video.reference"

    @property
    def media_type(self) -> MediaType:
        return MediaType(self.value.split(".", 1)[0])


class InputRole(StrEnum):
    """What an attached asset is for. The output type plus the roles of the inputs decide the capability."""

    # The photo an edit changes
    EDIT_TARGET = "edit_target"
    # A photo or clip to take a person, an outfit, a style or a motion from
    REFERENCE = "reference"


class Quality(StrEnum):
    """How big an output is: each workflow maps these to its own sizes and the person never sees pixels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


def string_enum[E: StrEnum](enum: type[E], name: str) -> Enum:
    # VARCHAR plus a CHECK constraint rather than a native Postgres enum: adding a value later is then a constraint
    # swap in a migration instead of ALTER TYPE. values_callable stores the values ("image.edit"), not the names.
    return Enum(
        enum,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda members: [member.value for member in members],
    )


def new_id() -> uuid.UUID:
    # Time-ordered, so sorting by id is sorting by creation and new rows land at the end of the index
    return uuid.uuid7()


class Asset(Base):
    """A stored image or video: an upload, or an output of a generation."""

    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    media_type: Mapped[MediaType] = mapped_column(string_enum(MediaType, "media_type"))
    source: Mapped[AssetSource] = mapped_column(string_enum(AssetSource, "source"))
    # Path under the media directory, with forward slashes
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    mime_type: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    width: Mapped[int]
    height: Mapped[int]
    duration_s: Mapped[float | None]
    # Videos only: a still of the first frame, under the media directory like storage_key
    poster_key: Mapped[str | None] = mapped_column(String(255))
    # Set for outputs: the generation that made this asset
    generation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("generations.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("(source = 'generation') = (generation_id IS NOT NULL)", name="output_has_generation"),
        CheckConstraint("(media_type = 'video') = (duration_s IS NOT NULL)", name="duration_for_video"),
        CheckConstraint("(media_type = 'video') = (poster_key IS NOT NULL)", name="poster_for_video"),
    )


class Project(Base):
    """A folder for generations. My generations isn't one: it is every generation, in a project or not."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (CheckConstraint("btrim(name) <> ''", name="name_not_blank"),)


class Generation(Base):
    """One request to run a workflow. The table is also the job queue: workers claim queued rows."""

    __tablename__ = "generations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    status: Mapped[GenerationStatus] = mapped_column(
        string_enum(GenerationStatus, "status"), default=GenerationStatus.QUEUED
    )
    capability: Mapped[Capability] = mapped_column(string_enum(Capability, "capability"))
    # The workflow the request resolved to
    workflow_id: Mapped[str] = mapped_column(String(64))
    prompt: Mapped[str] = mapped_column(Text)
    # The project it was made in, if any. Deleting a project leaves its generations in My generations.
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"))

    quality: Mapped[Quality] = mapped_column(string_enum(Quality, "quality"))
    # Width to height, e.g. "3:4". None when the output takes its shape from an input, as an edit does.
    aspect_ratio: Mapped[str | None] = mapped_column(String(8))
    duration_s: Mapped[float | None]
    count: Mapped[int]
    # Chosen when the request is accepted, so running the job again gives the same result
    seed: Mapped[int] = mapped_column(BigInteger)

    # 0 to 1 while running
    progress: Mapped[float | None]
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(default=0)
    # ComfyUI's id for the current run, for following it and cancelling it
    comfy_prompt_id: Mapped[str | None] = mapped_column(String(64))
    # Refreshed by the worker while it runs the job; a stale one means the worker died
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    inputs: Mapped[list[GenerationInput]] = relationship(
        order_by="GenerationInput.position", cascade="all, delete-orphan", lazy="selectin"
    )
    outputs: Mapped[list[Asset]] = relationship(order_by=Asset.id, lazy="selectin")

    __table_args__ = (
        CheckConstraint("count >= 1", name="count_positive"),
        CheckConstraint("progress BETWEEN 0 AND 1", name="progress_fraction"),
        CheckConstraint("(status = 'failed') = (error IS NOT NULL)", name="error_when_failed"),
        CheckConstraint("(status IN ('done', 'failed')) = (finished_at IS NOT NULL)", name="finished_when_ended"),
        # The worker's claim query scans only what is waiting
        Index("ix_generations_queued", "created_at", postgresql_where=text("status = 'queued'")),
        # A project's generations, newest first
        Index("ix_generations_project_id", "project_id", "id"),
    )


class GenerationInput(Base):
    """An asset attached to a generation, in the role it plays there."""

    __tablename__ = "generation_inputs"

    generation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("generations.id", ondelete="CASCADE"), primary_key=True)
    # Order within the request, which is how the prompt numbers them: photo 1, photo 2, clip 1
    position: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[InputRole] = mapped_column(string_enum(InputRole, "role"))
    # An asset that is in use can't be deleted
    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assets.id", ondelete="RESTRICT"), index=True)

    asset: Mapped[Asset] = relationship(lazy="selectin")
