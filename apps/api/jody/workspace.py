"""Owner-scoped read model for the dashboard. Lists show the latest 100 records."""

import re
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, StringConstraints, ValidationInfo, field_validator
from sqlalchemy import Connection, Select, Table, delete, func, select, true, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .config import private_preview
from .controls import Key, Result, execute
from .gmail.service import GmailStatus
from .gmail.service import status as gmail_status
from .integration_setup import IntegrationCard, cards
from .routes import Owner
from .security import tenant
from .tables import (
    applications,
    approvals,
    artifacts,
    audits,
    blocks,
    companies,
    connections,
    gmail_evidence,
    jobs,
    mail,
    outreach,
    projects,
    settings,
    sources,
    trust,
)


class Entry(BaseModel):
    id: UUID
    title: str
    detail: str | None = None
    status: str | None = None
    created_at: datetime


class JobView(BaseModel):
    gmail_platform: str | None
    employment_type: str | None
    gmail_review: bool | None
    id: UUID
    description: str
    role: str | None
    company: str | None
    source_url: str | None
    location: str | None
    status: str
    trust_score: int | None
    ats_score: int | None
    created_at: datetime


class Workspace(BaseModel):
    gmail: GmailStatus
    jobs: list[JobView]
    applications: list[Entry]
    approvals: list[Entry]
    outreach: list[Entry]
    mail: list[Entry]
    audit: list[Entry]
    projects: list[Entry]
    allowlist: list[Entry]
    blocklist: list[Entry]
    integrations: list[str]
    integration_cards: list[IntegrationCard]
    total_jobs: int
    total_applications: int
    pending_approvals: int
    trust_threshold: int
    ats_target: int


workspace = APIRouter(prefix="/api/v1")


def recent(conn: Connection, query: Select[Any], table: Table) -> list[Entry]:
    rows = conn.execute(
        query.order_by(table.c.created_at.desc(), table.c.id.desc()).limit(100)
    ).mappings()
    return [Entry.model_validate(row) for row in rows]


@workspace.get("/workspace")
def overview(request: Request, owner: Owner) -> Workspace:
    with tenant(request.app.state.db, owner) as conn:
        score = (
            select(trust.c.score)
            .where(trust.c.job_id == jobs.c.id)
            .order_by(trust.c.created_at.desc(), trust.c.id.desc())
            .limit(1)
            .scalar_subquery()
        )
        ats = (
            select(artifacts.c.ats_score)
            .where(artifacts.c.job_id == jobs.c.id, artifacts.c.ats_score.is_not(None))
            .order_by(artifacts.c.created_at.desc(), artifacts.c.id.desc())
            .limit(1)
            .scalar_subquery()
        )
        evidence = (
            select(gmail_evidence)
            .where(gmail_evidence.c.job_id == jobs.c.id)
            .order_by(gmail_evidence.c.created_at.desc())
            .limit(1)
            .lateral()
        )
        query = (
            select(
                jobs.c.id,
                jobs.c.description,
                jobs.c.role,
                evidence.c.platform.label("gmail_platform"),
                evidence.c.needs_review.label("gmail_review"),
                evidence.c.facts["employment_type"].astext.label("employment_type"),
                companies.c.name.label("company"),
                jobs.c.source_url,
                jobs.c.location,
                jobs.c.status,
                jobs.c.created_at,
                score.label("trust_score"),
                ats.label("ats_score"),
            )
            .select_from(
                jobs.outerjoin(companies, jobs.c.company_id == companies.c.id).outerjoin(
                    evidence, true()
                )
            )
            .order_by(jobs.c.created_at.desc(), jobs.c.id.desc())
            .limit(100)
        )
        thresholds = conn.execute(
            select(settings.c.min_trust_score_auto_apply, settings.c.min_ats_score_threshold)
        ).one()
        stored = list(conn.scalars(select(connections.c.provider).order_by(connections.c.provider)))
        return Workspace(
            gmail=gmail_status(conn),
            jobs=[JobView.model_validate(r) for r in conn.execute(query).mappings()],
            applications=recent(
                conn,
                select(
                    applications.c.id,
                    func.coalesce(
                        jobs.c.role, func.left(func.split_part(jobs.c.description, "\n", 1), 120)
                    ).label("title"),
                    applications.c.method.label("detail"),
                    applications.c.status,
                    applications.c.created_at,
                ).select_from(applications.join(jobs, applications.c.job_id == jobs.c.id)),
                applications,
            ),
            approvals=recent(
                conn,
                select(
                    approvals.c.id,
                    approvals.c.action.label("title"),
                    approvals.c.destination.label("detail"),
                    approvals.c.status,
                    approvals.c.created_at,
                ),
                approvals,
            ),
            outreach=recent(
                conn,
                select(
                    outreach.c.id,
                    outreach.c.recipient.label("title"),
                    outreach.c.status,
                    outreach.c.created_at,
                ),
                outreach,
            ),
            mail=recent(
                conn,
                select(mail.c.id, mail.c.classification.label("title"), mail.c.created_at),
                mail,
            ),
            audit=recent(
                conn,
                select(audits.c.id, audits.c.action.label("title"), audits.c.created_at),
                audits,
            ),
            projects=recent(
                conn,
                select(
                    projects.c.id,
                    projects.c.repo_url.label("title"),
                    projects.c.description.label("detail"),
                    projects.c.commit_sha.label("status"),
                    projects.c.created_at,
                ),
                projects,
            ),
            allowlist=recent(
                conn,
                select(
                    sources.c.id,
                    sources.c.identifier.label("title"),
                    sources.c.kind.label("status"),
                    sources.c.created_at,
                ).where(sources.c.is_whitelisted),
                sources,
            ),
            blocklist=recent(
                conn,
                select(
                    blocks.c.id,
                    blocks.c.value.label("title"),
                    blocks.c.reason.label("detail"),
                    blocks.c.kind.label("status"),
                    blocks.c.created_at,
                ),
                blocks,
            ),
            integrations=stored,
            integration_cards=cards(stored, private_preview()),
            total_jobs=conn.scalar(select(func.count()).select_from(jobs)) or 0,
            total_applications=conn.scalar(select(func.count()).select_from(applications)) or 0,
            pending_approvals=conn.scalar(
                select(func.count())
                .select_from(approvals)
                .where(approvals.c.status == "pending", approvals.c.expires_at > func.now())
            )
            or 0,
            trust_threshold=thresholds[0],
            ats_target=thresholds[1],
        )


