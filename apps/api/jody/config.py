import os

from sqlalchemy import URL, make_url


def database_url() -> str | URL:
    if value := os.getenv("DATABASE_URL"):
        url = make_url(value)
        if url.drivername in {"postgresql", "postgres"}:
            return url.set(drivername="postgresql+psycopg")
        return url
    return URL.create(
        "postgresql+psycopg",
        username="jody",
        password=os.environ["POSTGRES_PASSWORD"],
        host="127.0.0.1",
        port=int(os.getenv("POSTGRES_PORT", "55432")),
        database="jody",
    )


def redis_url() -> str:
    return os.getenv("REDIS_URL") or f"redis://127.0.0.1:{os.getenv('REDIS_PORT', '56379')}/0"


def runtime_url() -> URL:
    """Same database, independent least-privilege login. Supports an explicit hosted URL."""
    from hashlib import sha256

    from sqlalchemy import make_url

    if value := os.environ.get("JODY_RUNTIME_DATABASE_URL"):
        return make_url(value)
    admin = make_url(database_url())
    suffix = sha256((admin.database or "").encode()).hexdigest()[:12]
    return admin.set(username=f"jody_app_{suffix}", password=os.environ["JODY_DB_APP_PASSWORD"])


def private_preview() -> bool:
    return os.getenv("JODY_PRIVATE_PREVIEW") == "1" or os.getenv("RENDER") == "true"


def ollama_address() -> tuple[str, int]:
    from urllib.parse import urlsplit

    address = urlsplit(os.getenv("JODY_OLLAMA_BASE_URL") or "http://127.0.0.1:11434")
    if (
        address.scheme != "http"
        or address.hostname not in {"127.0.0.1", "::1"}
        or address.username is not None
        or address.password is not None
        or address.path not in {"", "/"}
        or address.query
        or address.fragment
    ):
        raise ValueError("Choose a loopback HTTP origin for local Ollama.")
    return address.hostname, address.port or 80
