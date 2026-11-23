import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import delete, func, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .contracts import Error, Job, Login, ManualJob, SessionToken
from .tables import events, jobs, observations, owners, sessions

router = APIRouter(prefix="/api/v1", responses={401: {"model": Error}, 422: {"model": Error}})
bearer = HTTPBearer(auto_error=False)
PRIVATE_OWNER = UUID("00000000-0000-4000-8000-000000000001")
SESSION_SECONDS = 8 * 3600


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def session_digest(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> str:
    if credentials is None:
        raise HTTPException(401, "Sign in to continue.")
    return digest(credentials.credentials)


def current_owner(request: Request, token: Annotated[str, Depends(session_digest)]) -> UUID:
    with request.app.state.db.connect() as conn:
        owner = conn.scalar(
            select(sessions.c.owner_id).where(
                sessions.c.digest == token, sessions.c.expires_at > func.now()
            )
        )
    if owner is None:
        raise HTTPException(401, "Your session has expired. Sign in again.")
    return UUID(str(owner))


Owner = Annotated[UUID, Depends(current_owner)]


@router.post("/session")
def login(payload: Login, request: Request) -> SessionToken:
    if not secrets.compare_digest(digest(payload.key), digest(request.app.state.owner_key)):
        raise HTTPException(401, "Invalid owner key.")
    token = secrets.token_urlsafe(32)
    with request.app.state.db.begin() as conn:
        conn.execute(pg_insert(owners).values(id=PRIVATE_OWNER).on_conflict_do_nothing())
        conn.execute(delete(sessions).where(sessions.c.expires_at <= func.now()))
        conn.execute(
            insert(sessions).values(
                digest=digest(token),
                owner_id=PRIVATE_OWNER,
                expires_at=datetime.now(UTC) + timedelta(seconds=SESSION_SECONDS),
            )
        )
    return SessionToken(token=token, max_age=SESSION_SECONDS)


@router.delete("/session", status_code=204)
def logout(request: Request, token: Annotated[str, Depends(session_digest)]) -> Response:
    with request.app.state.db.begin() as conn:
        conn.execute(delete(sessions).where(sessions.c.digest == token))
    return Response(status_code=204)


@router.get("/jobs")
def list_jobs(request: Request, owner: Owner) -> list[Job]:
    with request.app.state.db.connect() as conn:
        rows = conn.execute(
            select(jobs)
            .where(jobs.c.owner_id == owner)
            .order_by(jobs.c.created_at.desc(), jobs.c.id.desc())
            .limit(100)
        ).mappings()
        return [Job.model_validate(row) for row in rows]


@router.get("/jobs/{job_id}", responses={404: {"model": Error}})
def get_job(job_id: UUID, request: Request, owner: Owner) -> Job:
    with request.app.state.db.connect() as conn:
        row = (
            conn.execute(select(jobs).where(jobs.c.id == job_id, jobs.c.owner_id == owner))
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
    with request.app.state.db.begin() as conn:
        row = (
            conn.execute(
                pg_insert(jobs)
                .values(
                    id=uuid4(),
                    owner_id=owner,
                    fingerprint=fingerprint,
                    description=payload.description,
                    source_url=url,
                )
                .on_conflict_do_nothing(index_elements=["owner_id", "fingerprint"])
                .returning(*jobs.c)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            row = (
                conn.execute(
                    select(jobs).where(jobs.c.owner_id == owner, jobs.c.fingerprint == fingerprint)
                )
                .mappings()
                .one()
            )
        else:
            reference = {"owner_id": owner, "job_id": row["id"]}
            conn.execute(insert(observations).values(id=uuid4(), source="manual", **reference))
            conn.execute(insert(events).values(id=uuid4(), kind="discovered", **reference))
        return Job.model_validate(row)
