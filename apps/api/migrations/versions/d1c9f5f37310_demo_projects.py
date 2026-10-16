"""demo projects

Revision ID: d1c9f5f37310
Revises: 925a268e110c
Create Date: 2026-10-16 13:01:36.604154

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1c9f5f37310"
down_revision: str | Sequence[str] | None = "925a268e110c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Demo projects are shown to everyone; app.demo files generations into one
    op.add_column("projects", sa.Column("is_demo", sa.Boolean(), server_default="false", nullable=False))


def downgrade() -> None:
    op.drop_column("projects", "is_demo")
