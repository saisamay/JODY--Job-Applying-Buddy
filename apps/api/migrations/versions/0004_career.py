"""Immutable career evidence, profile decisions, metering and tailored drafts."""

from pathlib import Path

from alembic import op

revision = "0004_career"
down_revision = "0003_candidate"
TABLES = ("career_sources", "career_versions", "career_cache", "career_usage", "career_proposals")


def upgrade() -> None:
    ddl = (Path(__file__).parents[1] / "sql" / "0004_upgrade.sql").read_text()
    for statement in ddl.split(";"):
        if statement.strip():
            op.execute(statement)
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY tenant_scope ON {table}
            USING (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid)
            WITH CHECK (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid)""")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
