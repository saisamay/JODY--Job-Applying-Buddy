from uuid import uuid4

from jody.career.inference import Mock, configured
from jody.worker import tick


def test_preview_lock_cannot_be_overridden(client, auth, monkeypatch):
    monkeypatch.setenv("JODY_PRIVATE_PREVIEW", "1")
    monkeypatch.setenv("JODY_AI_PROVIDER", "ollama")
    assert isinstance(configured(), Mock)
    assert not tick(client.app.state.db, client.app.state.queue)
    gate = "/api/v1/system/kill-switch"
    assert client.get(gate).status_code == 401
    assert client.get(gate, headers=auth).json() == {"paused": True, "locked": True}
    for method, path, payload in [
        ("POST", gate, {"paused": False}),
        ("PATCH", "/api/v1/profile/settings", {"outbound_enabled": True}),
        ("PATCH", "/api/v1/profile/settings", {"auto_trash_scams": True}),
        ("PATCH", "/api/v1/profile/settings", {"auto_archive_rejections": True}),
        ("PUT", "/api/v1/integrations/gmail", {"credential": "test"}),
        ("POST", "/api/v1/tasks/probe", None),
    ]:
        headers = {**auth, "Idempotency-Key": str(uuid4())}
        assert client.request(method, path, headers=headers, json=payload).status_code == 403
    assert client.get("/api/v1/workspace", headers=auth).status_code == 200
    preflight = client.options(
        gate, headers={"Origin": "https://example.org", "Access-Control-Request-Method": "POST"}
    )
    assert "access-control-allow-origin" not in preflight.headers


def test_preview_import_refuses_before_network(monkeypatch):
    import pytest
    from fastapi import HTTPException
    from jody.career.web_source import fetch

    monkeypatch.setenv("RENDER", "true")
    with pytest.raises(HTTPException) as exc:
        fetch("https://example.org", html=True)
    assert exc.value.status_code == 403
