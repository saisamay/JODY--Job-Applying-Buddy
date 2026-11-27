"""Deterministic, local job screening. Input text is evidence, never an instruction."""

import re
from datetime import UTC, date, datetime
from typing import Any, Literal
from urllib.parse import urlsplit

from fastapi import HTTPException
from pydantic import BaseModel

from .career.inference import terms
from .career.matching import INSTRUCTION, OPTIONAL, YEARS, job_clauses
from .gmail.extract import FIELDS, safe_url
from .gmail.platforms import posting

Facts = dict[str, Any]
Decision = Literal[
    "eligible",
    "needs_review",
    "ineligible",
    "outside_preferences",
    "expired_or_closed",
    "blocklisted",
]
Code = Literal[
    "blocked_source",
    "closed",
    "expired",
    "experience",
    "graduation",
    "education",
    "authorization",
    "location_requirement",
    "excluded_role",
    "role",
    "employment",
    "location",
    "work_mode",
    "salary",
    "missing",
    "ambiguous",
    "skills",
    "legacy",
    "duplicate",
]


class Reason(BaseModel):
    code: Code
    outcome: Literal["hard", "review", "preference", "excluded", "closed"]
    evidence: str
    explanation: str


class Screening(BaseModel):
    decision: Decision
    mandatory: Literal["incompatible", "unknown", "no_known_conflict"]
    preference: Literal["outside", "aligned", "unspecified"]
    inferred_roles: list[str]
    reasons: list[Reason]
    missing: list[str]
    assessed_on: date


LABELS = {
    **FIELDS,
    "title": "title",
    "role": "title",
    "job title": "title",
    "company domain": "domain",
    "country": "country",
    "posting status": "posting_status",
    "status": "posting_status",
    "required location": "required_location",
    "work authorization required": "authorization",
    "recruiter email": "recruiter_email",
    "minimum experience": "minimum_experience",
    "required education": "required_education",
    "eligible graduation year": "graduation_year",
    "posting url": "posting_url",
}
PATTERNS = {
    "backend": r"\b(backend|back.end|python api|rest(?:ful)? apis?|server.side|api development)\b",
    "ai/ml": r"\b(ai|ml|machine learning|train(?:ing)? models?|deep learning|neural networks?|generative ai)\b",
    "mobile": r"\b(mobile|flutter|android|ios)\b",
    "full stack": r"\b(mern|full.stack|frontend and backend|web development)\b",
    "data analytics": r"\b(data analy\w+|business intelligence|analytical dashboards)\b",
}


def categories(text: str) -> set[str]:
    return {k for k, v in PATTERNS.items() if re.search(v, text, re.I)}


