"""Authenticated source intake, fact review, job comparison and tailoring."""

import base64
import binascii
import os
import re
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import Field, HttpUrl
from sqlalchemy import Connection, func, select

from ..candidate import Draft
from ..candidate_contracts import Model, Short
from ..controls import Key, execute
from ..routes import Owner
from ..security import tenant
from ..tables import career_sources, career_usage, projects, uploaded_resumes
from .contracts import CareerProfile, Comparison, ProposalReceipt
from .knowledge import Json, knowledge, review, snapshot, unpack
from .service import Method, comparison, propose, resume_view
from .web_source import fetch

career = APIRouter(prefix="/api/v1/career")


class Source(Model):
    kind: Literal["pdf", "docx", "tex", "resume_text", "portfolio", "github"]
    label: Short
    content_base64: str = Field(min_length=4, max_length=6990508)
    reference: HttpUrl | None = None


class Decisions(Model):
    revision: int = Field(ge=0)
    decisions: dict[str, Literal["verified", "rejected"]] = Field(min_length=1, max_length=350)


class Preparation(Model):
    method: Method


@career.post("/sources")
def add_source(body: Source, request: Request, owner: Owner, key: Key) -> Json:
    ref = str(body.reference or "")
    if body.reference and (
        body.reference.scheme != "https"
        or body.reference.username
        or body.reference.password
        or body.reference.query
        or body.reference.fragment
    ):
        raise HTTPException(422, "Use a public HTTPS citation without credentials or query.")
    if body.kind == "github" and not re.fullmatch(
        r"https://github\.com/[\w.-]+/[\w.-]+/(?:blob|tree)/[a-fA-F0-9]{40}(?:/[^?#]+)?", ref
    ):
        raise HTTPException(422, "Cite a commit-pinned repository snapshot.")
    if body.kind == "portfolio" and not ref:
        raise HTTPException(422, "Cite the portfolio page for this snapshot.")
    try:
        data = base64.b64decode(body.content_base64, validate=True)
    except (ValueError, binascii.Error):
        raise HTTPException(422, "Invalid source encoding.") from None
    return execute(
        request,
        owner,
        key,
        "career.import",
        body.model_dump(mode="json"),
        lambda c: snapshot(
            c, owner, request.app.state.secret_key, body.kind, body.label, ref, data
        ),
    )


@career.post("/sources/existing/{kind}/{record_id}")
def existing(
    kind: Literal["resume", "github"], record_id: UUID, request: Request, owner: Owner, key: Key
) -> Json:
    def change(c: Connection) -> Json:
        table = uploaded_resumes if kind == "resume" else projects
        row = c.execute(select(table).where(table.c.id == record_id)).mappings().first()
        if row is None:
            raise HTTPException(404, "Source not found.")
        secret = request.app.state.secret_key
        if kind == "resume":
            return snapshot(
                c,
                owner,
                secret,
                "pdf",
                row["label"],
                f"candidate-resume:{record_id}",
                unpack(secret, owner, f"candidate-resume:{record_id}", row["ciphertext"]),
            )
        if not re.fullmatch(r"[a-fA-F0-9]{40}", row["commit_sha"]):
            raise HTTPException(422, "Project requires a full commit reference.")
        data = "\n".join(
            str(row[k])
            for k in ("description", "readme_summary", "tech_stack", "verified_metrics")
            if row[k]
        )
        return snapshot(
            c,
            owner,
            secret,
            "github",
            "Repository evidence",
            f"{row['repo_url']}/tree/{row['commit_sha']}",
            data.encode(),
        )

    return execute(
        request, owner, key, "career.import-existing", {"kind": kind, "id": str(record_id)}, change
    )


@career.post("/sources/profile")
def profile_import(request: Request, owner: Owner, key: Key) -> Json:
    def change(c: Connection) -> Json:
        secret = request.app.state.secret_key
        draft = Draft(c, owner, secret)
        lines = []
        for field, heading in [
            ("education", "Education"),
            ("work_experience", "Employment"),
            ("projects", "Projects"),
            ("skills", "Skills"),
            ("work_authorization", "Eligibility"),
        ]:
            if draft.sources.get(field, {}).get("status") == "verified" and draft.values.get(field):
                lines.append(heading)
                value = draft.values[field]
                for item in value if isinstance(value, list) else [value]:
                    lines.append(
                        " — ".join(str(v) for v in item.values() if v)
                        if isinstance(item, dict)
                        else str(item)
                    )
        if not lines:
            raise HTTPException(409, "Verify a profile qualification before importing.")
        return snapshot(
            c,
            owner,
            secret,
            "profile",
            "Reviewed profile",
            f"candidate-profile:{draft.revision}",
            "\n".join(lines).encode(),
        )

    return execute(request, owner, key, "career.import-profile", {}, change)


