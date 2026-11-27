"""Local trust rubric. Only the operator policy and separately obtained evidence can corroborate claims."""

import re
from datetime import UTC, date, datetime
from difflib import SequenceMatcher
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel

from .career.matching import INSTRUCTION
from .gmail.extract import safe_url

VERSION = "trust-1"
State = Literal[
    "trusted", "needs_review", "high_risk", "confirmed_scam", "insufficient", "not_assessed"
]


class Signal(BaseModel):
    code: str
    kind: Literal["verified", "claim", "risk", "unknown"]
    severity: Literal["info", "context", "high", "critical"] = "info"
    points: int = 0
    explanation: str
    reference: str


class Assessment(BaseModel):
    state: State
    score: int
    threshold: int
    coverage: int
    confidence: Literal["low", "medium", "high"]
    signals: list[Signal]
    version: str = VERSION
    assessed_at: datetime
    review: str | None = None


FEES = re.compile(
    r"\b(?:pay|send|transfer|submit|require[ds]?|charge[ds]?)\b[^.!?\n]{0,65}\b(?:fees?|deposit|security payment)\b|\b(?:recruitment fee|security deposit|application fee|training fee)\b[^.!?\n]{0,35}\b(?:required|mandatory|payable)\b",
    re.I,
)
FINANCE = re.compile(
    r"\b(?:send|share|provide|submit|enter)\b[^.!?\n]{0,80}\b(?:bank (?:account|details|password)|credit card|debit card|card number|PIN number|OTP|one.time password|routing number)\b",
    re.I,
)
NEGATION = re.compile(r"\b(?:never|no|do not|don't|will not|won't|without)\b", re.I)
FREE = {"gmail.com", "outlook.com", "hotmail.com", "yahoo.com", "proton.me", "protonmail.com"}


