"""Create private, shell-compatible local defaults without replacing existing credentials."""

import os
import secrets
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
template = (root / ".env.example").read_text()
names = ["POSTGRES_PASSWORD", "JODY_OWNER_KEY", "JODY_DB_APP_PASSWORD", "JODY_ENCRYPTION_KEY"]
if "--upgrade" in sys.argv and (root / ".env").exists():
    path = root / ".env"
    keys = {line.split("=", 1)[0] for line in path.read_text().splitlines()}
    with path.open("a") as stream:
        for name in names:
            if name not in keys:
                stream.write(f"\n{name}={secrets.token_hex(32)}\n")
    raise SystemExit(0)
for name in names:
    template = template.replace(f"{name}=\n", f"{name}={secrets.token_hex(32)}\n")
try:
    fd = os.open(root / ".env", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    raise SystemExit("Existing .env retained.")
with os.fdopen(fd, "w") as output:
    output.write(template)
print("Created .env with local credentials.")
