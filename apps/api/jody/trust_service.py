"""Assessment history is append-only under the same tenant lock as canonical intake."""

import json
import re
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import Connection, func, insert, select

from .eligibility import normalize
from .gmail.extract import safe_url
from .security import audit, digest
from .tables import audits, blocks, companies, gmail_evidence, jobs, observations, settings, trust
from .trust_check import official_domain, verify
from .trust_rules import VERSION, Assessment, hostname, rubric, same_site

Action = Literal["reassess", "verify", "approve", "skip", "block", "confirmed_scam"]


def assessment(
    c: Connection,
    owner: UUID,
    jid: UUID,
    action: Action = "reassess",
    reference: str = "",
    note: str = "",
    expected: str | None = None,
) -> Assessment:
    from .job_pipeline import dispatch, lock

    if re.search(
        r"(?i)\bbearer\s+\S+|\b[0-9a-f]{64}\b|(?:api[_-]?key|password|secret)\s*[=:]\s*\S+", note
    ):
        raise HTTPException(422, "Remove credentials from the review note.")
    lock(c, owner)
    if not dispatch(c):
        raise HTTPException(409, "Trust assessment is paused.")
    row = (
        c.execute(
            select(jobs, companies.c.name.label("company"))
            .select_from(jobs.outerjoin(companies, jobs.c.company_id == companies.c.id))
            .where(jobs.c.id == jid)
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(404, "Job not found.")
    f = row["canonical"]
    if not f:
        saved = (
            c.scalar(
                select(gmail_evidence.c.facts)
                .where(gmail_evidence.c.job_id == jid)
                .order_by(gmail_evidence.c.created_at.desc())
                .limit(1)
            )
            or {}
        )
        f = normalize(
            row["description"],
            row["source_url"],
            {"title": row["role"], "company": row["company"], "location": row["location"], **saved},
        )
    refs = [
        (source + ":" + str(oid), facts or {})
        for oid, source, facts in c.execute(
            select(observations.c.id, observations.c.source, observations.c.facts)
            .where(observations.c.job_id == jid)
            .order_by(observations.c.id)
            .limit(101)
        )
    ]
    company = f.get("company") or ""
    official = official_domain(company)
    threshold = c.scalar(select(settings.c.min_trust_score_auto_apply))
    assert threshold is not None
    block = False
    for kind, value in c.execute(select(blocks.c.kind, blocks.c.value)):
        for facts in [f, *[raw for _, raw in refs]]:
            email = str(facts.get("recruiter_email") or "").lower()
            hosts = [
                hostname(facts.get(k) or "")
                for k in ("source_url", "posting_url", "application_url")
            ] + [facts.get("domain") or "", email.rpartition("@")[2]]
            if (
                kind == "company"
                and (facts.get("company") or "").casefold() == value
                or kind == "email"
                and email == value
                or kind == "domain"
                and any(same_site(h, value) for h in hosts)
            ):
                block = True
    material = digest(
        json.dumps([f, refs, official, block, threshold, VERSION], sort_keys=True, default=str)
    )
    last = c.execute(
        select(trust.c.id, trust.c.evidence, trust.c.created_at)
        .where(trust.c.job_id == jid, trust.c.rules_version == VERSION)
        .order_by(trust.c.created_at.desc(), trust.c.id.desc())
        .limit(1)
    ).first()
    previous = last.evidence if last else {}
    now = datetime.now(UTC)
    if expected and (not last or str(last.id) != expected or previous.get("material") != material):
        raise HTTPException(409, "Assessment changed. Reassess before recording a review.")
    current = previous.get("material") == material
    proof = dict(previous.get("proof", {})) if current else {}
    if proof and now >= datetime.fromisoformat(proof["expires"]):
        proof = {}
    decision = previous.get("review")
    if decision not in ("confirmed_scam", "block", "skip") and not proof:
        decision = None
    if action == "verify":
        if not (
            current
            and previous.get("checked")
            and now - datetime.fromisoformat(previous["checked"]) < timedelta(hours=24)
        ):
            used = c.scalar(
                select(func.count())
                .select_from(audits)
                .where(
                    audits.c.action == "trust.public_check",
                    audits.c.created_at >= now - timedelta(hours=1),
                )
            )
            if (used or 0) >= 3:
                raise HTTPException(429, "Hourly verification limit reached.")
            result = verify(f, official)
            proof = {**result, "expires": (now + timedelta(days=1)).isoformat()}
            previous = {**previous, "checked": now.isoformat()}
            audit(c, owner, "trust.public_check", jid)
    if action == "approve":
        if decision in ("confirmed_scam", "block"):
            raise HTTPException(409, "Blocked opportunities cannot be approved.")
        link = f.get("posting_url") or ""
        if (
            not note
            or not company
            or not official
            or reference != link
            or not safe_url(link)
            or not same_site(hostname(link), official)
        ):
            raise HTTPException(
                422,
                "Confirm the exact official vacancy URL and record the independent evidence checked.",
            )
        proof = {
            **proof,
            "posting": link,
            "posting_ref": "owner verification: " + note,
            "expires": (now + timedelta(days=1)).isoformat(),
        }
        decision = "approve"
    elif action in ("skip", "block", "confirmed_scam"):
        if not note:
            raise HTTPException(422, "Record the evidence or reason for this decision.")
        if decision != "confirmed_scam" and (decision != "block" or action == "confirmed_scam"):
            decision = action
    report = rubric(f, refs[:100], official, proof, block, threshold, decision, len(refs) > 100)
    if action == "approve" and report.state != "trusted":
        raise HTTPException(409, "Evidence, threshold or risk findings prevent approval.")
    if (
        action == "reassess"
        and current
        and last
        and proof == previous.get("proof", {})
        and last.created_at >= now - timedelta(hours=24)
    ):
        return Assessment.model_validate(previous["report"])
    detail = report.model_dump(mode="json")
    data = {
        "report": detail,
        "material": material,
        "proof": proof,
        "review": decision,
        "checked": previous.get("checked") if current or action == "verify" else None,
        "review_reason": note or previous.get("review_reason"),
    }
    if (
        action == "verify"
        and current
        and previous.get("proof") == proof
        and previous.get("report", {}).get("state") == report.state
        and last
        and previous.get("checked") != now.isoformat()
    ):
        return Assessment.model_validate(previous["report"])
    c.execute(
        insert(trust).values(
            created_at=func.clock_timestamp(),
            user_id=owner,
            job_id=jid,
            score=report.score,
            risk_flags=[s.code for s in report.signals if s.kind == "risk"],
            rules_version=VERSION,
            evidence=data,
        )
    )
    return report
