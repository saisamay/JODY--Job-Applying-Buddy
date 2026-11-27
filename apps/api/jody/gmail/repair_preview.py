"""Explicit, owner-local, one-receipt dry run. No list/history endpoint or storage writer."""

import argparse
import json
import os
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select

from ..career.knowledge import unpack
from ..config import runtime_url
from ..local_providers import load
from ..provider_check import operator_session
from ..security import PRIVATE_OWNER, digest, encryption_key, runtime_engine, tenant
from ..tables import gmail_accounts, gmail_evidence, gmail_messages
from .extract import RELEVANT, Posting, body, classify, headers
from .google import Mailbox
from .platforms import parse
from .service import Policy, gate, lock


def preview(receipt: UUID) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    if runtime_url().host not in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit("Choose the local restricted database.")
    db = runtime_engine()
    try:
        with operator_session(), tenant(db, PRIVATE_OWNER) as c:
            gate(c)
            lock(c, PRIVATE_OWNER)
            row = c.execute(select(gmail_accounts)).mappings().one()
            policy = Policy.model_validate(row["policy"])
            key = c.scalar(
                select(gmail_messages.c.message_key).where(
                    gmail_messages.c.id == receipt,
                    gmail_messages.c.account_key == digest(row["account"] or ""),
                )
            )
            if not key or not row["grant"]:
                raise SystemExit("No matching connected-account receipt.")
            mail = Mailbox(
                unpack(encryption_key(), PRIVATE_OWNER, "gmail:refresh", row["grant"]).decode()
            )

            def allowed(msg: dict[str, Any]) -> bool:
                sender, subject, trusted = headers(msg)
                return bool(
                    trusted
                    and sender in policy.senders
                    and sender.endswith("@linkedin.com")
                    and policy.subject.casefold() in subject.casefold()
                    and (not policy.label or policy.label in msg.get("labelIds", []))
                )

            path = "messages/" + key
            if not allowed(mail.get(path, format="metadata")):
                raise SystemExit("Current policy excludes this message.")
            msg = mail.get(path, format="full")
            sender, subject, trusted = headers(msg)
            content = body(msg.get("payload", {}))
            if not allowed(msg) or classify(subject, content, trusted) not in RELEVANT:
                raise SystemExit("Source requires review.")
            old = c.execute(
                select(gmail_evidence.c.job_id, gmail_evidence.c.facts).where(
                    gmail_evidence.c.message_id == receipt
                )
            ).all()
            for v, _ in parse("linkedin.com", msg["payload"], content):
                matches = [
                    (jid, facts)
                    for jid, facts in old
                    if facts.get("title", "").casefold() == v.title.casefold()
                ]
                proposals.append(
                    {
                        "proposed_job_fields": v.model_dump(exclude_none=True),
                        "same_title_existing_jobs": [str(jid) for jid, _ in matches],
                        "proposed_additions_by_job": {
                            str(jid): {
                                field: val
                                for field, val in v.model_dump(exclude_none=True).items()
                                if not facts.get(field)
                            }
                            for jid, facts in matches
                        },
                    }
                )
                for jid, facts in matches:
                    fields = [k for k, val in v.model_dump().items() if val and not facts.get(k)]
                    print(
                        "Candidate",
                        jid,
                        "additional fields",
                        ", ".join(fields) or "none",
                        "same-title candidates",
                        len(matches),
                        "platform identity available",
                        isinstance(v, Posting),
                    )
                if not matches:
                    print("Unmapped card requires owner review.")
    finally:
        db.dispose()
    return proposals


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=UUID, required=True)
    parser.add_argument("--authorized-read", required=True, action="store_true")
    parser.add_argument(
        "--private-report",
        action="store_true",
        help="Write proposed job fields to a new owner-only file outside Git.",
    )
    args = parser.parse_args()
    load()
    proposals = preview(args.receipt)
    if args.private_report:
        directory = Path.home() / ".config/jody"
        if (
            directory.is_symlink()
            or directory.stat().st_uid != os.getuid()
            or directory.stat().st_mode & 0o077
        ):
            raise SystemExit("Private report directory requires owner-only permissions.")
        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", prefix="gmail-review-", suffix=".json", dir=directory, delete=False
        ) as f:
            json.dump(proposals, f, ensure_ascii=False, indent=2)
            print("Private proposed job fields:", f.name)
