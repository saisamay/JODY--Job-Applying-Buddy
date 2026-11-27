"""Extractive parsing only. No browser, attachment, link resolver or tool execution."""

import base64
import binascii
import ipaddress
import re
from email.message import Message
from email.utils import getaddresses
from html.parser import HTMLParser
from typing import Annotated, Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field

Json = dict[str, Any]
Short = Annotated[str, Field(min_length=1, max_length=240)]
ROLE = r"(?:engineer|developer|intern|analyst|designer|manager|scientist|architect|associate|consultant|specialist|lead|officer|coordinator|administrator|researcher)"
ADDRESS = r"[a-z0-9._%+\-]+@(?:[a-z0-9-]+\.)+[a-z]{2,63}"
THREAT = re.compile(
    r"ignore (?:all |the |previous |prior |system )*(?:instructions|rules)|(?:reveal|print|send) (?:your |the )?(?:credentials|secrets|resume)|execute (?:this|the) command|registration fee|security deposit|pay to (?:apply|get)",
    re.I,
)
RELEVANT = {"Job alert", "Direct job opportunity", "Campus placement opportunity"}


class Vacancy(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: Short
    company: Short | None = None
    employment_type: Short | None = None
    location: Short | None = None
    work_mode: Short | None = None
    description: Annotated[str, Field(max_length=1500)] | None = None
    required_skills: Short | None = None
    preferred_skills: Short | None = None
    experience: Short | None = None
    education: Short | None = None
    graduation_year: Short | None = None
    compensation: Short | None = None
    deadline: Short | None = None
    application_url: Annotated[str, Field(max_length=2000)] | None = None
    requisition: Short | None = None


def safe_url(value: str) -> str | None:
    try:
        p = urlsplit(value.strip())
        host = (p.hostname or "").lower()
        if (
            p.scheme != "https"
            or p.username is not None
            or p.password is not None
            or p.port not in {None, 443}
            or len(value) > 2000
            or re.search(r"[\s\\\x00-\x1f]", value)
            or not re.fullmatch(r"(?:[a-z0-9-]+\.)+[a-z]{2,63}", host)
            or host.endswith((".local", ".internal", ".localhost", ".test"))
        ):
            return None
        try:
            ipaddress.ip_address(host)
            return None
        except ValueError:
            pass
        query = [
            (k, v)
            for k, v in parse_qsl(p.query, keep_blank_values=True)
            if not k.lower().startswith("utm_")
            and k.lower() not in {"trk", "trackingid", "refid", "fbclid", "gclid"}
        ]
        if any(
            re.search(r"(token|signature|password|secret|redirect|^url$|^dest$)", k, re.I)
            or "://" in v
            for k, v in query
        ):
            return None
        return urlunsplit(("https", host, p.path or "/", urlencode(sorted(query)), ""))
    except ValueError:
        return None


class TextHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.hidden = 0
        self.link = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "template", "svg", "head"}:
            self.hidden += 1
        if self.hidden:
            return
        if tag in {"p", "div", "tr", "td", "li", "br", "h1", "h2", "h3", "a"}:
            self.out.append("\n")
        if tag == "a":
            self.link = dict(attrs).get("href") or ""

    def handle_endtag(self, tag: str) -> None:
        if self.hidden:
            if tag in {"script", "style", "template", "svg", "head"}:
                self.hidden -= 1
        elif tag == "a" and self.link:
            self.out.append("\nLink: " + self.link + "\n")
            self.link = ""
        elif tag in {"p", "div", "tr", "td", "li", "h1", "h2", "h3"}:
            self.out.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.out.append(data)


def body(part: Json, depth: int = 0, *, html_only: bool = False) -> str:
    if depth > 12 or part.get("filename") or part.get("body", {}).get("attachmentId"):
        return ""
    mime = part.get("mimeType", "")
    if mime.startswith("multipart/"):
        parts = part.get("parts", [])[:80]
        if mime == "multipart/alternative":
            parts = sorted(parts, key=lambda item: item.get("mimeType") == "text/html")
        pieces = [body(p, depth + 1, html_only=html_only) for p in parts]
        if mime == "multipart/alternative":
            return next((p for p in reversed(pieces) if p.strip()), "")
        return "\n".join(pieces)[:80000]
    if mime not in {"text/plain", "text/html"}:
        return ""
    if html_only and mime != "text/html":
        return ""
    data = part.get("body", {}).get("data", "")
    if not isinstance(data, str) or len(data) > 500000:
        return ""
    try:
        blob = base64.b64decode(data + "=" * (-len(data) % 4), altchars=b"-_", validate=True)
        hints = Message()
        hints["content-type"] = next(
            (h["value"] for h in part.get("headers", []) if h["name"].lower() == "content-type"),
            mime,
        )
        try:
            value = blob.decode(hints.get_content_charset() or "utf-8", errors="replace")
        except LookupError:
            value = blob.decode(errors="replace")
        if html_only:
            return value[:200000]
        if mime == "text/html":
            html = TextHTML()
            html.feed(value[:200000])
            html.close()
            value = "".join(html.out)
        return value.replace("\x00", "")[:80000]
    except (ValueError, binascii.Error, AssertionError):
        return ""


