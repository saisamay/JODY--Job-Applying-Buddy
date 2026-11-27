"""Grounded multi-stage retrieval. Scores and recommendation thresholds are internal estimates."""

import math
import re
from typing import Any

from fastapi import HTTPException

from .inference import FACETS, Inference, terms
from .knowledge import Json

OPTIONAL = re.compile(
    r"\b(preferred|optional|nice[- ]to[- ]have|bonus|a plus|desirable|not required)\b", re.I
)
MANDATORY = re.compile(r"\b(must|required|mandatory|minimum|at least|essential|need to)\b", re.I)
ELIGIBILITY = re.compile(
    r"\b(visa|sponsor\w*|clearance|eligible|eligibility|authori[sz]\w*|citizen\w*|licen[sc]e)\b",
    re.I,
)
NEG = re.compile(r"\b(no|never|without|lack\w*|cannot|unable|not)\b", re.I)
INSTRUCTION = re.compile(
    r"\b(ignore|disregard|override) (?:all |the |previous |prior |system |your |above )*(?:instructions?|rules?|prompts?)|\b(system prompt|mark (?:me|the candidate) qualified|call the tool)\b",
    re.I,
)
YEARS = re.compile(r"\b(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\b", re.I)
HEAD = {
    "requirements": "required",
    "qualifications": "required",
    "required qualifications": "required",
    "what you bring": "required",
    "responsibilities": "responsibility",
    "what you will do": "responsibility",
    "preferred qualifications": "preferred",
    "nice to have": "preferred",
    "required": "required",
    "preferred": "preferred",
    "eligibility": "hard",
    "requirements and qualifications": "required",
}
NOISE = set(
    "hands hands-on practical demonstrated engineer engineering minimum least plus nice mandatory candidate candidates qualifications qualification seeking role excellent including knowledge expertise relevant equivalent".split()
)


def job_clauses(description: str, role: str | None) -> tuple[str | None, list[Json]]:
    clauses: list[Json] = []
    section = "responsibility"
    for line in description.splitlines():
        line = line.strip(" \t-*•")
        if (
            not line
            or line.partition(":")[0].casefold()
            in {"company", "company domain", "recruiter email", "posting url"}
            and ":" in line
        ):
            continue
        if line.lower().startswith(("title:", "job title:", "role:")):
            role = line.split(":", 1)[1].strip()
            continue
        if (
            not role
            and not clauses
            and not re.search(r"\b(design|build|maintain|develop|operate|implement)\b", line, re.I)
            and len(line.split()) <= 8
            and re.search(
                r"\b(engineer|developer|analyst|scientist|designer|manager)\b", line, re.I
            )
            and not MANDATORY.search(line)
            and ":" not in line
        ):
            role = line
            continue
        label, colon, rest = line.partition(":")
        if label.casefold() in HEAD:
            section = HEAD[label.casefold()]
            line = rest.strip() if colon else ""
        for clause in re.split(
            r"(?<=[.!?])\s+|;\s*|,?\s+but\s+|,\s*(?=(?:preferably|preferred|bonus|optional|nice to have)\b)",
            line,
            flags=re.I,
        ):
            if not clause or INSTRUCTION.search(clause):
                continue
            explicit = bool(OPTIONAL.search(clause) or MANDATORY.search(clause))
            priority = (
                "preferred"
                if OPTIONAL.search(clause)
                else "required"
                if MANDATORY.search(clause)
                else section
            )
            facet = "responsibility"
            if ELIGIBILITY.search(clause):
                facet = "eligibility"
                if priority in {"required", "hard"}:
                    priority = "hard"
            elif YEARS.search(clause):
                facet = "experience"
            elif re.search(r"degree|bachelor|master.s|diploma|ph\.?d", clause, re.I):
                facet = "education"
            elif re.search(r"onsite|on-site|hybrid|located|reside|relocat", clause, re.I):
                facet = "location"
                if priority == "required":
                    priority = "hard"
            elif re.search(r"\b(senior|leadership|junior|principal)\b", clause, re.I):
                facet = "seniority"
            elif priority != "responsibility":
                facet = "skill"
            clauses.append(
                {
                    "text": clause,
                    "priority": priority,
                    "facet": facet,
                    "fixed": explicit or priority != "responsibility" or section == "preferred",
                }
            )
    if len(clauses) > 60 or any(len(c["text"]) > 2000 for c in clauses):
        raise HTTPException(422, "Split this job into shorter reviewable requirements.")
    return role, clauses


