# FastAPI router endpoints for FAIR data export.

import asyncio
import io

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

import schemas
from services.security import limiter
from services.exporter import build_export_context, build_ro_crate
from qrosetta_commons.helpers import get_logger

logger = get_logger("rosetta-export")

router = APIRouter()


@router.post("/export")
@limiter.limit("10/minute")
async def export_ro_crate(request: Request, payload: schemas.ExportRequest):
    """Build a FAIR-compliant RO-Crate ZIP bundle from results supplied in the request body.

    Stateless and public: it depends on neither authentication nor stored history, so any
    user can export the results they are currently viewing.
    """
    results = payload.results
    if not results:
        raise HTTPException(status_code=400, detail="No results provided to export")

    ctx = build_export_context(results, payload)

    try:
        # Figure rendering + zip assembly is CPU-bound; run it off the event loop.
        zip_bytes = await asyncio.to_thread(build_ro_crate, ctx)
    except Exception:
        logger.error("RO-Crate export failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Export failed")

    ts_slug = ctx.timestamp.replace(":", "-").replace("+", "p")
    filename = f"rosetta-export-{ts_slug}.zip"

    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
