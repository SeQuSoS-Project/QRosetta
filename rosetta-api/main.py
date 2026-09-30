# FastAPI application entry point: middleware, static mounts and routers.

from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from routers import frontend, generation, benchmark, auth, history, export, publication, experiment
from routers.errors import register_error_handlers
import db.models as models
from db.database import engine
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
from services.security import limiter
from services.job_manager import ACTIVE_JOBS
from config import settings
from qrosetta_commons.helpers import get_logger
from contextlib import asynccontextmanager
import asyncio
import time
import logging

logger = get_logger("rosetta-main")
_JOB_TTL_SEC = 1800

class _SuppressAlgorithmsFilter(logging.Filter):
    """Drop GET /algorithms access log entries — they are frontend keepalive polls."""
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not ('GET /algorithms' in msg and '" 200' in msg)

logging.getLogger("uvicorn.access").addFilter(_SuppressAlgorithmsFilter())

async def _cleanup_old_jobs():
    while True:
        await asyncio.sleep(600)
        cutoff = time.time() - _JOB_TTL_SEC
        expired = [jid for jid, job in list(ACTIVE_JOBS.items())
                   if job.get("status") in ("completed", "failed")
                   and job.get("finished_at", 0) < cutoff]
        for jid in expired:
            ACTIVE_JOBS.pop(jid, None)
        if expired:
            logger.info(f"Evicted {len(expired)} expired jobs from ACTIVE_JOBS")

@asynccontextmanager
async def lifespan(app: FastAPI):
    cleanup_task = asyncio.create_task(_cleanup_old_jobs())
    yield
    cleanup_task.cancel()

app = FastAPI(title="Quantum Rosetta API", lifespan=lifespan)

models.Base.metadata.create_all(bind=engine)

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

app.add_middleware(LimitUploadSize, max_upload_size=settings.MAX_UPLOAD_BYTES)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

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