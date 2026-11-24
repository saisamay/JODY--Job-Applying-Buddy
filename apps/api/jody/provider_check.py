"""Explicit, read-only operator probes. Secrets and provider bodies never go to stdout."""

import argparse
import json
import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

import psycopg

from .config import ollama_address
from .security import PRIVATE_OWNER


class CheckError(Exception):
    pass


def setting(name: str) -> str:
    value = os.getenv("JODY_" + name)
    if not value:
        raise CheckError(f"Set JODY_{name} in the private operator environment.")
    return value


class NoRedirect(HTTPRedirectHandler):
    # Tokens must never follow a provider redirect to a different origin.
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def read(
    url: str,
    headers: dict[str, str] | None = None,
    *,
    method: str = "GET",
    data: bytes | None = None,
) -> dict[str, Any]:
    req = Request(url, data=data, headers=headers or {}, method=method)
    try:
        with build_opener(NoRedirect()).open(req, timeout=15) as r:
            raw = r.read(8_000_001)
            if len(raw) > 8_000_000:
                raise CheckError("Provider metadata exceeded the size limit.")
            result = json.loads(raw) if raw else {}
            if not isinstance(result, dict):
                raise ValueError
            return result
    except HTTPError as exc:
        raise CheckError(f"Provider returned HTTP {exc.code}. See the credential guide.") from None
    except (OSError, ValueError):
        raise CheckError("Connection, TLS or provider response failed.") from None


def bearer(value: str) -> dict[str, str]:
    return {"Authorization": "Bearer " + value}


@contextmanager
def operator_session() -> Iterator[None]:
    api = "http://127.0.0.1:8000/api/v1"
    login = read(
        api + "/session",
        {"Content-Type": "application/json"},
        method="POST",
        data=json.dumps({"key": setting("OWNER_KEY")}).encode(),
    )
    token = login.get("token")
    if not isinstance(token, str) or not token:
        raise CheckError("Local owner sign-in failed.")
    headers = bearer(token)
    try:
        if read(api + "/session", headers).get("user_id") != str(PRIVATE_OWNER):
            raise CheckError("The operator check requires the local private owner.")
        yield
    finally:
        read(api + "/session", headers, method="DELETE")


def check(provider: str) -> str:
    if provider == "gmail":
        from .gmail_check import run

        return run()
    if provider == "neon":
        url = setting("NEON_TEST_DATABASE_URL")
        host = urlsplit(url).hostname or ""
        if not host.endswith(".neon.tech") or "-pooler." in host:
            raise CheckError("Select a direct Neon rehearsal branch URL.")
        with psycopg.connect(
            url,
            sslmode="verify-full",
            sslrootcert="system",
            connect_timeout=10,
            options="-c default_transaction_read_only=on",
        ) as conn:
            row = conn.execute(
                "SELECT current_setting('transaction_read_only'), default_version FROM pg_available_extensions WHERE name='vector'"
            ).fetchone()
            if row and row[0] == "on":
                return "Neon direct TLS connection succeeded; pgvector is available."
    if provider in {"github", "resume_git"}:
        repo = setting("GITHUB_REPOSITORY")
        if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo) or any(
            p in {".", ".."} for p in repo.split("/")
        ):
            raise CheckError("Use owner/repository for JODY_GITHUB_REPOSITORY.")
        url = "https://api.github.com/repos/" + repo
        headers = bearer(setting("GITHUB_TOKEN"))
        if provider == "github":
            if str(read(url, headers).get("full_name")).casefold() == repo.casefold():
                return "Selected repository metadata readable."
        else:
            ref, path = setting("RESUME_GIT_REF"), setting("RESUME_GIT_PATH")
            if not re.fullmatch(r"[a-fA-F0-9]{40}", ref) or any(
                p in {"", ".", ".."} for p in path.split("/")
            ):
                raise CheckError("Use a full commit SHA and a repository-relative file path.")
            headers["Accept"] = "application/vnd.github.object+json"
            item = read(
                url + "/contents/" + quote(path, safe="/") + "?" + urlencode({"ref": ref}), headers
            )
            if item.get("type") == "file" and item.get("path") == path and item.get("sha"):
                return "Pinned resume source readable. No file saved."
    if provider == "telegram":
        token = setting("TELEGRAM_BOT_TOKEN")
        if not re.fullmatch(r"\d+:[A-Za-z0-9_-]+", token):
            raise CheckError("Invalid Telegram bot token format.")
        result = read("https://api.telegram.org/bot" + token + "/getMe")
        if result.get("ok") is True and result.get("result", {}).get("is_bot") is True:
            return "Bot identity verified. Chat linking remains pending."
    if provider == "gemini":
        models = read(
            "https://generativelanguage.googleapis.com/v1beta/models",
            {"x-goog-api-key": setting("GEMINI_API_KEY")},
        ).get("models", [])
        if any("generateContent" in m.get("supportedGenerationMethods", []) for m in models):
            return "Gemini text generation catalog readable. Confirm free quota in AI Studio."
    if provider == "groq":
        models = read("https://api.groq.com/openai/v1/models", bearer(setting("GROQ_API_KEY"))).get(
            "data", []
        )
        if any(m.get("id") and m.get("active", True) for m in models):
            return "Groq model catalog readable. Confirm free limits in the console."
    if provider == "openrouter":
        if read("https://openrouter.ai/api/v1/key", bearer(setting("OPENROUTER_API_KEY"))).get(
            "data"
        ):
            models = read("https://openrouter.ai/api/v1/models").get("data", [])
            if any(
                m.get("id", "").endswith(":free")
                and all(m.get("pricing", {}).get(k) == "0" for k in ["prompt", "completion"])
                for m in models
            ):
                return "OpenRouter key recognized and a free text variant is listed."
    if provider == "ntfy":
        origin = setting("NTFY_BASE_URL").rstrip("/")
        parts = urlsplit(origin)
        if (
            parts.scheme != "https"
            or not parts.hostname
            or parts.username
            or parts.password
            or parts.path
            or parts.fragment
            or parts.query
        ):
            raise CheckError("Use the HTTPS origin of your trusted private ntfy server.")
        if read(origin + "/v1/account", bearer(setting("NTFY_TOKEN"))).get("role") in {
            "user",
            "admin",
        }:
            return "Private ntfy account verified. Topic ACL and delivery remain untested."
    if provider == "ollama":
        host, port = ollama_address()
        base = f"http://[{host}]:{port}" if ":" in host else f"http://{host}:{port}"
        models = read(base + "/api/tags").get("models", [])
        if any(m.get("name") == os.getenv("JODY_CHAT_MODEL", "llama3:latest") for m in models):
            return "Configured local chat model is installed."
    raise CheckError("Provider response did not confirm the required capability.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "provider",
        choices="gmail github resume_git telegram ntfy gemini groq openrouter ollama neon".split(),
    )
    try:
        provider = parser.parse_args().provider
        with operator_session():
            print(check(provider))
    except CheckError as exc:
        raise SystemExit(str(exc)) from None
    except (OSError, ValueError, psycopg.Error, KeyError, TypeError, AttributeError):
        raise SystemExit(
            "Probe failed. Check configuration and provider access; see docs/SECRETS_CHECKLIST.md."
        ) from None


if __name__ == "__main__":
    main()