def headers(message: Json) -> tuple[str, str, bool]:
    items = message.get("payload", {}).get("headers", [])

    def values(name: str) -> list[str]:
        return [str(i.get("value", "")) for i in items if i.get("name", "").lower() == name]

    senders = getaddresses(values("from"))
    sender = senders[0][1].lower() if len(senders) == 1 else ""
    auth = next(iter(values("authentication-results")), "")
    domain = sender.partition("@")[2]
    # Require Gmail's inbound authentication result and exact alignment.
    trusted = bool(
        domain
        and re.match(r"^\s*mx\.google\.com\s*;", auth, re.I)
        and re.search(
            r"\bdmarc=pass\b[^;]*?\bheader\.from=" + re.escape(domain) + r"(?=[;\s]|$)", auth, re.I
        )
    )
    return sender, " ".join(values("subject"))[:500], trusted


def classify(subject: str, text: str, trusted: bool) -> str:
    s = (subject + "\n" + text).lower()
    if not trusted or THREAT.search(s):
        return "Suspicious"
    if re.search(r"paid course|discount|limited.time sale|webinar|subscribe (?:to|for) premium", s):
        return "Promotional"
    if re.search(
        r"interview invitation|assessment invitation|offer letter|application received|thank you for applying",
        s,
    ):
        return "Potential recruitment communication"
    if re.search(r"campus placement|campus recruitment|placement drive", s):
        return "Campus placement opportunity"
    if re.search(
        r"job alerts?|jobs for you|new (?:jobs|vacancies)|recommended jobs|job openings|jobs matching",
        s,
    ):
        return "Job alert"
    if re.search(r"we(?:'re| are) hiring|job opportunity|hiring for|open position", s):
        return "Direct job opportunity"
    return "Unknown / needs review" if re.search(r"\b" + ROLE + r"\b", s) else "Irrelevant"


FIELDS = {
    "company": "company",
    "employer": "company",
    "employment type": "employment_type",
    "job type": "employment_type",
    "location": "location",
    "work mode": "work_mode",
    "description": "description",
    "required skills": "required_skills",
    "preferred skills": "preferred_skills",
    "experience": "experience",
    "education": "education",
    "graduation year": "graduation_year",
    "salary": "compensation",
    "compensation": "compensation",
    "deadline": "deadline",
    "apply by": "deadline",
    "job id": "requisition",
    "requisition": "requisition",
    "application url": "application_url",
    "apply": "application_url",
    "link": "application_url",
}


def extract(text: str) -> list[tuple[Vacancy, bool]]:
    rows: list[tuple[Vacancy, bool]] = []
    current: dict[str, str] = {}
    unsafe = False

    def finish() -> None:
        if current and len(rows) < 60:
            rows.append((Vacancy.model_validate(current), unsafe))

    for raw in text.splitlines():
        line = " ".join(raw.split())
        if not line:
            continue
        if re.search(
            r"^(unsubscribe|manage (?:your )?(?:alerts|preferences)|privacy policy)\b", line, re.I
        ):
            break
        label, sep, value = line.partition(":")
        field = FIELDS.get(label.lower())
        if current and field and sep:
            value = value.strip()
            if field == "application_url":
                link = safe_url(value)
                if link:
                    current.setdefault(field, link)
                else:
                    unsafe = True
            elif value and "://" not in value and not re.search(ADDRESS, value, re.I):
                current[field] = value[: 1500 if field == "description" else 240]
            continue
        if current and line.startswith("https://"):
            link = safe_url(line)
            if link:
                current.setdefault("application_url", link)
            else:
                unsafe = True
            continue
        named = re.match(r"^(?:job title|title|role|position)\s*:\s*(.+)$", line, re.I)
        possible = bool(
            re.search(r"\b" + ROLE + r"\b", line, re.I)
            and not sep
            and len(line.split()) <= 12
            and not re.search(
                r"[!?@]|jobs for|new jobs|alert|click|we are|we're|apply now", line, re.I
            )
        )
        if named or possible:
            finish()
            title, _, company = (named[1] if named else line).partition(" at ")
            current = {"title": title.strip()[:240]} if title.strip() else {}
            if current and company.strip():
                current["company"] = company.strip()[:240]
            unsafe = False
        elif current and not sep and re.fullmatch(r"remote|hybrid|on[- ]?site", line, re.I):
            current["work_mode"] = line
    finish()
    return rows


class Posting(Vacancy):
    platform_job_id: str
    posting_url: str
    observed_path: str
