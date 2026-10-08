# FastAPI application entry point: middleware, static mounts and routers.

from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from routers import frontend, generation, benchmark, auth, history, export, publication, experiment, share
from routers.errors import document_route_errors, register_error_handlers
from routers.rate_limit import RateLimitHeaders
import db.models as models
from db.database import add_missing_nullable_columns, engine
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
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
    """Drop GET /algorithms access log entries — they are frontend keepalive polls."""
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not ('GET /algorithms' in msg and '" 200' in msg)

logging.getLogger("uvicorn.access").addFilter(_SuppressAlgorithmsFilter())

async def _cleanup_old_jobs():
    while True:
        await asyncio.sleep(600)
        expired = expired_job_ids()
        for jid in expired:
            ACTIVE_JOBS.pop(jid, None)
        if expired:
            logger.info(f"Evicted {len(expired)} expired jobs from ACTIVE_JOBS")

@asynccontextmanager
async def lifespan(app: FastAPI):
    reset_spill_dir()
    cleanup_task = asyncio.create_task(_cleanup_old_jobs())
    yield
    cleanup_task.cancel()

app = FastAPI(title="Quantum Rosetta API", version=settings.PLATFORM_VERSION, lifespan=lifespan,
              docs_url=None, redoc_url=None)

models.Base.metadata.create_all(bind=engine)
for _column in add_missing_nullable_columns(models.Base.metadata, engine):
    logger.info(f"Added missing column {_column}")

app.state.limiter = limiter
register_error_handlers(app)

class LimitUploadSize(BaseHTTPMiddleware):
    def __init__(self, app, max_upload_size: int) -> None:
        super().__init__(app)
        self.max_upload_size = max_upload_size

    _BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})

    async def dispatch(self, request: Request, call_next):
        if request.method in self._BODY_METHODS:
            raw_length = request.headers.get('content-length')
            if raw_length is not None:
                try:
                    content_length = int(raw_length)
                except ValueError:
                    return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length header"})
                if content_length > self.max_upload_size:
                    return JSONResponse(status_code=413, content={"detail": f"Request body exceeds the upload limit of {self.max_upload_size} bytes"})
        return await call_next(request)

SHARE_PAGE_HEADERS = {
    "Content-Security-Policy": ("default-src 'self'; script-src 'self'; style-src 'self'; "
                                "img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; "
                                "form-action 'none'"),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


class SharePageHeaders(BaseHTTPMiddleware):
    """The read-only share page gets its security headers on every path that serves it."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path.endswith("/share.html"):
            response.headers.update(SHARE_PAGE_HEADERS)
        return response


app.add_middleware(LimitUploadSize, max_upload_size=settings.MAX_UPLOAD_BYTES)
app.add_middleware(SharePageHeaders)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(RateLimitHeaders)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/js", StaticFiles(directory="static/js"), name="js")
app.mount("/css", StaticFiles(directory="static/css"), name="css")

app.include_router(frontend.router)
app.include_router(generation.router)
app.include_router(benchmark.router)
app.include_router(auth.router)
app.include_router(history.router)
app.include_router(export.router)
app.include_router(publication.router)
app.include_router(experiment.router)
app.include_router(share.router)

document_route_errors(app)