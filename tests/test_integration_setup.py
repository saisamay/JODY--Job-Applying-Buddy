import os
from uuid import uuid4

import pytest
from jody import gmail_check, provider_check
from jody.config import ollama_address
from jody.integration_setup import GMAIL_CALLBACK, READ_SCOPE, ConnectionState, cards
from jody.provider_check import CheckError


def test_setup_cards_and_callback(client, auth):
    assert len(ConnectionState) == 7
    assert client.get("/api/v1/workspace").status_code == 401
    assert client.get(GMAIL_CALLBACK, headers=auth, params={"code": "synthetic"}).status_code == 409
    url = "/api/v1/integrations/groq"

    def mutate():
        return {**auth, "Idempotency-Key": str(uuid4())}

    assert client.put(url, headers=mutate(), json={"credential": "fake-fixture"}).status_code == 200
    catalog = client.get("/api/v1/workspace", headers=auth).json()["integration_cards"]
    assert next(c for c in catalog if c["provider"] == "groq")["state"] == "Authorization required"
    assert client.delete(url, headers=mutate()).status_code == 200
    assert all(c.state == ConnectionState.disabled for c in cards(["groq"], True))


def test_gmail_nonce_and_refresh_probe(monkeypatch):
    attempt = gmail_check.Attempt()
    with pytest.raises(CheckError):
        attempt.consume(attempt.state, "wrong")
    attempt.consume(attempt.state, attempt.browser)
    with pytest.raises(CheckError):
        attempt.consume(attempt.state, attempt.browser)
    expired = gmail_check.Attempt(expires=0)
    with pytest.raises(CheckError):
        expired.consume(expired.state, expired.browser)
    replies = iter(
        [
            {"scope": READ_SCOPE, "refresh_token": "test"},
            {"access_token": "test", "scope": READ_SCOPE},
            {"emailAddress": "fixture@example.org"},
        ]
    )
    calls = []

    def read(url, *args, **kwargs):
        calls.append(url)
        return next(replies)

    monkeypatch.setattr(gmail_check, "read", read)
    gmail_check.verify_code("test", attempt, "client", "secret")
    assert calls[-1].endswith("/gmail/v1/users/me/profile")
    monkeypatch.setattr(
        gmail_check,
        "read",
        lambda *args, **kwargs: {"scope": READ_SCOPE + " other", "refresh_token": "test"},
    )
    with pytest.raises(CheckError):
        gmail_check.verify_code("test", attempt, "client", "secret")


@pytest.mark.parametrize(
    ("name", "env", "reply"),
    [
        (
            "telegram",
            {"TELEGRAM_BOT_TOKEN": "12:fixture"},
            {"ok": True, "result": {"is_bot": True}},
        ),
        (
            "gemini",
            {"GEMINI_API_KEY": "test"},
            {"models": [{"supportedGenerationMethods": ["generateContent"]}]},
        ),
        ("groq", {"GROQ_API_KEY": "test"}, {"data": [{"id": "synthetic"}]}),
        (
            "github",
            {"GITHUB_TOKEN": "test", "GITHUB_REPOSITORY": "sample/repo"},
            {"full_name": "sample/repo"},
        ),
        (
            "resume_git",
            {
                "GITHUB_TOKEN": "test",
                "GITHUB_REPOSITORY": "sample/repo",
                "RESUME_GIT_REF": "a" * 40,
                "RESUME_GIT_PATH": "cv.tex",
            },
            {"type": "file", "path": "cv.tex", "sha": "sha"},
        ),
        (
            "ntfy",
            {"NTFY_TOKEN": "test", "NTFY_BASE_URL": "https://notify.example.org"},
            {"role": "user"},
        ),
        (
            "ollama",
            {"OLLAMA_BASE_URL": "http://127.0.0.1:11434"},
            {"models": [{"name": os.getenv("JODY_CHAT_MODEL", "llama3:latest")}]},
        ),
    ],
)
def test_read_only_checks(monkeypatch, name, env, reply):
    for k, v in env.items():
        monkeypatch.setenv("JODY_" + k, v)
    monkeypatch.setattr(provider_check, "read", lambda *args, **kwargs: reply)
    assert provider_check.check(name)
    monkeypatch.setattr(provider_check, "read", lambda *args, **kwargs: {})
    with pytest.raises(CheckError):
        provider_check.check(name)


def test_checks_reject_unsafe_targets(monkeypatch):
    monkeypatch.setenv("JODY_OLLAMA_BASE_URL", "https://example.org")
    with pytest.raises(ValueError):
        ollama_address()
    monkeypatch.setenv(
        "JODY_NEON_TEST_DATABASE_URL", "postgresql://u:p@ep-demo-pooler.example.neon.tech/test"
    )
    with pytest.raises(CheckError):
        provider_check.check("neon")
    monkeypatch.setenv("JODY_NTFY_BASE_URL", "https://example.org@bad.example.org/topic")
    with pytest.raises(CheckError):
        provider_check.check("ntfy")


def test_gmail_loopback_browser(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from http.client import HTTPConnection
    from queue import Queue
    from urllib.parse import parse_qs, urlsplit

    from jody.integration_setup import LOCAL_CALLBACK

    for key, value in [
        ("CLIENT_ID", "local"),
        ("CLIENT_SECRET", "fixture"),
        ("REDIRECT_URI", LOCAL_CALLBACK),
    ]:
        monkeypatch.setenv("JODY_GOOGLE_" + key, value)
    started = Queue()
    monkeypatch.setattr(
        "builtins.print", lambda message, **kwargs: started.put(message.split()[-1])
    )
    verified = []
    monkeypatch.setattr(gmail_check, "verify_code", lambda code, *_: verified.append(code))
    with ThreadPoolExecutor(1) as pool:
        pending = pool.submit(gmail_check.run)
        start = urlsplit(started.get(timeout=5))
        http = HTTPConnection(start.hostname, start.port, timeout=5)
        http.request("GET", start.path)
        redirect = http.getresponse()
        assert redirect.status == 302
        cookie = redirect.getheader("Set-Cookie").split(";")[0]
        params = parse_qs(urlsplit(redirect.getheader("Location")).query)
        assert params["redirect_uri"] == [LOCAL_CALLBACK]
        assert params["scope"] == [READ_SCOPE] and params["code_challenge_method"] == ["S256"]
        redirect.read()
        http.request(
            "GET",
            GMAIL_CALLBACK + "?state=" + params["state"][0] + "&code=fixture",
            headers={"Cookie": cookie},
        )
        ok = http.getresponse()
        assert ok.status == 200
        ok.read()
        http.close()
        assert pending.result(timeout=5).endswith("verified.")
    assert verified == ["fixture"]


def test_free_catalog_key_is_separate_from_model_price(monkeypatch):
    monkeypatch.setenv("JODY_OPENROUTER_API_KEY", "fixture")

    def answer(url, *args):
        if url.endswith("/key"):
            return {"data": {"label": "fixture"}}
        return {"data": [{"id": "demo:free", "pricing": {"prompt": "0", "completion": "0"}}]}

    monkeypatch.setattr(provider_check, "read", answer)
    assert provider_check.check("openrouter").startswith("OpenRouter")
