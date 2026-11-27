"""Allow canonical source observations for Gmail. Existing jobs and receipts are untouched."""

from alembic import op

revision = "0006_gmail_source"
down_revision = "0005_gmail"


def upgrade() -> None:
    op.execute("ALTER TYPE job_source_enum ADD VALUE IF NOT EXISTS 'gmail'")


def downgrade() -> None:
    # PostgreSQL cannot remove a single enum label. Preserve existing Gmail observations.
    pass
