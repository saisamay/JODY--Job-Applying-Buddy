"""Owner-facing operations shared by REST and the restricted MCP projection."""

from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import HTTPException, Request
from sqlalchemy import Connection, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..security import tenant
from ..tables import applications, blocks, career_proposals, companies, jobs, resumes
from .inference import Inference, configured
from .knowledge import RESUME_KINDS, Json, knowledge, lock, verified
from .matching import INSTRUCTION, analyze, assess

Method = Literal[
    "cold_email",
    "linkedin_easy_apply",
    "greenhouse",
    "lever",
    "workday",
    "wellfound",
    "internshala",
    "custom_portal",
]


def comparison(
    request: Request,
    conn: Connection | None,
    owner: UUID,
    job_id: UUID,
    *,
    cached_only: bool = False,
    normalized_only: bool = False,
) -> Json:
    def inputs(c: Connection) -> tuple[Json, list[Json], int]:
        row = c.execute(
            select(jobs.c.description, jobs.c.role, jobs.c.canonical).where(jobs.c.id == job_id)
        ).first()
        if row is None:
            raise HTTPException(404, "Job not found.")
        state = knowledge(c, owner, request.app.state.secret_key)
        return (
            {
                "description": (row.canonical or {}).get("description") or row.description,
                "role": (row.canonical or {}).get("title") or row.role,
            },
            [f for f in verified(state) if not INSTRUCTION.search(f["quote"])],
            state["revision"],
        )

    if conn is None:
        with tenant(request.app.state.db, owner) as c:
            info, facts, revision = inputs(c)
    else:
        info, facts, revision = inputs(conn)
    ai = Inference(request.app.state.db, owner, request.app.state.secret_key, configured())
    job: Json = ai.cached(
        "analysis",
        info,
        lambda: analyze(ai, info["description"], info["role"]),
        read=conn if cached_only else None,
    )
    if normalized_only:
        return job
    match: Json = ai.cached(
        "match",
        {"job": job, "facts": [f["id"] for f in facts]},
        lambda: assess(ai, job, facts),
        read=conn if cached_only else None,
    )
    return {
        **match,
        "job_id": str(job_id),
        "revision": revision,
        "provider": ai.provider.identity,
        "analysis": job,
    }


def latex_text(value: str) -> str:
    escaped = {
        "\\": r"\textbackslash{}",
        "{": r"\{",
        "}": r"\}",
        "%": r"\%",
        "&": r"\&",
        "#": r"\#",
        "_": r"\_",
        "$": r"\$",
        "^": r"\textasciicircum{}",
        "~": r"\textasciitilde{}",
    }
    return "".join(escaped.get(c, c) for c in value)


