import os
import secrets
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from jody.config import database_url
from jody.main import app
from sqlalchemy import create_engine, make_url


@pytest.fixture(scope="session", autouse=True)
def test_database():
    # Only drop the unique database created here. The configured database is the admin connection.
    url = make_url(database_url())
    name = f"jody_test_{uuid4().hex}"
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.exec_driver_sql(f"CREATE DATABASE {name}")
    try:
        with pytest.MonkeyPatch.context() as patch:
            patch.setenv(
                "DATABASE_URL", url.set(database=name).render_as_string(hide_password=False)
            )
            patch.setenv("JODY_OWNER_KEY", secrets.token_hex(32))
            config = Config("alembic.ini")
            command.upgrade(config, "head")
            command.check(config)
            yield
            command.downgrade(config, "base")
            command.upgrade(config, "head")
    finally:
        with admin.connect() as conn:
            conn.exec_driver_sql(f"DROP DATABASE {name}")
        admin.dispose()


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


@pytest.fixture
def auth(client):
    response = client.post("/api/v1/session", json={"key": os.environ["JODY_OWNER_KEY"]})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["token"]}
