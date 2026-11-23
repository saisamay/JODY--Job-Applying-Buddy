"""Source snapshots and optimistic, append-only review of extracted claims."""

import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import Connection, insert, select, text

from ..security import seal, unseal
from ..tables import career_sources as sources
from ..tables import career_versions as versions

Json = dict[str, Any]
HEADINGS = {
    "education": "education",
    "degrees": "education",
    "work experience": "employment",
    "professional experience": "employment",
    "employment history": "employment",
    "work history": "employment",
    "professional background": "employment",
    "internship experience": "internship",
    "research experience": "research",
    "research projects": "research",
    "academic projects": "project",
    "awards and achievements": "achievement",
    "licenses and certifications": "certification",
    "employment": "employment",
    "experience": "employment",
    "internships": "internship",
    "skills": "skill",
    "technical skills": "skill",
    "technologies": "technology",
    "projects": "project",
    "selected projects": "project",
    "research": "research",
    "publications": "publication",
    "achievements": "achievement",
    "awards": "achievement",
    "accomplishments": "accomplishment",
    "certifications": "certification",
    "work authorization": "eligibility",
    "eligibility": "eligibility",
    "dates": "date",
}
RESUME_KINDS = {"tex", "pdf", "docx", "resume_text"}


def pack(key: bytes, user: UUID, context: str, value: bytes) -> bytes:
    return b"".join(seal(key, user, context, value))


def unpack(key: bytes, user: UUID, context: str, value: bytes) -> bytes:
    return unseal(key, user, context, value[:12], value[12:])


def lock(conn: Connection, owner: UUID) -> None:
    conn.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:name,0))"),
        {"name": "career:" + str(owner)},
    )


def fact_key(kind: str, quote: str) -> str:
    # An explicit label identifies an attribute across variants. Otherwise compare
    # statements with differing dates/metrics and preserve distinct observations.
    label = quote.split(":", 1)[0] if ":" in quote else quote
    label = re.sub(r"\b(?:19|20)\d\d\b|\d+(?:\.\d+)?%?", " ", label.casefold())
    if kind == "eligibility":
        label = re.sub(r"\b(not|currently|no|active)\b", " ", label)
    return kind + "/" + " ".join(re.findall(r"\w+", label))


def parse_facts(data: bytes, kind: str, sid: UUID) -> list[Json]:
    try:
        proc = subprocess.run(
            [sys.executable, "-I", str(Path(__file__).with_name("parser.py")), kind],
            input=data,
            env={},
            capture_output=True,
            timeout=10,
            check=True,
        )
    except (subprocess.SubprocessError, OSError):
        raise HTTPException(
            422, "Cannot extract bounded text. Supply a text-readable source."
        ) from None
    group = {"github": "project", "portfolio": "project", "portfolio_html": "statement"}.get(
        kind, "statement"
    )
    output: list[Json] = []
    for i, line in enumerate(proc.stdout.decode().splitlines(), 1):
        quote = " ".join(line.strip(" \t•-*").split())
        if not quote:
            continue
        heading, sep, rest = quote.partition(":")
        if heading.casefold() in HEADINGS:
            group = HEADINGS[heading.casefold()]
            if not sep or not rest.strip():
                continue
        if len(quote) > 2000 or len(output) >= 350:
            raise HTTPException(422, "Source requires shorter sections before review.")
        output.append(
            {
                "id": f"{sid}/{i}",
                "source_id": str(sid),
                "line": i,
                "category": group,
                "quote": quote,
                "dates": re.findall(
                    r"\b(?:Jan(?:uary)? |Feb(?:ruary)? |Mar(?:ch)? |Apr(?:il)? |May |Jun(?:e)? |Jul(?:y)? |Aug(?:ust)? |Sep(?:tember)? |Oct(?:ober)? |Nov(?:ember)? |Dec(?:ember)? )?(?:19|20)\d{2}(?:-\d{2}(?:-\d{2})?)?\b",
                    quote,
                    re.I,
                ),
                "key": fact_key(
                    group, rest.strip() if sep and heading.casefold() in HEADINGS else quote
                ),
            }
        )
    if not output:
        raise HTTPException(422, "Source has no reviewable statements.")
    return output


