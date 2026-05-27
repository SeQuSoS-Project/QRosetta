# FastAPI router endpoints for FAIR data export.

import io

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

import schemas
from config import settings
from services.security import limiter
from services.exporter import ExportContext, build_ro_crate
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

    mode = "measured" if "n_shots" in results else "statevector"
    qasm_string = results.get("input_qasm", results.get("qasm_string", ""))

    ctx = ExportContext(
        qasm_string=qasm_string,
        results=results,
        mode=mode,
        runner_services=settings.get_runner_services(),
        include_statevectors=payload.include_statevectors,
        author_name=payload.author_name,
        author_affiliation=payload.author_affiliation,
    )

    try:
        zip_bytes = build_ro_crate(ctx)
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
