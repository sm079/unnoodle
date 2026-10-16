"""name columns after pipelines

Revision ID: 14eb6df5a136
Revises: 27077e63f64d
Create Date: 2026-10-16 18:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "14eb6df5a136"
down_revision: str | Sequence[str] | None = "27077e63f64d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The code calls them pipelines and the renderer's run; the columns follow
    op.alter_column("generations", "workflow_id", new_column_name="pipeline_id")
    op.alter_column("generations", "comfy_prompt_id", new_column_name="run_id")


def downgrade() -> None:
    op.alter_column("generations", "run_id", new_column_name="comfy_prompt_id")
    op.alter_column("generations", "pipeline_id", new_column_name="workflow_id")
