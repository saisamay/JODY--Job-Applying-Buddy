"""Read job-card boundaries before flattening mail. No network resolution."""

import re
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

from .extract import Json, Posting, Vacancy, body, extract, safe_url


class Node:
    def __init__(
        self, tag: str = "", attrs: dict[str, str | None] | None = None, parent: "Node|None" = None
    ):
        self.tag, self.attrs, self.parent = tag, attrs or {}, parent
        self.parts: list[str | Node] = []

    def lines(self) -> list[str]:
        out = []
        for item in self.parts:
            if isinstance(item, str):
                if item.strip():
                    out.append(" ".join(item.split()))
            else:
                out.extend(item.lines())
        classes = (self.attrs.get("class") or "").lower().split()
        for label in ("company", "location", "employment-type"):
            if (
                any(re.search(r"(?:^|[-_])" + label + r"(?:-name)?$", token) for token in classes)
                and out
            ):
                return [label.replace("-", " ") + ": " + " ".join(out)]
        return out


class Tree(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.root = Node()
        self.current = self.root
        self.links: list[Node] = []
        self.depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.depth >= 100:
            raise ValueError("HTML too deeply nested")
        node = Node(tag, dict(attrs), self.current)
        self.current.parts.append(node)
        if tag == "a":
            self.links.append(node)
        if tag not in {
            "img",
            "br",
            "hr",
            "input",
            "meta",
            "link",
            "wbr",
            "source",
            "area",
            "base",
            "col",
            "embed",
            "param",
            "track",
        }:
            self.current = node
            self.depth += 1

    def handle_endtag(self, tag: str) -> None:
        node = self.current
        depth = self.depth
        while node.parent:
            depth -= 1
            if node.tag == tag:
                self.current = node.parent
                self.depth = depth
                return
            node = node.parent

    def handle_data(self, data: str) -> None:
        if self.current.tag not in {"script", "style", "template"}:
            self.current.parts.append(data)


def posting(href: str) -> tuple[str, str] | None:
    if len(href) > 8192 or re.search(r"[\s\\\x00-\x1f]", href):
        return None
    if not safe_url(href.split("?", 1)[0]):
        return None
    url = urlsplit(href)
    if url.hostname not in {"linkedin.com", "www.linkedin.com"}:
        return None
    match = re.fullmatch(r"/(?:comm/)?jobs/view/(?:[\w-]+-)?(\d{1,20})/?", url.path)
    if match:
        return match[1], url.path
    if url.path.rstrip("/") in {"/jobs/search", "/comm/jobs/search"}:
        ids = parse_qs(url.query).get("currentJobId", [])
        if len(ids) == 1 and re.fullmatch(r"\d{1,20}", ids[0]):
            return ids[0], url.path
    return None


def linkedin(html: str) -> list[tuple[Vacancy, bool]]:
    tree = Tree()
    try:
        tree.feed(html)
    except (ValueError, AssertionError):
        return []
    grouped: dict[Node, set[str]] = {}
    anchors = []
    for a in tree.links:
        identity = posting(a.attrs.get("href") or "")
        if not identity:
            continue
        anchors.append((a, *identity))
        node: Node | None = a
        while node:
            grouped.setdefault(node, set()).add(identity[0])
            node = node.parent
    rows: list[tuple[Vacancy, bool]] = []
    for a, jid, path in anchors:
        anchor_lines = [
            line
            for line in a.lines()
            if not line.startswith(("company: ", "location: ", "employment type: "))
        ]
        title = (
            next((line for line in anchor_lines if line), "")
            if any("·" in line for line in anchor_lines)
            else " ".join(anchor_lines)
        )
        if (
            not title
            or len(title) > 240
            or re.match(r"^(?:apply|view|see|show|learn more)\b", title, re.I)
        ):
            continue
        node = a
        company = location = mode = employment = None
        while grouped.get(node) == {jid}:
            lines = node.lines()
            for line in lines:
                parts = re.split(r"\s+[·•]\s+", line)
                if len(parts) == 2 and title not in line and len(line) < 240:
                    company, location = parts
                    continue
                label, sep, val = line.partition(":")
                if sep and val.strip() and len(val) < 240:
                    if label.lower() == "company":
                        company = val.strip()
                    if label.lower() == "location":
                        location = val.strip()
                    if label.lower() == "employment type":
                        employment = val.strip()
                if re.fullmatch(r"remote|hybrid|on[- ]?site", line, re.I):
                    mode = line
            if company and location or node.parent is None:
                break
            node = node.parent
        if location and (work := re.search(r"\s*\((Remote|Hybrid|On[- ]?site)\)$", location, re.I)):
            mode = work[1]
            location = location[: work.start()].strip() or None
        rows.append(
            (
                Posting(
                    title=title,
                    company=company,
                    location=location,
                    work_mode=mode,
                    employment_type=employment,
                    platform_job_id=jid,
                    posting_url="https://www.linkedin.com/jobs/view/" + jid,
                    observed_path=path,
                ),
                False,
            )
        )
    return rows


REGISTRY = {"linkedin.com": linkedin}


def parse(domain: str, part: Json, content: str) -> list[tuple[Vacancy, bool]]:
    adapter = REGISTRY.get(domain)
    if adapter and (rows := adapter(body(part, html_only=True))):
        return rows
    generic = extract(content)
    if domain != "linkedin.com":
        return generic
    result: list[tuple[Vacancy, bool]] = []
    for v, unsafe in generic:
        link = v.application_url
        identity = posting(link) if link else None
        facts = v.model_dump(exclude={"application_url"})
        if identity:
            jid, path = identity
            result.append(
                (
                    Posting(
                        **facts,
                        platform_job_id=jid,
                        observed_path=path,
                        posting_url="https://www.linkedin.com/jobs/view/" + jid,
                    ),
                    unsafe,
                )
            )
        else:
            # A generic link inside a platform notification has unknown purpose.
            result.append((Vacancy(**facts), True))
    return result
