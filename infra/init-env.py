"""Create private, shell-compatible local defaults without replacing existing credentials."""

import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
template = (root / ".env.example").read_text()
for name in ["POSTGRES_PASSWORD", "JODY_OWNER_KEY"]:
    template = template.replace(f"{name}=\n", f"{name}={secrets.token_hex(32)}\n")
try:
    fd = os.open(root / ".env", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    raise SystemExit("Existing .env retained.")
with os.fdopen(fd, "w") as output:
    output.write(template)
print("Created .env with local credentials.")