def hostname(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def same_site(host: str, domain: str) -> bool:
    return bool(domain and (host == domain or host.endswith("." + domain)))


def rubric(
    f: dict[str, Any],
    sightings: list[tuple[str, dict[str, Any]]],
    official: str,
    proof: dict[str, Any],
    blocked: bool,
    threshold: int,
    review: str | None = None,
    overflow: bool = False,
) -> Assessment:
    signals: list[Signal] = []

    def mark(
        code: str,
        kind: Literal["verified", "claim", "risk", "unknown"],
        points: int,
        msg: str,
        ref: str,
        severity: Literal["info", "context", "high", "critical"] = "info",
    ) -> None:
        if not any(s.code == code for s in signals):
            signals.append(
                Signal(
                    code=code,
                    kind=kind,
                    points=points,
                    explanation=msg,
                    reference=ref,
                    severity=severity,
                )
            )

    company = f.get("company") or ""
    link = f.get("posting_url") or f.get("application_url") or ""
    host = hostname(link)
    if company:
        mark("named_company", "claim", 0, "Source names an employer.", "job.company")
    if official:
        mark(
            "official_identity",
            "verified",
            30,
            "Employer domain independently identified.",
            proof.get("domain_ref", "operator employer policy"),
        )
    else:
        mark(
            "official_identity",
            "unknown",
            0,
            "Official employer identity has no independent confirmation.",
            "job.company",
        )
    aligned = same_site(host, official) and bool(safe_url(link))
    if aligned:
        mark(
            "career_alignment",
            "verified",
            10,
            "Posting URL belongs to the established employer domain.",
            "job.posting_url",
        )
    if aligned and proof.get("posting") == link:
        mark(
            "vacancy_confirmed",
            "verified",
            40,
            "Exact role and vacancy were corroborated on the official employer site.",
            proof.get("posting_ref", "owner review"),
        )
    else:
        mark(
            "vacancy_confirmed",
            "unknown",
            0,
            "The vacancy has not been corroborated on the employer site.",
            "job.posting_url",
        )
    reg = proof.get("registered")
    if reg:
        age = (datetime.now(UTC).date() - date.fromisoformat(reg)).days
        mark("registration", "verified", 0, "Registry creation date: " + reg, "RDAP registry")
        if age < 180:
            mark(
                "young_domain",
                "risk",
                -4,
                "Recently registered employer domain; contextual indicator only.",
                "RDAP registry",
                "context",
            )
    else:
        mark("registration", "unknown", 0, "Registration information unavailable.", "RDAP")
    for ref, raw in [("canonical job", f), *sightings]:
        if ref.startswith("gmail:") and raw.get("platform_job_id"):
            mark(
                "authorized_posting",
                "verified",
                10,
                "Authorized Gmail evidence contains a platform posting identifier.",
                ref,
            )
        email = (raw.get("recruiter_email") or "").casefold()
        if email and "@" in email:
            domain = email.rsplit("@", 1)[1]
            if domain in FREE:
                mark(
                    "webmail", "risk", -4, "Recruiter uses a public email service.", ref, "context"
                )
            elif same_site(domain, official):
                mark(
                    "recruiter_alignment",
                    "claim",
                    10,
                    "Source recruiter address matches the independently established domain; mailbox ownership is unverified.",
                    ref,
                )
            elif official:
                mark(
                    "recruiter_mismatch",
                    "risk",
                    -15,
                    "Recruiter domain differs from the official employer domain.",
                    ref,
                    "context",
                )
        for k in ("source_url", "posting_url", "application_url", "domain"):
            u = raw.get(k)
            if not isinstance(u, str) or not u:
                continue
            h = hostname(u) if k != "domain" else u.lower()
            if k != "domain" and not safe_url(u):
                mark(
                    "unsafe_url",
                    "risk",
                    -20,
                    "Source URL does not meet public HTTPS safety rules.",
                    ref,
                    "high",
                )
            if official and h and not same_site(h, official):
                if (
                    h.startswith(official + ".")
                    or h.startswith("xn--")
                    or SequenceMatcher(None, h.removeprefix("www."), official).ratio() >= 0.82
                ):
                    mark(
                        "lookalike",
                        "risk",
                        -30,
                        "Source hostname resembles the official employer domain without belonging to it.",
                        ref,
                        "high",
                    )
                elif k == "domain":
                    mark(
                        "identity_conflict",
                        "risk",
                        -20,
                        "Claimed company domain conflicts with the established employer identity.",
                        ref,
                        "high",
                    )
        desc = raw.get("description") or ""
        for sentence in re.split(r"(?<=[.!?])\s+|[;\n]|\bbut\b", desc, flags=re.I):
            for code, pattern, reason in [
                ("payment_demand", FEES, "A recruitment payment is requested."),
                (
                    "financial_data",
                    FINANCE,
                    "The source requests sensitive financial or authentication information.",
                ),
            ]:
                for match in pattern.finditer(sentence):
                    if NEGATION.search(sentence[max(0, match.start() - 28) : match.start() + 1]):
                        continue
                    mark(code, "risk", -45, reason, ref, "critical")
            if re.search(r"\b(?:telegram|whatsapp|signal)\b", sentence, re.I) and re.search(
                r"\b(?:only|must|immediately|urgent|within \d+ hours?)\b", sentence, re.I
            ):
                mark(
                    "off_platform_pressure",
                    "risk",
                    -15,
                    "The posting pressures applicants to use an off-platform channel.",
                    ref,
                    "context",
                )
            if re.search(
                r"\b(?:act now|last chance|respond immediately|within \d+ (?:hours|minutes))\b",
                sentence,
                re.I,
            ):
                mark(
                    "urgency",
                    "risk",
                    -5,
                    "Source uses unusually time-pressured language.",
                    ref,
                    "context",
                )
            if INSTRUCTION.search(sentence):
                mark(
                    "untrusted_instruction",
                    "risk",
                    -15,
                    "The source contains instructions aimed at the evaluator.",
                    ref,
                    "high",
                )
    if not any(s.code in {"webmail", "recruiter_alignment", "recruiter_mismatch"} for s in signals):
        mark(
            "recruiter",
            "unknown",
            0,
            "Recruiter identity is uncorroborated.",
            "job.recruiter_email",
        )
    if blocked:
        mark(
            "blocklist",
            "risk",
            0,
            "An owner blocklist entry applies.",
            "tenant blocklist",
            "critical",
        )
    if overflow or f.get("ambiguous"):
        mark(
            "conflicting_evidence",
            "risk",
            0,
            "Source evidence is conflicting or exceeds the bounded review window.",
            "source observations",
            "high",
        )
    score = max(0, min(100, sum(s.points for s in signals)))
    coverage = (
        sum(
            any(s.code in codes and s.kind != "unknown" for s in signals)
            for codes in [
                {"official_identity"},
                {"vacancy_confirmed"},
                {"registration"},
                {"webmail", "recruiter_mismatch", "recruiter_alignment"},
                {"career_alignment", "authorized_posting"},
            ]
        )
        * 20
    )
    adequate = bool(aligned and proof.get("posting") == link and official)
    state: State = "insufficient"
    if review == "confirmed_scam":
        state = "confirmed_scam"
    elif review == "block" or any(s.severity in {"critical", "high"} for s in signals):
        state = "high_risk"
    elif review == "skip":
        state = "needs_review"
    elif adequate and (score >= threshold or review == "approve"):
        state = "trusted"
    elif adequate or any(s.kind == "risk" for s in signals):
        state = "needs_review"
    return Assessment(
        state=state,
        score=score,
        threshold=threshold,
        coverage=coverage,
        confidence="high" if adequate and coverage >= 80 else "medium" if adequate else "low",
        signals=signals,
        review=review,
        assessed_at=datetime.now(UTC),
    )
