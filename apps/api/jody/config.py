import os

from sqlalchemy import URL


def database_url() -> str | URL:
    return os.environ.get("DATABASE_URL") or URL.create(
        "postgresql+psycopg",
        username="jody",
        password=os.environ["POSTGRES_PASSWORD"],
        host="127.0.0.1",
        port=int(os.getenv("POSTGRES_PORT", "55432")),
        database="jody",
    )


def redis_url() -> str:
    return os.getenv("REDIS_URL") or f"redis://127.0.0.1:{os.getenv('REDIS_PORT', '56379')}/0"
