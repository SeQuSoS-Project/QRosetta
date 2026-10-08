"""Frontend routes: the index page, the runner registry, and client-facing limits."""

from services.run_registry import GATE
from fastapi import APIRouter, Request
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import FileResponse, JSONResponse
from config import settings
from schemas import AgreementThresholds
from schemas.auth import EMAIL_MAX_LENGTH, PASSWORD_MAX_BYTES, PASSWORD_MIN_CHARS
from services.availability import runner_availability
from services.compilation import COMPILER_SERVICES

router = APIRouter()

SWAGGER_UI_VERSION = "5.17.14"
REDOC_VERSION = "2.1.5"
_CDN = "https://cdn.jsdelivr.net/npm"


def _openapi_url(request: Request) -> str:
    return request.scope.get("root_path", "").rstrip("/") + request.app.openapi_url


@router.get("/docs", include_in_schema=False)
async def swagger_ui(request: Request):
    """The interactive API reference (Swagger UI at a pinned version)."""
    return get_swagger_ui_html(
        openapi_url=_openapi_url(request), title=f"{request.app.title} - Swagger UI",
        swagger_js_url=f"{_CDN}/swagger-ui-dist@{SWAGGER_UI_VERSION}/swagger-ui-bundle.js",
        swagger_css_url=f"{_CDN}/swagger-ui-dist@{SWAGGER_UI_VERSION}/swagger-ui.css",
        swagger_favicon_url="data:,")


@router.get("/redoc", include_in_schema=False)
async def redoc(request: Request):
    """The API reference as ReDoc (pinned version)."""
    return get_redoc_html(
        openapi_url=_openapi_url(request), title=f"{request.app.title} - ReDoc",
        redoc_js_url=f"{_CDN}/redoc@{REDOC_VERSION}/bundles/redoc.standalone.js",
        redoc_favicon_url="data:,", with_google_fonts=False)


@router.get("/")
async def read_index():
    """Serves the main HTML page."""
    return FileResponse(
        'static/index.html',
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0"}
    )

@router.get("/runners")
async def get_runners():
    """Enabled status, availability, max optimization level, and per-level descriptions for
    every runner.

    ``available`` is False for a disabled runner (``unavailable_reason`` "disabled"), and
    for an enabled one that cannot run here: unreachable, or reporting no usable device
    via its GET /capabilities, or (Kubernetes, or a runner without that endpoint)
    ``requires_gpu`` on a deployment without QROSETTA_GPU_AVAILABLE. Probes are cached
    for 60 s. ``device`` is what the runner's /capabilities reported, else None.
    """
    services = settings.get_runner_services()
    availability = await runner_availability()
    result = []
    for name, config in services.items():
        opt_levels = config.get("optimization_levels", {})

        opt_levels_str = {str(k): v for k, v in opt_levels.items()}
        enabled = config.get("enabled", True)
        info = availability.get(name) or {"available": False, "reason": "disabled", "device": None}
        result.append({
            "id": name,
            "enabled": enabled,
            "available": bool(enabled and info["available"]),
            "unavailable_reason": None if (enabled and info["available"]) else (info["reason"] or "unavailable"),
            "device": info.get("device"),
            "requires_gpu": bool(config.get("requires_gpu", False)),
            "max_level": max(opt_levels.keys()) if opt_levels else 0,
            "optimization_levels": opt_levels_str,
        })
    return JSONResponse(content=result)

