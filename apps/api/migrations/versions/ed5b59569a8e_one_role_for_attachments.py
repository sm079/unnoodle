"""one role for attachments

Revision ID: ed5b59569a8e
Revises: 738b396addd0
Create Date: 2026-10-16 02:10:06.460623

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ed5b59569a8e"
down_revision: str | Sequence[str] | None = "738b396addd0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The edit model treats every photo alike, so a photo to edit is just the first reference
    op.drop_constraint(op.f("ck_generation_inputs_role"), "generation_inputs", type_="check")
    op.execute("UPDATE generation_inputs SET role = 'reference' WHERE role = 'edit_target'")
    op.create_check_constraint(op.f("ck_generation_inputs_role"), "generation_inputs", "role IN ('reference')")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_generation_inputs_role"), "generation_inputs", type_="check")
    # Which photo was the one to edit isn't recorded any more; in an edit it was the first
    op.execute(
        "UPDATE generation_inputs i SET role = 'edit_target' FROM generations g "
        "WHERE g.id = i.generation_id AND g.capability = 'image.edit' AND i.position = 0"
    )
    op.create_check_constraint(
        op.f("ck_generation_inputs_role"), "generation_inputs", "role IN ('edit_target', 'reference')"
    )