@career.get("/sources/{source_id}/original")
def original(source_id: UUID, request: Request, owner: Owner) -> Response:
    with tenant(request.app.state.db, owner) as c:
        blob = c.scalar(select(career_sources.c.original).where(career_sources.c.id == source_id))
        if blob is None:
            raise HTTPException(404, "Source not found.")
        return Response(
            unpack(request.app.state.secret_key, owner, f"original:{source_id}", blob),
            media_type="application/octet-stream",
            headers={"Content-Disposition": "attachment", "X-Content-Type-Options": "nosniff"},
        )


@career.get("/profile", response_model=CareerProfile)
def profile(
    request: Request, owner: Owner, revision: Annotated[int | None, Query(ge=0)] = None
) -> Json:
    with tenant(request.app.state.db, owner) as c:
        return knowledge(c, owner, request.app.state.secret_key, revision)


@career.post("/profile/review")
def decide(body: Decisions, request: Request, owner: Owner, key: Key) -> Json:
    return execute(
        request,
        owner,
        key,
        "career.review",
        body.model_dump(),
        lambda c: review(c, owner, request.app.state.secret_key, body.revision, body.decisions),
    )


@career.post("/jobs/{job_id}/compare", response_model=Comparison)
def compare(job_id: UUID, request: Request, owner: Owner) -> Json:
    return comparison(request, None, owner, job_id)


@career.post("/jobs/{job_id}/proposal", response_model=ProposalReceipt)
def proposal(job_id: UUID, body: Preparation, request: Request, owner: Owner, key: Key) -> Json:
    return execute(
        request,
        owner,
        key,
        "career.proposal",
        {"job": str(job_id), **body.model_dump()},
        lambda c: propose(request, c, owner, job_id, body.method),
    )


@career.get("/versions/{version_id}")
def version(version_id: UUID, request: Request, owner: Owner) -> Json:
    with tenant(request.app.state.db, owner) as c:
        return resume_view(c, version_id)


class RepositoryDocument(Model):
    repository: str = Field(pattern=r"^[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+$", max_length=140)
    commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    path: str = Field(default="README.md", pattern=r"^[a-zA-Z0-9_. /-]+$", max_length=256)


@career.post("/sources/repository")
def import_repository(body: RepositoryDocument, request: Request, owner: Owner, key: Key) -> Json:
    from urllib.parse import quote

    if any(part in {".", "..", ""} for part in (body.repository + "/" + body.path).split("/")):
        raise HTTPException(422, "Supply a repository document path.")
    path = quote(body.path, safe="/")
    ref = f"https://github.com/{body.repository}/blob/{body.commit}/{path}"

    def change(c: Connection) -> Json:
        data = fetch(
            f"https://raw.githubusercontent.com/{body.repository}/{body.commit}/{path}", html=False
        )
        return snapshot(
            c, owner, request.app.state.secret_key, "github", body.repository, ref, data
        )

    return execute(request, owner, key, "career.import-repository", body.model_dump(), change)


@career.post("/sources/portfolio-page")
def import_portfolio(request: Request, owner: Owner, key: Key) -> Json:
    def change(c: Connection) -> Json:
        secret = request.app.state.secret_key
        draft = Draft(c, owner, secret)
        url = draft.values.get("portfolio")
        if not url:
            raise HTTPException(409, "Save a portfolio URL in the candidate profile first.")
        return snapshot(
            c, owner, secret, "portfolio_html", "Portfolio page", url, fetch(url, html=True)
        )

    return execute(request, owner, key, "career.import-portfolio", {}, change)


@career.get("/usage")
def usage(request: Request, owner: Owner) -> Json:
    with tenant(request.app.state.db, owner) as c:
        row = c.execute(
            select(
                func.count(),
                func.coalesce(func.sum(career_usage.c.tokens), 0),
                func.coalesce(func.sum(career_usage.c.cost_microusd), 0),
            )
            .select_from(career_usage)
            .where(career_usage.c.created_at >= func.date_trunc("day", func.now()))
        ).one()
        return {
            "attempts_today": row[0],
            "tokens_today": row[1],
            "cost_microusd_today": row[2],
            "daily_call_limit": int(os.getenv("JODY_AI_DAILY_CALLS", "100")),
            "spending_limit_microusd": 0,
        }
