from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)

metadata = MetaData()
owners = Table("owners", metadata, Column("id", Uuid, primary_key=True))
sessions = Table(
    "sessions",
    metadata,
    Column("digest", String(64), primary_key=True),
    Column("owner_id", Uuid, ForeignKey("owners.id"), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
)
jobs = Table(
    "jobs",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("owner_id", Uuid, ForeignKey("owners.id"), nullable=False),
    Column("fingerprint", String(64), nullable=False),
    Column("description", Text, nullable=False),
    Column("source_url", Text),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("owner_id", "id"),
    UniqueConstraint("owner_id", "fingerprint"),
)


def job_history(name: str, field: str) -> Table:
    return Table(
        name,
        metadata,
        Column("id", Uuid, primary_key=True),
        Column("owner_id", Uuid, nullable=False),
        Column("job_id", Uuid, nullable=False),
        Column(field, Text, nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        ForeignKeyConstraint(["owner_id", "job_id"], ["jobs.owner_id", "jobs.id"]),
    )


observations = job_history("source_observations", "source")
events = job_history("job_events", "kind")