def propose(request: Request, conn: Connection, owner: UUID, job_id: UUID, method: Method) -> Json:
    lock(conn, owner)
    vacancy = (
        conn.execute(
            select(
                jobs.c.status,
                jobs.c.canonical,
                jobs.c.application_url,
                jobs.c.source_url,
                jobs.c.recruiter_email,
                companies.c.name,
                companies.c.domain,
            )
            .select_from(jobs.outerjoin(companies, jobs.c.company_id == companies.c.id))
            .where(jobs.c.id == job_id)
        )
        .mappings()
        .first()
    )
    if vacancy is None:
        raise HTTPException(404, "Job not found.")
    if vacancy["canonical"]:
        from ..job_pipeline import evaluate

        screening = evaluate(conn, owner, request.app.state.secret_key, vacancy["canonical"])
        if screening.decision in {"ineligible", "blocklisted", "expired_or_closed"}:
            raise HTTPException(409, "This job is excluded from preparation.")
    domains = {str(vacancy["domain"] or "").casefold()}
    for url in [vacancy["application_url"], vacancy["source_url"]]:
        if url:
            domains.add((urlsplit(url).hostname or "").casefold())
    email = (vacancy["recruiter_email"] or "").casefold()
    if "@" in email:
        domains.add(email.rsplit("@", 1)[1])
    name = (vacancy["name"] or "").casefold()
    denied = any(
        (kind == "company" and value.casefold() == name)
        or (kind == "email" and value.casefold() == email)
        or (
            kind == "domain"
            and any(d == value.casefold() or d.endswith("." + value.casefold()) for d in domains)
        )
        for kind, value in conn.execute(select(blocks.c.kind, blocks.c.value))
    )
    if vacancy["status"] in {"scam_blocked", "skipped"} or denied:
        raise HTTPException(409, "This job is excluded from preparation.")
    match = comparison(request, conn, owner, job_id, cached_only=True)
    if match["recommendation"] not in {"Strong Match", "Potential Match"}:
        raise HTTPException(409, "Job needs qualification review before preparing a proposal.")
    state = knowledge(conn, owner, request.app.state.secret_key)
    facts = [f for f in verified(state) if not INSTRUCTION.search(f["quote"])]
    weights: dict[str, int] = {}
    for name, weight in [("matched", 2), ("transferable", 1)]:
        for item in match[name]:
            eid = item["evidence_id"]
            weights[eid] = weights.get(eid, 0) + weight
    evidence_text = {f["quote"].casefold(): weights[f["id"]] for f in facts if f["id"] in weights}
    variants = [
        s
        for s in state["sources"]
        if s["kind"] in RESUME_KINDS and any(f["source_id"] == s["id"] for f in facts)
    ]
    if not variants:
        raise HTTPException(409, "Review at least one resume baseline.")

    def fitness(s: Json) -> tuple[int, int]:
        lines = {f["quote"].casefold() for f in facts if f["source_id"] == s["id"]}
        return sum(evidence_text.get(q, 0) for q in lines), len(lines)

    baseline = max(variants, key=fitness)
    before = [f for f in state["facts"].values() if f["source_id"] == baseline["id"]]
    selected = [f for f in facts if f["source_id"] == baseline["id"]]
    seen = {f["quote"].casefold() for f in selected}
    for f in facts:
        if f["quote"].casefold() not in seen and (
            f["id"] in weights or f["category"] in {"education", "employment", "internship", "date"}
        ):
            selected.append(f)
            seen.add(f["quote"].casefold())
    # Preserve grouping and order of work history. Promote entire relevant sections.
    categories = list(dict.fromkeys(f["category"] for f in selected))
    categories.sort(
        key=lambda c: (
            -sum(
                evidence_text.get(f["quote"].casefold(), 0) for f in selected if f["category"] == c
            )
        )
    )
    after = sorted(selected, key=lambda f: categories.index(f["category"]))
    positions = {f["id"]: i for i, f in enumerate(before)}
    diff = [
        {
            "fact_id": f["id"],
            "before_index": positions.get(f["id"]),
            "after_index": i,
            "text": f["quote"],
            "reason": "Include reviewed supporting evidence or career history."
            if f["id"] not in positions
            else "Group verified facts by job relevance while preserving section order.",
        }
        for i, f in enumerate(after)
        if positions.get(f["id"]) != i
    ]
    missing = [r["text"] for r in match["missing_required"]]
    after_ids = {f["id"] for f in after}
    unreviewed = []
    for f in before:
        if f["id"] not in after_ids:
            diff.append(
                {
                    "fact_id": f["id"],
                    "before_index": positions[f["id"]],
                    "after_index": None,
                    "reason": "Owner rejected this statement."
                    if f["state"] == "rejected"
                    else "Requires owner review before inclusion.",
                }
            )
            if f["state"] != "rejected":
                unreviewed.append(f["id"])
    manifest = {
        "baseline_id": baseline["id"],
        "profile_revision": state["revision"],
        "before": [f["id"] for f in before],
        "after": [f["id"] for f in after],
        "diff": diff,
        "missing_information": missing,
        "baseline_facts_to_review": unreviewed,
        "stage": "proposal",
    }
    latex = "\n".join(
        r"\section*{"
        + latex_text(group.title())
        + "}\n"
        + "\n\n".join(latex_text(f["quote"]) for f in after if f["category"] == group)
        for group in categories
    )
    existing = conn.execute(
        select(
            career_proposals.c.id,
            career_proposals.c.application_id,
            career_proposals.c.resume_version_id,
        )
        .join(applications, applications.c.id == career_proposals.c.application_id)
        .join(resumes, resumes.c.id == career_proposals.c.resume_version_id)
        .where(
            applications.c.job_id == job_id,
            applications.c.method == method,
            career_proposals.c.revision == state["revision"],
            resumes.c.claim_manifest == manifest,
            resumes.c.latex_source == latex,
        )
        .limit(1)
    ).first()
    if existing:
        return {
            "proposal_id": str(existing.id),
            "application_id": str(existing.application_id),
            "resume_version_id": str(existing.resume_version_id),
        }
    rid = conn.scalar(
        insert(resumes)
        .values(
            user_id=owner,
            job_id=job_id,
            template_revision="evidence-fragment-v1",
            latex_source=latex,
            claim_manifest=manifest,
        )
        .returning(resumes.c.id)
    )
    conn.execute(
        pg_insert(applications)
        .values(user_id=owner, job_id=job_id, method=method)
        .on_conflict_do_nothing()
    )
    aid = conn.scalar(
        select(applications.c.id).where(
            applications.c.job_id == job_id, applications.c.method == method
        )
    )
    pid = conn.scalar(
        insert(career_proposals)
        .values(
            user_id=owner,
            application_id=aid,
            baseline_id=baseline["id"],
            resume_version_id=rid,
            revision=state["revision"],
        )
        .returning(career_proposals.c.id)
    )
    return {"proposal_id": str(pid), "application_id": str(aid), "resume_version_id": str(rid)}


def resume_view(conn: Connection, rid: UUID) -> Json:
    row = (
        conn.execute(
            select(
                resumes.c.id, resumes.c.job_id, resumes.c.latex_source, resumes.c.claim_manifest
            ).where(resumes.c.id == rid)
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(404, "Version not found.")
    return dict(row)
