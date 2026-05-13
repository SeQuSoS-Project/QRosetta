# FastAPI application entry point.

from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from routers import frontend, generation, benchmark, auth, history
import db.models as models
from db.database import engine
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from services.security import limiter
import os
import logging

class _SuppressAlgorithmsFilter(logging.Filter):
    """Drop GET /algorithms access log entries — they are frontend keepalive polls."""
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not ('GET /algorithms' in msg and '" 200' in msg)

logging.getLogger("uvicorn.access").addFilter(_SuppressAlgorithmsFilter())

app = FastAPI(title="Quantum Rosetta API")

models.Base.metadata.create_all(bind=engine)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

class LimitUploadSize(BaseHTTPMiddleware):
    def __init__(self, app, max_upload_size: int) -> None:
        super().__init__(app)
        self.max_upload_size = max_upload_size

    async def dispatch(self, request: Request, call_next):
        if request.method == 'POST':
            if 'content-length' in request.headers:
                content_length = int(request.headers['content-length'])
                if content_length > self.max_upload_size:
                    return JSONResponse(status_code=413, content={"detail": "Payload too large"})
        return await call_next(request)

app.add_middleware(LimitUploadSize, max_upload_size=1048576)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://rosetta-frontend-652754634999.us-central1.run.app",
        "http://localhost",
        "http://127.0.0.1"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/js", StaticFiles(directory="static/js"), name="js")

app.include_router(frontend.router)
app.include_router(generation.router)
app.include_router(benchmark.router)
app.include_router(auth.router)
app.include_router(history.router)