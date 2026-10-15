"""one output per generation

Revision ID: 20e318569d2b
Revises: ed5b59569a8e
Create Date: 2026-10-16 02:34:56.002670

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20e318569d2b"
down_revision: str | Sequence[str] | None = "ed5b59569a8e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Asking for several now queues several generations, each one run with one output, so a GPU never makes a batch
    op.drop_constraint(op.f("ck_generations_count_positive"), "generations", type_="check")
    op.drop_column("generations", "count")


def downgrade() -> None:
    op.add_column("generations", sa.Column("count", sa.Integer(), server_default="1", nullable=False))
    op.alter_column("generations", "count", server_default=None)
    op.create_check_constraint(op.f("ck_generations_count_positive"), "generations", "count >= 1")
