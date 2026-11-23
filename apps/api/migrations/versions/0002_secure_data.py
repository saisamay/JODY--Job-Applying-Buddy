"""Tenant-scoped PRD records, private credentials and execution controls."""

from pathlib import Path

from alembic import op

revision = "0002_secure_data"
down_revision = "0001_foundation"
SQL = Path(__file__).resolve().parents[1] / "sql"


def upgrade() -> None:
    op.get_bind().exec_driver_sql((SQL / "0002_upgrade.sql").read_text())


def downgrade() -> None:
    op.get_bind().exec_driver_sql((SQL / "0002_downgrade.sql").read_text())
