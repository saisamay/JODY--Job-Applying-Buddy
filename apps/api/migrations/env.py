from alembic import context
from jody.config import database_url
from jody.tables import metadata
from sqlalchemy import Connection, create_engine, pool


def migrate(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=metadata)
    with context.begin_transaction():
        context.run_migrations()


if supplied := context.config.attributes.get("connection"):
    migrate(supplied)
else:
    engine = create_engine(database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        migrate(connection)
