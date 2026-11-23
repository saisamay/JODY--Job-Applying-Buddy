import json
import logging
import os
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from redis import Redis, RedisError
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from .config import database_url, redis_url
from .contracts import Error, Live, Ready
from .routes import router

log = logging.getLogger("jody.http")
log.setLevel(logging.INFO)
log.addHandler(logging.StreamHandler())
log.propagate = False


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    key = os.environ.get("JODY_OWNER_KEY", "")
    if len(key) < 32:
        raise RuntimeError("Set JODY_OWNER_KEY to a generated key of at least 32 characters.")
    app.state.owner_key = key
    app.state.db = create_engine(
        database_url(),
        pool_pre_ping=True,
        pool_timeout=3,
        connect_args={"connect_timeout": 3, "options": "-c statement_timeout=5000"},
    )
    app.state.queue = Redis.from_url(redis_url(), socket_connect_timeout=2, socket_timeout=2)
    try:
        yield
    finally:
        app.state.queue.close()
        app.state.db.dispose()


app = FastAPI(title="JODY", version="0.1.0", lifespan=lifespan)
app.include_router(router)


@app.middleware("http")
async def request_log(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    started = time.monotonic()
    request_id = uuid4().hex
    failure = None
    try:
        response = await call_next(request)
    except Exception as exc:
        failure = type(exc).__name__
        response = JSONResponse({"detail": "Service error. Please try again."}, status_code=500)
    response.headers["X-Request-ID"] = request_id
    response.headers["Cache-Control"] = "no-store"
    # Never log request bodies, query strings, session keys or provider error messages.
    log.info(
        json.dumps(
            {
                "time": datetime.now(UTC).isoformat(),
                "event": "http_request",
                "request_id": request_id,
                "method": request.method,
                "route": getattr(request.scope.get("route"), "path", "unmatched"),
                "status": response.status_code,
                "duration_ms": round((time.monotonic() - started) * 1000),
                "error_type": failure,
            }
        )
    )
    return response


@app.exception_handler(RequestValidationError)
async def invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(Error(detail="Check the submitted fields.").model_dump(), status_code=422)


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    return JSONResponse(
        Error(detail="Database temporarily unavailable.").model_dump(), status_code=503
    )


@app.get("/health/live")
def live() -> Live:
    return Live()


@app.get("/health/ready", responses={503: {"model": Ready}})
def ready(request: Request, response: Response) -> Ready:
    try:
        with request.app.state.db.connect() as conn:
            postgres = bool(
                conn.scalar(
                    text("""
                SELECT EXISTS (SELECT FROM pg_extension WHERE extname = 'vector')
                   AND EXISTS (SELECT FROM alembic_version WHERE version_num = '0001_foundation')
            """)
                )
            )
    except SQLAlchemyError:
        postgres = False
    try:
        redis = bool(request.app.state.queue.ping())
    except (RedisError, OSError):
        redis = False
    if not (postgres and redis):
        response.status_code = 503
    return Ready(
        status="ready" if postgres and redis else "unavailable", postgres=postgres, redis=redis
    )
