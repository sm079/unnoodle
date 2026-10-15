"""add posters for videos

Revision ID: 738b396addd0
Revises: f00d4fafeda5
Create Date: 2026-10-16 01:26:49.702004

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "738b396addd0"
down_revision: str | Sequence[str] | None = "f00d4fafeda5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Every video has a still of its first frame for grids. No videos were stored before this, so none lacks one.
    op.add_column("assets", sa.Column("poster_key", sa.String(length=255), nullable=True))
    op.create_check_constraint(
        op.f("ck_assets_poster_for_video"), "assets", "(media_type = 'video') = (poster_key IS NOT NULL)"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_assets_poster_for_video"), "assets", type_="check")
    op.drop_column("assets", "poster_key")
