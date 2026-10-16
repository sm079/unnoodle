"""narrow to the real pipelines

Revision ID: f00d4fafeda5
Revises: ffca2f469778
Create Date: 2026-10-16 00:48:21.400001

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f00d4fafeda5"
down_revision: str | Sequence[str] | None = "ffca2f469778"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# The models store these enums as VARCHAR checked against their values (app.models.string_enum)
CAPABILITIES = "'image.generate', 'image.edit', 'video.generate', 'video.reference'"
ROLES = "'edit_target', 'reference'"
QUALITIES = "'low', 'medium', 'high'"

OLD_CAPABILITIES = (
    "'image.generate', 'image.edit', 'image.restyle', 'image.multi_ref', 'video.generate', 'video.from_frame', "
    "'video.first_last', 'video.keyframes', 'video.reference', 'video.character_swap'"
)
OLD_ROLES = "'start_frame', 'end_frame', 'keyframe', 'reference', 'edit_target', 'restyle', 'source_video'"


def upgrade() -> None:
    # Only the capabilities and roles the real pipelines serve remain. Rows using the others would fail the new
    # checks, which is the point: nothing ever ran them.
    op.drop_constraint(op.f("ck_generations_capability"), "generations", type_="check")
    op.create_check_constraint(op.f("ck_generations_capability"), "generations", f"capability IN ({CAPABILITIES})")
    op.drop_constraint(op.f("ck_generation_inputs_position_for_keyframes"), "generation_inputs", type_="check")
    op.drop_column("generation_inputs", "position_s")
    op.drop_constraint(op.f("ck_generation_inputs_role"), "generation_inputs", type_="check")
    op.create_check_constraint(op.f("ck_generation_inputs_role"), "generation_inputs", f"role IN ({ROLES})")

    # Sizes are a quality now, which each pipeline maps to its own sizes; "1K" and "2K" were the only labels used
    op.add_column("generations", sa.Column("quality", sa.String(length=32), nullable=True))
    op.execute("UPDATE generations SET quality = CASE resolution WHEN '2K' THEN 'high' ELSE 'medium' END")
    op.alter_column("generations", "quality", nullable=False)
    op.create_check_constraint(op.f("ck_generations_quality"), "generations", f"quality IN ({QUALITIES})")
    op.drop_column("generations", "resolution")
    # An edit takes its shape from the photo
    op.alter_column("generations", "aspect_ratio", existing_type=sa.String(length=8), nullable=True)
    # Whether a video has sound is up to its pipeline
    op.drop_column("generations", "audio")


def downgrade() -> None:
    op.add_column("generations", sa.Column("audio", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.alter_column("generations", "audio", server_default=None)
    op.execute("UPDATE generations SET aspect_ratio = '1:1' WHERE aspect_ratio IS NULL")
    op.alter_column("generations", "aspect_ratio", existing_type=sa.String(length=8), nullable=False)
    op.add_column("generations", sa.Column("resolution", sa.String(length=16), nullable=True))
    op.execute("UPDATE generations SET resolution = CASE quality WHEN 'high' THEN '2K' ELSE '1K' END")
    op.alter_column("generations", "resolution", nullable=False)
    op.drop_constraint(op.f("ck_generations_quality"), "generations", type_="check")
    op.drop_column("generations", "quality")

    op.drop_constraint(op.f("ck_generation_inputs_role"), "generation_inputs", type_="check")
    op.create_check_constraint(op.f("ck_generation_inputs_role"), "generation_inputs", f"role IN ({OLD_ROLES})")
    op.add_column("generation_inputs", sa.Column("position_s", sa.Double(), nullable=True))
    op.create_check_constraint(
        op.f("ck_generation_inputs_position_for_keyframes"),
        "generation_inputs",
        "(role = 'keyframe') = (position_s IS NOT NULL)",
    )
    op.drop_constraint(op.f("ck_generations_capability"), "generations", type_="check")
    op.create_check_constraint(op.f("ck_generations_capability"), "generations", f"capability IN ({OLD_CAPABILITIES})")
