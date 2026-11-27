import base64
import json
import os
import subprocess
import sys

import pytest
from jody.gmail.extract import Posting, body
from jody.gmail.platforms import parse, posting
from jody.local_providers import load


def card(jid, metadata):
    return f'<tr><td><table><tr><td><a href="https://www.linkedin.com/comm/jobs/view/{jid}/?midToken=fixture">Platform Engineer</a></td></tr><tr><td>{metadata}</td></tr></table></td></tr>'


def part(mime, data):
    return {"mimeType": mime, "body": {"data": base64.urlsafe_b64encode(data.encode()).decode()}}


def test_nested_cards_and_alternatives():
    html = (
        "<h2>Engineering jobs</h2><table>"
        + card(100, "Example Labs · Kochi (Hybrid)")
        + card(101, "Other Labs · Pune")
        + card(102, "")
        + "</table>"
    )
    msg = {
        "mimeType": "multipart/alternative",
        "parts": [part("text/html", html), part("text/plain", "Title: repeated heading")],
    }
    rows = [v for v, _ in parse("linkedin.com", msg, body(msg))]
    assert all(isinstance(v, Posting) for v in rows)
    assert [
        (
            v.title,
            v.company,
            v.location,
            v.work_mode,
            v.platform_job_id,
            v.posting_url,
            v.application_url,
        )
        for v in rows
    ] == [
        (
            "Platform Engineer",
            company,
            location,
            mode,
            str(i),
            f"https://www.linkedin.com/jobs/view/{i}",
            None,
        )
        for i, company, location, mode in [
            (100, "Example Labs", "Kochi", "Hybrid"),
            (101, "Other Labs", "Pune", None),
            (102, None, None, None),
        ]
    ]
    assert posting("https://www.linkedin.com/jobs/search/?currentJobId=100&trk=other")[0] == "100"
    for url in [
        "https://www.linkedin.com.fake.example/jobs/view/100",
        "javascript:1",
        "https://www.linkedin.com/redirect?url=/jobs/view/100",
    ]:
        assert posting(url) is None


def test_local_startup_loader(tmp_path, monkeypatch):
    path = tmp_path / "providers.env"
    path.write_text(
        "JODY_GOOGLE_CLIENT_ID=fixture\nJODY_GOOGLE_CLIENT_SECRET=$(false)\nUNRELATED_FIXTURE=unsafe\n"
    )
    path.chmod(0o600)
    monkeypatch.setenv("JODY_PROVIDERS_FILE", str(path))
    monkeypatch.delenv("JODY_GOOGLE_CLIENT_SECRET", raising=False)
    monkeypatch.setenv("JODY_GOOGLE_CLIENT_ID", "override")
    env = dict(os.environ, PYTHONPATH="apps/api")
    result = subprocess.check_output(
        [
            sys.executable,
            "-m",
            "jody.local_providers",
            sys.executable,
            "-c",
            "import os,json;from jody.gmail.google import configured;print(json.dumps([configured(),os.getenv('JODY_GOOGLE_CLIENT_ID')=='override',os.getenv('JODY_GOOGLE_CLIENT_SECRET')=='$(false)', 'UNRELATED_FIXTURE' not in os.environ]))",
        ],
        env=env,
    )
    assert json.loads(result) == [True] * 4
    path.chmod(0o644)
    with pytest.raises(ValueError):
        load()


