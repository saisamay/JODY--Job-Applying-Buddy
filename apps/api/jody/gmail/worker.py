"""Each transaction checkpoints one filtered page or one message."""

import json
import logging
import random
import re
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import Request
from sqlalchemy import Connection, Engine, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..career.knowledge import unpack
from ..job_pipeline import ingest
from ..routes import Owner
from ..security import digest, tenant
from ..tables import (
    gmail_evidence,
    gmail_messages,
    jobs,
    users,
)
from ..tables import gmail_runs as runs
from . import google
from .extract import RELEVANT, Json, Posting, Vacancy, body, classify, headers
from .models import assisted
from .platforms import parse
from .service import GmailStatus, Policy, account, change, enqueue, gate, lock, status
from .service import router as router


def store(
    c: Connection,
    owner: UUID,
    mid: UUID,
    platform: str,
    slot: int,
    v: Vacancy,
    review: bool,
    key: bytes,
) -> bool:
    url = v.application_url
    # Generic careers pages are not vacancy identifiers.
    specific = url and re.search(
        r"/(?:jobs?|positions?|openings?|vacancies|view)/(?:view/)?[a-z0-9_-]*[0-9][a-z0-9_-]*(?:[/?]|$)|[?&](?:jobid|gh_jid|jk)=[^&]+",
        url,
        re.I,
    )
    identity: list[object] = ["url", url] if specific else ["message", str(mid), slot]
    if isinstance(v, Posting):
        identity = ["platform", platform, v.platform_job_id]
    fingerprint = digest(json.dumps(["gmail", identity]))
    jid, new = ingest(
        c,
        owner,
        key,
        "gmail",
        platform,
        v.description or "",
        v.posting_url if isinstance(v, Posting) else url,
        v.model_dump(exclude_none=True),
        json.dumps([str(mid), slot]),
        fingerprint,
    )
    alternatives = []
    if not specific and not isinstance(v, Posting):
        candidates = (
            select(gmail_evidence.c.job_id)
            .join(jobs, gmail_evidence.c.job_id == jobs.c.id)
            .where(
                gmail_evidence.c.platform == platform,
                jobs.c.id != jid,
                func.lower(jobs.c.role) == v.title.lower(),
                jobs.c.source_url.is_(None),
                gmail_evidence.c.facts["company"].astext == v.company,
                gmail_evidence.c.facts["location"].astext == v.location,
                gmail_evidence.c.facts["requisition"].astext == v.requisition,
            )
        )
        alternatives = [str(candidate) for candidate in c.scalars(candidates.distinct().limit(100))]
    c.execute(
        pg_insert(gmail_evidence)
        .values(
            user_id=owner,
            message_id=mid,
            job_id=jid,
            platform=platform,
            needs_review=review,
            facts={
                **v.model_dump(exclude_none=True),
                "possible_duplicates": alternatives,
                "extraction_confidence": "needs_review" if review else "explicit_fields",
            },
        )
        .on_conflict_do_nothing()
        .returning(gmail_evidence.c.id)
    )
    return new


def process(
    db: Engine,
    c: Connection,
    owner: UUID,
    key: bytes,
    mail: google.Mailbox,
    account_key: str,
    msg: str,
    policy: Policy,
    n: Json,
) -> None:
    seen = c.scalar(
        select(gmail_messages.c.id).where(
            gmail_messages.c.account_key == account_key, gmail_messages.c.message_key == msg
        )
    )
    if seen:
        return
    try:
        message = mail.get("messages/" + msg, format="full")
    except google.Problem as exc:
        if exc.status == 404:
            return
        raise
    sender, subject, trusted = headers(message)
    n["examined"] += 1
    if (
        sender not in policy.senders
        or policy.label
        and policy.label not in message.get("labelIds", [])
    ):
        return
    content = body(message.get("payload", {}))
    category = classify(subject, content, trusted)
    rows = (
        parse(sender.split("@")[-1], message.get("payload", {}), content)
        if category in RELEVANT
        else []
    )
    if not rows and category in RELEVANT and policy.providers and content:
        answer = assisted(db, c, owner, key, list(policy.providers), content, n)
        category = answer.classification
        rows = [(v, True) for v in answer.vacancies] if category in RELEVANT else []
    elif (
        len(rows) == 1
        and rows[0][0]._card_excerpt
        and policy.providers
        and (not rows[0][0].company or not rows[0][0].location)
    ):
        original, unsafe = rows[0]
        # A single candidate has no competing card for a model to splice fields from.
        try:
            proposal = assisted(
                db, c, owner, key, list(policy.providers), original._card_excerpt, n
            )
        except google.Problem:
            rows = [(original, True)]
        else:
            matches = [v for v in proposal.vacancies if v.title == original.title]
            if len(matches) == 1 and len(proposal.vacancies) == 1:
                additions = {
                    k: value
                    for k, value in matches[0].model_dump(exclude_none=True).items()
                    if k in {"company", "location", "employment_type", "work_mode"}
                    and not getattr(original, k)
                }
                rows = [(original.model_copy(update=additions), unsafe or bool(additions))]
    mid = c.execute(
        insert(gmail_messages)
        .values(user_id=owner, message_key=msg, account_key=account_key, classification=category)
        .returning(gmail_messages.c.id)
    ).scalar_one()
    n["relevant"] += int(category in RELEVANT)
    n["review"] += int(not rows and category in RELEVANT | {"Unknown / needs review", "Suspicious"})
    seen_cards: set[str] = set()
    for slot, (v, unsafe) in enumerate(rows):
        signature = v.model_dump_json()
        if signature in seen_cards and (
            isinstance(v, Posting) or v.application_url or v.requisition
        ):
            n["duplicates"] += 1
            continue
        seen_cards.add(signature)
        review = unsafe or not (v.company and (v.application_url or isinstance(v, Posting)))
        new = store(c, owner, mid, sender.split("@")[1], slot, v, review, key)
        n["extracted"] += 1
        n["stored" if new else "duplicates"] += 1
        n["review"] += int(review)


