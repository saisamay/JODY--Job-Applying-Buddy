"""Transactional intake and bounded screening. Callers supply a tenant-scoped connection."""

import json
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import ColumnElement, Connection, func, insert, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .config import private_preview
from .eligibility import Facts, Screening, assess, normalize, strong_keys
from .security import audit, digest, unseal
from .tables import blocks, companies, events, jobs, observations, profiles, sources


def lock(c: Connection, owner: UUID) -> None:
    c.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:name,0))"),
        {"name": "canonical:" + str(owner)},
    )


def dispatch(c: Connection) -> bool:
    return not private_preview() and bool(c.scalar(text("SELECT jody_dispatch_open()")))


def evaluate(c: Connection, owner: UUID, key: bytes, f: Facts) -> Screening:
    encrypted = c.scalar(select(profiles.c.candidate_ciphertext).where(profiles.c.user_id == owner))
    profile = (
        json.loads(unseal(key, owner, "candidate-profile", encrypted[:12], encrypted[12:])).get(
            "values", {}
        )
        if encrypted
        else {}
    )
    return assess(f, profile, {(k, v) for k, v in c.execute(select(blocks.c.kind, blocks.c.value))})


def ingest(
    c: Connection,
    owner: UUID,
    key: bytes,
    source: str,
    platform: str,
    description: str,
    url: str | None,
    supplied: Facts,
    sighting: str,
    fallback: str,
) -> tuple[UUID, bool]:
    lock(c, owner)
    f = normalize(description, url, supplied)
    identities = strong_keys(f)
    # Older LinkedIn fingerprints remain addressable without touching their evidence.
    if f.get("identity_conflict"):
        fallback = digest("conflict:" + source + sighting)
    fingerprints = [fallback]
    for identity in identities:
        if identity.startswith("linkedin:"):
            fingerprints.append(
                digest(json.dumps(["gmail", ["platform", "linkedin.com", identity.split(":")[1]]]))
            )
    sight_key = digest(json.dumps([source, sighting]))
    known = c.scalar(select(observations.c.job_id).where(observations.c.sighting_key == sight_key))
    if known:
        return known, False
    condition: ColumnElement[bool] = jobs.c.fingerprint.in_(fingerprints)
    for identity in identities:
        condition |= jobs.c.canonical["identities"].contains([identity])
    matches = c.execute(
        select(jobs.c.id, jobs.c.canonical).where(condition).order_by(jobs.c.id)
    ).all()
    # A different platform ID sharing only a non-employer link is insufficient.
    # Matching employer ATS identities can link distinct platform listings.
    if len(matches) == 1 and matches[0].canonical:
        old_ids = set(matches[0].canonical.get("identities", []))
        incoming = {k for k in identities if k.startswith("linkedin:")}
        existing = {k for k in old_ids if k.startswith("linkedin:")}
        if (
            incoming
            and existing
            and incoming.isdisjoint(existing)
            and not any(
                k.startswith(("workday:", "greenhouse:")) for k in old_ids.intersection(identities)
            )
        ):
            f["possible_duplicates"] = [str(matches[0].id)]
            matches = []
    if len(matches) > 1:
        f["ambiguous"] = True
        f["possible_duplicates"] = [str(r.id) for r in matches]
    new = len(matches) != 1
    if new:
        company = (
            c.scalar(
                insert(companies)
                .values(user_id=owner, name=f["company"], domain=f.get("domain"))
                .returning(companies.c.id)
            )
            if f.get("company")
            else None
        )
        f["identities"] = identities if not matches else []
        jid = c.scalar(
            insert(jobs)
            .values(
                user_id=owner,
                role=f.get("title"),
                description=description,
                location=f.get("location"),
                company_id=company,
                source_url=f.get("posting_url") or url,
                application_url=f.get("application_url"),
                recruiter_email=f.get("recruiter_email"),
                fingerprint=digest("ambiguous:" + sight_key) if matches else fallback,
                canonical=f,
            )
            .returning(jobs.c.id)
        )
        assert jid is not None
        c.execute(insert(events).values(user_id=owner, job_id=jid, kind="discovered"))
        audit(c, owner, "job.discovered", jid)
    else:
        jid, old = matches[0]
        if old:
            # Keep original facts on disagreement and surface the conflict for review.
            merged = {**f, **old}
            for field in ("inferred_roles", "clauses"):
                merged[field] = old.get(field, []) + [
                    v for v in f.get(field, []) if v not in old.get(field, [])
                ]
            merged["identities"] = sorted(set(old.get("identities", [])) | set(identities))
            if any(
                old.get(k) and f.get(k) and old[k] != f[k]
                for k in (
                    "company",
                    "graduation_year",
                    "minimum_experience",
                    "required_education",
                    "deadline",
                    "posting_status",
                )
            ):
                merged["ambiguous"] = True
            f = merged
            c.execute(update(jobs).where(jobs.c.id == jid).values(canonical=f))
    c.execute(
        pg_insert(sources)
        .values(user_id=owner, kind=source, identifier=platform)
        .on_conflict_do_nothing()
    )
    sid = c.scalar(
        select(sources.c.id).where(sources.c.kind == source, sources.c.identifier == platform)
    )
    c.execute(
        insert(observations).values(
            user_id=owner,
            source=source,
            source_id=sid,
            job_id=jid,
            sighting_key=sight_key,
            facts={"description": description, "source_url": url, **supplied},
        )
    )
    if new or matches[0].canonical:
        screen = evaluate(c, owner, key, f).model_dump(mode="json") if dispatch(c) else None
        c.execute(update(jobs).where(jobs.c.id == jid).values(screening=screen))
    return jid, new


def batch(
    c: Connection, owner: UUID, key: bytes, limit: int = 25, job_id: UUID | None = None
) -> int:
    lock(c, owner)
    if not dispatch(c):
        return 0
    q = select(jobs.c.id, jobs.c.canonical).where(jobs.c.canonical.is_not(None))
    if job_id:
        q = q.where(jobs.c.id == job_id)
    else:
        q = q.where(
            jobs.c.screening.is_(None)
            | (jobs.c.screening["assessed_on"].astext < func.to_char(func.now(), "YYYY-MM-DD"))
        )
    rows = c.execute(q.order_by(jobs.c.id).limit(limit)).all()
    if job_id and not rows:
        raise HTTPException(404, "No canonical intake for this job.")
    for jid, f in rows:
        c.execute(
            update(jobs)
            .where(jobs.c.id == jid)
            .values(screening=evaluate(c, owner, key, f).model_dump(mode="json"))
        )
    return len(rows)


def invalidate(c: Connection, owner: UUID, key: bytes) -> None:
    lock(c, owner)
    c.execute(update(jobs).where(jobs.c.canonical.is_not(None)).values(screening=None))
    batch(c, owner, key)
