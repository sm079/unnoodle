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
    """What an attached asset is for. The output type plus the roles of the inputs decide the capability.

    There is one role while every pipeline treats its inputs alike; start and end frames would be others."""

    # A photo or clip to work from: one to change, several to combine, or a person, an outfit, a style or a motion
    # to take from it
    REFERENCE = "reference"


class CreditKind(StrEnum):
    """Why a credit entry moved someone's balance."""

    # Given by an admin, or taken back with a negative amount
    GRANT = "grant"
    # From redeeming an invite code
    INVITE = "invite"
    # Taken when a generation is queued
    CHARGE = "charge"
    # Given back when a generation fails
    REFUND = "refund"


class Quality(StrEnum):
    """How big an output is: each pipeline maps these to its own sizes and the person never sees pixels."""

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


class User(Base):
    """Someone with an account. Everything they make or upload is theirs alone."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    # Stored lowercased, so an address is one account however it is typed
    email: Mapped[str] = mapped_column(String(254), unique=True)
    # Argon2. None: the account can't sign in until a password is set from the command line (app.users).
    password_hash: Mapped[str | None] = mapped_column(String(255))
    # Can change settings that affect everyone, such as Smart Queue
    is_admin: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (CheckConstraint("email = lower(email)", name="email_lowercase"),)


class UserSession(Base):
    """A signed-in browser. The cookie holds a random token and only its hash is stored, so a copy of the database
    can't be used to sign in. Deleting the row signs that browser out."""

    __tablename__ = "sessions"

    # SHA-256 of the token, in hex
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(lazy="joined")


class BannedWord(Base):
    """A word or phrase prompts may not contain (app.moderation). Admins keep the list."""

    __tablename__ = "banned_words"

    # As the admin typed it, lowercased
    word: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (CheckConstraint("word = lower(word) AND btrim(word) <> ''", name="word_lowercase"),)


class FailedSignIn(Base):
    """A wrong password, kept for a while so guessing one can be slowed down (app.accounts)."""

    __tablename__ = "failed_sign_ins"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    # As typed, lowercased: an address with no account is limited the same way, so the limit doesn't tell either
    email: Mapped[str] = mapped_column(String(254))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_failed_sign_ins_email", "email", "created_at"),)


class Asset(Base):
    """A stored image or video: an upload, or an output of a generation."""

    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    # An output belongs to whoever owns its generation. Deleting an account deletes everything it made.
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
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
    poster_key: Mapped[str | None] = mapped_column(String(255), unique=True)
    # Set for outputs: the generation that made this asset
    generation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("generations.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("(source = 'generation') = (generation_id IS NOT NULL)", name="output_has_generation"),
        CheckConstraint("(media_type = 'video') = (duration_s IS NOT NULL)", name="duration_for_video"),
        CheckConstraint("(media_type = 'video') = (poster_key IS NOT NULL)", name="poster_for_video"),
        # Someone's uploads, newest first
        Index("ix_assets_owner_id", "owner_id", "id"),
    )