def snapshot(
    conn: Connection, owner: UUID, key: bytes, kind: str, label: str, reference: str, data: bytes
) -> Json:
    if not 0 < len(data) <= 5 * 1024**2:
        raise HTTPException(413, "Source must be between one byte and 5 MiB.")
    lock(conn, owner)
    fingerprint = hashlib.sha256(
        json.dumps([kind, label, reference, hashlib.sha256(data).hexdigest()]).encode()
    ).hexdigest()
    prior = conn.scalar(select(sources.c.id).where(sources.c.fingerprint == fingerprint))
    if prior:
        return {"source_id": str(prior)}
    sid = uuid4()
    facts = parse_facts(data, kind, sid)
    document = {"label": label, "reference": reference, "kind": kind, "facts": facts}
    conn.execute(
        insert(sources).values(
            user_id=owner,
            id=sid,
            kind=kind,
            fingerprint=fingerprint,
            original=pack(key, owner, f"original:{sid}", data),
            extraction=pack(key, owner, f"extract:{sid}", json.dumps(document).encode()),
        )
    )
    return {"source_id": str(sid)}


def knowledge(conn: Connection, owner: UUID, key: bytes, revision: int | None = None) -> Json:
    query = select(versions).order_by(versions.c.revision.desc()).limit(1)
    if revision is not None:
        query = query.where(versions.c.revision == revision)
    row = conn.execute(query).mappings().first()
    if revision and not row:
        raise HTTPException(404, "Unknown profile revision.")
    decisions = row["decisions"] if row else {}
    docs: list[Json] = []
    facts: dict[str, Json] = {}
    groups: dict[str, list[Json]] = {}
    entries = select(sources.c.id, sources.c.extraction).order_by(
        sources.c.created_at, sources.c.id
    )
    if revision is not None:
        if row is None:
            return {"revision": 0, "sources": [], "facts": {}, "conflicts": [], "decisions": {}}
        entries = entries.where(sources.c.id.in_(row["decisions"]["sources"]))
    for sid, blob in conn.execute(entries):
        doc = json.loads(unpack(key, owner, f"extract:{sid}", blob))
        items = doc.pop("facts")
        docs.append({"id": str(sid), **doc})
        for f in items:
            state = decisions.get("states", {}).get(f["id"], "pending")
            facts[f["id"]] = {**f, "reference": doc["reference"], "state": state}
            if state != "rejected":
                groups.setdefault(f["key"], []).append(f)
    conflicts = [
        [f["id"] for f in group]
        for group in groups.values()
        if len({f["quote"].casefold() for f in group}) > 1
        and len({f["source_id"] for f in group}) > 1
    ]
    return {
        "revision": row["revision"] if row else 0,
        "sources": docs,
        "facts": facts,
        "conflicts": conflicts,
        "decisions": decisions.get("states", {}),
    }


def review(
    conn: Connection, owner: UUID, key: bytes, expected: int, changes: Mapping[str, str]
) -> Json:
    lock(conn, owner)
    state = knowledge(conn, owner, key)
    if state["revision"] != expected:
        raise HTTPException(409, "Reload the current career profile.")
    if not changes.keys() <= state["facts"].keys():
        raise HTTPException(422, "Unknown source fact.")
    states = state["decisions"] | dict(changes)
    active: dict[str, list[Json]] = {}
    for f in state["facts"].values():
        if states.get(f["id"]) != "rejected":
            active.setdefault(f["key"], []).append(f)
    for group in active.values():
        if (
            len({f["source_id"] for f in group}) > 1
            and len({f["quote"].casefold() for f in group}) > 1
            and any(changes.get(f["id"]) == "verified" for f in group)
        ):
            raise HTTPException(409, "Explicitly reject competing facts in the same review.")
    revision = expected + 1
    conn.execute(
        insert(versions).values(
            user_id=owner,
            revision=revision,
            decisions={"states": states, "sources": [s["id"] for s in state["sources"]]},
        )
    )
    return {"revision": revision}


def verified(state: Json) -> list[Json]:
    disputed = {i for group in state["conflicts"] for i in group}
    return [f for i, f in state["facts"].items() if f["state"] == "verified" and i not in disputed]
