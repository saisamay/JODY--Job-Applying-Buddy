"""OAuth and intake share a per-tenant transaction lock. Only the BFF holds a session."""

import os
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Connection, Engine, func, insert, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..career.knowledge import pack, unpack
from ..config import private_preview
from ..routes import Owner, session_digest
from ..security import audit, digest, tenant
from ..tables import gmail_accounts as accounts
from ..tables import gmail_runs as runs
from . import google
from .extract import ADDRESS

router = APIRouter(prefix="/api/v1/gmail")
Session = Annotated[str, Depends(session_digest)]


class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    senders: list[str] = Field(min_length=1, max_length=12)
    label: str = Field(default="", pattern=r"^[a-zA-Z0-9_-]{0,100}$")
    subject: str = Field(default="", pattern=r"^[\w -]{0,100}$")
    days: int = Field(default=3, ge=1, le=7)
    limit: int = Field(default=10, ge=1, le=25)
    providers: list[Literal["ollama", "gemini", "groq"]] = Field(default_factory=list, max_length=3)

    @field_validator("senders")
    @classmethod
    def addresses(cls, values: list[str]) -> list[str]:
        result = sorted({v.strip().lower() for v in values})
        if any(len(v) > 254 or not re.fullmatch(ADDRESS, v) for v in result):
            raise ValueError("Enter exact sender addresses.")
        return result


class GmailStatus(BaseModel):
    state: str
    enabled: bool
    account: str | None = None
    reconnect: bool = False
    last_success: datetime | None = None
    run_id: UUID | None = None
    started: datetime | None = None
    finished: datetime | None = None
    finalizing: bool = False
    result: str | None = None
    counts: dict[str, int] = Field(default_factory=dict)
    retry_at: datetime | None = None
    policy: Policy | None = None


def status(c: Connection) -> GmailStatus:
    row = c.execute(select(accounts)).mappings().one_or_none()
    last = c.execute(select(runs).order_by(runs.c.created_at.desc()).limit(1)).mappings().first()
    state = row["state"] if row else "Disconnected"
    return GmailStatus(
        state=state,
        enabled=not private_preview() and google.configured(),
        account=row["account"] if row else None,
        last_success=row["last_success"] if row else None,
        run_id=last["id"] if last else None,
        started=last["created_at"] if last else None,
        finished=last["finished"] if last else None,
        finalizing=bool(
            last and last["progress"].get("complete") and not last["progress"].get("ids")
        ),
        result=last["status"] if last else None,
        counts=last["counts"] if last else {},
        retry_at=last["due"] if last and last["status"] == "retry" else None,
        reconnect=state in {"Revoked", "Authorization expired", "Authorization required"},
        policy=Policy.model_validate(row["policy"]) if row and row["policy"] else None,
    )


def lock(c: Connection, owner: UUID) -> None:
    if not c.scalar(
        text("SELECT pg_try_advisory_xact_lock(hashtextextended(:k,0))"),
        {"k": "gmail:" + str(owner)},
    ):
        raise HTTPException(409, "A Gmail operation is in progress. Refresh shortly.")


def gate(c: Connection) -> None:
    if private_preview() or not c.scalar(text("SELECT jody_dispatch_open()")):
        raise HTTPException(403, "Gmail access is paused or locked for this preview.")
    if not google.configured():
        raise HTTPException(503, "Configure the Google web client on the API.")


def account(c: Connection, owner: UUID) -> Any:
    c.execute(pg_insert(accounts).values(user_id=owner).on_conflict_do_nothing())
    return c.execute(select(accounts).where(accounts.c.user_id == owner)).mappings().one()


def change(c: Connection, owner: UUID, **values: Any) -> None:
    c.execute(update(accounts).where(accounts.c.user_id == owner).values(**values))


def cancel(c: Connection, owner: UUID) -> None:
    c.execute(
        update(runs)
        .where(runs.c.user_id == owner, runs.c.status.in_(("pending", "retry")))
        .values(status="cancelled", progress={}, finished=func.now())
    )


@router.get("")
def read_status(request: Request, owner: Owner) -> GmailStatus:
    with tenant(request.app.state.db, owner) as c:
        return status(c)


@router.put("/policy")
def set_policy(payload: Policy, request: Request, owner: Owner) -> GmailStatus:
    with tenant(request.app.state.db, owner) as c:
        if private_preview():
            raise HTTPException(403, "The hosted preview is locked.")
        lock(c, owner)
        row = account(c, owner)
        if row["policy"] != payload.model_dump():
            cancel(c, owner)
            change(
                c,
                owner,
                policy=payload.model_dump(),
                history_id=None,
                state="Connected"
                if row["grant"]
                and row["state"] not in {"Authorization expired", "Authorization required"}
                else row["state"],
            )
            audit(c, owner, "gmail.filters_updated")
        return status(c)


class Consent(BaseModel):
    url: str


