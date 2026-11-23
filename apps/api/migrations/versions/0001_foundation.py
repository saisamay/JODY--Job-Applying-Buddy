"""Private owner sessions and manual intake."""

from alembic import op

revision = "0001_foundation"
down_revision = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE TABLE owners (id uuid PRIMARY KEY)")
    op.execute("""
        CREATE TABLE sessions (
            digest varchar(64) PRIMARY KEY,
            owner_id uuid NOT NULL REFERENCES owners(id),
            expires_at timestamptz NOT NULL
        )
    """)
    op.execute("""
        CREATE TABLE jobs (
            id uuid PRIMARY KEY, owner_id uuid NOT NULL REFERENCES owners(id),
            fingerprint varchar(64) NOT NULL, description text NOT NULL, source_url text,
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (owner_id, id), UNIQUE (owner_id, fingerprint)
        )
    """)
    for table, field in [("source_observations", "source"), ("job_events", "kind")]:
        op.execute(f"""
            CREATE TABLE {table} (
                id uuid PRIMARY KEY, owner_id uuid NOT NULL, job_id uuid NOT NULL,
                {field} text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
                FOREIGN KEY (owner_id, job_id) REFERENCES jobs(owner_id, id)
            )
        """)


def downgrade() -> None:
    for table in ["job_events", "source_observations", "jobs", "sessions", "owners"]:
        op.drop_table(table)