class SourcePolicy(BaseModel):
    kind: Literal["whatsapp", "linkedin_feed", "linkedin_post", "manual"]
    identifier: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)
    ]
    enabled: bool


class BlockPolicy(BaseModel):
    kind: Literal["company", "domain", "email"]
    value: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=250)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
    enabled: bool

    @field_validator("value")
    @classmethod
    def normalize_value(cls, value: str, info: ValidationInfo) -> str:
        value = value.casefold()
        domain_pattern = r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}"
        if info.data.get("kind") == "domain" and not re.fullmatch(domain_pattern, value):
            raise ValueError("Enter a DNS hostname.")
        if info.data.get("kind") == "email" and not re.fullmatch(
            r"[^\s@]+@" + domain_pattern, value
        ):
            raise ValueError("Enter an email address.")
        return value


@workspace.put("/workspace/source-policy")
def source_policy(body: SourcePolicy, request: Request, owner: Owner, key: Key) -> Result:
    def change(c: Connection) -> Result:
        if body.enabled:
            c.execute(
                pg_insert(sources)
                .values(
                    user_id=owner, kind=body.kind, identifier=body.identifier, is_whitelisted=True
                )
                .on_conflict_do_update(
                    index_elements=["user_id", "kind", "identifier"], set_={"is_whitelisted": True}
                )
            )
        else:
            c.execute(
                update(sources)
                .where(sources.c.kind == body.kind, sources.c.identifier == body.identifier)
                .values(is_whitelisted=False)
            )
        return {"enabled": body.enabled}

    return execute(request, owner, key, "source.allowlist", body.model_dump(), change)


@workspace.put("/workspace/block-policy")
def block_policy(body: BlockPolicy, request: Request, owner: Owner, key: Key) -> Result:
    def change(c: Connection) -> Result:
        if body.enabled:
            c.execute(
                pg_insert(blocks)
                .values(user_id=owner, kind=body.kind, value=body.value, reason=body.reason)
                .on_conflict_do_update(
                    index_elements=["user_id", "kind", "value"], set_={"reason": body.reason}
                )
            )
        else:
            c.execute(
                delete(blocks).where(blocks.c.kind == body.kind, blocks.c.value == body.value)
            )
        return {"enabled": body.enabled}

    return execute(request, owner, key, "source.blocklist", body.model_dump(), change)
