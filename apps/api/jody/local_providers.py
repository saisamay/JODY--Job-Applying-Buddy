"""Allowlisted local settings, parsed as literal data. Called only by local entry points."""

import os
import stat
import sys
from pathlib import Path

NAMES = {
    "JODY_" + s
    for s in """GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET GOOGLE_REDIRECT_URI
GITHUB_TOKEN GITHUB_REPOSITORY RESUME_GIT_REF RESUME_GIT_PATH GEMINI_API_KEY GROQ_API_KEY
TELEGRAM_BOT_TOKEN OPENROUTER_API_KEY NTFY_TOKEN NTFY_BASE_URL OLLAMA_BASE_URL
NEON_TEST_DATABASE_URL GMAIL_GEMINI_MODEL GMAIL_GROQ_MODEL""".split()
}


RUNTIME_NAMES = {
    "JODY_GOOGLE_CLIENT_ID",
    "JODY_GOOGLE_CLIENT_SECRET",
    "JODY_OLLAMA_BASE_URL",
    "JODY_GMAIL_GEMINI_MODEL",
    "JODY_GMAIL_GROQ_MODEL",
}


def load(names: set[str] | None = None) -> None:
    if names is None:
        names = RUNTIME_NAMES

    path = Path(os.getenv("JODY_PROVIDERS_FILE", str(Path.home() / ".config/jody/providers.env")))
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return
    with os.fdopen(fd) as file:
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.getuid() or meta.st_mode & 0o077:
            raise ValueError("Provider file requires private owner-only permissions.")
        for line in file:
            name, sep, value = line.strip().removeprefix("export ").partition("=")
            if sep and name in names and name in NAMES:
                value = value.strip()
                if value[:1] in {"'", '"'} and value[-1:] == value[:1]:
                    value = value[1:-1]
                os.environ.setdefault(name, value)


if __name__ == "__main__":
    for name in NAMES - RUNTIME_NAMES:
        os.environ.pop(name, None)
    load()
    os.execvp(sys.argv[1], sys.argv[1:])
