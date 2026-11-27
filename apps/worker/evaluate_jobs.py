"""Process up to 25 pending or stale evaluations locally, without provider calls."""

from jody.job_pipeline import batch
from jody.security import PRIVATE_OWNER, encryption_key, runtime_engine, tenant

if __name__ == "__main__":
    engine = runtime_engine()
    try:
        with tenant(engine, PRIVATE_OWNER) as conn:
            print("Evaluated jobs:", batch(conn, PRIVATE_OWNER, encryption_key()))
    finally:
        engine.dispose()
