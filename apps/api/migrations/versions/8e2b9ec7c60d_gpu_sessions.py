"""gpu sessions: one row per rented GPU (app.gpu)

Revision ID: 8e2b9ec7c60d
Revises: 5c3e9a1d7b20
Create Date: 2026-10-16 17:51:26.302040

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "8e2b9ec7c60d"
down_revision: str | Sequence[str] | None = "5c3e9a1d7b20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "gpu_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("phase", sa.String(length=32), nullable=True),
        sa.Column(
            "ready", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("requested_by", sa.String(length=320), nullable=False),
        sa.Column("pod_id", sa.String(length=64), nullable=True),
        sa.Column("gpu_type", sa.String(length=64), nullable=True),
        sa.Column("cost_per_hour", sa.Double(), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("ssh_port", sa.Integer(), nullable=True),
        sa.Column("stop_requested", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("stop_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("launched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('requested', 'launching', 'preparing', 'ready', 'stopped', 'failed')",
            name=op.f("ck_gpu_sessions_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gpu_sessions")),
    )
    # At most one live session, so two requests can never rent two GPUs
    op.create_index(
        "uq_gpu_sessions_live",
        "gpu_sessions",
        [sa.literal_column("(true)")],
        unique=True,
        postgresql_where=sa.text("status NOT IN ('stopped', 'failed')"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_gpu_sessions_live",
        table_name="gpu_sessions",
        postgresql_where=sa.text("status NOT IN ('stopped', 'failed')"),
    )
    op.drop_table("gpu_sessions")