def test_five_message_boundary_and_platform_identity(client, admin_db, monkeypatch):
    from uuid import uuid4

    from jody.career.knowledge import pack
    from jody.gmail import google, worker
    from jody.gmail.service import enqueue
    from jody.main import app
    from jody.security import tenant
    from jody.tables import (
        control,
        gmail_accounts,
        gmail_evidence,
        gmail_messages,
        gmail_runs,
        jobs,
        observations,
        users,
    )
    from sqlalchemy import func, insert, select, update

    owner = uuid4()
    with admin_db.begin() as c:
        paused = c.scalar(select(control.c.is_system_paused))
        c.execute(update(control).values(is_system_paused=False))
        c.execute(
            insert(users).values(id=owner, email=f"{owner}@fixture.invalid", full_name="Fixture")
        )
        c.execute(
            insert(gmail_accounts).values(
                user_id=owner,
                account="synthetic@fixture.invalid",
                state="Connected",
                grant=pack(app.state.secret_key, owner, "gmail:refresh", b"synthetic"),
                policy={"senders": ["fixture@linkedin.com"], "limit": 5},
            )
        )

    class Mailbox:
        calls = 0

        def __init__(self, *args):
            pass

        def get(self, path, **kwargs):
            self.calls += 1
            if path == "profile":
                return {"historyId": "50"}
            if path == "messages":
                return {"messages": [{"id": str(i)} for i in range(5)]}
            fixture = (
                card(100, "Example · Kochi")
                + card(100, "Example · Kochi")
                + card(101, "Other · Pune")
            )
            payload = part("text/html", fixture)
            payload["headers"] = [
                {"name": "From", "value": "fixture@linkedin.com"},
                {"name": "Subject", "value": "Job alert"},
                {
                    "name": "Authentication-Results",
                    "value": "mx.google.com; dmarc=pass header.from=linkedin.com",
                },
            ]
            return {"payload": payload}

    monkeypatch.setattr(google, "Mailbox", Mailbox)
    monkeypatch.setattr(google, "configured", lambda: True)
    try:
        run = enqueue(app.state.db, owner)
        clients = {}
        for _ in range(5):
            assert worker.step(app.state.db, owner, app.state.secret_key, clients, run)
        assert not worker.step(app.state.db, owner, app.state.secret_key, clients, run)
        with tenant(app.state.db, owner) as c:
            state = c.execute(select(gmail_runs)).mappings().one()
            assert (
                state["status"] == "succeeded"
                and state["finished"]
                and state["counts"]["duplicates"] == 8
            )
            assert c.scalar(select(gmail_accounts.c.history_id)) == "50"
            assert c.scalar(select(func.count()).select_from(jobs)) == 2
            for table in (gmail_evidence, observations):
                assert c.scalar(select(func.count()).select_from(table)) == 10
        from contextlib import nullcontext

        from jody.gmail import repair_preview

        with tenant(app.state.db, owner) as c:
            receipt = c.scalar(select(gmail_messages.c.id).limit(1))
        calls = []

        class ReceiptMailbox(Mailbox):
            def get(self, path, **params):
                assert path.startswith("messages/")
                calls.append(params["format"])
                return super().get(path, **params)

        monkeypatch.setattr(repair_preview, "Mailbox", ReceiptMailbox)
        monkeypatch.setattr(repair_preview, "PRIVATE_OWNER", owner)
        monkeypatch.setattr(repair_preview, "operator_session", nullcontext)
        proposals = repair_preview.preview(receipt)
        assert proposals[0]["proposed_job_fields"]["company"] == "Example"
        assert len(proposals[0]["same_title_existing_jobs"]) == 2
        assert calls == ["metadata", "full"]
        with tenant(app.state.db, owner) as c:
            assert c.scalar(select(func.count()).select_from(jobs)) == 2
            assert c.scalar(select(gmail_accounts.c.history_id)) == "50"
    finally:
        with admin_db.begin() as c:
            c.execute(update(control).values(is_system_paused=paused))


@pytest.mark.parametrize("name", ["gemini", "groq"])
def test_synthetic_cloud_extraction(name, monkeypatch):
    import io

    from jody.gmail.models import Extractor

    raw = json.dumps(
        {
            "classification": "Job alert",
            "vacancies": [{"title": "Fixture engineer", "company": "Fixture company"}],
        }
    )

    class Mock:
        def open(self, req, timeout):
            assert "Fixture engineer" in req.data.decode()
            obj = (
                {"candidates": [{"content": {"parts": [{"text": raw}]}}]}
                if name == "gemini"
                else {"choices": [{"message": {"content": raw}}]}
            )
            return io.BytesIO(json.dumps(obj).encode())

    monkeypatch.setattr("jody.gmail.models.build_opener", lambda *_: Mock())
    result, _ = Extractor(name, "synthetic", "fixture").call(
        "gmail_extract", {"excerpt": "Fixture engineer at Fixture company"}
    )
    assert result["vacancies"][0]["company"] == "Fixture company"


def test_wrapped_card_with_semantic_metadata():
    html = '<table><tr><td><a href="https://www.linkedin.com/jobs/view/500"><strong>Dev Engineer</strong><span class="job-company-name">Fixture employer</span><span class="job-location">Fixture city</span></a></td></tr></table>'
    msg = part("text/html", html)
    [(v, _)] = parse("linkedin.com", msg, body(msg))
    assert (v.title, v.company, v.location) == ("Dev Engineer", "Fixture employer", "Fixture city")


def test_alert_heading_alone_is_not_a_platform_card():
    from jody.gmail.platforms import linkedin

    assert linkedin("<h2>New engineer jobs</h2>") == []


def test_responsive_copies_count_once_and_use_title_anchor():
    href = "https://www.linkedin.com/jobs/view/100"
    html = f'<article><a href="{href}">Company logo</a><a href="{href}"><b>Engineer</b><span>Example · Pune</span></a></article>'
    msg = part("text/html", html + html)
    [(v, _)] = parse("linkedin.com", msg, body(msg))
    assert (v.title, v.company, v.location) == ("Engineer", "Example", "Pune")
