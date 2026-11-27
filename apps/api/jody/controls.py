"""Authenticated commands. Changes, replay receipts and audit records commit together."""

import hashlib
import hmac
import json
from collections.abc import Callable
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import Connection, delete, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .config import private_preview
from .routes import Owner
from .security import PRIVATE_OWNER, audit, seal, tenant
from .tables import audits, commands, connections, control, profiles, settings, tasks, users

controls = APIRouter(prefix="/api/v1")
Key = Annotated[UUID, Header(alias="Idempotency-Key")]
Provider = Literal["github", "gmail", "telegram", "resume_git", "gemini", "groq", "openrouter"]
Result = dict[str, Any]


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Pause(Command):
    paused: bool


class GateState(Pause):
    locked: bool


class Preferences(Command):
    min_trust_score_auto_apply: int | None = Field(default=None, ge=0, le=100)
    min_ats_score_threshold: int | None = Field(default=None, ge=0, le=100)
    max_daily_linkedin_connects: int | None = Field(default=None, ge=0, le=1000)
    max_daily_linkedin_dms: int | None = Field(default=None, ge=0, le=1000)
    outbound_enabled: bool | None = None
    auto_archive_rejections: bool | None = None
    auto_trash_scams: bool | None = None


class Secret(Command):
    credential: SecretStr = Field(min_length=1, max_length=16384)


def execute(
    request: Request,
    user: UUID,
    key: UUID,
    action: str,
    inputs: Result,
    change: Callable[[Connection], Result],
) -> Result:
    material = json.dumps([action, inputs], sort_keys=True, separators=(",", ":")).encode()
    fingerprint = hmac.new(request.app.state.secret_key, material, hashlib.sha256).hexdigest()
    with tenant(request.app.state.db, user) as conn:
        claimed = conn.scalar(
            pg_insert(commands)
            .values(user_id=user, key=key, request_digest=fingerprint)
            .on_conflict_do_nothing()
            .returning(commands.c.key)
        )
        match = (commands.c.user_id == user) & (commands.c.key == key)
        if claimed is None:
            prior = conn.execute(select(commands).where(match)).mappings().one()
            if not hmac.compare_digest(prior["request_digest"], fingerprint):
                raise HTTPException(409, "Idempotency key already used for another command.")
            return dict(prior["response"])
        result = change(conn)
        conn.execute(update(commands).where(match).values(response=result))
        audit(conn, user, action, key, result)
        return result


@controls.get("/profile")
def profile(request: Request, owner: Owner) -> Result:
    with tenant(request.app.state.db, owner) as conn:
        identity = (
            conn.execute(select(users.c.id, users.c.email, users.c.full_name)).mappings().one()
        )
        candidate = (
            conn.execute(
                select(
                    profiles.c.user_id,
                    profiles.c.github_username,
                    profiles.c.linkedin_profile_url,
                    profiles.c.portfolio_url,
                    profiles.c.telegram_chat_id,
                    profiles.c.resume_git_repo_url,
                    profiles.c.resume_master_branch,
                    profiles.c.master_latex_template,
                    profiles.c.profile_vault_json,
                    profiles.c.updated_at,
                )
            )
            .mappings()
            .one()
        )
        prefs = dict(conn.execute(select(settings)).mappings().one())
        prefs.pop("user_id")
        prefs["is_system_paused"] = conn.scalar(select(control.c.is_system_paused))
        return {
            **identity,
            **candidate,
            "settings_json": prefs,
            "integrations": list(
                conn.scalars(select(connections.c.provider).order_by(connections.c.provider))
            ),
        }


@controls.get("/system/kill-switch")
def gate(request: Request, owner: Owner) -> GateState:
    with tenant(request.app.state.db, owner) as conn:
        return GateState(
            paused=private_preview()
            or conn.execute(select(control.c.is_system_paused)).scalar_one(),
            locked=private_preview(),
        )


@controls.post("/system/kill-switch", response_model=Pause)
def kill_switch(payload: Pause, request: Request, owner: Owner, key: Key) -> Result:
    if owner != PRIVATE_OWNER:
        raise HTTPException(403, "Only the private operator can change the global pause.")

    if private_preview() and not payload.paused:
        raise HTTPException(403, "External automation is locked for this preview.")

    def change(conn: Connection) -> Result:
        conn.execute(
            update(control)
            .where(control.c.singleton.is_(True))
            .values(is_system_paused=payload.paused)
        )
        return {"paused": payload.paused}

    return execute(
        request,
        owner,
        key,
        "system.pause" if payload.paused else "system.resume",
        payload.model_dump(),
        change,
    )


