from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from jody.security import digest
from jody.tables import audits, commands, profiles, sessions, uploaded_resumes, users
from sqlalchemy import insert, select

BASE = "/api/v1/candidate"
PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"


def command(headers):
    return {**headers, "Idempotency-Key": str(uuid4())}


@pytest.fixture
def identities(admin_db):
    accounts = []
    with admin_db.begin() as conn:
        for _ in range(2):
            uid, token = uuid4(), uuid4().hex
            conn.execute(
                insert(users).values(
                    id=uid, full_name="Private owner", email=f"{uid}@private.invalid"
                )
            )
            conn.execute(
                insert(sessions).values(
                    user_id=uid,
                    digest=digest(token),
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            )
            accounts.append((uid, {"Authorization": "Bearer " + token}))
    return accounts


def snapshot(client, headers):
    response = client.get(BASE, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def edit(client, headers, values):
    return client.patch(
        BASE,
        headers=command(headers),
        json={"revision": snapshot(client, headers)["revision"], "fields": values},
    )


def advance(client, headers, step, status="completed"):
    return client.post(
        BASE + "/onboarding",
        headers=command(headers),
        json={"revision": snapshot(client, headers)["revision"], "step": step, "status": status},
    )


def test_edit_private_profile_and_preserve_legacy_projection(client, identities, admin_db):
    (uid, a), (_, b) = identities
    fields = {
        "full_name": "Test Candidate",
        "email": "candidate@example.invalid",
        "phone": "+1 555 0100",
        "education": [{"institution": "Fixture University", "program": "Computer Science"}],
        "work_experience": [{"organization": "Example Org", "role": "Engineer"}],
        "skills": ["Python"],
        "projects": [{"name": "Fixture project", "description": "Synthetic fixture"}],
        "github": "https://github.com/example",
        "linkedin": "https://linkedin.com/in/example",
        "portfolio": "https://example.invalid/",
        "preferred_roles": ["Backend engineer"],
        "employment_types": ["Internship"],
        "preferred_locations": ["Example City"],
        "work_modes": ["hybrid"],
        "salary_expectations": "Private salary fixture",
        "availability": "After graduation",
        "work_authorization": "Private authorization fixture",
        "application_preferences": "Ask before travel",
    }
    assert edit(client, a, fields).status_code == 200
    result = snapshot(client, a)
    for name, value in fields.items():
        if name not in {"education", "work_experience", "projects"}:
            assert result["fields"][name] == value
        assert result["provenance"][name]["status"] == "user_provided"
    assert result["fields"]["work_experience"][0]["role"] == "Engineer"
    assert result["fields"]["projects"][0]["name"] == "Fixture project"
    old = client.get("/api/v1/profile", headers=a).json()
    assert old["full_name"] == "Test Candidate" and old["github_username"] == "example"
    assert "candidate_ciphertext" not in old
    assert snapshot(client, b)["fields"]["phone"] is None
    with admin_db.connect() as conn:
        blob = conn.scalar(select(profiles.c.candidate_ciphertext).where(profiles.c.user_id == uid))
        receipts = str(
            conn.execute(select(commands.c.response).where(commands.c.user_id == uid)).all()
        )
        log = str(conn.execute(select(audits.c.details).where(audits.c.user_id == uid)).all())
        for secret in (
            fields["phone"],
            fields["work_authorization"],
            fields["salary_expectations"],
        ):
            assert secret.encode() not in blob and secret not in log + receipts
    assert edit(client, a, {"phone": None}).status_code == 200
    assert snapshot(client, a)["fields"]["phone"] is None


def test_suggestions_evidence_and_clarification(client, identities):
    _, a = identities[0]
    url = BASE + "/application-preview"

    def preview():
        return client.post(
            url,
            headers=a,
            json={
                "required_fields": ["skills", "custom question", "phone"],
                "include_portfolio": True,
            },
        ).json()

    for field, value, origin in [
        ("skills", ["Fixture ML"], "user_provided"),
        ("phone", "555-0101", "inferred"),
    ]:
        r = client.patch(
            BASE + "/suggestions",
            headers=command(a),
            json={
                "revision": snapshot(client, a)["revision"],
                "fields": {field: value},
                "origin": origin,
            },
        )
        assert r.status_code == 200
    state = snapshot(client, a)
    assert state["suggestion_origins"] == {"skills": "user_provided", "phone": "inferred"}
    assert state["fields"]["skills"] is None and preview()["answers"] == {}
    assert (
        edit(
            client, a, {"skills": ["Fixture ML"], "portfolio": "https://example.invalid/"}
        ).status_code
        == 200
    )
    assert set(preview()["clarifications"]) == {"skills", "custom question", "phone"}
    proof = {
        "revision": snapshot(client, a)["revision"],
        "field": "skills",
        "evidence": "Reviewed fixture project revision 23",
    }
    assert client.post(BASE + "/review", headers=command(a), json=proof).status_code == 200
    checked = preview()
    assert checked["answers"] == {"skills": ["Fixture ML"], "portfolio": "https://example.invalid/"}
    assert (
        checked["explicit_submission_approval_required"]
        and checked["explicit_email_approval_required"]
    )
    assert client.post(url, headers=a, json={"required_fields": []}).json()["answers"] == {}
    assert edit(client, a, {"skills": ["Another skill"]}).status_code == 200
    assert "skills" in preview()["clarifications"]
    assert edit(client, a, {"status": "verified"}).status_code == 422


def test_skips_confirmation_and_reopening(client, identities):
    _, a = identities[0]
    state = snapshot(client, a)
    assert len(state["steps"]) == 8 and not state["confirmed"]
    assert advance(client, a, "basic_profile").status_code == 422
    assert advance(client, a, "final_confirmation").status_code == 409
    assert advance(client, a, "automation_permissions", "skipped").status_code == 422
    assert (
        edit(
            client, a, {"full_name": "Fixture Owner", "email": "steps@example.invalid"}
        ).status_code
        == 200
    )
    for step in state["steps"][:-1]:
        response = advance(client, a, step["step"], "skipped" if step["optional"] else "completed")
        assert response.status_code == 200, response.text
    assert advance(client, a, "final_confirmation").status_code == 200
    assert snapshot(client, a)["confirmed"] and not any(snapshot(client, a)["permissions"].values())
    assert edit(client, a, {"skills": ["Fixture skill"]}).status_code == 200
    state = snapshot(client, a)
    assert not state["confirmed"] and state["steps"][2]["status"] == "pending"
    assert advance(client, a, "skills_projects").status_code == 200
    assert advance(client, a, "final_confirmation").status_code == 200
    client.patch(
        "/api/v1/profile/settings", headers=command(a), json={"auto_archive_rejections": True}
    ).raise_for_status()
    state = snapshot(client, a)
    assert not state["confirmed"] and state["steps"][6]["status"] == "pending"


def test_stale_and_duplicate_edits(client, identities):
    _, a = identities[0]
    hdr = command(a)
    payload = {"revision": 0, "fields": {"phone": "123"}}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: client.patch(BASE, headers=hdr, json=payload), range(2)))
    assert [r.json() for r in results] == [{"revision": 1}] * 2
    assert client.patch(BASE, headers=command(a), json=payload).status_code == 409
    assert (
        client.patch(
            BASE, headers=hdr, json={"revision": 0, "fields": {"phone": "456"}}
        ).status_code
        == 409
    )
    assert edit(client, a, {"email": "invalid"}).status_code == 422


