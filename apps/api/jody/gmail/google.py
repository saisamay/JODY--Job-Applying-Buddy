"""Fixed-origin Google transport. Provider errors contain no upstream text or parameters."""

import base64
import hashlib
import json
import os
import re
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, build_opener

from ..integration_setup import READ_SCOPE
from ..provider_check import NoRedirect

CALLBACK = "http://127.0.0.1:3000/gmail/callback"
AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN = "https://oauth2.googleapis.com/token"
BASE = "https://gmail.googleapis.com/gmail/v1/users/me/"


class Problem(Exception):
    def __init__(self, state: str, status: int = 0) -> None:
        self.state, self.status = state, status
        super().__init__(state)


def configured() -> bool:
    return all(os.getenv("JODY_GOOGLE_" + k) for k in ("CLIENT_ID", "CLIENT_SECRET"))


def authorize(state: str, verifier: str) -> str:
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    )
    return (
        AUTH
        + "?"
        + urlencode(
            dict(
                client_id=os.environ["JODY_GOOGLE_CLIENT_ID"],
                redirect_uri=CALLBACK,
                response_type="code",
                access_type="offline",
                prompt="consent",
                scope=READ_SCOPE,
                state=state,
                code_challenge_method="S256",
                code_challenge=challenge,
            )
        )
    )


def call(url: str, *, token: str = "", form: dict[str, str] | None = None) -> dict[str, Any]:
    req = Request(
        url,
        data=urlencode(form).encode() if form is not None else None,
        headers={"Authorization": "Bearer " + token} if token else {},
    )
    try:
        with build_opener(NoRedirect()).open(req, timeout=8) as r:
            raw = r.read(2_000_001)
            if len(raw) > 2_000_000:
                raise Problem("Failed")
            obj = json.loads(raw) if raw else {}
            if not isinstance(obj, dict):
                raise ValueError
            return obj
    except HTTPError as exc:
        try:
            detail = json.loads(exc.read(8192)).get("error")
        except (ValueError, AttributeError):
            detail = None
        if exc.code == 401 or detail == "invalid_grant":
            state = "Authorization expired"
        elif exc.code == 429 or (
            exc.code == 403
            and isinstance(detail, dict)
            and any(
                e.get("reason")
                in {
                    "rateLimitExceeded",
                    "userRateLimitExceeded",
                    "quotaExceeded",
                    "dailyLimitExceeded",
                }
                for e in detail.get("errors", [])
                if isinstance(e, dict)
            )
        ):
            state = "Rate limited"
        else:
            state = "Temporarily unavailable" if exc.code >= 500 else "Failed"
        raise Problem(state, exc.code) from None
    except (OSError, ValueError):
        raise Problem("Temporarily unavailable") from None


def exchange(**params: str) -> dict[str, Any]:
    obj = call(
        TOKEN,
        form={
            **params,
            "client_id": os.environ["JODY_GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["JODY_GOOGLE_CLIENT_SECRET"],
        },
    )
    if set(str(obj.get("scope", "")).split()) != {READ_SCOPE} or not obj.get("access_token"):
        raise Problem("Authorization required")
    return obj


class Mailbox:
    def __init__(self, refresh: str) -> None:
        self.calls = 0
        self.access = exchange(grant_type="refresh_token", refresh_token=refresh)["access_token"]

    def get(self, path: str, **params: Any) -> dict[str, Any]:
        if not re.fullmatch(r"profile|history|messages(?:/[a-zA-Z0-9_-]+)?", path):
            raise Problem("Failed")
        self.calls += 1
        return call(
            BASE
            + path
            + "?"
            + urlencode({k: v for k, v in params.items() if v is not None}, doseq=True),
            token=self.access,
        )
