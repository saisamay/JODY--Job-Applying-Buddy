"""Explicit, owner-local, one-receipt dry run. No list/history endpoint or storage writer."""

import argparse
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


def preview(receipt: UUID) -> None:
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=UUID, required=True)
    parser.add_argument("--authorized-read", required=True, action="store_true")
    args = parser.parse_args()
    load()
    preview(args.receipt)