@router.get("/config")
async def get_config():
    """Server-side circuit limits, request bounds, agreement-threshold defaults and the
    execution mode.

    ``limits`` holds the bounds the run endpoints validate against: qubit caps per mode,
    ``timeout_min``/``timeout_max`` (seconds; larger requests are clamped to
    ``timeout_max``), ``timeout_default`` (every run endpoint), ``shots_min``/``shots_max``,
    ``timing_repeats_max``, ``max_qasm_gate_statements`` (top-level operation statements;
    the header, includes, register declarations and gate definitions are not counted),
    ``max_request_bytes`` (every POST/PUT/PATCH body, the JSON as sent; 413 above it),
    ``run_rate_limit`` (requests per client address to each run, export and lookup route;
    429 above it), ``access_token_expire_sec`` (lifetime of a sign-in token),
    ``max_experiment_cells`` (circuits x preprocessing axes of one experiment, unless
    bypass_limits), ``max_export_items`` (publication items of one RO-Crate export),
    ``max_label_length`` (characters of a run, circuit, task or author name; control and
    invisible formatting characters are rejected) and the account limits
    ``email_max_length``, ``password_min_chars`` and ``password_max_bytes`` (UTF-8).
    ``default_n_shots`` is the shot count the measured, batch and experiment endpoints use
    when ``n_shots`` is omitted. The top-level keys repeat the qubit, size and gate limits.
    """
    return JSONResponse(content={
        "max_qubits_statevector": settings.MAX_QUBITS_STATEVECTOR,
        "max_qubits_measured": settings.MAX_QUBITS_MEASURED,
        "max_qubits_compile": settings.MAX_QUBITS_COMPILE,
        "max_qasm_size": settings.MAX_QASM_SIZE,
        "max_qasm_gates": settings.MAX_QASM_GATES,
        "max_runs_per_runner": settings.MAX_RUNS_PER_RUNNER,
        "max_total_runs": settings.MAX_TOTAL_RUNS,
        "execution_mode": settings.EXECUTION_MODE,
        "queue_max_wait_sec": settings.RUNNER_QUEUE_MAX_WAIT_SEC,
        "agreement_threshold_defaults": AgreementThresholds().model_dump(),
        "default_n_shots": settings.DEFAULT_SHOTS,
        "limits": {
            "max_qubits_statevector": settings.MAX_QUBITS_STATEVECTOR,
            "max_qubits_measured": settings.MAX_QUBITS_MEASURED,
            "max_qubits_compile": settings.MAX_QUBITS_COMPILE,
            "timeout_min": settings.MIN_TIMEOUT_SEC,
            "timeout_max": settings.RUNNER_TIMEOUT_SEC,
            "timeout_default": settings.DEFAULT_TIMEOUT_SEC,
            "timing_repeats_max": settings.MAX_TIMING_REPEATS,
            "max_qasm_gate_statements": settings.MAX_QASM_GATES,
            "max_expanded_gates": settings.MAX_EXPANDED_GATES,
            "max_nested_gate_calls": settings.MAX_NESTED_GATE_CALLS,
            "shots_min": settings.MIN_SHOTS,
            "shots_max": settings.MAX_SHOTS,
            "shots_default": settings.DEFAULT_SHOTS,
            "max_request_bytes": settings.MAX_UPLOAD_BYTES,
            "run_rate_limit": settings.RUN_RATE_LIMIT,
            "access_token_expire_sec": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "max_experiment_cells": settings.MAX_EXPERIMENT_CELLS,
            "max_export_items": settings.MAX_EXPORT_ITEMS,
            "max_label_length": settings.MAX_LABEL_LENGTH,
            "email_max_length": EMAIL_MAX_LENGTH,
            "password_min_chars": PASSWORD_MIN_CHARS,
            "password_max_bytes": PASSWORD_MAX_BYTES,
        },
        "exclusive": {"enabled": settings.EXCLUSIVE_ENABLED,
                      "max_wait_sec": settings.EXCLUSIVE_MAX_WAIT_SEC,
                      **GATE.status()},
    })


@router.get("/compilers")
async def get_compilers():
    """Compile-only services: id, display name, enabled and available state, the
    description of each optimization level, and ``versions`` as the running image reports
    them (pip SDK versions, native components built from source, build-file sha256, image
    commit; null when no long-lived service answered, as in Kubernetes mode). A compiler
    turns a run's circuit into circuit text only; it is never simulated or compared (see
    the compilers field of the run payloads)."""
    availability = await runner_availability(services=COMPILER_SERVICES)
    result = []
    for cid, svc in COMPILER_SERVICES.items():
        enabled = svc.get("enabled", True)
        info = availability.get(cid) or {"available": False, "reason": "disabled"}
        result.append({
            "id": cid,
            "name": svc["name"],
            "enabled": enabled,
            "available": bool(enabled and info["available"]),
            "unavailable_reason": None if (enabled and info["available"]) else (info["reason"] or "unavailable"),
            "optimization_levels": {str(k): v for k, v in svc["optimization_levels"].items()},
            "versions": info.get("versions"),
        })
    return JSONResponse(content=result)
