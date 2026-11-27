import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import delete, func, insert, select, text

from .contracts import Error, Job, Login, ManualJob, SessionToken
from .job_pipeline import ingest
from .security import PRIVATE_OWNER, audit, digest, tenant
from .tables import jobs, sessions, users

router = APIRouter(prefix="/api/v1", responses={401: {"model": Error}, 422: {"model": Error}})
bearer = HTTPBearer(auto_error=False)
SESSION_SECONDS = 8 * 3600


def session_digest(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> str:
    if credentials is None:
        raise HTTPException(401, "Sign in to continue.")
    return digest(credentials.credentials)


def current_owner(request: Request, token: Annotated[str, Depends(session_digest)]) -> UUID:
    with request.app.state.db.connect() as conn:
        owner = conn.scalar(text("SELECT jody_session_owner(:digest)"), {"digest": token})
    if owner is None:
        raise HTTPException(401, "Your session has expired. Sign in again.")
    return UUID(str(owner))


Owner = Annotated[UUID, Depends(current_owner)]


@router.post("/session")
def login(payload: Login, request: Request) -> SessionToken:
    if not secrets.compare_digest(digest(payload.key), digest(request.app.state.owner_key)):
        raise HTTPException(401, "Invalid owner key.")
    token = secrets.token_urlsafe(32)
    with tenant(request.app.state.db, PRIVATE_OWNER) as conn:
        if not conn.scalar(select(users.c.is_active).where(users.c.id == PRIVATE_OWNER)):
            raise HTTPException(401, "Invalid owner key.")
        audit(conn, PRIVATE_OWNER, "session.login")
        conn.execute(delete(sessions).where(sessions.c.expires_at <= func.now()))
        conn.execute(
            insert(sessions).values(
                digest=digest(token),
                user_id=PRIVATE_OWNER,
                expires_at=datetime.now(UTC) + timedelta(seconds=SESSION_SECONDS),
            )
        )
    return SessionToken(token=token, max_age=SESSION_SECONDS)


@router.get("/session")
def identity(owner: Owner) -> dict[str, UUID]:
    return {"user_id": owner}


@router.delete("/session", status_code=204)
def logout(
    request: Request, owner: Owner, token: Annotated[str, Depends(session_digest)]
) -> Response:
    with tenant(request.app.state.db, owner) as conn:
        audit(conn, owner, "session.logout")
        conn.execute(delete(sessions).where(sessions.c.digest == token))
    return Response(status_code=204)


@router.get("/jobs")
def list_jobs(request: Request, owner: Owner) -> list[Job]:
    with tenant(request.app.state.db, owner) as conn:
        rows = conn.execute(
            select(jobs)
            .where(jobs.c.user_id == owner)
            .order_by(jobs.c.created_at.desc(), jobs.c.id.desc())
            .limit(100)
        ).mappings()
        return [Job.model_validate(row) for row in rows]


@router.get("/jobs/{job_id}", responses={404: {"model": Error}})
def get_job(job_id: UUID, request: Request, owner: Owner) -> Job:
    with tenant(request.app.state.db, owner) as conn:
        row = (
            conn.execute(select(jobs).where(jobs.c.id == job_id, jobs.c.user_id == owner))
            .mappings()
            .one_or_none()
        )
    if row is None:
        raise HTTPException(404, "Job not found.")
    return Job.model_validate(row)


@router.post("/jobs/manual")
def intake(payload: ManualJob, request: Request, owner: Owner) -> Job:
    url = str(payload.source_url) if payload.source_url else None
    fingerprint = digest(json.dumps([" ".join(payload.description.split()), url]))
    with tenant(request.app.state.db, owner) as conn:
        jid, _ = ingest(
            conn,
            owner,
            request.app.state.secret_key,
            "manual",
            "manual",
            payload.description,
            url,
            {},
            fingerprint,
            fingerprint,
        )
        row = conn.execute(select(jobs).where(jobs.c.id == jid)).mappings().one()
        return Job.model_validate(row)
