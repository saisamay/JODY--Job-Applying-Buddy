from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    id: str
    source_id: UUID
    line: int
    category: str
    quote: str
    key: str
    dates: list[str]
    reference: str
    state: Literal["pending", "verified", "rejected"]


class SourceInfo(BaseModel):
    id: UUID
    label: str
    reference: str
    kind: str


class CareerProfile(BaseModel):
    revision: int
    sources: list[SourceInfo]
    facts: dict[str, Evidence]
    conflicts: list[list[str]]
    decisions: dict[str, Literal["verified", "rejected"]]


class Clause(BaseModel):
    text: str
    priority: Literal["required", "preferred", "hard", "responsibility"]
    facet: str


class JobAnalysis(BaseModel):
    title: str | None
    functional_terms: list[str]
    requires_owner_review: bool
    requirements: list[Clause]


class Alignment(Clause):
    evidence_id: str | None


class Comparison(BaseModel):
    job_id: UUID
    revision: int
    provider: str
    score_type: Literal["internal estimate"]
    qualification_estimate: int = Field(ge=0, le=100)
    confidence: Literal["low", "medium", "high"]
    recommendation: Literal["Strong Match", "Potential Match", "Needs Review", "Not Eligible"]
    job_title: str | None
    title_used_in_score: Literal[False]
    analysis: JobAnalysis
    matched: list[Alignment]
    transferable: list[Alignment]
    missing_required: list[Alignment]
    preferred_unmet: list[Alignment]
    eligibility_blockers: list[Alignment]
    unmet_responsibilities: list[Alignment]
    evidence: list[Evidence]


class ProposalReceipt(BaseModel):
    application_id: UUID
    proposal_id: UUID
    resume_version_id: UUID
