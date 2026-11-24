"""Restore a real encrypted custom-format archive into a fresh disposable PostgreSQL database."""

import os
import secrets
import subprocess
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from jody.config import database_url, runtime_url
from jody.provision import provision
from jody.security import PRIVATE_OWNER, encryption_key, runtime_engine, seal, tenant, unseal
from jody.tables import connections, metadata
from sqlalchemy import create_engine, delete, func, insert, make_url, select, text


def test_encrypted_restore(test_database, tmp_path: Path, monkeypatch):
    source = make_url(database_url())
    assert source.database.startswith("jody_test_")
    db = create_engine(source)
    provider = "restore_" + uuid4().hex
    nonce, ciphertext = seal(encryption_key(), PRIVATE_OWNER, provider, "synthetic backup canary")
    with db.begin() as c:
        c.execute(
            insert(connections).values(
                user_id=PRIVATE_OWNER,
                provider=provider,
                encrypted_credentials=ciphertext,
                credentials_iv=nonce,
                key_version=1,
            )
        )
        counts = {
            t.name: c.scalar(select(func.count()).select_from(t)) for t in metadata.sorted_tables
        }
    db.dispose()
    target = source.set(database="jody_restore_" + uuid4().hex)
    admin = create_engine(source, isolation_level="AUTOCOMMIT")

    def pg_env(url):
        return dict(
            os.environ,
            PGDATABASE=url.database,
            PGHOST=url.host,
            PGPORT=str(url.port),
            PGUSER=url.username,
            PGPASSWORD=url.password,
        )

    archive = tmp_path / "synthetic.dump.gpg"
    home = tmp_path / "gnupg"
    home.mkdir(mode=0o700)
    password = (secrets.token_hex(32) + "\n").encode()
    # Feed keys via stdin and archive bytes via an OS pipe. No plaintext dump on disk.
    import tempfile

    with tempfile.TemporaryFile() as key:
        key.write(password)
        key.seek(0)
        gpg = [
            "gpg",
            "--batch",
            "--yes",
            "--homedir",
            str(home),
            "--pinentry-mode",
            "loopback",
            "--passphrase-fd",
            str(key.fileno()),
        ]
        with subprocess.Popen(
            ["/usr/lib/postgresql/16/bin/pg_dump", "--format=custom", "--no-owner", "--no-acl"],
            env=pg_env(source),
            stdout=subprocess.PIPE,
        ) as dump:
            subprocess.run(
                [*gpg, "--symmetric", "--cipher-algo", "AES256", "--output", str(archive)],
                stdin=dump.stdout,
                pass_fds=(key.fileno(),),
                check=True,
            )
            assert dump.wait() == 0
        with admin.connect() as c:
            c.exec_driver_sql("CREATE DATABASE " + target.database)
        monkeypatch.setenv("DATABASE_URL", target.render_as_string(hide_password=False))
        role = runtime_url().username
        try:
            key.seek(0)
            with subprocess.Popen(
                [*gpg, "--decrypt", str(archive)], pass_fds=(key.fileno(),), stdout=subprocess.PIPE
            ) as decrypted:
                subprocess.run(
                    [
                        "/usr/lib/postgresql/16/bin/pg_restore",
                        "--no-acl",
                        "--no-owner",
                        "--exit-on-error",
                        "--single-transaction",
                        "--dbname",
                        target.database,
                    ],
                    stdin=decrypted.stdout,
                    env=pg_env(target),
                    check=True,
                )
                assert decrypted.wait() == 0
            command.upgrade(Config("alembic.ini"), "head")
            provision()
            check = create_engine(target)
            with check.connect() as c:
                assert {
                    t.name: c.scalar(select(func.count()).select_from(t))
                    for t in metadata.sorted_tables
                } == counts
                assert c.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
                assert not c.scalar(
                    text(
                        "SELECT has_function_privilege('public','jody_session_owner(text)','EXECUTE')"
                    )
                )
            check.dispose()
            runtime = runtime_engine()
            with tenant(runtime, PRIVATE_OWNER) as c:
                row = (
                    c.execute(select(connections).where(connections.c.provider == provider))
                    .mappings()
                    .one()
                )
                assert (
                    unseal(
                        encryption_key(),
                        PRIVATE_OWNER,
                        provider,
                        row["credentials_iv"],
                        row["encrypted_credentials"],
                    )
                    == b"synthetic backup canary"
                )
            with tenant(runtime, uuid4()) as c:
                assert not c.scalar(select(connections.c.id))
            runtime.dispose()
        finally:
            with admin.connect() as c:
                c.exec_driver_sql("DROP DATABASE " + target.database + " WITH (FORCE)")
                c.exec_driver_sql('DROP ROLE IF EXISTS "' + role + '"')
            with admin.begin() as c:
                c.execute(delete(connections).where(connections.c.provider == provider))
            admin.dispose()
