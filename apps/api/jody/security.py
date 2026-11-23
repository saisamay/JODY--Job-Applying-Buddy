import hashlib
import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import UUID

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import Connection, Engine, create_engine, insert, text

from .config import runtime_url
from .tables import audits

PRIVATE_OWNER = UUID("00000000-0000-4000-8000-000000000001")


def runtime_engine() -> Engine:
    db = create_engine(
        runtime_url(),
        pool_pre_ping=True,
        pool_timeout=3,
        hide_parameters=True,
        connect_args={"connect_timeout": 3, "options": "-c statement_timeout=5000"},
    )
    with db.connect() as conn:
        if not conn.scalar(
            text("SELECT row_security_active('jobs') AND row_security_active('users')")
        ):
            raise RuntimeError("The runtime database role must enforce tenant row security.")
    return db


@contextmanager
def tenant(db: Engine, user: UUID) -> Iterator[Connection]:
    with db.begin() as conn:
        conn.execute(text("SELECT set_config('jody.user_id',:user,true)"), {"user": str(user)})
        yield conn


def audit(
    conn: Connection,
    user: UUID,
    action: str,
    resource: UUID | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        insert(audits).values(
            user_id=user, action=action, resource_id=resource, details=details or {}
        )
    )


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def encryption_key() -> bytes:
    key = bytes.fromhex(os.environ["JODY_ENCRYPTION_KEY"])
    if len(key) != 32:
        raise ValueError("JODY_ENCRYPTION_KEY must encode 32 bytes.")
    return key


def seal(key: bytes, user: UUID, provider: str, secret: str | bytes) -> tuple[bytes, bytes]:
    nonce = os.urandom(12)
    return nonce, AESGCM(key).encrypt(
        nonce,
        secret.encode() if isinstance(secret, str) else secret,
        f"jody:v1:{user}:{provider}".encode(),
    )


def unseal(key: bytes, user: UUID, provider: str, nonce: bytes, ciphertext: bytes) -> bytes:
    return AESGCM(key).decrypt(nonce, ciphertext, f"jody:v1:{user}:{provider}".encode())
