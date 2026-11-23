"""PostgreSQL schema. Every link between tenant resources includes user_id."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()
job_source = Enum("whatsapp", "linkedin_feed", "linkedin_post", "manual", name="job_source_enum")
job_status = Enum(
    "discovered",
    "pending_approval",
    "tailoring",
    "applied",
    "outreach_active",
    "shortlisted",
    "assessment",
    "interview",
    "offer",
    "rejected",
    "scam_blocked",
    "skipped",
    name="job_status_enum",
)
apply_method = Enum(
    "cold_email",
    "linkedin_easy_apply",
    "greenhouse",
    "lever",
    "workday",
    "wellfound",
    "internshala",
    "custom_portal",
    name="apply_method_enum",
)
outreach_status = Enum(
    "queued",
    "connect_sent",
    "accepted",
    "dm_sent",
    "followup_sent",
    "replied",
    "failed",
    name="outreach_status_enum",
)
email_class = Enum(
    "application_ack",
    "assessment",
    "shortlist_interview",
    "offer",
    "rejection",
    "scam_spam",
    "unrelated",
    name="email_class_enum",
)


def uid() -> Column[UUID]:
    return Column("id", Uuid, primary_key=True, server_default=func.gen_random_uuid())


def user_id(*, primary: bool = False) -> Column[UUID]:
    return Column(
        "user_id",
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=primary,
        nullable=False,
    )


def timestamp(name: str = "created_at") -> Column[datetime]:
    return Column(name, DateTime(timezone=True), nullable=False, server_default=func.now())


def doc(name: str) -> Column[Any]:
    return Column(name, JSONB, nullable=False, server_default=text("'{}'::jsonb"))


def ref(field: str, parent: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(["user_id", field], [parent + ".user_id", parent + ".id"])


def entity(
    name: str, *fields: Column[Any] | CheckConstraint | UniqueConstraint | ForeignKeyConstraint
) -> Table:
    return Table(
        name, metadata, uid(), user_id(), *fields, timestamp(), UniqueConstraint("user_id", "id")
    )


users = Table(
    "users",
    metadata,
    uid(),
    Column("email", String(255), nullable=False, unique=True),
    Column("full_name", String(255), nullable=False),
    Column("is_active", Boolean, nullable=False, server_default=text("true")),
    timestamp(),
    timestamp("updated_at"),
)
profiles = Table(
    "candidate_profiles",
    metadata,
    user_id(primary=True),
    Column("github_username", String(100)),
    Column("linkedin_profile_url", Text),
    Column("portfolio_url", Text),
    Column("telegram_chat_id", BigInteger, unique=True),
    Column("resume_git_repo_url", Text),
    Column("resume_master_branch", String(50), server_default="main"),
    Column("master_latex_template", Text),
    doc("profile_vault_json"),
    timestamp("updated_at"),
)
settings = Table(
    "user_settings",
    metadata,
    user_id(primary=True),
    *[
        Column(k, Integer, nullable=False, server_default=str(v))
        for k, v in [
            ("min_trust_score_auto_apply", 80),
            ("min_ats_score_threshold", 82),
            ("max_daily_linkedin_connects", 12),
            ("max_daily_linkedin_dms", 20),
        ]
    ],
    *[
        Column(k, Boolean, nullable=False, server_default=text("false"))
        for k in ["outbound_enabled", "auto_trash_scams", "auto_archive_rejections"]
    ],
    CheckConstraint(
        "min_trust_score_auto_apply BETWEEN 0 AND 100 AND min_ats_score_threshold BETWEEN 0 AND 100"
    ),
    CheckConstraint(
        "max_daily_linkedin_connects BETWEEN 0 AND 1000 AND max_daily_linkedin_dms BETWEEN 0 AND 1000"
    ),
)
control = Table(
    "system_control",
    metadata,
    Column("singleton", Boolean, primary_key=True),
    Column("is_system_paused", Boolean, nullable=False, server_default=text("true")),
    CheckConstraint("singleton"),
)
sessions = Table(
    "sessions",
    metadata,
    Column("digest", String(64), primary_key=True),
    user_id(),
    Column("expires_at", DateTime(timezone=True), nullable=False),
)
companies = entity("companies", Column("name", Text, nullable=False), Column("domain", Text))
sources = entity(
    "job_sources",
    Column("kind", job_source, nullable=False),
    Column("identifier", Text, nullable=False),
    Column("is_whitelisted", Boolean, nullable=False, server_default=text("false")),
    UniqueConstraint("user_id", "kind", "identifier"),
)
jobs = entity(
    "jobs",
    Column("fingerprint", String(64), nullable=False),
    Column("description", Text, nullable=False),
    Column("source_url", Text),
    Column("role", Text),
    Column("location", Text),
    Column("is_remote", Boolean),
    Column("application_url", Text),
    Column("recruiter_email", String(255)),
    Column("company_id", Uuid),
    ref("company_id", "companies"),
    Column("status", job_status, nullable=False, server_default="discovered"),
    UniqueConstraint("user_id", "fingerprint"),
)
observations = entity(
    "source_observations",
    Column("job_id", Uuid, nullable=False),
    ref("job_id", "jobs"),
    Column("source", job_source, nullable=False),
    Column("source_id", Uuid),
    ref("source_id", "job_sources"),
)
events = entity(
    "job_events",
    Column("job_id", Uuid, nullable=False),
    ref("job_id", "jobs"),
    Column("kind", job_status, nullable=False),
)
trust = entity(
    "trust_evaluations",
    Column("job_id", Uuid, nullable=False),
    ref("job_id", "jobs"),
    Column("score", Integer, nullable=False),
    CheckConstraint("score BETWEEN 0 AND 100"),
    Column("risk_flags", JSONB, nullable=False),
    doc("evidence"),
    Column("rules_version", Text, nullable=False),
)
projects = entity(
    "github_projects",
    Column("repo_url", Text, nullable=False),
    Column("commit_sha", Text, nullable=False),
    Column("description", Text),
    Column("readme_summary", Text),
    Column("tech_stack", JSONB),
    Column("live_links", JSONB),
    doc("verified_metrics"),
    Column("embedding", Vector()),
    UniqueConstraint("user_id", "repo_url", "commit_sha"),
)
resumes = entity(
    "resume_versions",
    Column("latex_source", Text, nullable=False),
    Column("template_revision", Text, nullable=False),
    Column("job_id", Uuid),
    ref("job_id", "jobs"),
    doc("claim_manifest"),
)
artifacts = entity(
    "generated_artifacts",
    Column("resume_version_id", Uuid),
    ref("resume_version_id", "resume_versions"),
    Column("job_id", Uuid, nullable=False),
    ref("job_id", "jobs"),
    Column("kind", Text, nullable=False),
    Column("storage_key", Text, nullable=False),
    Column("sha256", String(64), nullable=False),
    CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'"),
    Column("ats_score", Integer),
    CheckConstraint("ats_score BETWEEN 0 AND 100"),
)
applications = entity(
    "applications",
    Column("job_id", Uuid, nullable=False),
    ref("job_id", "jobs"),
    Column("method", apply_method, nullable=False),
    Column("status", job_status, nullable=False, server_default="discovered"),
    Column("resume_version_id", Uuid),
    ref("resume_version_id", "resume_versions"),
    UniqueConstraint("user_id", "job_id", "method"),
)
application_statuses = entity(
    "application_statuses",
    Column("application_id", Uuid, nullable=False),
    ref("application_id", "applications"),
    Column("status", job_status, nullable=False),
    Column("reason", Text),
)
outreach = entity(
    "recruiter_outreach",
    Column("application_id", Uuid, nullable=False),
    ref("application_id", "applications"),
    Column("recipient", Text, nullable=False),
    Column("draft", Text, nullable=False),
    Column("status", outreach_status, nullable=False, server_default="queued"),
)
mail = entity(
    "email_events",
    Column("application_id", Uuid),
    ref("application_id", "applications"),
    Column("message_id", Text, nullable=False),
    Column("event_key", Text, nullable=False),
    Column("classification", email_class, nullable=False),
    doc("previous_labels"),
    UniqueConstraint("user_id", "event_key"),
)
connections = entity(
    "integration_connections",
    Column("provider", Text, nullable=False),
    Column("encrypted_credentials", LargeBinary, nullable=False),
    Column("credentials_iv", LargeBinary, nullable=False),
    Column("key_version", Integer, nullable=False),
    CheckConstraint(
        "octet_length(credentials_iv) = 12 AND octet_length(encrypted_credentials) >= 16"
    ),
    UniqueConstraint("user_id", "provider"),
)
approvals = entity(
    "approval_requests",
    Column("application_id", Uuid),
    ref("application_id", "applications"),
    Column("action", Text, nullable=False),
    Column("destination", Text, nullable=False),
    Column("content_digest", String(64), nullable=False),
    CheckConstraint("content_digest ~ '^[0-9a-f]{64}$'"),
    Column("status", Text, nullable=False, server_default="pending"),
    CheckConstraint("status IN ('pending','approved','rejected','consumed','revoked')"),
    Column("expires_at", DateTime(timezone=True), nullable=False),
)
blocks = entity(
    "blocked_entities",
    Column("kind", Text, nullable=False),
    CheckConstraint("kind IN ('company','domain','email')"),
    Column("value", Text, nullable=False),
    Column("reason", Text, nullable=False),
    UniqueConstraint("user_id", "kind", "value"),
)
tasks = entity(
    "background_tasks",
    Column("kind", Text, nullable=False),
    Column("status", Text, nullable=False, server_default="pending"),
    CheckConstraint("status IN ('pending','succeeded','failed')"),
    Column("next_publish_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
audits = entity(
    "audit_events",
    Column("action", Text, nullable=False),
    Column("resource_id", Uuid),
    doc("details"),
)
commands = Table(
    "idempotency_keys",
    metadata,
    user_id(primary=True),
    Column("key", Uuid, primary_key=True),
    Column("request_digest", String(64), nullable=False),
    doc("response"),
    timestamp(),
)
