"""Owner-scoped candidate editing, onboarding progress and application preparation."""

import json
from collections.abc import Callable
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import Connection, func, select, update
from sqlalchemy.exc import IntegrityError

from .candidate_contracts import (
    OPTIONAL,
    QUALIFICATIONS,
    STEP_FIELDS,
    Advance,
    Candidate,
    Edit,
    Fields,
    Permissions,
    Preview,
    PreviewRequest,
    ResumeInfo,
    Review,
    Step,
    Suggest,
    Version,
)
from .controls import Key, Result, execute
from .job_pipeline import invalidate
from .routes import Owner
from .security import seal, tenant, unseal
from .tables import profiles, settings, uploaded_resumes, users

candidate = APIRouter(prefix="/api/v1/candidate")
LINKS = {
    "github": "github_username",
    "linkedin": "linkedin_profile_url",
    "portfolio": "portfolio_url",
}
CANONICAL = {"full_name", "email", *LINKS}
RESUME_COLUMNS = [uploaded_resumes.c[k] for k in ResumeInfo.model_fields]


class Draft:
    """One transaction holds the profile lock from revision check through commit."""

    def __init__(
        self, conn: Connection, owner: UUID, key: bytes, revision: int | None = None
    ) -> None:
        self.conn, self.owner, self.key = conn, owner, key
        query = select(profiles).where(profiles.c.user_id == owner)
        row = conn.execute(query.with_for_update(read=revision is None)).mappings().one()
        self.revision = int(row["candidate_revision"])
        if revision is not None and revision != self.revision:
            raise HTTPException(409, "Profile changed. Reload before saving.")
        self.steps = dict(row["onboarding_steps"])
        encrypted = row["candidate_ciphertext"]
        self.private: dict[str, Any] = (
            json.loads(unseal(key, owner, "candidate-profile", encrypted[:12], encrypted[12:]))
            if encrypted
            else {}
        )
        self.values = dict(self.private.get("values", {}))
        self.sources = self.private.setdefault("provenance", {})
        self.suggestions = self.private.setdefault("suggestions", {})
        self.origins = self.private.setdefault("origins", {})
        identity = (
            conn.execute(select(users.c.full_name, users.c.email).where(users.c.id == owner))
            .mappings()
            .one()
        )
        if identity["email"] != f"{owner}@private.invalid":
            self.values["email"] = identity["email"]
        if identity["full_name"] != "Private owner" or "full_name" in self.sources:
            self.values["full_name"] = identity["full_name"]
        for field, column in LINKS.items():
            if row[column]:
                self.values[field] = (
                    f"https://github.com/{row[column]}" if field == "github" else row[column]
                )

    def invalidate(self, step: Step) -> None:
        self.steps.pop(step, None)
        self.steps.pop(Step.confirm, None)

    def persist(self) -> Result:
        self.private["values"] = {k: v for k, v in self.values.items() if k not in CANONICAL}
        iv, data = seal(
            self.key, self.owner, "candidate-profile", json.dumps(self.private).encode()
        )
        self.conn.execute(
            update(profiles)
            .where(profiles.c.user_id == self.owner)
            .values(
                candidate_ciphertext=iv + data,
                onboarding_steps=self.steps,
                candidate_revision=self.revision + 1,
                updated_at=func.now(),
            )
        )
        invalidate(self.conn, self.owner, self.key)
        return {"revision": self.revision + 1}

    def view(self) -> Candidate:
        permissions = (
            self.conn.execute(
                select(*[settings.c[k] for k in Permissions.model_fields]).where(
                    settings.c.user_id == self.owner
                )
            )
            .mappings()
            .one()
        )
        files = self.conn.execute(
            select(*RESUME_COLUMNS)
            .where(uploaded_resumes.c.user_id == self.owner)
            .order_by(uploaded_resumes.c.created_at, uploaded_resumes.c.id)
        ).mappings()
        return Candidate.model_validate(
            {
                "revision": self.revision,
                "fields": self.values,
                "provenance": {
                    k: self.sources.get(k, {"status": "user_provided"}) for k in self.values
                },
                "suggestions": self.suggestions,
                "suggestion_origins": self.origins,
                "resumes": list(files),
                "permissions": permissions,
                "confirmed": self.steps.get(Step.confirm) == "completed",
                "steps": [
                    {"step": s, "optional": s in OPTIONAL, "status": self.steps.get(s, "pending")}
                    for s in Step
                ],
            }
        )


def mutate(
    request: Request,
    owner: UUID,
    key: UUID,
    action: str,
    inputs: Result,
    revision: int,
    change: Callable[[Draft], Result | None],
) -> Result:
    def transaction(conn: Connection) -> Result:
        draft = Draft(conn, owner, request.app.state.secret_key, revision)
        extra = change(draft) or {}
        return {**draft.persist(), **extra}

    return execute(request, owner, key, action, inputs, transaction)


@candidate.get("", response_model=Candidate)
def get_candidate(request: Request, owner: Owner) -> Candidate:
    with tenant(request.app.state.db, owner) as conn:
        return Draft(conn, owner, request.app.state.secret_key).view()


