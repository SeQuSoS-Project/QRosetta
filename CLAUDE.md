# Quantum Rosetta

Microservices platform benchmarking 16 quantum simulators against QASM 2.0 circuits.
Two execution modes: `local` (Docker Compose, HTTP dispatch) and `kubernetes` (CSC Rahti, K8s Job dispatch).

Full design spec: @design_guidelines.txt
Runner canonical IDs & config: @rosetta-api/config.py
Pydantic schemas: @rosetta-api/schemas/ (package: benchmark.py, auth.py, history.py)

## Architecture

```
Local:  Nginx (port 80, public_net) → rosetta-api (isolated_net) → 16 runners (isolated_net, HTTP)
K8s:    rosetta-api pod → K8s Job pods (ephemeral, QROSETTA_PAYLOAD env var → S3 result)
```

`isolated_net` has `internal: true` in Docker Compose. In K8s mode, runners are Jobs — no persistent network.

## rosetta-api Layout

```
rosetta-api/
  main.py                    — mounts routers only, no logic
  config.py                  — all settings, runner URLs, limits (MAX_QASM_SIZE, RUNNER_TIMEOUT_SEC, etc.)
  routers/
    benchmark.py             — /compare, /compare_measured, /batch, /job/* endpoints
    generation.py            — circuit generation endpoints
    frontend.py              — serves index.html, static files
    history.py               — run history CRUD
    auth.py                  — login/register/logout
  services/
    dispatcher.py            — routes to HTTP or K8s dispatch
    dispatcher_http.py       — local Docker Compose HTTP dispatch
    dispatcher_k8s.py        — K8s Job spawn + S3 result fetch
    job_manager.py           — async job state (ACTIVE_JOBS)
    circuit_library.py       — QASM circuit generation (exec's algorithm_templates/)
    validator.py             — QASM size/gate-count guards
    aggregator.py            — fidelity, JS divergence, consensus
    storage.py               — S3 / local file abstraction for run reports
    security.py              — JWT creation/verification, get_current_user
    quirk_converter.py       — OpenQASM 2.0 → Quirk JSON
    analysis/                — divergence, performance, resource report builders
  db/
    database.py              — SQLAlchemy engine + get_db()
    models.py                — ORM models (User, SavedCircuit, RunHistory)
  schemas/
    benchmark.py             — QasmPayload, ComparisonResult, JobStatusResponse, etc.
    auth.py                  — UserCreate, UserResponse, Token
    history.py               — SavedCircuit*, RunHistory* models
  algorithm_templates/       — JSON files: {id, code} pairs executed by circuit_library.py
  circuits/                  — Example QASM files for testing
  tests/
    unit/                    — pytest unit tests
```

## Code Rules

**Backend:** Router-Service pattern. No logic in `main.py` or routers — services only. Files >300 lines → split. `get_logger("name")` everywhere. No `print()`. CPU-heavy math → `loop.run_in_executor()`. Internal calls stay in-process (no loopback HTTP).

**Frontend:** Vanilla JS. `state.js` (global state + dispatch) → `app.js` (events/orchestration) → `renderers.js` / `tables_renderer.js` (DOM only) → `utils.js` (helpers). No innerHTML string concat — use `<template>` cloning. Shared controls (timeout, opt level) live in the config panel with one element ID.

**Dependencies:** Pinned versions in all `requirements.txt`. `boto3` and `botocore` must be `<1.36.0` (CSC Allas S3 checksum compat).

## Security Invariants

- Runners: no `ports:` in docker-compose.yml, `isolated_net` only.
- API: never add `public_net`. All containers run as `appuser` (non-root).
- No curl/wget in runner images. No volume mounts in production.
- Passwords: bcrypt via `passlib`. Never logged or stored plaintext.
- Upload limit: 1MB. Rate limiting: `slowapi`.
- Limits live in `config.py` Settings: `MAX_QUBITS_STATEVECTOR=18`, `MAX_QUBITS_MEASURED=24`, `MAX_QASM_SIZE=1_000_000`, `MAX_QASM_GATES=10_000`. Never hardcode these values elsewhere.
- `check_qubits_limit(payload["circuit_data"], 24)` is the first call in every runner's try block.

## Naming: Canonical IDs

Docker hostnames (e.g. `pytket-qiskit-runner`) ≠ Canonical IDs (e.g. `qiskit`).
Canonical IDs = dict keys in `config.py:get_runner_services()`. Used in all payloads, JS state, HTML IDs, runner JSON responses.
Infrastructure names = used only in `config.py` base_url values and image registry paths.
Never derive one from the other with string manipulation.

## Benchmarking Contract

Every runner implements `process_run(payload)` and `process_run_measured(payload)`, plus FastAPI endpoints and K8s CLI entrypoint.
Returns: `compilation_time_sec` + `simulation_time_sec` (must sum to `execution_time_sec`), `memory_usage_mb`, `process_peak_mb`.
One warm-up run before timing. `check_qubits_limit` before compilation.

## K8s Dispatch

Payload via `QROSETTA_PAYLOAD` env var (no S3 pending key).
Results written to S3 `jobs/completed/<job_id>.json`.
Phase 1: poll K8s pod status. Phase 2: exponential backoff S3 fetch.
Job spec: `backoffLimit=0`, `ttlSecondsAfterFinished=300`, `imagePullPolicy=IfNotPresent`.
Resources: requests=100m/256Mi, limits=500m/1Gi (5:1 ratio = Rahti LimitRange max).

## Extending

- **New simulator:** `runners/<name>-runner/` (Dockerfile + main.py with check_qubits_limit) → `docker-compose.yml` → `config.py:get_runner_services()` → `scripts/safe_boot.sh` RUNNERS array → `scripts/rahti_push.sh` SERVICE_MAP.
- **New algorithm:** `services/circuit_library.py` (add QASM fn) → `algorithm_templates/` (add JSON template) → `routers/generation.py` (endpoint).
- **New UI feature:** `index.html` (element + ID) → renderer → `app.js` (handler).

## Running Locally

```bash
docker compose build && docker compose up
# UI: http://localhost  |  API docs: http://localhost/docs
```

## Cloud (CSC)

- **Rahti:** `strategy: Recreate` only. No ResourceQuota — LimitRange enforces min=50m, max=4CPU, maxLimitRequestRatio=5. Deploy: `docker compose build && ./scripts/rahti_push.sh`
- **Allas (S3):** `signature_version='s3v4'`, explicit `ContentLength` on `put_object`, body as `bytes`.
- **Pukki (PostgreSQL):** URL-encode passwords in `DATABASE_URL` (e.g. `#` → `%23`). S3 failure → `db.rollback()`.
- **safe_boot.sh:** has hardcoded RUNNERS array — must be updated when adding a new runner.
