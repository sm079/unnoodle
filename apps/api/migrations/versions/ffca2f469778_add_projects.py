"""add projects

Revision ID: ffca2f469778
Revises: d949252b5622
Create Date: 2026-10-15 20:21:01.441702

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ffca2f469778"
down_revision: str | Sequence[str] | None = "d949252b5622"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Every generation is in My generations; a project_id also files it in one project
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("btrim(name) <> ''", name=op.f("ck_projects_name_not_blank")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
    )
    op.add_column("generations", sa.Column("project_id", sa.Uuid(), nullable=True))
    op.create_index("ix_generations_project_id", "generations", ["project_id", "id"], unique=False)
    op.create_foreign_key(
        op.f("fk_generations_project_id_projects"),
        "generations",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_generations_project_id_projects"), "generations", type_="foreignkey")
    op.drop_index("ix_generations_project_id", table_name="generations")
    op.drop_column("generations", "project_id")
    op.drop_table("projects")
