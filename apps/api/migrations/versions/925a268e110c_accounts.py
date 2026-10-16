"""accounts

Revision ID: 925a268e110c
Revises: 98e46aa0b9eb
Create Date: 2026-10-16 12:35:27.050532

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "925a268e110c"
down_revision: str | Sequence[str] | None = "98e46aa0b9eb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Owns whatever was made before there were accounts. It has no password, so it can't sign in until one is set with
# python -m app.users set-password owner@unnoodle.local
OWNER = "owner@unnoodle.local"
OWNED = ("assets", "generations", "projects")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("email = lower(email)", name=op.f("ck_users_email_lowercase")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_sessions_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("token_hash", name=op.f("pk_sessions")),
    )
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)

    # Nullable until the rows already there have an owner
    for table in OWNED:
        op.add_column(table, sa.Column("owner_id", sa.Uuid(), nullable=True))
    anything = " UNION ALL ".join(f"SELECT 1 FROM {table}" for table in OWNED)
    op.execute(
        sa.text(
            f"INSERT INTO users (id, email, is_admin) SELECT gen_random_uuid(), :owner, true WHERE EXISTS ({anything})"
        ).bindparams(owner=OWNER)
    )
    for table in OWNED:
        op.execute(
            sa.text(f"UPDATE {table} SET owner_id = (SELECT id FROM users WHERE email = :owner)").bindparams(
                owner=OWNER
            )
        )
        op.alter_column(table, "owner_id", nullable=False)
        op.create_index(f"ix_{table}_owner_id", table, ["owner_id", "id"], unique=False)
        op.create_foreign_key(
            op.f(f"fk_{table}_owner_id_users"), table, "users", ["owner_id"], ["id"], ondelete="CASCADE"
        )
    # Media is looked up by key to check its owner, posters included
    op.create_unique_constraint(op.f("uq_assets_poster_key"), "assets", ["poster_key"])


def downgrade() -> None:
    op.drop_constraint(op.f("uq_assets_poster_key"), "assets", type_="unique")
    for table in OWNED:
        op.drop_constraint(op.f(f"fk_{table}_owner_id_users"), table, type_="foreignkey")
        op.drop_index(f"ix_{table}_owner_id", table_name=table)
        op.drop_column(table, "owner_id")
    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("users")
