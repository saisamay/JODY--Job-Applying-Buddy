"""Drain a bounded amount of private-owner work. Scheduling new reads requires --schedule."""

import argparse
import os

from fastapi import HTTPException
from jody.gmail.service import enqueue
from jody.gmail.worker import step
from jody.security import PRIVATE_OWNER, encryption_key, runtime_engine

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schedule", action="store_true")
    args = parser.parse_args()
    db = runtime_engine()
    try:
        if args.schedule:
            enqueue(db, PRIVATE_OWNER)
        for _ in range(min(30, max(1, int(os.getenv("JODY_GMAIL_WORK_UNITS", "6"))))):
            if not step(db, PRIVATE_OWNER, encryption_key()):
                break
    except HTTPException as exc:
        parser.exit(1, str(exc.detail) + "\n")
    finally:
        db.dispose()
