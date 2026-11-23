from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from cryptography.exceptions import InvalidTag
from jody.main import app
from jody.security import PRIVATE_OWNER, digest, tenant, unseal
from jody.tables import (
    applications,
    audits,
    connections,
    events,
    jobs,
    metadata,
    observations,
    sessions,
    tasks,
    trust,
    users,
)
from jody.worker import tick
from sqlalchemy import func, insert, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError

API = "/api/v1"
OTHER = UUID("11111111-1111-4111-8111-111111111111")
LEGACY_JOB = UUID("22222222-2222-4222-8222-222222222222")


def mutation(auth):
    return {**auth, "Idempotency-Key": str(uuid4())}


@pytest.fixture
def second_auth(admin_db):
    token = uuid4().hex
    with admin_db.begin() as conn:
        conn.execute(
            insert(sessions).values(
                user_id=OTHER,
                digest=digest(token),
                expires_at=datetime.now(UTC) + timedelta(minutes=1),
            )
        )
    return {"Authorization": "Bearer " + token}


def test_all_registered_private_routes_require_a_live_session(client):
    for path, methods in app.openapi()["paths"].items():
        if not path.startswith(API):
            continue
        path = path.replace("{provider}", "gmail")
        for param in ["job_id", "task_id"]:
            path = path.replace("{" + param + "}", str(uuid4()))
        for method in methods:
            if (method, path) == ("post", API + "/session"):
                continue
            response = client.request(
                method.upper(), path, headers={"Idempotency-Key": str(uuid4())}, json={}
            )
            assert response.status_code == 401, (method, path, response.status_code)
    assert client.post(API + "/signup", json={}).status_code == 404


def test_upgrade_and_seed_integrity(admin_db):
    with admin_db.connect() as conn:
        assert conn.scalar(select(jobs.c.user_id).where(jobs.c.id == LEGACY_JOB)) == OTHER
        assert (
            conn.scalar(select(events.c.kind).where(events.c.job_id == LEGACY_JOB)) == "discovered"
        )
        assert conn.scalar(
            select(observations.c.source_id).where(observations.c.job_id == LEGACY_JOB)
        )
        assert conn.scalar(select(sessions.c.user_id).where(sessions.c.digest == "a" * 64)) == OTHER
        for name in [
            "github_projects",
            "generated_artifacts",
            "trust_evaluations",
            "companies",
            "resume_versions",
            "approval_requests",
            "application_statuses",
            "email_events",
            "recruiter_outreach",
        ]:
            table = metadata.tables[name]
            assert conn.scalar(select(func.count()).where(table.c.user_id == OTHER)) == 1
        assert (
            conn.scalar(select(applications.c.method).where(applications.c.user_id == OTHER))
            == "cold_email"
        )
        for table in metadata.sorted_tables:
            if table.name in {"users", "system_control"}:
                continue
            assert not table.c.user_id.nullable
            assert conn.scalar(
                text("SELECT relrowsecurity FROM pg_class WHERE oid=to_regclass(:table)"),
                {"table": table.name},
            )


def test_database_constraints_and_unscoped_pool(client, admin_db):
    with admin_db.begin() as conn:
        for stmt in [
            insert(trust).values(
                user_id=OTHER, job_id=LEGACY_JOB, score=101, risk_flags=[], rules_version="test"
            ),
            insert(applications).values(user_id=PRIVATE_OWNER, job_id=LEGACY_JOB, method="lever"),
            insert(applications).values(user_id=OTHER, job_id=LEGACY_JOB, method="cold_email"),
            insert(jobs).values(user_id=None, fingerprint="test", description="test"),
            update(jobs).where(jobs.c.id == LEGACY_JOB).values(status="invalid"),
        ]:
            with pytest.raises(DBAPIError), conn.begin_nested():
                conn.execute(stmt)
    with tenant(app.state.db, PRIVATE_OWNER) as conn:
        assert conn.scalar(select(jobs.c.id).where(jobs.c.id == LEGACY_JOB)) is None
        with pytest.raises(DBAPIError), conn.begin_nested():
            conn.execute(
                insert(jobs).values(user_id=OTHER, fingerprint="cross", description="fixture")
            )
        with pytest.raises(DBAPIError), conn.begin_nested():
            conn.execute(audits.delete())
    with app.state.db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(jobs)) == 0
        assert conn.scalar(text("SELECT row_security_active('jobs')"))


