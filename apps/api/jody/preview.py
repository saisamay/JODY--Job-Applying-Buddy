"""Run the preview migrations once under a database lock, then replace this process with the API."""

import os
import sys

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from .config import database_url, runtime_url
from .provision import provision
from .security import encryption_key


def main() -> None:
    os.environ["JODY_PRIVATE_PREVIEW"] = "1"
    if not all(os.environ.get(k) for k in ("DATABASE_URL", "JODY_DB_APP_PASSWORD", "REDIS_URL")):
        raise RuntimeError("Configure the preview database, runtime password and queue.")
    if os.getenv("JODY_RUNTIME_DATABASE_URL") or len(os.getenv("JODY_OWNER_KEY", "")) < 32:
        raise RuntimeError("Use the preview role provisioner and a generated owner key.")
    encryption_key()
    admin = create_engine(database_url(), connect_args={"connect_timeout": 10})
    try:
        with admin.begin() as connection:
            connection.execute(text("SET LOCAL lock_timeout = '60s'"))
            connection.execute(text("SELECT pg_advisory_xact_lock(431027114)"))
            config = Config("alembic.ini")
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        # Grants are transactional and serialized separately, including on concurrent boots.
        provision()
    finally:
        admin.dispose()
    env = dict(
        os.environ, JODY_RUNTIME_DATABASE_URL=runtime_url().render_as_string(hide_password=False)
    )
    for key in ("DATABASE_URL", "POSTGRES_PASSWORD", "JODY_DB_APP_PASSWORD"):
        env.pop(key, None)
    os.execve(
        sys.executable,
        [
            sys.executable,
            "-m",
            "uvicorn",
            "jody.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(int(env.get("PORT", "10000"))),
            "--no-access-log",
        ],
        env,
    )


if __name__ == "__main__":
    main()
