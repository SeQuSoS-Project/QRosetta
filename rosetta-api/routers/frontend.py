"""Frontend routes: the index page, the runner registry, and client-facing limits."""

import html

from services.run_registry import GATE
from fastapi import APIRouter, Request
from fastapi.openapi.docs import get_redoc_html
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from config import settings
from routers.errors import responses
from schemas import AgreementThresholds
from schemas.auth import EMAIL_MAX_LENGTH, PASSWORD_MAX_BYTES, PASSWORD_MIN_CHARS
from schemas.listings import CompilerList, RunnerList, ServerConfig
from services.preparation_limits import bundled_over_prep_limit
from services.report_summary import outcome_catalog
from services.request_defaults import request_defaults
from services.server_info import server_block
from services.security import rate_limit_key
from services.service_listing import compiler_rows, fresh_rows, runner_rows
from services.status_labels import status_labels

router = APIRouter()

SWAGGER_UI_VERSION = "5.33.2"
REDOC_VERSION = "2.1.5"
_CDN = "https://cdn.jsdelivr.net/npm"


def _root_path(request: Request) -> str:
    return request.scope.get("root_path", "").rstrip("/")


def _openapi_url(request: Request) -> str:
    return _root_path(request) + request.app.openapi_url


def swagger_ui_page(request: Request) -> str:
    """Swagger UI from static/vendor, started by js/api_docs_main.js (no inline script)."""
    root = _root_path(request)
    assets = f"{root}/vendor/swagger-ui/{SWAGGER_UI_VERSION}"
    title = html.escape(f"{request.app.title} - Swagger UI")
    openapi_url = html.escape(_openapi_url(request), quote=True)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="{assets}/swagger-ui.css">
