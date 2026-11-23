"""Bounded text extraction in a child process. LaTeX is read as inert text."""

import io
import re
import resource
import sys
import zipfile
from html.parser import HTMLParser

from defusedxml import ElementTree  # type: ignore[import-untyped]
from pypdf import PdfReader


class VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.text: list[str] = []
        self.hidden = 0
        self.description: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "meta":
            meta = dict(attrs)
            if (meta.get("name") or "").lower() == "description":
                self.description = meta.get("content")
        if tag in {"script", "style", "noscript", "template", "head"}:
            self.hidden += 1
        if tag in {"div", "p", "li", "h1", "h2", "h3", "br", "section"}:
            self.text.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "template", "head"}:
            self.hidden = max(0, self.hidden - 1)
        if tag in {"p", "li", "h1", "h2", "h3"}:
            self.text.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.text.append(data)


def extract(kind: str, data: bytes) -> str:
    if kind == "pdf":
        pdf = PdfReader(io.BytesIO(data))
        if pdf.is_encrypted or len(pdf.pages) > 80:
            raise ValueError
        return "\n".join(page.extract_text() for page in pdf.pages)
    if kind == "docx":
        with zipfile.ZipFile(io.BytesIO(data)) as package:
            info = package.getinfo("word/document.xml")
            if info.file_size > 4_000_000:
                raise ValueError
            document = ElementTree.fromstring(package.read(info))
            return "\n".join(
                "".join(t.text or "" for t in p.iterfind(".//{*}t"))
                for p in document.iterfind(".//{*}p")
            )
    text = data.decode("utf-8")
    if kind == "portfolio_html":
        parser = VisibleText()
        parser.feed(text)
        return "\n".join([parser.description or "", "".join(parser.text)])
    if kind == "tex":
        text = re.sub(r"(?m)(?<!\\)%.*$", "", text)
        text = re.sub(r"\\(?:sub)*section\*?\{([^{}]*)\}", r"\n\1\n", text)
        text = re.sub(r"\\(?:item|resumeItem)\b", "\n", text)
        text = re.sub(r"\\(?:begin|end|documentclass|usepackage)\{[^{}]*\}", "", text)
        text = re.sub(r"\\[A-Za-z]+\*?", " ", text).translate(str.maketrans("{}", "  "))
    return text


if __name__ == "__main__":
    resource.setrlimit(resource.RLIMIT_AS, (384 << 20, 384 << 20))
    resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
    try:
        result = extract(sys.argv[1], sys.stdin.buffer.read(5 * 1024**2 + 1)).strip()
        if not result or len(result) > 100_000:
            raise ValueError
        sys.stdout.buffer.write(result.encode())
    except Exception:
        sys.exit(1)
