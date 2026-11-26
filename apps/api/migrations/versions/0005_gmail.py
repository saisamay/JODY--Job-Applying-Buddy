"""Tenant-scoped Gmail authorization, resumable reads and job provenance."""

from pathlib import Path

from alembic import op

revision = "0005_gmail"
down_revision = "0004_career"
TABLES = ("gmail_accounts", "gmail_runs", "gmail_messages", "gmail_job_evidence")


def upgrade() -> None:
    op.get_bind().exec_driver_sql((Path(__file__).parents[1] / "sql/0005_upgrade.sql").read_text())
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY tenant_scope ON {table}
            USING (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid)
            WITH CHECK (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid)""")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
