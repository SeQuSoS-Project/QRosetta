# Quantum Rosetta

Microservices platform benchmarking 8 quantum simulators (Qiskit, Cirq, Qulacs, Braket, ProjectQ, QuEST, PennyLane Lightning, PennyLane Default) against QASM 2.0 circuits.

Full design spec & constitution: @design_guidelines.txt
Runner canonical IDs & URLs: @rosetta-api/config.py
Pydantic schemas: @rosetta-api/schemas.py

## Architecture

```
Nginx (port 80, public_net) → rosetta-api (isolated_net) → 8 runners (isolated_net)
```

`isolated_net` has `internal: true` — no internet access for API or runners. Nginx is the only public-facing service.

## Code Rules

**Backend:** Router-Service pattern. No logic in `main.py` or routers — services only. Files >300 lines → split into modules. `get_logger("name")` from `qrosetta_commons` everywhere. No `print()`. CPU-heavy math (fidelity, JS divergence) → `loop.run_in_executor()`. Internal calls stay in-process (no loopback HTTP).

**Frontend:** Vanilla JS only. `app.js` (state/events) → `renderers.js` (DOM via `<template>` cloning) → `utils.js` (helpers). No string concatenation for HTML.

**Dependencies:** All `requirements.txt` must use pinned versions. `boto3` and `botocore` must be `<1.36.0` (CSC Allas S3 checksum compat).

## Security Invariants

- Runners: no `ports:` in docker-compose.yml, 1 Gunicorn worker, `isolated_net` only.
- API: never add `public_net`. All containers run as `appuser` (non-root).
- Resource caps on all services (standard: 0.5 CPU, 512MB RAM).
- No curl/wget in runner images. No volume mounts in production.
- Passwords: bcrypt via `passlib`. Never logged or stored plaintext.
- Upload limit: 1MB (middleware). Rate limiting: `slowapi`.

## Naming: Canonical IDs

Docker hostnames (e.g. `pytket-qiskit-runner`) ≠ Canonical IDs (e.g. `qiskit`). Canonical IDs are the dict keys in `config.py:get_runner_services()`. Never use string manipulation to derive one from the other. All API payloads, JS state, and HTML IDs use canonical IDs.

## Benchmarking Contract

Every runner implements `POST /run` (statevector) and `POST /run_measured` (counts). Must return split timing: `compilation_time_sec` (parse+transpile) and `simulation_time_sec` (execute+retrieve). Must do one warm-up run before timing. Memory: `memory_usage_mb` (RSS delta via MemoryMonitor) + `process_peak_mb`.

## Extending

- **New simulator:** `<name>-runner/` folder → `docker-compose.yml` (isolated_net, no ports, resource limits) → `config.py:get_runner_services()` entry with canonical ID as key.
- **New algorithm:** `library.py` (QASM fn) → `routers/generation.py` (register endpoint).
- **New UI feature:** `index.html` (element + ID) → `renderers.js` (render fn) → `app.js` (event handler).

## Running Locally

```bash
docker compose up --build   # first build is slow (9 containers)
# UI: http://localhost  |  API docs: http://localhost/docs

pip install httpx && python3 tests/integration_test_live.py  # smoke test
```

## Cloud (CSC)

- **Rahti (OpenShift):** `strategy: type: Recreate` only — RollingUpdate causes quota deadlocks. See @scripts/deploy_rahti.sh
- **Allas (S3):** `signature_version='s3v4'`, explicit `ContentLength` on `put_object`, encode body to `bytes`.
- **Pukki (PostgreSQL):** URL-encode special chars in `DATABASE_URL` (e.g. `#` → `%23`). S3 upload failure → `db.rollback()`.
