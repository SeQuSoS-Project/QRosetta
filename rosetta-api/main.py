# FastAPI application entry point: middleware, static mounts and routers.

from fastapi import FastAPI, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from routers import frontend, generation, benchmark, auth, history, export, publication, experiment, share, plan, summary, selftest, timing
from routers import local as local_routes
from routers import circuits
from routers import health
from routers.errors import document_route_errors, register_error_handlers
from routers.rate_limit import RateLimitHeaders
from routers.same_origin import RefuseCrossSite
from routers.security_headers import SecurityHeaders
from db.database import engine
from db.migrate import upgrade_database
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from services.security import limiter
from services.job_manager import ACTIVE_JOBS, expired_job_ids
from services.job_store import reset_spill_dir
from config import settings
from qrosetta_commons.helpers import get_logger
from contextlib import asynccontextmanager
import asyncio
import logging

logger = get_logger("rosetta-main")

class _SuppressAlgorithmsFilter(logging.Filter):
    """Drop 200 access log entries of GET /algorithms (frontend keepalive polls) and of the
    health and readiness probes."""
    _QUIET = ('GET /algorithms', 'GET /health ', 'GET /ready ')

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not ('" 200' in msg and any(path in msg for path in self._QUIET))

logging.getLogger("uvicorn.access").addFilter(_SuppressAlgorithmsFilter())

async def _cleanup_old_jobs():
    while True:
        await asyncio.sleep(600)
        expired = expired_job_ids()
        for jid in expired:
            ACTIVE_JOBS.pop(jid, None)
        if expired:
            logger.info(f"Evicted {len(expired)} expired jobs from ACTIVE_JOBS")

def _upgrade_schema():
    migration = upgrade_database(engine)
    if migration["adopted"] is not None:
        logger.info(f"Database predates migrations; brought to the baseline (added: {migration['adopted'] or 'nothing'})")
    if migration["from"] != migration["to"]:
        logger.info(f"Database schema upgraded from {migration['from']} to {migration['to']}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    _upgrade_schema()
    reset_spill_dir()
    cleanup_task = asyncio.create_task(_cleanup_old_jobs())
    yield
    cleanup_task.cancel()

# default_response_class=JSONResponse serialises response models with json.dumps
# (allow_nan=False, so a NaN is a 500, not null); strict_content_type=True reads a body as JSON
# only with a JSON Content-Type. DESIGN_DECISIONS.md, "Web framework versions".
app = FastAPI(title="Quantum Rosetta API", version=settings.PLATFORM_VERSION, lifespan=lifespan,
              docs_url=None, redoc_url=None, default_response_class=JSONResponse,
              strict_content_type=True)

app.state.limiter = limiter
register_error_handlers(app)

class BodyTooLarge(HTTPException):
    """413 raised while a request body is read past its limit."""

    def __init__(self, limit: int) -> None:
        super().__init__(status_code=413, detail=f"Request body exceeds the upload limit of {limit} bytes")


class LimitUploadSize:
    """413 for a POST, PUT or PATCH body over the limit of its path: refused at once when
    Content-Length says so, otherwise counted as it arrives (chunked bodies) and stopped at
    the first byte over the limit."""

    _BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})

    def __init__(self, app, max_upload_size: int, path_limits: dict = None) -> None:
        self.app = app
        self.max_upload_size = max_upload_size
        self.path_limits = path_limits or {}

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in self._BODY_METHODS:
            await self.app(scope, receive, send)
            return
        limit = self.path_limits.get(scope["path"], self.max_upload_size)
        headers = dict(scope.get("headers") or [])
        raw_length = headers.get(b"content-length")
        if raw_length is not None:
            try:
                content_length = int(raw_length)
            except ValueError:
                await JSONResponse(status_code=400, content={"detail": "Invalid Content-Length header"})(scope, receive, send)
                return
            if content_length > limit:
                await JSONResponse(status_code=413, content={"detail": BodyTooLarge(limit).detail})(scope, receive, send)
                return
        received = 0
        started = False

        async def counted_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise BodyTooLarge(limit)
            return message

        async def tracked_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, counted_receive, tracked_send)
        except BodyTooLarge as exc:
            if started:
                raise
            await JSONResponse(status_code=413, content={"detail": exc.detail})(scope, receive, send)

app.add_middleware(LimitUploadSize, max_upload_size=settings.MAX_UPLOAD_BYTES,
                   path_limits={"/plan": settings.MAX_PLAN_REQUEST_BYTES})

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(RateLimitHeaders)
app.add_middleware(RefuseCrossSite)
app.add_middleware(SecurityHeaders)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/js", StaticFiles(directory="static/js"), name="js")
app.mount("/css", StaticFiles(directory="static/css"), name="css")
app.mount("/vendor", StaticFiles(directory="static/vendor"), name="vendor")

app.include_router(frontend.router)
app.include_router(generation.router)
app.include_router(benchmark.router)
app.include_router(auth.router)
app.include_router(history.router)
app.include_router(export.router)
app.include_router(publication.router)
app.include_router(experiment.router)
app.include_router(share.router)
app.include_router(plan.router)
app.include_router(summary.router)
app.include_router(selftest.router)
app.include_router(timing.router)
app.include_router(local_routes.router)
app.include_router(circuits.router)
app.include_router(health.router)

document_route_errors(app)