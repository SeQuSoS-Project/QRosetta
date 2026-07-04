# FastAPI router for on-demand publication figure rendering.
#
# Text artifacts (tables/QASM/glossary) are generated in the browser (no upload). Only
# raster/vector *figures* need matplotlib, so this single endpoint renders one figure on
# demand from the small statevector-stripped report the frontend posts. Stateless, public,
# and stores nothing.

import io

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

import schemas
from services.security import limiter
from services.publication import render_artifact
from qrosetta_commons.helpers import get_logger

logger = get_logger("rosetta-publication-api")

router = APIRouter()


@router.post("/publication/render")
@limiter.limit("30/minute")
async def publication_render(request: Request, payload: schemas.PublicationRenderRequest):
    """Render a single publication figure (svg/png/pdf) and stream the bytes back.

    The report is inferred as measured vs statevector from the presence of ``n_shots``.
    Legends are already carried by the client-side catalog, so none is returned here.
    """
    results = payload.results
    if not results:
        raise HTTPException(status_code=400, detail="No results provided")

    mode = "measured" if "n_shots" in results else "statevector"
    try:
        data, mime, _legend = render_artifact(
            results, mode, payload.artifact_id, payload.format, payload.scale
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown artifact: {payload.artifact_id}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.error("Publication render failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Render failed")

    filename = f"{payload.artifact_id}.{payload.format}"
    return StreamingResponse(
        io.BytesIO(data),
        media_type=mime,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