@candidate.patch("", response_model=Version)
def edit(payload: Edit, request: Request, owner: Owner, key: Key) -> Result:
    values = payload.fields.model_dump(exclude_unset=True, mode="json")
    if not values:
        raise HTTPException(422, "Supply at least one profile field.")

    def change(draft: Draft) -> None:
        for field, value in values.items():
            if field in {"email", "full_name"} and not value:
                raise HTTPException(422, "Name and email must be nonempty when supplied.")
            if value is None:
                draft.values.pop(field, None)
                draft.sources.pop(field, None)
            else:
                draft.values[field] = value
                draft.sources[field] = {"status": "user_provided"}
            draft.suggestions.pop(field, None)
            draft.origins.pop(field, None)
        identity = {k: v for k, v in values.items() if k in {"email", "full_name"}}
        links = {LINKS[k]: v for k, v in values.items() if k in LINKS}
        if links.get("github_username"):
            links["github_username"] = (
                payload.fields.github.path.strip("/")
                if payload.fields.github and payload.fields.github.path
                else None
            )
        if identity:
            try:
                draft.conn.execute(
                    update(users)
                    .where(users.c.id == owner)
                    .values(**identity, updated_at=func.now())
                )
            except IntegrityError as exc:
                raise HTTPException(409, "Identity update could not be saved.") from exc
        if links:
            draft.conn.execute(update(profiles).where(profiles.c.user_id == owner).values(**links))
        for step, names in STEP_FIELDS.items():
            if values.keys() & set(names):
                draft.invalidate(step)

    return mutate(
        request,
        owner,
        key,
        "candidate.edit",
        payload.model_dump(mode="json", exclude_unset=True),
        payload.revision,
        change,
    )


@candidate.patch("/suggestions", response_model=Version)
def suggest(payload: Suggest, request: Request, owner: Owner, key: Key) -> Result:
    values = payload.fields.model_dump(exclude_unset=True, mode="json")
    if not values:
        raise HTTPException(422, "Supply at least one suggestion.")

    def change(draft: Draft) -> None:
        for field, value in values.items():
            if value is None:
                draft.suggestions.pop(field, None)
                draft.origins.pop(field, None)
            else:
                draft.suggestions[field] = value
                draft.origins[field] = payload.origin

    return mutate(
        request,
        owner,
        key,
        "candidate.suggest",
        payload.model_dump(mode="json", exclude_unset=True),
        payload.revision,
        change,
    )


@candidate.post("/review", response_model=Version)
def review(payload: Review, request: Request, owner: Owner, key: Key) -> Result:
    def change(draft: Draft) -> None:
        if not draft.values.get(payload.field):
            raise HTTPException(422, "Save the field and review its supporting evidence first.")
        draft.sources[payload.field] = {"status": "verified", "evidence": payload.evidence}
        draft.steps.pop(Step.confirm, None)

    return mutate(
        request, owner, key, "candidate.verify", payload.model_dump(), payload.revision, change
    )


@candidate.post("/onboarding", response_model=Version)
def advance(payload: Advance, request: Request, owner: Owner, key: Key) -> Result:
    def change(draft: Draft) -> None:
        step = payload.step
        if payload.status == "skipped" and step not in OPTIONAL:
            raise HTTPException(422, "This step requires explicit confirmation.")
        if payload.status == "completed":
            if step == Step.basic and not all(draft.values.get(k) for k in ("full_name", "email")):
                raise HTTPException(
                    422, "Enter your full name and email to complete the basic profile."
                )
            if (
                step in OPTIONAL
                and step != Step.resume
                and not any(draft.values.get(k) for k in STEP_FIELDS[step])
            ):
                raise HTTPException(422, "Enter a value or skip this optional section.")
            if step == Step.resume and not draft.conn.scalar(
                select(uploaded_resumes.c.id).limit(1)
            ):
                raise HTTPException(422, "Upload a resume or skip this step.")
            if step == Step.confirm and any(
                draft.steps.get(s) not in {"completed", "skipped"}
                for s in Step
                if s != Step.confirm
            ):
                raise HTTPException(409, "Review or skip the remaining steps before confirming.")
        draft.steps.pop(Step.confirm, None)
        draft.steps[step] = payload.status

    return mutate(
        request,
        owner,
        key,
        "onboarding." + payload.step.value + "." + payload.status,
        payload.model_dump(),
        payload.revision,
        change,
    )


@candidate.post("/application-preview")
def preview(payload: PreviewRequest, request: Request, owner: Owner) -> Preview:
    with tenant(request.app.state.db, owner) as conn:
        draft = Draft(conn, owner, request.app.state.secret_key)
        answers: Result = {}
        questions: dict[str, str] = {}
        for field in payload.required_fields:
            if field == "resume":
                if payload.resume_id:
                    answers[field] = str(payload.resume_id)
                else:
                    questions[field] = "Which resume should be attached to this application?"
            elif not draft.values.get(field) or field not in Fields.model_fields:
                questions[field] = f"Please provide {field} for this application."
            elif (
                field in QUALIFICATIONS and draft.sources.get(field, {}).get("status") != "verified"
            ):
                questions[field] = f"Please review the evidence for {field} before using it."
            else:
                answers[field] = draft.values[field]
        if payload.include_portfolio and draft.values.get("portfolio"):
            answers["portfolio"] = draft.values["portfolio"]
        if payload.resume_id and not conn.scalar(
            select(uploaded_resumes.c.id).where(uploaded_resumes.c.id == payload.resume_id)
        ):
            raise HTTPException(404, "Resume not found.")
        return Preview(answers=answers, clarifications=questions, resume_id=payload.resume_id)