def normalize(description: str, source: str | None, supplied: Facts) -> Facts:
    facts: Facts = {}
    for line in description.splitlines():
        label, sep, value = line.partition(":")
        field = LABELS.get(label.casefold().strip())
        if sep and field and value.strip() and not INSTRUCTION.search(line):
            if field in facts and facts[field] != value.strip():
                facts["ambiguous"] = True
            facts.setdefault(field, value.strip())
    facts.update({k: v for k, v in supplied.items() if v is not None})
    # The existing career analyzer bounds the number and length of clauses.
    try:
        prose = "\n".join(
            line
            for line in description.splitlines()
            if line.partition(":")[0].strip().casefold() not in LABELS or ":" not in line
        )
        role, clauses = job_clauses(prose, facts.get("title"))
    except HTTPException:
        role, clauses = None, []
        facts["ambiguous"] = True
    if INSTRUCTION.search(description):
        facts["ambiguous"] = True
    if role and not INSTRUCTION.search(role):
        facts.setdefault("title", role)
    if facts.get("title"):
        facts["normalized_title"] = " ".join(facts["title"].casefold().split())
    platform_ids = set()
    for k in ("posting_url", "application_url"):
        raw = facts.get(k) or (source if k == "posting_url" else None)
        if raw:
            clean = safe_url(raw)
            identity = posting(raw)
            if identity:
                clean = "https://www.linkedin.com/jobs/view/" + identity[0]
                platform_ids.add(identity[0])
                facts["platform_job_id"] = identity[0]
            if clean:
                facts[k] = clean
            else:
                facts.pop(k, None)
    if len(platform_ids) > 1:
        facts["ambiguous"] = True
        facts["identity_conflict"] = True
        facts.pop("platform_job_id", None)
    if "description" in facts and facts["description"] != description:
        try:
            _, extra = job_clauses(facts["description"], facts.get("title"))
            clauses.extend(c for c in extra if c not in clauses)
        except HTTPException:
            facts["ambiguous"] = True
    for clause in clauses:
        if clause["priority"] in ("required", "hard"):
            cohort = re.fullmatch(
                r"(?:must (?:graduate in|be (?:a )?graduate of)|class of|graduation year) (20\d{2})[.]?",
                clause["text"],
                re.I,
            )
            if cohort:
                facts.setdefault("graduation_year", cohort[1])
    facts["clauses"] = clauses
    facts["inferred_roles"] = sorted(
        categories(
            " ".join(
                [facts.get("title", "")]
                + [c["text"] for c in clauses if c["priority"] == "responsibility"]
            )
        )
    )
    for k in ("work_mode", "employment_type"):
        if k in facts:
            facts[k] = (
                facts[k].casefold().replace("on-site", "onsite").replace("full time", "full-time")
            )
    if facts.get("recruiter_email") and (
        len(facts["recruiter_email"]) > 254
        or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", facts["recruiter_email"])
    ):
        del facts["recruiter_email"]
    if facts.get("domain"):
        facts["domain"] = facts["domain"].strip().lower().rstrip(".")
    money = re.search(r"\b(USD|INR|EUR|GBP|CAD|AUD)\b", facts.get("compensation", ""), re.I)
    if money:
        facts["currency"] = money[1].upper()
    if description:
        facts.setdefault("description", description)
    return facts


def strong_keys(f: Facts) -> list[str]:
    if f.get("identity_conflict"):
        return []
    keys = []
    for field in ("posting_url", "application_url"):
        link = f.get(field)
        if not link:
            continue
        identity = posting(link)
        if identity:
            keys.append("linkedin:" + identity[0])
            continue
        u = urlsplit(link)
        # Workday exposes the employer requisition in the employer-scoped URL.
        wd = re.fullmatch(r"([a-z0-9-]+)\.wd\d+\.myworkdayjobs\.com", u.hostname or "")
        req = re.search(r"/job/(?:[^/]+/)*[^/]+_(R(?:EQ)?[-_]?\d+)/?$", u.path, re.I)
        if wd and req:
            keys.append(f"workday:{wd[1]}:{req[1].upper()}")
            continue
        if u.hostname in {"boards.greenhouse.io", "job-boards.greenhouse.io"}:
            m = re.fullmatch(r"/([\w-]+)/jobs/(\d+)/?", u.path)
            if m:
                keys.append(f"greenhouse:{m[1]}:{m[2]}")
                continue
        if re.search(
            r"/(?:jobs?|positions?|openings?|vacancies)/(?:view/)?[\w-]*\d[\w-]*/?$", u.path, re.I
        ) or re.search(r"(?:^|&)(?:gh_jid|jobid|jk)=[\w-]+(?:&|$)", u.query, re.I):
            keys.append("url:" + link)
    return sorted(set(keys))


