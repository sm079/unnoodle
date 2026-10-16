"""previews for pictures

Revision ID: 5c3e9a1d7b20
Revises: 14eb6df5a136
Create Date: 2026-10-16 21:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5c3e9a1d7b20"
down_revision: str | Sequence[str] | None = "14eb6df5a136"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Pictures get a preview in poster_key too now; a video still must have its poster
    op.drop_constraint(op.f("ck_assets_poster_for_video"), "assets", type_="check")
    op.create_check_constraint(
        op.f("ck_assets_video_has_poster"), "assets", "media_type <> 'video' OR poster_key IS NOT NULL"
    )


def downgrade() -> None:
    # Previews made since can't stay: the old rule allowed a still for videos only (their files are left on disk)
    op.execute("UPDATE assets SET poster_key = NULL WHERE media_type <> 'video'")
    op.drop_constraint(op.f("ck_assets_video_has_poster"), "assets", type_="check")
    op.create_check_constraint(
        op.f("ck_assets_poster_for_video"), "assets", "(media_type = 'video') = (poster_key IS NOT NULL)"
    )