@controls.patch("/profile/settings")
def preferences(payload: Preferences, request: Request, owner: Owner, key: Key) -> Result:
    values = payload.model_dump(exclude_unset=True)
    if private_preview() and any(
        values.get(k) for k in ("outbound_enabled", "auto_trash_scams", "auto_archive_rejections")
    ):
        raise HTTPException(403, "External automation is locked for this preview.")
    if not values or None in values.values():
        raise HTTPException(422, "Supply one or more valid settings.")

    def change(conn: Connection) -> Result:
        if {"outbound_enabled", "auto_trash_scams", "auto_archive_rejections"} & values.keys():
            steps = dict(
                conn.execute(
                    select(profiles.c.onboarding_steps)
                    .where(profiles.c.user_id == owner)
                    .with_for_update()
                ).scalar_one()
            )
            steps.pop("automation_permissions", None)
            steps.pop("final_confirmation", None)
            conn.execute(
                update(profiles)
                .where(profiles.c.user_id == owner)
                .values(
                    onboarding_steps=steps,
                    candidate_revision=profiles.c.candidate_revision + 1,
                    updated_at=func.now(),
                )
            )
        conn.execute(update(settings).where(settings.c.user_id == owner).values(**values))
        if "min_trust_score_auto_apply" in values:
            from .job_pipeline import invalidate

            invalidate(conn, owner, request.app.state.secret_key)
        return values

    return execute(request, owner, key, "settings.update", values, change)


@controls.put("/integrations/{provider}")
def store_secret(
    provider: Provider, payload: Secret, request: Request, owner: Owner, key: Key
) -> Result:
    if private_preview():
        raise HTTPException(403, "Integration connections are disabled for this preview.")
    if provider == "telegram":
        raise HTTPException(422, "Configure the shared bot token on the backend.")
    credential = payload.credential.get_secret_value()

    def change(conn: Connection) -> Result:
        iv, ciphertext = seal(request.app.state.secret_key, owner, provider, credential)
        encrypted = {"credentials_iv": iv, "encrypted_credentials": ciphertext, "key_version": 1}
        conn.execute(
            pg_insert(connections)
            .values(user_id=owner, provider=provider, **encrypted)
            .on_conflict_do_update(index_elements=["user_id", "provider"], set_=encrypted)
        )
        return {"provider": provider, "stored": True}

    return execute(
        request,
        owner,
        key,
        "integration.store",
        {"provider": provider, "credential": credential},
        change,
    )


@controls.delete("/integrations/{provider}")
def revoke(provider: Provider, request: Request, owner: Owner, key: Key) -> Result:
    def change(conn: Connection) -> Result:
        conn.execute(
            delete(connections).where(
                connections.c.user_id == owner, connections.c.provider == provider
            )
        )
        return {"provider": provider, "stored": False}

    return execute(request, owner, key, "integration.remove", {"provider": provider}, change)


@controls.post("/tasks/probe", status_code=202)
def enqueue_probe(request: Request, owner: Owner, key: Key) -> Result:
    if private_preview():
        raise HTTPException(403, "Background tasks are disabled for this preview.")

    def change(conn: Connection) -> Result:
        task = conn.scalar(
            insert(tasks).values(user_id=owner, kind="local_probe").returning(tasks.c.id)
        )
        return {"id": str(task), "status": "pending"}

    return execute(request, owner, key, "task.enqueue", {}, change)


@controls.get("/tasks/{task_id}")
def task_status(task_id: UUID, request: Request, owner: Owner) -> Result:
    with tenant(request.app.state.db, owner) as conn:
        row = (
            conn.execute(
                select(tasks.c.id, tasks.c.kind, tasks.c.status).where(tasks.c.id == task_id)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise HTTPException(404, "Task not found.")
        return dict(row)


@controls.get("/audit")
def audit_log(request: Request, owner: Owner) -> list[Result]:
    with tenant(request.app.state.db, owner) as conn:
        rows = conn.execute(
            select(audits).order_by(audits.c.created_at.desc(), audits.c.id.desc()).limit(100)
        ).mappings()
        return [dict(row) for row in rows]
