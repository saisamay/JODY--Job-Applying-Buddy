from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from jody.main import app
from jody.security import digest
from jody.tables import events, observations, sessions, users
from redis import ConnectionError
from sqlalchemy import func, insert, select, text


def test_health_and_pgvector(client):
    assert client.get("/health/live").json() == {"status": "live"}
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "postgres": True, "redis": True}
    assert response.headers["X-Request-ID"]
    with app.state.db.connect() as conn:
        assert conn.scalar(text("SELECT '[1,2]'::vector <-> '[1,2]'::vector")) == 0


def test_unavailable_broker(client, monkeypatch):
    def offline():
        raise ConnectionError("offline")

    monkeypatch.setattr(app.state.queue, "ping", offline)
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "postgres": True, "redis": False}
    assert client.get("/health/live").status_code == 200


def test_closed_access_and_logout(client, auth):
    assert client.get("/api/v1/jobs").status_code == 401
    assert client.post("/api/v1/session", json={"key": "invalid"}).status_code == 401
    assert client.delete("/api/v1/session", headers=auth).status_code == 204
    assert client.get("/api/v1/jobs", headers=auth).status_code == 401


def test_validation(client, auth):
    for body in [{"description": "  "}, {"description": "Job", "source_url": "invalid"}]:
        rejected = client.post("/api/v1/jobs/manual", headers=auth, json=body)
        assert rejected.status_code == 422
        assert rejected.json() == {"detail": "Check the submitted fields."}


def test_concurrent_intake(client, auth, admin_db):
    body = {"description": "Synthetic engineer opening", "source_url": "https://example.org/jobs/1"}

    def submit(_):
        response = client.post("/api/v1/jobs/manual", headers=auth, json=body)
        assert response.status_code == 200
        return response.json()["id"]

    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(submit, range(8)))
    assert len(set(ids)) == 1
    assert (
        sum(item["id"] == ids[0] for item in client.get("/api/v1/jobs", headers=auth).json()) == 1
    )
    with admin_db.connect() as conn:
        for table in [events, observations]:
            assert conn.scalar(select(func.count()).where(table.c.job_id == ids[0])) == 1


def test_owner_scope(client, auth, admin_db):
    job = client.post(
        "/api/v1/jobs/manual", headers=auth, json={"description": "Private fixture"}
    ).json()
    other_owner = uuid4()
    other_token = uuid4().hex
    with admin_db.begin() as conn:
        conn.execute(
            insert(users).values(
                id=other_owner, email="other-fixture@example.invalid", full_name="Fixture"
            )
        )
        conn.execute(
            insert(sessions).values(
                user_id=other_owner,
                digest=digest(other_token),
                expires_at=datetime.now(UTC) + timedelta(minutes=1),
            )
        )
    headers = {"Authorization": "Bearer " + other_token}
    assert client.get("/api/v1/jobs", headers=headers).json() == []
    assert client.get("/api/v1/jobs/" + job["id"], headers=headers).status_code == 404
    assert client.get("/api/v1/jobs/" + job["id"], headers=auth).status_code == 200


def test_restart_persistence():
    import os

    with TestClient(app) as first:
        token = first.post("/api/v1/session", json={"key": os.environ["JODY_OWNER_KEY"]}).json()[
            "token"
        ]
        headers = {"Authorization": "Bearer " + token}
        job = first.post(
            "/api/v1/jobs/manual", headers=headers, json={"description": "Restart fixture"}
        ).json()
    with TestClient(app) as restarted:
        response = restarted.get("/api/v1/jobs/" + job["id"], headers=headers)
        assert response.status_code == 200
        assert response.json() == job


def test_unavailable_database(client, auth, monkeypatch):
    from sqlalchemy.exc import OperationalError

    def offline():
        raise OperationalError("sensitive database details", {}, Exception())

    monkeypatch.setattr(app.state.db, "connect", offline)
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "postgres": False, "redis": True}
    response = client.get("/api/v1/jobs", headers=auth)
    assert response.status_code == 503
    assert response.json() == {"detail": "Database temporarily unavailable."}


def test_request_log_redacts_input(client, caplog, monkeypatch):
    import json

    from jody.main import log

    monkeypatch.setattr(log, "propagate", True)
    response = client.post("/api/v1/session?query_private=ignore", json={"key": "private-fixture"})
    entry = json.loads(next(record.message for record in caplog.records if record.name == log.name))
    assert entry["request_id"] == response.headers["X-Request-ID"]
    assert entry["route"] == "/api/v1/session"
    assert entry["status"] == 401
    assert "private" not in json.dumps(entry)
