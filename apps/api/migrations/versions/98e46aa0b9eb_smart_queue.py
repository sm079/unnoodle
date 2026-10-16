"""smart queue

Revision ID: 98e46aa0b9eb
Revises: 20e318569d2b
Create Date: 2026-10-16 11:04:07.017119

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "98e46aa0b9eb"
down_revision: str | Sequence[str] | None = "20e318569d2b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Settings for the whole app, in one row, until there are accounts
    op.create_table(
        "preferences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("smart_queue", sa.Boolean(), nullable=False),
        sa.CheckConstraint("id = 1", name=op.f("ck_preferences_one_row")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_preferences")),
    )
    # Generations queued before there were estimates count as a minute, the estimate a pipeline gets without one
    op.add_column("generations", sa.Column("estimated_s", sa.Double(), server_default="60", nullable=False))
    op.alter_column("generations", "estimated_s", server_default=None)


def downgrade() -> None:
    op.drop_column("generations", "estimated_s")
    op.drop_table("preferences")