def test_profile_and_settings(client, auth, second_auth):
    prefs = client.get(API + "/profile", headers=auth).json()["settings_json"]
    assert prefs == {
        "min_trust_score_auto_apply": 80,
        "min_ats_score_threshold": 82,
        "max_daily_linkedin_connects": 12,
        "max_daily_linkedin_dms": 20,
        "outbound_enabled": False,
        "auto_trash_scams": False,
        "auto_archive_rejections": False,
        "is_system_paused": True,
    }
    url = API + "/profile/settings"
    for payload in [
        {"min_ats_score_threshold": 101},
        {"outbound_enabled": "true"},
        {"user_id": str(OTHER)},
        {},
    ]:
        assert client.patch(url, headers=mutation(auth), json=payload).status_code == 422
    assert (
        client.patch(
            url, headers=mutation(auth), json={"min_trust_score_auto_apply": 81}
        ).status_code
        == 200
    )
    assert (
        client.get(API + "/profile", headers=second_auth).json()["settings_json"][
            "min_trust_score_auto_apply"
        ]
        == 80
    )


def test_expired_and_inactive_sessions(client, admin_db, second_auth):
    token = second_auth["Authorization"].split()[1]
    with admin_db.begin() as conn:
        conn.execute(update(users).where(users.c.id == OTHER).values(is_active=False))
    try:
        assert client.get(API + "/profile", headers=second_auth).status_code == 401
    finally:
        with admin_db.begin() as conn:
            conn.execute(update(users).where(users.c.id == OTHER).values(is_active=True))
            conn.execute(
                update(sessions)
                .where(sessions.c.digest == digest(token))
                .values(expires_at=func.now())
            )
    assert client.get(API + "/profile", headers=second_auth).status_code == 401


def test_encrypted_integration_and_replay(client, auth, admin_db, second_auth):
    url = API + "/integrations/gmail"
    headers = mutation(auth)
    value = "test-secret-" + uuid4().hex

    def store(_):
        return client.put(url, headers=headers, json={"credential": value})

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert all(r.status_code == 200 for r in pool.map(store, range(4)))
    assert client.put(url, headers=headers, json={"credential": "changed"}).status_code == 409
    with admin_db.connect() as conn:
        row = (
            conn.execute(select(connections).where(connections.c.user_id == PRIVATE_OWNER))
            .mappings()
            .one()
        )
        assert value.encode() not in row["encrypted_credentials"]
        args = (row["credentials_iv"], row["encrypted_credentials"])
        assert unseal(app.state.secret_key, PRIVATE_OWNER, "gmail", *args) == value.encode()
        for user, provider in [(OTHER, "gmail"), (PRIVATE_OWNER, "github")]:
            with pytest.raises(InvalidTag):
                unseal(app.state.secret_key, user, provider, *args)
    assert client.get(API + "/profile", headers=second_auth).json()["integrations"] == []
    audit = client.get(API + "/audit", headers=auth)
    assert sum(r["action"] == "integration.store" for r in audit.json()) == 1
    assert value not in audit.text and value not in client.get(API + "/profile", headers=auth).text
    assert client.delete(url, headers=mutation(auth)).status_code == 200
    assert client.get(API + "/profile", headers=auth).json()["integrations"] == []


def test_global_gate_queue_recovery_and_replay(client, auth, second_auth, admin_db, monkeypatch):
    gate = API + "/system/kill-switch"
    assert (
        client.post(gate, headers=mutation(second_auth), json={"paused": False}).status_code == 403
    )
    headers = mutation(auth)
    body = client.post(API + "/tasks/probe", headers=headers).json()
    assert client.post(API + "/tasks/probe", headers=headers).json() == body
    task_id = body["id"]
    assert client.get(API + "/tasks/" + task_id, headers=second_auth).status_code == 404
    assert not tick(app.state.db, app.state.queue)
    with pytest.raises(IntegrityError), admin_db.begin() as conn:
        conn.execute(update(tasks).where(tasks.c.id == task_id).values(status="succeeded"))
    resume = mutation(auth)
    assert client.post(gate, headers=resume, json={"paused": False}).status_code == 200
    assert not client.get(gate, headers=second_auth).json()["paused"]
    assert client.post(gate, headers=mutation(auth), json={"paused": True}).status_code == 200
    assert client.post(gate, headers=resume, json={"paused": False}).status_code == 200
    assert client.get(gate, headers=auth).json()["paused"] is True
    assert client.post(gate, headers=mutation(auth), json={"paused": False}).status_code == 200
    queue = f"jody:{app.state.db.url.database}:probe:{PRIVATE_OWNER}"
    # Publish then lose the Redis list before consumption. Simulate the republish deadline.
    with monkeypatch.context() as patch:
        patch.setattr(app.state.queue, "lpop", lambda key: None)
        assert not tick(app.state.db, app.state.queue)
    assert app.state.queue.lrange(queue, 0, -1) == [task_id.encode()]
    app.state.queue.delete(queue)
    with admin_db.begin() as conn:
        conn.execute(update(tasks).where(tasks.c.id == task_id).values(next_publish_at=func.now()))
    assert tick(app.state.db, app.state.queue)
    app.state.queue.rpush(queue, task_id)
    assert not tick(app.state.db, app.state.queue)
    assert client.get(API + "/tasks/" + task_id, headers=auth).json()["status"] == "succeeded"
    assert client.post(gate, headers=mutation(auth), json={"paused": True}).status_code == 200
    assert (
        sum(
            row["action"] == "task.probe_completed"
            for row in client.get(API + "/audit", headers=auth).json()
        )
        == 1
    )