def finish(c: Connection, owner: UUID, rid: UUID, p: Json, n: Json) -> None:
    change(
        c,
        owner,
        history_id=p["target"],
        last_success=func.now(),
        state="Last synchronization successful",
    )
    c.execute(
        update(runs)
        .where(runs.c.id == rid)
        .values(status="succeeded", finished=func.now(), progress={}, counts=n)
    )


def step(
    db: Engine,
    owner: UUID,
    key: bytes,
    clients: dict[bytes, google.Mailbox] | None = None,
    run_id: UUID | None = None,
) -> bool:
    with tenant(db, owner) as c:
        gate(c)
        lock(c, owner)
        if not c.scalar(select(users.c.is_active)):
            return False
        row = account(c, owner)
        run = (
            c.execute(
                select(runs).where(
                    runs.c.status.in_(("pending", "retry")), runs.c.due <= func.now()
                )
            )
            .mappings()
            .first()
        )
        if not run or (run_id is not None and run_id != run["id"]) or not row["grant"]:
            return False
        policy = Policy.model_validate(row["policy"])
        p = dict(run["progress"])
        n = dict(run["counts"]) or dict.fromkeys(
            (
                "examined",
                "relevant",
                "extracted",
                "stored",
                "duplicates",
                "review",
                "failures",
                "gmail_requests",
                "cursor_recoveries",
            ),
            0,
        )
        match = runs.c.id == run["id"]
        mail = None
        try:
            if p.get("complete") and not p.get("ids"):
                finish(c, owner, run["id"], p, n)
                return False
            grant = bytes(row["grant"])
            mail = clients.get(grant) if clients is not None else None
            if mail is None:
                mail = google.Mailbox(unpack(key, owner, "gmail:refresh", grant).decode())
                if clients is not None:
                    clients.clear()
                    clients[grant] = mail
            mail.calls = 0
            if p.get("ids"):
                msg = p["ids"][0]
                process(db, c, owner, key, mail, digest(row["account"]), msg, policy, n)
                p["ids"] = p["ids"][1:]
            elif not p and row["history_id"]:
                try:
                    delta = mail.get(
                        "history",
                        startHistoryId=row["history_id"],
                        historyTypes=["messageAdded", "labelAdded"],
                        labelId=policy.label or None,
                        maxResults=10,
                    )
                except google.Problem as exc:
                    if exc.status != 404:
                        raise
                    n["cursor_recoveries"] += 1
                    change(c, owner, history_id=None)
                else:
                    history = delta.get("history", [])
                    changed = {
                        item["message"]["id"]
                        for h in history
                        for field in ("messagesAdded", "labelsAdded")
                        for item in h.get(field, [])
                    }
                    target = (
                        history[-1]["id"]
                        if history and delta.get("nextPageToken")
                        else delta["historyId"]
                    )
                    p = dict(target=target, changed=list(changed), complete=not changed)
            else:
                if not p:
                    p = dict(
                        target=mail.get("profile")["historyId"],
                        after=int(time.time()) - policy.days * 86400,
                        remaining=policy.limit,
                    )
                q = "{" + " ".join("from:" + s for s in policy.senders) + "}"
                if policy.subject:
                    q += ' subject:"' + policy.subject + '"'
                if "after" in p:
                    q += " after:" + str(p["after"])
                page = mail.get(
                    "messages",
                    q=q,
                    labelIds=policy.label or None,
                    maxResults=min(100, p.get("remaining", 100)),
                    pageToken=p.get("page"),
                )
                ids = [m["id"] for m in page.get("messages", [])]
                if "changed" in p:
                    wanted = set(p["changed"])
                    ids = [i for i in ids if i in wanted]
                    p["changed"] = list(wanted.difference(ids))
                else:
                    p["remaining"] -= len(ids)
                p.update(ids=ids, page=page.get("nextPageToken"))
                p["complete"] = not p["page"] or p.get("remaining") == 0 or p.get("changed") == []
        except google.Problem as exc:
            n["gmail_requests"] += mail.calls if mail else 0
            attempts = run["attempts"] + 1
            retry = attempts < 4 and exc.state in {"Rate limited", "Temporarily unavailable"}
            n["failures"] += 1
            change(c, owner, state=exc.state)
            c.execute(
                update(runs)
                .where(match)
                .values(
                    status="retry" if retry else "failed",
                    attempts=attempts,
                    due=datetime.now(UTC)
                    + timedelta(seconds=30 * 2**attempts + random.uniform(0, 10)),
                    counts=n,
                )
            )
            return False
        n["gmail_requests"] += mail.calls
        if p.get("complete") and not p.get("ids"):
            finish(c, owner, run["id"], p, n)
            return False
        c.execute(
            update(runs).where(match).values(progress=p, counts=n, status="pending", attempts=0)
        )
        logging.getLogger("jody.http").info(json.dumps({"event": "gmail_checkpoint", "counts": n}))
        return True


@router.post("/sync")
def sync(request: Request, owner: Owner) -> GmailStatus:
    run_id = enqueue(request.app.state.db, owner)
    clients: dict[bytes, google.Mailbox] = {}
    for _ in range(6):
        if not step(request.app.state.db, owner, request.app.state.secret_key, clients, run_id):
            break
    with tenant(request.app.state.db, owner) as c:
        return status(c)
