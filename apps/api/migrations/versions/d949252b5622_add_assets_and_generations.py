"""add assets and generations

Revision ID: d949252b5622
Revises:
Create Date: 2026-10-15 17:04:26.522319

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d949252b5622"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The models store these enums as VARCHAR checked against their values (app.models.string_enum)
CAPABILITIES = (
    "'image.generate', 'image.edit', 'image.restyle', 'image.multi_ref', 'video.generate', 'video.from_frame', "
    "'video.first_last', 'video.keyframes', 'video.reference', 'video.character_swap'"
)
ROLES = "'start_frame', 'end_frame', 'keyframe', 'reference', 'edit_target', 'restyle', 'source_video'"


def upgrade() -> None:
    op.create_table(
        "generations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("capability", sa.String(length=32), nullable=False),
        sa.Column("workflow_id", sa.String(length=64), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("aspect_ratio", sa.String(length=8), nullable=False),
        sa.Column("resolution", sa.String(length=16), nullable=False),
        sa.Column("duration_s", sa.Double(), nullable=True),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("seed", sa.BigInteger(), nullable=False),
        sa.Column("audio", sa.Boolean(), nullable=False),
        sa.Column("progress", sa.Double(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("comfy_prompt_id", sa.String(length=64), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('queued', 'running', 'failed', 'done')", name=op.f("ck_generations_status")),
        sa.CheckConstraint(f"capability IN ({CAPABILITIES})", name=op.f("ck_generations_capability")),
        sa.CheckConstraint("count >= 1", name=op.f("ck_generations_count_positive")),
        sa.CheckConstraint("progress BETWEEN 0 AND 1", name=op.f("ck_generations_progress_fraction")),
        sa.CheckConstraint("(status = 'failed') = (error IS NOT NULL)", name=op.f("ck_generations_error_when_failed")),
        sa.CheckConstraint(
            "(status IN ('done', 'failed')) = (finished_at IS NOT NULL)",
            name=op.f("ck_generations_finished_when_ended"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_generations")),
    )
    op.create_index(
        "ix_generations_queued",
        "generations",
        ["created_at"],
        unique=False,
        postgresql_where=sa.text("status = 'queued'"),
    )

    op.create_table(
        "assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("media_type", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("duration_s", sa.Double(), nullable=True),
        sa.Column("generation_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("media_type IN ('image', 'video')", name=op.f("ck_assets_media_type")),
        sa.CheckConstraint("source IN ('upload', 'generation')", name=op.f("ck_assets_source")),
        sa.CheckConstraint(
            "(source = 'generation') = (generation_id IS NOT NULL)", name=op.f("ck_assets_output_has_generation")
        ),
        sa.CheckConstraint(
            "(media_type = 'video') = (duration_s IS NOT NULL)", name=op.f("ck_assets_duration_for_video")
        ),
        sa.ForeignKeyConstraint(
            ["generation_id"], ["generations.id"], name=op.f("fk_assets_generation_id_generations"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assets")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_assets_storage_key")),
    )
    op.create_index(op.f("ix_assets_generation_id"), "assets", ["generation_id"], unique=False)

    op.create_table(
        "generation_inputs",
        sa.Column("generation_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("position_s", sa.Double(), nullable=True),
        sa.CheckConstraint(f"role IN ({ROLES})", name=op.f("ck_generation_inputs_role")),
        sa.CheckConstraint(
            "(role = 'keyframe') = (position_s IS NOT NULL)", name=op.f("ck_generation_inputs_position_for_keyframes")
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"], ["assets.id"], name=op.f("fk_generation_inputs_asset_id_assets"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["generation_id"],
            ["generations.id"],
            name=op.f("fk_generation_inputs_generation_id_generations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("generation_id", "position", name=op.f("pk_generation_inputs")),
    )
    op.create_index(op.f("ix_generation_inputs_asset_id"), "generation_inputs", ["asset_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_generation_inputs_asset_id"), table_name="generation_inputs")
    op.drop_table("generation_inputs")
    op.drop_index(op.f("ix_assets_generation_id"), table_name="assets")
    op.drop_table("assets")
    op.drop_index("ix_generations_queued", table_name="generations", postgresql_where=sa.text("status = 'queued'"))
    op.drop_table("generations")
