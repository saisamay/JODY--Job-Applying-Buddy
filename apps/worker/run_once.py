"""Run one local probe queue iteration using the restricted database account."""

from jody.config import redis_url
from jody.security import PRIVATE_OWNER, runtime_engine
from jody.worker import tick
from redis import Redis

if __name__ == "__main__":
    db = runtime_engine()
    try:
        with Redis.from_url(redis_url(), socket_timeout=2, socket_connect_timeout=2) as broker:
            completed = tick(db, broker, PRIVATE_OWNER)
            print("Probe completed." if completed else "No runnable probe.")
    finally:
        db.dispose()