def test_role_resumes_are_private_and_versioned(client, identities, admin_db):
    (uid, a), (_, b) = identities
    url = BASE + "/resumes"

    def upload(role, body, revision, headers=None, kind="application/pdf"):
        return client.post(
            url,
            params={"revision": revision},
            content=body,
            headers={
                **(headers or command(a)),
                "Content-Type": kind,
                "X-Resume-Label": "Fixture",
                "X-Resume-Role": role,
            },
        )

    assert upload("Dev", PDF, 0, kind="text/plain").status_code == 415
    assert upload("Dev", b"bad", 0).status_code == 422
    assert upload("Dev", b"x" * (5 * 1024 * 1024 + 1), 0).status_code == 413
    hdr = command(a)
    first = upload("Backend", PDF, 0, hdr)
    assert first.status_code == 201, first.text
    rid = first.json()["resume_id"]
    assert upload("Backend", PDF, 0, hdr).json() == first.json()
    assert upload("Mobile", PDF, 1).status_code == 201
    assert {r["target_role"] for r in snapshot(client, a)["resumes"]} == {"Backend", "Mobile"}
    assert advance(client, a, "resume_upload").status_code == 200
    draft = BASE + "/application-preview"
    assert (
        "resume"
        in client.post(draft, headers=a, json={"required_fields": ["resume"]}).json()[
            "clarifications"
        ]
    )
    assert (
        client.post(
            draft, headers=a, json={"required_fields": ["resume"], "resume_id": rid}
        ).json()["answers"]["resume"]
        == rid
    )
    path = url + "/" + rid
    assert client.get(path, headers=b).status_code == 404
    assert client.delete(path, params={"revision": 0}, headers=command(b)).status_code == 404
    assert (
        client.post(
            BASE + "/application-preview", headers=b, json={"required_fields": [], "resume_id": rid}
        ).status_code
        == 404
    )
    response = client.get(path, headers=a)
    assert response.content == PDF and response.headers["Content-Disposition"].startswith(
        "attachment"
    )
    with admin_db.connect() as conn:
        encrypted = conn.scalar(
            select(uploaded_resumes.c.ciphertext).where(uploaded_resumes.c.user_id == uid)
        )
        assert PDF not in encrypted
    assert (
        client.patch(path, headers=command(a), json={"label": "Updated", "revision": 3}).status_code
        == 200
    )
    assert client.delete(path, params={"revision": 4}, headers=command(a)).status_code == 200
    assert client.get(path, headers=a).status_code == 404