@router.post("/connect")
def connect(request: Request, owner: Owner, session: Session) -> Consent:
    with tenant(request.app.state.db, owner) as c:
        gate(c)
        lock(c, owner)
        row = account(c, owner)
        state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
        change(
            c,
            owner,
            state_hash=digest(state),
            session_hash=session,
            expires=datetime.now(UTC) + timedelta(minutes=5),
            verifier=pack(request.app.state.secret_key, owner, "gmail:pkce", verifier.encode()),
            state=row["state"] if row["grant"] else "Authorization required",
        )
        audit(c, owner, "gmail.consent_started")
        return Consent(url=google.authorize(state, verifier))


class Callback(BaseModel):
    state: str = Field(min_length=1, max_length=256)
    code: str = Field(default="", max_length=4096)


CLEAR = dict(state_hash=None, session_hash=None, expires=None, verifier=None)


@router.post("/callback")
def finish(payload: Callback, request: Request, owner: Owner, session: Session) -> GmailStatus:
    key = request.app.state.secret_key
    with tenant(request.app.state.db, owner) as c:
        gate(c)
        lock(c, owner)
        row = account(c, owner)
        if (
            row["state_hash"] != digest(payload.state)
            or row["session_hash"] != session
            or row["expires"] <= datetime.now(UTC)
        ):
            raise HTTPException(409, "Expired or mismatched authorization. Reconnect Gmail.")
        change(c, owner, **CLEAR)
        try:
            if not payload.code:
                raise google.Problem("Authorization required")
            grant = google.exchange(
                grant_type="authorization_code",
                code=payload.code,
                code_verifier=unpack(key, owner, "gmail:pkce", row["verifier"]).decode(),
                redirect_uri=google.CALLBACK,
            )
            profile = google.call(google.BASE + "profile", token=grant["access_token"])
            who = str(profile.get("emailAddress", "")).lower()
            if not re.fullmatch(ADDRESS, who) or (row["account"] and who != row["account"]):
                raise google.Problem("Authorization required")
            encrypted = row["grant"]
            if refresh := grant.get("refresh_token"):
                encrypted = pack(key, owner, "gmail:refresh", refresh.encode())
            elif not encrypted:
                raise google.Problem("Authorization required")
            else:
                existing = google.Mailbox(unpack(key, owner, "gmail:refresh", encrypted).decode())
                if str(existing.get("profile").get("emailAddress", "")).lower() != who:
                    raise google.Problem("Authorization required")
            change(c, owner, grant=encrypted, account=who, state="Connected")
            audit(c, owner, "gmail.connected")
        except google.Problem as exc:
            change(c, owner, state=row["state"] if row["grant"] else exc.state)
            audit(c, owner, "gmail.consent_failed")
            failed = True
        else:
            failed = False
        response = status(c)
    if failed:
        raise HTTPException(
            409, "Authorization incomplete. Check the selected account, grant and scope."
        )
    return response


@router.post("/disconnect")
def disconnect(request: Request, owner: Owner) -> GmailStatus:
    with tenant(request.app.state.db, owner) as c:
        lock(c, owner)
        row = account(c, owner)
        revoked = False
        if row["grant"] and not private_preview():
            try:
                google.call(
                    "https://oauth2.googleapis.com/revoke",
                    form={
                        "token": unpack(
                            request.app.state.secret_key, owner, "gmail:refresh", row["grant"]
                        ).decode()
                    },
                )
                revoked = True
            except google.Problem:
                pass
        cancel(c, owner)
        change(
            c,
            owner,
            grant=None,
            account=None,
            history_id=None,
            policy={},
            last_success=None,
            state="Revoked" if revoked else "Disconnected",
            **CLEAR,
        )
        audit(c, owner, "gmail.disconnected", details={"provider_revoked": revoked})
        return status(c)


def enqueue(db: Engine, owner: UUID) -> UUID:
    with tenant(db, owner) as c:
        gate(c)
        lock(c, owner)
        row = account(c, owner)
        if not row["grant"] or row["state"] in {
            "Authorization expired",
            "Authorization required",
            "Revoked",
        }:
            raise HTTPException(409, "Connect or reconnect Gmail first.")
        if not row["policy"]:
            raise HTTPException(422, "Choose authorized senders before synchronizing.")
        active = c.scalar(select(runs.c.id).where(runs.c.status.in_(("pending", "retry"))))
        if active:
            return UUID(str(active))
        last = c.execute(
            select(runs.c.created_at).order_by(runs.c.created_at.desc()).limit(1)
        ).scalar()
        if last and (datetime.now(UTC) - last).total_seconds() < int(
            os.getenv("JODY_GMAIL_MIN_INTERVAL", "30")
        ):
            raise HTTPException(429, "Wait before starting another synchronization.")
        rid = c.execute(
            insert(runs).values(user_id=owner, status="pending").returning(runs.c.id)
        ).scalar_one()
        change(c, owner, state="Synchronizing")
        audit(c, owner, "gmail.sync_requested", rid)
        return UUID(str(rid))
