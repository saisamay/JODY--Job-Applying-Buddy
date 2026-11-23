"""Verify worker-to-broker connectivity without creating or consuming tasks."""

from jody.config import redis_url
from redis import Redis

if __name__ == "__main__":
    with Redis.from_url(redis_url(), socket_connect_timeout=2, socket_timeout=2) as client:
        client.ping()
    print('{"event":"broker_ready"}')