class Project(Base):
    """A folder for generations. My generations isn't one: it is every generation, in a project or not."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80))
    # Shown to everyone, read-only for all but its owner (app.sharing)
    is_demo: Mapped[bool] = mapped_column(default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("btrim(name) <> ''", name="name_not_blank"),
        Index("ix_projects_owner_id", "owner_id", "id"),
    )


class Generation(Base):
    """One request to run a pipeline. The table is also the job queue: workers claim queued rows."""

    __tablename__ = "generations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[GenerationStatus] = mapped_column(
        string_enum(GenerationStatus, "status"), default=GenerationStatus.QUEUED
    )
    capability: Mapped[Capability] = mapped_column(string_enum(Capability, "capability"))
    # The pipeline the request resolved to
    pipeline_id: Mapped[str] = mapped_column(String(64))
    prompt: Mapped[str] = mapped_column(Text)
    # The project it was made in, if any. Deleting a project leaves its generations in My generations.
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"))

    quality: Mapped[Quality] = mapped_column(string_enum(Quality, "quality"))
    # Width to height, e.g. "3:4". None: the shape of the first attachment.
    aspect_ratio: Mapped[str | None] = mapped_column(String(8))
    duration_s: Mapped[float | None]
    # Chosen when the request is accepted, so running the job again gives the same result
    seed: Mapped[int] = mapped_column(BigInteger)
    # Roughly how long it runs on the GPU, from the pipeline's estimate when it was queued; Smart Queue orders by it
    estimated_s: Mapped[float]
    # Credits taken when it was queued, and given back if it fails (app.credits)
    cost: Mapped[int] = mapped_column(default=0, server_default="0")

    # 0 to 1 while running
    progress: Mapped[float | None]
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(default=0)
    # The renderer's id for the current run, for following it and cancelling it
    run_id: Mapped[str | None] = mapped_column(String(64))
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
        CheckConstraint("progress BETWEEN 0 AND 1", name="progress_fraction"),
        CheckConstraint("(status = 'failed') = (error IS NOT NULL)", name="error_when_failed"),
        CheckConstraint("(status IN ('done', 'failed')) = (finished_at IS NOT NULL)", name="finished_when_ended"),
        # The worker's claim query scans only what is waiting
        Index("ix_generations_queued", "created_at", postgresql_where=text("status = 'queued'")),
        # A project's generations, newest first
        Index("ix_generations_project_id", "project_id", "id"),
        # Someone's generations (My generations), newest first
        Index("ix_generations_owner_id", "owner_id", "id"),
    )


class Preferences(Base):
    """Settings for the whole app, in one row. Only admins change them, since they affect everyone."""

    __tablename__ = "preferences"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    # Lets quick generations go ahead of long ones in the queue (see app.worker.queue)
    smart_queue: Mapped[bool] = mapped_column(default=False)

    __table_args__ = (CheckConstraint("id = 1", name="one_row"),)


class InviteCode(Base):
    """A code that gives credits to whoever redeems it, once each, up to max_uses people."""

    __tablename__ = "invite_codes"

    # Stored uppercased; redeeming ignores case
    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    credits: Mapped[int]
    max_uses: Mapped[int]
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("code = upper(code)", name="code_uppercase"),
        CheckConstraint("credits > 0", name="credits_positive"),
        CheckConstraint("max_uses > 0", name="max_uses_positive"),
    )


class CreditEntry(Base):
    """One movement of someone's credits. Rows are only ever added, never changed, so a balance is the sum of its
    entries and every change to it can be traced."""

    __tablename__ = "credit_entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # Positive adds credits, negative takes them
    amount: Mapped[int]
    kind: Mapped[CreditKind] = mapped_column(string_enum(CreditKind, "kind"))
    # Charges and refunds: the generation they were for
    generation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("generations.id", ondelete="SET NULL"))
    # Invites: the code redeemed
    invite_code: Mapped[str | None] = mapped_column(ForeignKey("invite_codes.code", ondelete="SET NULL"))
    # Grants: why, as the admin put it
    note: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        # Charges take; invites and refunds give; a grant can do either
        CheckConstraint("kind = 'grant' OR (kind = 'charge') = (amount < 0)", name="sign_follows_kind"),
        CheckConstraint("amount <> 0", name="amount_not_zero"),
        # A balance is summed from someone's entries
        Index("ix_credit_entries_user_id", "user_id"),
        # One charge and at most one refund per generation, however often the worker retries
        Index(
            "uq_credit_entries_generation_kind",
            "generation_id",
            "kind",
            unique=True,
            postgresql_where=text("generation_id IS NOT NULL"),
        ),
        # Each person redeems a code once
        Index(
            "uq_credit_entries_user_invite",
            "user_id",
            "invite_code",
            unique=True,
            postgresql_where=text("invite_code IS NOT NULL"),
        ),
    )


class GenerationInput(Base):
    """An asset attached to a generation, in the role it plays there."""

    __tablename__ = "generation_inputs"

    generation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("generations.id", ondelete="CASCADE"), primary_key=True)
    # Order within the request, which is how the prompt names them: @photo1, @photo2, @clip1
    position: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[InputRole] = mapped_column(string_enum(InputRole, "role"))
    # An asset that is in use can't be deleted
    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assets.id", ondelete="RESTRICT"), index=True)

    asset: Mapped[Asset] = relationship(lazy="selectin")