def test_pause_transaction_fences_racing_worker(client, auth, admin_db):
    import time

    from jody.tables import control

    queued = client.post(API + "/tasks/probe", headers=mutation(auth)).json()
    with admin_db.begin() as conn:
        conn.execute(update(control).values(is_system_paused=False))
    with ThreadPoolExecutor(max_workers=1) as pool:
        with admin_db.begin() as pausing:
            pausing.execute(update(control).values(is_system_paused=True))
            worker = pool.submit(tick, app.state.db, app.state.queue)
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                with admin_db.connect() as observer:
                    if observer.scalar(
                        text("""SELECT EXISTS(SELECT FROM pg_stat_activity
                        WHERE datname=current_database() AND wait_event_type='Lock'
                        AND query='SELECT jody_dispatch_open()')""")
                    ):
                        break
                time.sleep(0.02)
            else:
                pytest.fail("Worker never reached the locked dispatch gate")
        assert worker.result(timeout=3) is False
    assert client.get(API + "/tasks/" + queued["id"], headers=auth).json()["status"] == "pending"


def test_prd_enum_labels(admin_db):
    expected = {
        "job_source_enum": "whatsapp linkedin_feed linkedin_post manual",
        "job_status_enum": "discovered pending_approval tailoring applied outreach_active shortlisted assessment interview offer rejected scam_blocked skipped",
        "apply_method_enum": "cold_email linkedin_easy_apply greenhouse lever workday wellfound internshala custom_portal",
        "outreach_status_enum": "queued connect_sent accepted dm_sent followup_sent replied failed",
        "email_class_enum": "application_ack assessment shortlist_interview offer rejection scam_spam unrelated",
    }
    with admin_db.connect() as conn:
        for name, labels in expected.items():
            actual = conn.scalars(
                text("""
                SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid=e.enumtypid
                WHERE t.typname=:name ORDER BY e.enumsortorder
            """),
                {"name": name},
            )
            assert list(actual) == labels.split()


def test_workspace_reads_tenant_records_and_policies(client, auth, second_auth):
    path = API + "/workspace"
    other = client.get(path, headers=second_auth).json()
    job = next(j for j in other["jobs"] if j["id"] == str(LEGACY_JOB))
    assert job["company"] == "Fixture Company" and job["trust_score"] == 45
    assert other["applications"] and other["approvals"] and other["mail"] and other["outreach"]
    private = client.get(path, headers=auth).json()
    assert all(j["id"] != str(LEGACY_JOB) for j in private["jobs"])
    assert "encrypted_credentials" not in str(private)
    for route, payload, field in [
        ("source-policy", {"kind": "manual", "identifier": "Owner feed"}, "allowlist"),
        (
            "block-policy",
            {"kind": "domain", "value": "test.invalid", "reason": "Owner choice"},
            "blocklist",
        ),
    ]:
        key = mutation(auth)
        for _ in range(2):
            assert (
                client.put(
                    f"{path}/{route}", headers=key, json={**payload, "enabled": True}
                ).status_code
                == 200
            )
        label = payload.get("value") or payload["identifier"]
        assert sum(r["title"] == label for r in client.get(path, headers=auth).json()[field]) == 1
        assert all(r["title"] != label for r in client.get(path, headers=second_auth).json()[field])
        assert (
            client.put(
                f"{path}/{route}", headers=mutation(auth), json={**payload, "enabled": False}
            ).status_code
            == 200
        )
        assert all(r["title"] != label for r in client.get(path, headers=auth).json()[field])
