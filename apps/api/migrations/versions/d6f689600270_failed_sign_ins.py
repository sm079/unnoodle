"""failed sign ins

Revision ID: d6f689600270
Revises: 51b6bc35808e
Create Date: 2026-10-16 13:40:23.113949

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d6f689600270"
down_revision: str | Sequence[str] | None = "51b6bc35808e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Wrong passwords in the last few minutes, to slow down guessing (app.accounts)
    op.create_table(
        "failed_sign_ins",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_failed_sign_ins")),
    )
    op.create_index("ix_failed_sign_ins_email", "failed_sign_ins", ["email", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_failed_sign_ins_email", table_name="failed_sign_ins")
    op.drop_table("failed_sign_ins")