def analyze(ai: Inference, description: str, role: str | None) -> Json:
    title, clauses = job_clauses(description, role)
    if clauses:
        result = ai.invoke("classify", {"clauses": [c["text"] for c in clauses]})
        items = result.get("items") if isinstance(result, dict) else None
        if not isinstance(items, list):
            raise HTTPException(503, "Invalid job classifications.")
        for item in items:
            if not isinstance(item, dict):
                continue
            index = item.get("index")
            if type(index) is not int or not 0 <= index < len(clauses):
                continue
            c = clauses[index]
            if c["facet"] in {"responsibility", "skill"} and item.get("facet") in FACETS:
                c["facet"] = item["facet"]
            if not c["fixed"] and item.get("priority") in {
                "preferred",
                "required",
                "responsibility",
            }:
                c["priority"] = item["priority"]
    for c in clauses:
        del c["fixed"]
    # A shared responsibility signature groups overlapping roles independently of their labels.
    functional_terms = sorted(
        {term for c in clauses if c["priority"] != "preferred" for term in terms(c["text"]) - NOISE}
    )
    return {
        "title": title,
        "requirements": clauses,
        "functional_terms": functional_terms,
        "requires_owner_review": bool(INSTRUCTION.search(description)),
    }


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise HTTPException(503, "Incompatible embedding dimensions.")
    norm = math.sqrt(sum(v * v for v in a) * sum(v * v for v in b))
    return sum(x * y for x, y in zip(a, b, strict=True)) / norm if norm else 0


def anchors(value: str) -> set[str]:
    return terms(value) - NOISE - {"build", "design", "maintain"}


def compare_one(
    ai: Inference, clause: Json, evidence: list[Json], vectors: list[list[float]]
) -> tuple[str, Json | None]:
    if not evidence:
        return "missing", None
    phrase = clause["text"]
    query = ai.invoke("embed", {"text": phrase})
    wanted = anchors(phrase)
    years = YEARS.search(phrase)
    actions = terms(phrase) & {"build", "design", "maintain"}
    ranked = sorted(range(len(evidence)), key=lambda i: cosine(query, vectors[i]), reverse=True)[:6]
    quotes = [evidence[i]["quote"] for i in ranked]
    judgement = ai.invoke("reason", {"requirement": phrase, "evidence": quotes})
    choice = judgement.get("choice") if isinstance(judgement, dict) else None
    if type(choice) is int and 0 <= choice < len(ranked):
        selected = ranked[choice]
        ranked = [selected, *[i for i in ranked if i != selected]]
    else:
        selected = -1
    related = None
    direct_denial = re.compile(
        r"\b(?:not (?:currently )?(?:authorized|eligible|licensed)|(?:no|lack(?:s)?) (?:active |current )?(?:security clearance|work authorization|license|citizenship))\b",
        re.I,
    )
    for i in ranked:
        fact = evidence[i]
        quote = fact["quote"]
        if INSTRUCTION.search(quote):
            continue
        have = anchors(quote)
        # Explicit contradictions require the same qualification and scope.
        # A number in an unrelated project or an undated job establishes no tenure.
        topic = wanted - {w for w in wanted if w.isnumeric()} - {"of", "least", "at", "minimum"}
        if years:
            observed = YEARS.search(quote)
            if (
                not observed
                or len(YEARS.findall(quote)) != 1
                or not topic
                or not topic <= have
                or NEG.search(quote)
            ):
                continue
            if float(observed[1]) < float(years[1]):
                continue
            return "matched", fact
        if clause["priority"] == "hard":
            if NEG.search(phrase):
                # A negative requirement needs explicit verbatim corroboration.
                if phrase.casefold().strip(".") == quote.casefold().strip("."):
                    return "matched", fact
                continue
            if wanted and wanted <= have:
                if NEG.search(quote):
                    if direct_denial.search(quote):
                        return "blocker", fact
                    continue
                return "matched", fact
            continue
        if NEG.search(quote) or (NEG.search(phrase) and not OPTIONAL.search(phrase)):
            continue
        if wanted and wanted <= have and actions <= terms(quote):
            return "matched", fact
        score = cosine(query, vectors[i])
        if clause["facet"] in {"experience", "education", "location", "seniority", "eligibility"}:
            continue
        # Free-form responsibilities can be entailed by a semantically equivalent
        # verified activity. Literal names, quantities and mandatory credentials
        # retain their independent, conservative checks.
        names = {
            w.casefold()
            for w in re.findall(r"(?<!^)(?<![.!?] )\b(?:[A-Z][a-zA-Z0-9+#.]*|\d+)\b", phrase)
        }
        if (
            i == selected
            and judgement.get("relation") == "direct"
            and score >= 0.72
            and clause["priority"] == "responsibility"
            and not (names - terms(quote))
        ):
            return "matched", fact
        if (score >= 0.30 and bool(wanted & have)) or (
            i == selected
            and score >= 0.55
            and judgement.get("relation") in {"direct", "transferable"}
        ):
            if related is None:
                related = fact
    return ("transferable", related) if related else ("missing", None)


