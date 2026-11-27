"""Derived screening state and immutable per-source intake facts."""

from alembic import op

revision = "0007_job_filter"
down_revision = "0006_gmail_source"


def upgrade() -> None:
    op.execute("ALTER TABLE jobs ADD COLUMN canonical jsonb, ADD COLUMN screening jsonb")
    op.execute(
        "ALTER TABLE source_observations ADD COLUMN facts jsonb, ADD COLUMN sighting_key text, ADD UNIQUE(user_id,sighting_key)"
    )
    op.execute(
        "CREATE INDEX job_screening_queue ON jobs(user_id,id) WHERE canonical IS NOT NULL AND screening IS NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE source_observations DROP COLUMN sighting_key, DROP COLUMN facts")
    op.execute("ALTER TABLE jobs DROP COLUMN screening, DROP COLUMN canonical")