def assess(f: Facts, profile: Facts, blocked: set[tuple[str, str]]) -> Screening:
    reasons = []
    today = datetime.now(UTC).date()

    def add(
        code: Code,
        outcome: Literal["hard", "review", "preference", "excluded", "closed"],
        evidence: str,
        explanation: str,
    ) -> None:
        reasons.append(
            Reason(code=code, outcome=outcome, evidence=evidence, explanation=explanation)
        )

    for kind, val in blocked:
        values = {
            "company": [f.get("company")],
            "email": [f.get("recruiter_email")],
            "domain": [
                f.get("domain"),
                *[urlsplit(f[k]).hostname for k in ("posting_url", "application_url") if f.get(k)],
            ],
        }[kind]
        if any(
            v and (v.casefold() == val or kind == "domain" and v.casefold().endswith("." + val))
            for v in values
        ):
            add("blocked_source", "excluded", val, "Matches a saved blocklist entry.")
    if f.get("posting_status", "").casefold() in {"closed", "expired", "filled"}:
        add("closed", "closed", f["posting_status"], "Source explicitly reports a closed posting.")
    if f.get("deadline"):
        try:
            if date.fromisoformat(f["deadline"]) < today:
                add("expired", "closed", f["deadline"], "The stated deadline has passed.")
        except ValueError:
            add("ambiguous", "review", f["deadline"], "Confirm the deadline format.")
    facet_codes: dict[str, Code] = {
        "education": "education",
        "location": "location_requirement",
        "eligibility": "authorization",
    }
    clauses = f.get("clauses", [])
    for facet, field in (
        ("experience", "minimum_experience"),
        ("education", "required_education"),
        ("location", "required_location"),
        ("eligibility", "authorization"),
    ):
        evidence = [
            c["text"]
            for c in clauses
            if c["priority"] in ("required", "hard") and c["facet"] == facet
        ]
        if f.get(field):
            evidence.append(str(f[field]))
        for value in dict.fromkeys(evidence):
            if OPTIONAL.search(value):
                continue
            if facet == "experience":
                match = YEARS.fullmatch(value.strip()) or re.fullmatch(
                    r"(?:at least |minimum |must have )?(\d+(?:\.\d+)?)\+? years?(?: of (?:total |professional |work )?experience)?[.]?",
                    value,
                    re.I,
                )
                available = profile.get("total_experience_years")
                if match and available is not None:
                    if available < float(match[1]):
                        add(
                            "experience",
                            "hard",
                            value,
                            "Declared total experience is below the explicit minimum.",
                        )
                else:
                    add(
                        "experience",
                        "review",
                        value,
                        "Confirm the scope and duration of the required experience.",
                    )
            else:
                if facet == "education" and any(
                    item.get("program", "") and item["program"].casefold() == value.casefold()
                    for item in profile.get("education") or []
                ):
                    continue
                if (
                    facet == "eligibility"
                    and profile.get("work_authorization", "").casefold() == value.casefold()
                ):
                    continue
                if facet == "location" and value.casefold() in [
                    v.casefold() for v in profile.get("preferred_locations") or []
                ]:
                    continue
                add(
                    facet_codes[facet],
                    "review",
                    value,
                    "Confirm the mandatory requirement against candidate evidence.",
                )
    year = f.get("graduation_year")
    if year and not OPTIONAL.search(str(year)):
        actual = profile.get("graduation_year")
        if actual is None or not re.fullmatch(r"\d{4}", year):
            add("graduation", "review", year, "Confirm the eligible graduation year.")
        elif str(actual) != year:
            add(
                "graduation",
                "hard",
                year,
                "Declared graduation year differs from the single eligible cohort.",
            )
    for name in ("experience", "education"):
        if f.get(name) and not OPTIONAL.search(f[name]):
            add("ambiguous", "review", f[name], "Confirm whether this qualification is mandatory.")
    for excluded in profile.get("excluded_roles") or []:
        if excluded.casefold() == f.get("normalized_title") or excluded.casefold() in f.get(
            "inferred_roles", []
        ):
            add("excluded_role", "excluded", excluded, "Matches an explicit role exclusion.")
    for key, pref, code in (
        ("employment_type", "employment_types", "employment"),
        ("location", "preferred_locations", "location"),
        ("work_mode", "work_modes", "work_mode"),
    ):
        if (
            f.get(key)
            and profile.get(pref)
            and f[key].casefold() not in [v.casefold() for v in profile[pref]]
        ):
            add(code, "preference", f[key], "Outside saved preferences; confirm flexibility.")  # type: ignore[arg-type]
    wanted = profile.get("preferred_roles") or []
    aligned = any(
        f.get(k) and profile.get(p) and f[k].casefold() in [v.casefold() for v in profile[p]]
        for k, p in (
            ("work_mode", "work_modes"),
            ("employment_type", "employment_types"),
            ("location", "preferred_locations"),
        )
    )
    if (
        wanted
        and all(categories(w) for w in wanted)
        and f.get("inferred_roles")
        and not (set(f["inferred_roles"]) & categories(" ".join(wanted)))
        and not any(terms(w) <= terms(f.get("title", "")) for w in wanted)
    ):
        add(
            "role",
            "preference",
            ", ".join(f["inferred_roles"]),
            "Inferred responsibilities fall outside the preferred role categories.",
        )
    if f.get("compensation") and profile.get("salary_expectations"):
        pattern = r"(USD|INR|EUR|GBP|CAD|AUD)\s+([0-9]{1,12}(?:,[0-9]{3}){0,3})(?:\s*/\s*| per )(year|month|hour)"
        offer = re.fullmatch(pattern, f["compensation"], re.I)
        floor = re.fullmatch(pattern, profile["salary_expectations"], re.I)
        if (
            offer
            and floor
            and (offer[1].upper(), offer[3].lower()) == (floor[1].upper(), floor[3].lower())
        ):
            if int(offer[2].replace(",", "")) < int(floor[2].replace(",", "")):
                add(
                    "salary",
                    "preference",
                    f["compensation"],
                    "Below the stated expectation for the same currency and pay period.",
                )
        else:
            add(
                "salary",
                "review",
                f["compensation"],
                "Compare currency, period and compensation with the saved expectation.",
            )
    if f.get("required_skills") or any(
        c["facet"] == "skill" and c["priority"] == "required" for c in clauses
    ):
        add(
            "skills",
            "review",
            f.get("required_skills") or "Required qualifications",
            "Review required skills against verified evidence.",
        )
    missing = [
        k
        for k in ("title", "company", "location", "posting_url", "compensation", "deadline")
        if not f.get(k)
    ]
    if any(k in missing for k in ("title", "company", "posting_url")):
        add("missing", "review", ", ".join(missing), "Source facts are incomplete.")
    if f.get("ambiguous"):
        add(
            "ambiguous",
            "review",
            "source text",
            "Conflicting, untrusted or ambiguous source material requires review.",
        )
    if f.get("possible_duplicates"):
        add(
            "duplicate",
            "review",
            "posting identity",
            "Conflicting source identifiers require comparison.",
        )
    if f.get("ambiguous"):
        for r in reasons:
            if r.outcome in ("hard", "closed"):
                r.outcome = "review"
                r.explanation = "Conflicting source evidence requires confirmation."
    outcomes = {r.outcome for r in reasons}
    priorities: dict[str, Decision] = {
        "excluded": "blocklisted",
        "closed": "expired_or_closed",
        "hard": "ineligible",
        "review": "needs_review",
        "preference": "outside_preferences",
    }
    return Screening(
        decision=next((v for k, v in priorities.items() if k in outcomes), "eligible"),
        mandatory="incompatible"
        if "hard" in outcomes
        else "unknown"
        if "review" in outcomes
        else "no_known_conflict",
        preference="outside"
        if "preference" in outcomes
        else "aligned"
        if aligned or (wanted and set(f.get("inferred_roles", [])) & categories(" ".join(wanted)))
        else "unspecified",
        inferred_roles=f.get("inferred_roles", []),
        reasons=reasons,
        missing=missing,
        assessed_on=today,
    )
