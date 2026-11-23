"""Publish and complete one inert task. Pending rows double as the transactional outbox."""

from datetime import timedelta
from uuid import UUID

from redis import Redis
from sqlalchemy import Engine, func, select, text, update

from .security import PRIVATE_OWNER, audit, tenant
from .tables import tasks, users


def tick(db: Engine, broker: Redis, user: UUID = PRIVATE_OWNER) -> bool:
    queue = f"jody:{db.url.database}:probe:{user}"
    with tenant(db, user) as conn:
        # The shared lock serializes each dispatch with the global pause update.
        if conn.scalar(text("SELECT jody_dispatch_open()")) is not True:
            return False
        if not conn.scalar(select(users.c.is_active)):
            return False
        due = conn.scalar(
            select(tasks.c.id)
            .where(
                tasks.c.status == "pending",
                tasks.c.kind == "local_probe",
                tasks.c.next_publish_at <= func.now(),
            )
            .order_by(tasks.c.next_publish_at, tasks.c.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if due:
            broker.rpush(queue, str(due))
            conn.execute(
                update(tasks)
                .where(tasks.c.id == due)
                .values(next_publish_at=func.now() + timedelta(seconds=10))
            )
        reference = broker.lpop(queue)
        if not reference:
            return False
        try:
            task_id = UUID(reference.decode() if isinstance(reference, bytes) else str(reference))
        except ValueError:
            return False
        done = conn.scalar(
            update(tasks)
            .where(
                tasks.c.id == task_id,
                tasks.c.user_id == user,
                tasks.c.kind == "local_probe",
                tasks.c.status == "pending",
            )
            .values(status="succeeded")
            .returning(tasks.c.id)
        )
        if done:
            audit(conn, user, "task.probe_completed", done)
        return done is not None