def assess(ai: Inference, job: Json, facts: list[Json]) -> Json:
    vectors = [ai.invoke("embed", {"text": f["quote"]}) for f in facts]
    buckets: dict[str, list[Any]] = {
        k: []
        for k in (
            "matched",
            "transferable",
            "missing_required",
            "preferred_unmet",
            "eligibility_blockers",
            "unmet_responsibilities",
        )
    }
    total, earned = 0.0, 0.0
    supported = {}
    uncertain_hard = False
    evaluated = 0
    optional_count = sum(c["priority"] == "preferred" for c in job["requirements"])
    for clause in job["requirements"]:
        relation, fact = compare_one(ai, clause, facts, vectors)
        priority = clause["priority"]
        weight = {"preferred": 0.25, "hard": 2, "required": 1.5, "responsibility": 1}[priority]
        if priority == "preferred":
            weight /= max(optional_count, 1)
        total += weight
        earned += weight * {"matched": 1, "transferable": 0.45}.get(relation, 0)
        if priority != "preferred":
            evaluated += int(relation in {"matched", "transferable"})
        record = {**clause, "evidence_id": fact["id"] if fact else None}
        if fact:
            supported[fact["id"]] = fact
        if relation == "blocker":
            buckets["eligibility_blockers"].append(record)
        elif relation in {"matched", "transferable"}:
            buckets[relation].append(record)
        if relation != "matched":
            if priority in {"required", "hard"}:
                buckets["missing_required"].append(record)
                uncertain_hard |= priority == "hard"
            elif priority == "preferred":
                buckets["preferred_unmet"].append(record)
            elif relation == "missing":
                buckets["unmet_responsibilities"].append(record)
    score = round(100 * earned / total) if total else 0
    recommendation = (
        "Not Eligible"
        if buckets["eligibility_blockers"]
        else "Needs Review"
        if uncertain_hard or not evaluated or job["requires_owner_review"]
        else "Strong Match"
        if score >= 80 and not buckets["missing_required"]
        else "Potential Match"
        if score >= 45
        else "Needs Review"
    )
    return {
        **buckets,
        "qualification_estimate": score,
        "score_type": "internal estimate",
        "confidence": "low"
        if not evaluated or uncertain_hard
        else "high"
        if score >= 80 and not buckets["missing_required"]
        else "medium",
        "recommendation": recommendation,
        "evidence": list(supported.values()),
        "job_title": job["title"],
        "title_used_in_score": False,
    }
