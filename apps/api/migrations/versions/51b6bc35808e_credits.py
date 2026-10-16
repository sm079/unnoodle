"""credits

Revision ID: 51b6bc35808e
Revises: d1c9f5f37310
Create Date: 2026-10-16 13:06:29.424074

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "51b6bc35808e"
down_revision: str | Sequence[str] | None = "d1c9f5f37310"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # An append-only ledger of credits (app.credits), invite codes, and what each generation was charged
    op.create_table(
        "invite_codes",
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("code = upper(code)", name=op.f("ck_invite_codes_code_uppercase")),
        sa.CheckConstraint("credits > 0", name=op.f("ck_invite_codes_credits_positive")),
        sa.CheckConstraint("max_uses > 0", name=op.f("ck_invite_codes_max_uses_positive")),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_invite_codes")),
    )
    op.create_table(
        "credit_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("generation_id", sa.Uuid(), nullable=True),
        sa.Column("invite_code", sa.String(length=32), nullable=True),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "kind = 'grant' OR (kind = 'charge') = (amount < 0)", name=op.f("ck_credit_entries_sign_follows_kind")
        ),
        sa.CheckConstraint("kind IN ('grant', 'invite', 'charge', 'refund')", name=op.f("ck_credit_entries_kind")),
        sa.CheckConstraint("amount <> 0", name=op.f("ck_credit_entries_amount_not_zero")),
        sa.ForeignKeyConstraint(
            ["generation_id"],
            ["generations.id"],
            name=op.f("fk_credit_entries_generation_id_generations"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["invite_code"],
            ["invite_codes.code"],
            name=op.f("fk_credit_entries_invite_code_invite_codes"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_credit_entries_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_credit_entries")),
    )
    op.create_index("ix_credit_entries_user_id", "credit_entries", ["user_id"], unique=False)
    op.create_index(
        "uq_credit_entries_generation_kind",
        "credit_entries",
        ["generation_id", "kind"],
        unique=True,
        postgresql_where=sa.text("generation_id IS NOT NULL"),
    )
    op.create_index(
        "uq_credit_entries_user_invite",
        "credit_entries",
        ["user_id", "invite_code"],
        unique=True,
        postgresql_where=sa.text("invite_code IS NOT NULL"),
    )
    op.add_column("generations", sa.Column("cost", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("generations", "cost")
    op.drop_index(
        "uq_credit_entries_user_invite",
        table_name="credit_entries",
        postgresql_where=sa.text("invite_code IS NOT NULL"),
    )
    op.drop_index(
        "uq_credit_entries_generation_kind",
        table_name="credit_entries",
        postgresql_where=sa.text("generation_id IS NOT NULL"),
    )
    op.drop_index("ix_credit_entries_user_id", table_name="credit_entries")
    op.drop_table("credit_entries")
    op.drop_table("invite_codes")
