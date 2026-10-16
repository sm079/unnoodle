"""banned words

Revision ID: 27077e63f64d
Revises: d6f689600270
Create Date: 2026-10-16 13:44:13.512743

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Kept here rather than imported, so the migration inserts the same list however app.moderation changes
DEFAULT_WORDS = (
    "nude",
    "naked",
    "nsfw",
    "porn",
    "pornographic",
    "sexual",
    "topless",
    "undressed",
    "gore",
    "beheading",
)

# revision identifiers, used by Alembic.
revision: str = "27077e63f64d"
down_revision: str | Sequence[str] | None = "d6f689600270"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Words prompts may not contain, starting with a short list admins can change (app.moderation)
    op.create_table(
        "banned_words",
        sa.Column("word", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("word = lower(word) AND btrim(word) <> ''", name=op.f("ck_banned_words_word_lowercase")),
        sa.PrimaryKeyConstraint("word", name=op.f("pk_banned_words")),
    )
    words = sa.table("banned_words", sa.column("word", sa.String))
    op.bulk_insert(words, [{"word": word} for word in DEFAULT_WORDS])


def downgrade() -> None:
    op.drop_table("banned_words")
