"""Candidate-facing data contracts. Save, review and consent are separate operations."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, field_validator

Short = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Labels = Annotated[list[Short], Field(max_length=100)]
Origin = Literal["user_provided", "inferred"]
WorkMode = Literal["remote", "hybrid", "onsite"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Education(Model):
    institution: Short
    program: Short | None = None
    details: Note | None = None


class Experience(Model):
    organization: Short
    role: Short
    details: Note | None = None


class Project(Model):
    name: Short
    description: Note | None = None
    url: HttpUrl | None = None


class Fields(Model):
    full_name: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
        | None
    ) = None
    email: Annotated[str, Field(max_length=255, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")] | None = (
        None
    )
    phone: Annotated[str, Field(max_length=60, min_length=1)] | None = None
    education: Annotated[list[Education], Field(max_length=50)] | None = None
    work_experience: Annotated[list[Experience], Field(max_length=100)] | None = None
    skills: Labels | None = None
    projects: Annotated[list[Project], Field(max_length=100)] | None = None
    github: HttpUrl | None = None
    linkedin: HttpUrl | None = None
    portfolio: HttpUrl | None = None
    preferred_roles: Labels | None = None
    employment_types: Labels | None = None
    preferred_locations: Labels | None = None
    work_modes: Annotated[list[WorkMode], Field(max_length=3)] | None = None
    salary_expectations: Note | None = None
    availability: Note | None = None
    work_authorization: Note | None = None
    application_preferences: Note | None = None

    @field_validator("github", "linkedin", "portfolio")
    @classmethod
    def check_link(cls, url: HttpUrl | None) -> HttpUrl | None:
        if url and (url.username or url.password):
            raise ValueError("Credentials in links are unsupported")
        return url

    @field_validator("github")
    @classmethod
    def github_account(cls, url: HttpUrl | None) -> HttpUrl | None:
        import re

        if url and (
            url.host not in {"github.com", "www.github.com"}
            or url.query
            or url.fragment
            or not re.fullmatch(r"/[A-Za-z0-9-]{1,39}/?", url.path or "")
        ):
            raise ValueError("Use a GitHub account URL")
        return url


class Step(StrEnum):
    basic = "basic_profile"
    history = "education_experience"
    skills = "skills_projects"
    links = "github_portfolio"
    resume = "resume_upload"
    preferences = "job_preferences"
    permissions = "automation_permissions"
    confirm = "final_confirmation"


STEP_FIELDS = {
    Step.basic: ("full_name", "email", "phone"),
    Step.history: ("education", "work_experience"),
    Step.skills: ("skills", "projects"),
    Step.links: ("github", "linkedin", "portfolio"),
    Step.preferences: (
        "preferred_roles",
        "employment_types",
        "preferred_locations",
        "work_modes",
        "salary_expectations",
        "availability",
        "work_authorization",
        "application_preferences",
    ),
}
OPTIONAL = {Step.history, Step.skills, Step.links, Step.resume, Step.preferences}
QUALIFICATIONS = {"education", "work_experience", "skills", "projects"}
StepStatus = Literal["pending", "completed", "skipped"]


class Version(Model):
    revision: int = Field(ge=0)


class Edit(Version):
    fields: Fields


class Suggest(Edit):
    origin: Origin = "user_provided"


class Review(Version):
    field: Short
    evidence: Note


class Advance(Version):
    step: Step
    status: Literal["completed", "skipped"]


class Provenance(Model):
    status: Literal["user_provided", "verified", "inferred"]
    evidence: str | None = None


class StepView(Model):
    step: Step
    status: StepStatus
    optional: bool


class ResumeInfo(Model):
    id: UUID
    label: Short
    target_role: Short | None
    byte_size: int
    created_at: datetime


class ResumeEdit(Version):
    label: Short
    target_role: Short | None = None


class Permissions(Model):
    outbound_enabled: bool
    auto_archive_rejections: bool
    auto_trash_scams: bool


class Candidate(Version):
    fields: Fields
    provenance: dict[str, Provenance]
    suggestions: Fields
    suggestion_origins: dict[str, Origin]
    resumes: list[ResumeInfo]
    permissions: Permissions
    steps: list[StepView]
    confirmed: bool


class PreviewRequest(Model):
    required_fields: Annotated[list[Short], Field(max_length=80)]
    include_portfolio: bool = False
    resume_id: UUID | None = None


class Preview(Model):
    answers: dict[str, Any]
    clarifications: dict[str, str]
    resume_id: UUID | None
    explicit_submission_approval_required: Literal[True] = True
    explicit_email_approval_required: Literal[True] = True
