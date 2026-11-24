"""One browser, one locally authenticated operator, one read-only verification. No mailbox import."""

import base64
import hashlib
import secrets
import time
from dataclasses import dataclass, field
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit

from .integration_setup import GMAIL_CALLBACK, LOCAL_CALLBACK, READ_SCOPE
from .provider_check import CheckError, bearer, read, setting


@dataclass
class Attempt:
    state: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    verifier: str = field(default_factory=lambda: secrets.token_urlsafe(48))
    browser: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    expires: float = field(default_factory=lambda: time.monotonic() + 300)
    used: bool = False

    def consume(self, state: str, cookie: str) -> None:
        if (
            self.used
            or time.monotonic() >= self.expires
            or not (
                secrets.compare_digest(self.state.encode(), state.encode())
                and secrets.compare_digest(self.browser.encode(), cookie.encode())
            )
        ):
            raise CheckError("Expired or mismatched browser authorization. Restart the check.")
        self.used = True


def verify_code(code: str, attempt: Attempt, client: str, secret: str) -> None:
    def exchange(params: dict[str, str]) -> dict[str, str]:
        return read(
            "https://oauth2.googleapis.com/token",
            {"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
            data=urlencode(dict(params, client_id=client, client_secret=secret)).encode(),
        )

    grant = exchange(
        {
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": attempt.verifier,
            "redirect_uri": LOCAL_CALLBACK,
        }
    )
    if set(grant.get("scope", "").split()) != {READ_SCOPE} or not grant.get("refresh_token"):
        raise CheckError("Grant must contain only gmail.readonly and an offline refresh token.")
    fresh = exchange({"grant_type": "refresh_token", "refresh_token": grant["refresh_token"]})
    if not fresh.get("access_token") or set(fresh.get("scope", READ_SCOPE).split()) != {READ_SCOPE}:
        raise CheckError("Refresh did not confirm the intended grant.")
    profile = read(
        "https://gmail.googleapis.com/gmail/v1/users/me/profile", bearer(fresh["access_token"])
    )
    if not profile.get("emailAddress"):
        raise CheckError("Gmail profile verification failed.")


def run() -> str:
    if setting("GOOGLE_REDIRECT_URI") != LOCAL_CALLBACK:
        raise CheckError("The local verifier requires " + LOCAL_CALLBACK)
    client, secret = setting("GOOGLE_CLIENT_ID"), setting("GOOGLE_CLIENT_SECRET")
    attempt = Attempt()
    start = "/begin/" + secrets.token_urlsafe(32)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(attempt.verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    authorize = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
        {
            "client_id": client,
            "redirect_uri": LOCAL_CALLBACK,
            "response_type": "code",
            "scope": READ_SCOPE,
            "access_type": "offline",
            "prompt": "consent",
            "state": attempt.state,
            "code_challenge_method": "S256",
            "code_challenge": challenge,
        }
    )
    result: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        timeout = 5

        def log_message(self, format: str, *args: object) -> None:
            pass  # OAuth codes and signed start paths are never logged.

        def do_GET(self) -> None:
            nonlocal start
            parts = urlsplit(self.path)
            status, message = 404, "No active authorization."
            redirect = False
            if self.headers.get("Host") != "127.0.0.1:8765":
                status = 400
            elif start and parts.path == start:
                start = ""
                status, redirect = 302, True
            elif parts.path == GMAIL_CALLBACK:
                try:
                    jar = SimpleCookie()
                    jar.load(self.headers.get("Cookie", ""))
                    cookie = jar.get("jody_check")
                    args = parse_qs(parts.query)
                    attempt.consume(args.get("state", [""])[0], cookie.value if cookie else "")
                    if "error" in args or len(args.get("code", [])) != 1:
                        raise CheckError("Consent declined or incomplete.")
                    verify_code(args["code"][0], attempt, client, secret)
                    status, message = 200, "Gmail read-only profile and offline refresh verified."
                except (CheckError, ValueError, TypeError, KeyError):
                    status, message = (
                        400,
                        "Gmail verification failed. Check consent, state and credentials.",
                    )
                if attempt.used:
                    result.append(message)
            self.send_response(status)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            if redirect:
                self.send_header(
                    "Set-Cookie",
                    f"jody_check={attempt.browser}; HttpOnly; SameSite=Lax; Path={GMAIL_CALLBACK}; Max-Age=300",
                )
                self.send_header("Location", authorize)
            self.end_headers()
            if not redirect:
                self.wfile.write(message.encode())

    with HTTPServer(("127.0.0.1", 8765), Handler) as server:
        server.timeout = 1
        print(
            "Open on this Ubuntu machine within five minutes: http://127.0.0.1:8765" + start,
            flush=True,
        )
        while not result and time.monotonic() < attempt.expires:
            server.handle_request()
    if not result or not result[0].endswith("verified."):
        raise CheckError(result[0] if result else "Gmail verification timed out.")
    return result[0]
