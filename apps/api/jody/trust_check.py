"""Two optional, explicitly authorized HTTPS lookups. Only public job and domain metadata leave JODY."""

import json
import os
import re
from datetime import date
from html.parser import HTMLParser
from typing import Any

from fastapi import HTTPException

from .career.web_source import fetch
from .gmail.extract import safe_url
from .trust_rules import hostname, same_site


def official_domain(company: str) -> str:
    try:
        m = json.loads(os.getenv("JODY_TRUST_EMPLOYERS", "{}"))
        domain = m.get(company.strip().casefold(), "") if isinstance(m, dict) else ""
        return (
            domain
            if isinstance(domain, str) and re.fullmatch(r"(?:[a-z0-9-]+\.)+[a-z]{2,63}", domain)
            else ""
        )
    except ValueError:
        return ""


class StructuredPosting(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.capture = False
        self.items: list[dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script":
            self.capture = dict(attrs).get("type") == "application/ld+json"

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self.capture = False

    def handle_data(self, data: str) -> None:
        if not self.capture:
            return
        try:
            value = json.loads(data)
        except (ValueError, RecursionError):
            return
        values = value if isinstance(value, list) else [value]
        for v in values[:100]:
            if isinstance(v, dict):
                graph = v.get("@graph")
                self.items.extend(
                    x
                    for x in (graph[:100] if isinstance(graph, list) else [v])
                    if isinstance(x, dict) and x.get("@type") == "JobPosting"
                )


def verify(f: dict[str, Any], official: str) -> dict[str, Any]:
    link = f.get("posting_url") or ""
    if (
        os.getenv("JODY_TRUST_PUBLIC_CHECKS") != "1"
        or not official
        or not same_site(hostname(link), official)
        or not safe_url(link)
        or "?" in link
        or "#" in link
        or any(
            same_site(official, d)
            for d in ("linkedin.com", "facebook.com", "whatsapp.com", "telegram.org", "t.me")
        )
    ):
        raise HTTPException(
            403,
            "Public verification requires an authorized exact posting on a configured official employer site.",
        )
    result: dict[str, Any] = {}
    try:
        parser = StructuredPosting()
        parser.feed(fetch(link, html=True, redirects=0).decode("utf-8", "replace"))
        for item in parser.items:
            org = item.get("hiringOrganization")
            if (
                isinstance(org, dict)
                and isinstance(item.get("title"), str)
                and str(org.get("name", "")).casefold() == f.get("company", "").casefold()
                and item["title"].casefold() == f.get("title", "").casefold()
                and item.get("url") == link
            ):
                result.update(posting=link, posting_ref="official JobPosting document")
                break
    except (HTTPException, ValueError):
        pass
    if re.fullmatch(r"[a-z0-9-]+\.com", official):
        try:
            data = json.loads(
                fetch(
                    "https://rdap.verisign.com/com/v1/domain/" + official,
                    html=False,
                    registry=True,
                    redirects=0,
                )
            )
            if (
                isinstance(data, dict)
                and str(data.get("ldhName", "")).lower() == official
                and isinstance(data.get("events"), list)
            ):
                for event in data["events"][:100]:
                    if isinstance(event, dict) and event.get("eventAction") == "registration":
                        when = date.fromisoformat(str(event.get("eventDate", ""))[:10])
                        if when <= date.today():
                            result["registered"] = when.isoformat()
                        break
        except (HTTPException, ValueError, RecursionError):
            pass
    return result
