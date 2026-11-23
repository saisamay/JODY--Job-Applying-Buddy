"""Short-lived capabilities bound to the issuing owner's still-active session."""

import base64
import hashlib
import hmac
import json
import time
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select, text

from ..candidate_contracts import Model
from ..controls import Key, execute
from ..routes import Owner, bearer, session_digest
from ..security import audit, tenant
from ..tables import applications, approvals, career_proposals, resumes
from .knowledge import Json, knowledge, verified
from .routes import Preparation
from .service import comparison, propose, resume_view

bridge = APIRouter(prefix="/api/v1/career/mcp")
Scope = Literal["read", "proposal"]


class Grant(Model):
    scope: Scope


def signature(key: bytes, body: str) -> str:
    return hmac.new(key, b"jody:mcp:v1:" + body.encode(), hashlib.sha256).hexdigest()


@bridge.post("/grant")
def grant(
    body: Grant, request: Request, owner: Owner, session: Annotated[str, Depends(session_digest)]
) -> Json:
    exp = int(time.time()) + 900
    claim = base64.urlsafe_b64encode(json.dumps([session, body.scope, exp]).encode()).decode()
    with tenant(request.app.state.db, owner) as c:
        audit(c, owner, "career.mcp.grant", details={"scope": body.scope})
    return {
        "token": claim + "." + signature(request.app.state.secret_key, claim),
        "expires_at": exp,
    }


def principal(
    request: Request, creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
) -> tuple[UUID, Scope]:
    try:
        claim, sig = (creds.credentials if creds else "").split(".")
        if len(claim) > 512 or not hmac.compare_digest(
            signature(request.app.state.secret_key, claim), sig
        ):
            raise ValueError
        session, scope, exp = json.loads(base64.urlsafe_b64decode(claim))
        if exp <= time.time() or scope not in {"read", "proposal"}:
            raise ValueError
        with request.app.state.db.connect() as c:
            owner = c.scalar(text("SELECT jody_session_owner(:digest)"), {"digest": session})
        if not owner:
            raise ValueError
    except (ValueError, TypeError, UnicodeError):
        raise HTTPException(401, "Valid MCP capability required.") from None
    return UUID(str(owner)), scope


Principal = Annotated[tuple[UUID, Scope], Depends(principal)]
View = Literal[
    "profile", "facts", "github", "job", "comparison", "versions", "version", "approval", "history"
]


@bridge.get("/read/{view}")
def read(view: View, request: Request, identity: Principal, record_id: UUID | None = None) -> Json:
    owner, scope = identity
    if scope != "read":
        raise HTTPException(403, "Read capability required.")
    with tenant(request.app.state.db, owner) as c:
        if view in {"profile", "facts", "github"}:
            state = knowledge(c, owner, request.app.state.secret_key)
            items = verified(state)
            if view == "github":
                ids = {s["id"] for s in state["sources"] if s["kind"] == "github"}
                items = [f for f in items if f["source_id"] in ids]
            if view == "profile":
                return {
                    "revision": state["revision"],
                    "sections": {
                        category: [
                            {"fact_id": f["id"], "text": f["quote"]}
                            for f in items
                            if f["category"] == category
                        ]
                        for category in sorted({f["category"] for f in items})
                    },
                    "verified_count": len(items),
                }
            return {"facts": items}
        if view == "history":
            rows = c.execute(
                select(
                    applications.c.id,
                    applications.c.job_id,
                    applications.c.status,
                    applications.c.method,
                )
                .order_by(applications.c.created_at.desc())
                .limit(100)
            )
            return {"applications": [dict(r._mapping) for r in rows]}
        if view == "versions":
            rows = c.execute(
                select(resumes.c.id, resumes.c.job_id, career_proposals.c.application_id)
                .outerjoin(career_proposals, career_proposals.c.resume_version_id == resumes.c.id)
                .order_by(resumes.c.created_at.desc())
                .limit(100)
            )
            return {"versions": [dict(r._mapping) for r in rows]}
        if record_id is None:
            raise HTTPException(422, "Supply the resource ID.")
        if view in {"job", "comparison"}:
            return comparison(
                request, c, owner, record_id, cached_only=True, normalized_only=view == "job"
            )
        if view == "version":
            return resume_view(c, record_id)
        row = (
            c.execute(
                select(approvals.c.id, approvals.c.status, approvals.c.expires_at).where(
                    approvals.c.id == record_id
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise HTTPException(404, "Approval not found.")
        return dict(row)


@bridge.post("/proposal/{job_id}")
def save(job_id: UUID, body: Preparation, request: Request, identity: Principal, key: Key) -> Json:
    owner, scope = identity
    if scope != "proposal":
        raise HTTPException(403, "Proposal capability required.")
    return execute(
        request,
        owner,
        key,
        "career.mcp.proposal",
        {"job": str(job_id), **body.model_dump()},
        lambda c: propose(request, c, owner, job_id, body.method),
    )