<link rel="icon" type="image/png" sizes="32x32" href="{assets}/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="{assets}/favicon-16x16.png">
</head>
<body>
<div id="swagger-ui" data-openapi-url="{openapi_url}"></div>
<script src="{assets}/swagger-ui-bundle.js"></script>
<script type="module" src="{root}/js/api_docs_main.js"></script>
</body>
</html>
"""


@router.get("/docs", include_in_schema=False)
async def swagger_ui(request: Request):
    """The interactive API reference (Swagger UI, vendored at a pinned version)."""
    return HTMLResponse(swagger_ui_page(request))


@router.get("/redoc", include_in_schema=False)
async def redoc(request: Request):
    """The API reference as ReDoc (pinned version)."""
    return get_redoc_html(
        openapi_url=_openapi_url(request), title=f"{request.app.title} - ReDoc",
        redoc_js_url=f"{_CDN}/redoc@{REDOC_VERSION}/bundles/redoc.standalone.js",
        redoc_favicon_url="data:,", with_google_fonts=False)


@router.get("/", response_class=HTMLResponse)
async def read_index():
    """Serves the main HTML page."""
    return FileResponse(
        'static/index.html',
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0"}
    )

@router.get("/runners", responses={200: {"model": RunnerList, "description": "Every registered runner."},
                                   **responses(401, 403, 429)})
async def get_runners(request: Request, fresh: bool = False):
    """Enabled status, availability, max optimization level, and per-level descriptions for
    every runner.

    ``available`` is False for a disabled runner (``unavailable_reason`` "disabled"), and
    for an enabled one that cannot run here: unreachable, or reporting no usable device
    via its GET /capabilities, or (Kubernetes, or a runner without that endpoint)
    ``requires_gpu`` on a deployment without QROSETTA_GPU_AVAILABLE. Probes are cached
    for 60 s. ``device`` is what the runner's /capabilities reported, else None.
    ``precision`` and ``qubit_ordering`` are ``{"statevector": ..., "measured": ...}``: the
    amplitude dtype (e.g. "complex128") and the bit-order label ("lsb" or "msb") the runner
    declares for each endpoint; null where the runner sets it at run time, in which case
    each result records the value used. ``default_selected`` is true for a runner a run that
    names no backends uses when it is available (every enabled runner). ``profiles`` lists
    the built-in profiles the runner belongs to (minimal, cpu, gpu, full). ``backend`` and
    ``version`` are null.

    ``fresh=true`` probes every enabled service now instead of reading the cache, and adds
    ``fresh`` (true when this round probed it), ``reason`` ("busy": a dispatch to it is in
    flight, so it was not probed and reads available; "exclusive_run": an exclusive run holds
    the server, so the last cached values are served; "no_long_lived_services" in Kubernetes
    mode; "disabled"; "not_deployed"), ``error_kind`` ("dns", "connect", "timeout" or "http"
    when the probe got no answer or an error status) and ``probed_at``. It needs a signed-in
    account or the local lifecycle token as the bearer token (401 otherwise, 403 for a
    deactivated account), is limited to 6 requests a minute per account or for the
    lifecycle token (429 with Retry-After), and serves a round younger than 5 s again.
    """
    if fresh:
        return JSONResponse(content=await fresh_rows("runners", request, rate_limit_key(request)))
    return JSONResponse(content=await runner_rows())

@router.get("/config", responses={200: {"model": ServerConfig, "description": "The handshake, limits, request defaults and gate state."}})
async def get_config():
    """Server-side circuit limits, request bounds, agreement-threshold defaults and the
    execution mode.

    ``server`` is the handshake: ``platform_version``, ``api_levels`` ([min, max], the API
    levels this server serves; a breaking change raises the maximum and the previous level
    stays served), ``analysis_version`` (the comparison code that labels new reports),
    ``git_sha`` (the API image's commit) and ``features`` ({name: version}).

    ``status_labels`` maps each live status to ``{label, hint}`` (hint null when there is
    none): ``runs`` for the values of ``runner_statuses``, ``tasks`` for a playlist circuit's
    status (and ``analysing``), ``phases`` for the job's ``phase``. A client shows a status
    missing from the map upper-cased.

    ``summary_outcomes`` lists the outcome names the summaries count, ``roles`` (name ->
    difference, not_established, runs_without_output or agreement), with the
    ``analysis_version`` of the rule that assigns them.

    ``limits`` holds the bounds the run endpoints validate against: qubit caps per mode,
    ``timeout_min``/``timeout_max`` (seconds; larger requests are clamped to
    ``timeout_max``), ``timeout_default`` (every run endpoint), ``shots_min``/``shots_max``,
    ``timing_repeats_max``, ``max_qasm_gate_statements`` (top-level operation statements;
    the header, includes, register declarations and gate definitions are not counted),
    ``max_request_bytes`` (every POST/PUT/PATCH body, the JSON as sent; 413 above it),
    ``max_plan_request_bytes`` (the larger body limit of POST /plan, so a plan can report a
    request over max_request_bytes), ``plan_rate_limit`` (requests per client to
    POST /plan; a client is the account of a valid bearer token, else the client address),
    ``run_rate_limit`` (requests per client to each run, export and lookup route; 429 above
    it) and ``run_rate_limit_per_address`` (requests per client address to each of those
    routes, whatever the accounts), ``render_rate_limit`` and ``render_rate_limit_per_address``
    (the same pair for the two publication render routes), ``login_rate_limit`` and
    ``register_rate_limit`` (requests per client address to POST /auth/token and
    POST /auth/register; 429 above them),
    ``access_token_expire_sec`` (lifetime of a sign-in token),
    ``max_experiment_cells`` (circuits x preprocessing axes of one experiment, unless
    bypass_limits), ``max_batch_tasks`` (circuits of one playlist run, unless bypass_limits),
    ``prep_max_mib`` and ``prep_timeout_sec`` (memory and wall-clock limits of preparing one
    circuit with preprocessing on; a preparation over either is stopped and the run fails),
    ``job_storage_max_mib`` and ``job_storage_min_free_mib`` (the server's disk budget for
    the reports of unexpired jobs, and the free disk space it keeps; a run is refused with 503
    while either is crossed, and a playlist or experiment stops), ``job_ttl_sec`` (seconds a
    finished job, its report and bundle are kept; QROSETTA_JOB_TTL_SEC, 1800 by default and
    86400 in the local compose file), ``job_evictable_after_sec`` (while the job storage is
    over a limit, finished jobs older than this are deleted oldest first before a run is
    refused), ``max_export_items``
    (publication items of one RO-Crate export),
    ``max_label_length`` (characters of a run, circuit, task or author name; control and
    invisible formatting characters are rejected) and the account limits
    ``email_max_length``, ``password_min_chars`` and ``password_max_bytes`` (UTF-8).
    ``default_n_shots`` is the shot count the measured, batch and experiment endpoints use
    when ``n_shots`` is omitted. The top-level keys repeat the qubit, size and gate limits.
    ``bypass_limits_requires_account`` is true when only a signed-in, active account may set
    bypass_limits (every execution mode except local); there it lifts the playlist and
    experiment limits but not the circuit size and statement-count limits, which it lifts
    only in local mode. ``bundled_over_prep_limit`` lists the
    bundled circuits (``source``, ``algorithm``, ``qubits``) whose preparation with
    preprocessing on is known to reach ``prep_max_mib``; runs that include one with
    preprocessing on are refused with 400.
    ``request_defaults`` lists every field of the run request bodies per endpoint
    (``requests``: compare, compare_measured, run_batch_suite, experiments; ``items`` for the
    playlist tasks and experiment circuits): ``server_fills`` false for a field the request
    must carry, else ``default``, the value the server uses when the field is omitted, and
    ``when_omitted`` where that value stands for something the server decides (a generated
    seed, every available runner, the agreement thresholds in ``agreement_thresholds``).
    ``compile_only`` says what makes /compare or /run_batch_suite a compile-only request.
    ``exclusive`` gives ``enabled``, ``max_wait_sec`` and the run gate now:
    ``exclusive_running``, ``exclusive_waiting``, ``shared_running`` (dispatches and fresh-probe
    rounds), ``saves_running`` (gated saves of a report or crate) and ``host_load_running``
    (open host-load notices of the qrosetta command).
    """
    return JSONResponse(content={
        "server": server_block(),
        "status_labels": status_labels(),
        "summary_outcomes": outcome_catalog(),
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
        "request_defaults": request_defaults(),
        "bypass_limits_requires_account": settings.bypass_requires_account(),
        "bundled_over_prep_limit": bundled_over_prep_limit(),
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
            "max_plan_request_bytes": settings.MAX_PLAN_REQUEST_BYTES,
            "plan_rate_limit": settings.PLAN_RATE_LIMIT,
            "run_rate_limit": settings.RUN_RATE_LIMIT,
            "run_rate_limit_per_address": settings.RUN_RATE_LIMIT_PER_ADDRESS,
            "render_rate_limit": settings.RENDER_RATE_LIMIT,
            "render_rate_limit_per_address": settings.RENDER_RATE_LIMIT_PER_ADDRESS,
            "login_rate_limit": settings.LOGIN_RATE_LIMIT,
            "register_rate_limit": settings.REGISTER_RATE_LIMIT,
            "access_token_expire_sec": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "max_experiment_cells": settings.MAX_EXPERIMENT_CELLS,
            "max_batch_tasks": settings.MAX_BATCH_TASKS,
            "prep_max_mib": settings.PREP_MAX_MIB,
            "prep_timeout_sec": settings.PREP_TIMEOUT_SEC,
            "job_storage_max_mib": settings.JOB_SPILL_MAX_MIB,
            "job_storage_min_free_mib": settings.JOB_SPILL_MIN_FREE_MIB,
            "job_ttl_sec": settings.JOB_TTL_SEC,
            "job_evictable_after_sec": settings.JOB_EVICTABLE_AFTER_SEC,
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


@router.get("/compilers", responses={200: {"model": CompilerList, "description": "Every registered compile-only service."},
                                     **responses(401, 403, 429)})
async def get_compilers(request: Request, fresh: bool = False):
    """Compile-only services: id, display name, enabled and available state, the
    description of each optimization level, and ``versions`` as the running image reports
    them (pip SDK versions, native components built from source, build-file sha256, image
    commit; null when no long-lived service answered, as in Kubernetes mode). A compiler
    turns a run's circuit into circuit text only; it is never simulated or compared (see
    the compilers field of the run payloads). ``default_selected`` is false: a compiler
    runs only when a request names it. ``profiles`` is ["compilers", "full"] for an enabled
    compiler. ``backend`` and ``version`` are null. ``fresh=true`` as for GET /runners.
    ``fresh=true`` probes every enabled service now instead of reading the cache, and adds
    ``fresh`` (true when this round probed it), ``reason`` ("busy": a dispatch to it is in
    flight, so it was not probed and reads available; "exclusive_run": an exclusive run holds
    the server, so the last cached values are served; "no_long_lived_services" in Kubernetes
    mode; "disabled"; "not_deployed"), ``error_kind`` ("dns", "connect", "timeout" or "http"
    when the probe got no answer or an error status) and ``probed_at``. It needs a signed-in
    account or the local lifecycle token as the bearer token (401 otherwise, 403 for a
    deactivated account), is limited to 6 requests a minute per account or for the
    lifecycle token (429 with Retry-After), and serves a round younger than 5 s again.
    """
    if fresh:
        return JSONResponse(content=await fresh_rows("compilers", request, rate_limit_key(request)))
    return JSONResponse(content=await compiler_rows())
