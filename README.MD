# Quantum Rosetta

**Quantum Rosetta** runs one OpenQASM 2.0 circuit across many quantum simulator backends and
reports both what each backend cost and whether they agree with each other. Each backend runs
in its own container with its own pinned dependencies, behind a single benchmarking contract,
so results are comparable across SDKs that could not otherwise share a process.

Every result set exports as a self-contained RO-Crate 1.1 archive holding the original
circuit, the circuit the API dispatched, the circuit each backend executed, the metrics, the
outputs, the run configuration and seeds, and the SDK versions that produced them.

## What it measures

For each backend, per run:

| Metric | Meaning |
| --- | --- |
| `compilation_time_sec` | Wall clock, t0..t1: parse the QASM, transpile, build the backend's native circuit |
| `simulation_time_sec` | Wall clock, t2..t3: execute and return the statevector or draw the shots |
| `simulation_cpu_time_sec` | Process CPU time (all threads) over t2..t3 |
| `cpu_time_sec` | Process CPU time of the whole runner process: interpreter start, SDK import, warm-up, timed run |
| `memory_usage_mb` | Peak RSS minus baseline RSS over the simulation window (kernel high-water mark, VmHWM) |
| `process_peak_mb` | Absolute peak RSS over the simulation window |
| `process_peak_rss_mb` | Peak RSS of the simulating process over its whole life; resources are ranked by this |
| `theoretical_statevector_mb` | `(2^N x 16) / 1024^2`, a dense complex128 statevector, for reference |
| `precision` | Amplitude dtype the backend simulated in (`complex128`, or `complex64` for qsim, Qrisp, TorchQuantum, Cirq's measured path) |

Each backend runs the circuit once as a discarded warm-up and then once timed, so every
timing is a single sample (`timing_samples = 1`). Every runner is started with
`OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS` and `NUMEXPR_NUM_THREADS` set
to 1. `memory_method` and `process_peak_rss_method` record `vmhwm`, or the fallback used
(`sampled_10ms`, `getrusage`) where the kernel counter is unavailable.

Across backends, per run, every pair gets an agreement label: the first registered transform
(direct, global phase, bit reversal, qubit permutation up to 7 qubits) under which the two
outputs agree, `agree_after_normalization` when an input norm was off, a residual/threshold
label when none applies, or `not_comparable` with a reason. Statevector pairs agree when
fidelity, stored unrounded, is at least 1 - `fidelity_tolerance` (default 1e-5); the
tolerances used are recorded in every pair record. Measured pairs are compared by
Jensen-Shannon divergence (nats) and Hellinger distance, with a chi-square and G-test of
homogeneity, Benjamini-Hochberg corrected across pairs.

Measured runs record a master seed; each backend receives a `runner_seed` made of the first
4 bytes of `sha256(f"{master}:{runner_key}")`, read big-endian with the top bit cleared, so
no two backends draw the same shot sequence. Any change the API makes to the circuit before dispatch
is listed with an `API:` prefix in `preprocessing_applied`, and each dispatched circuit is
written to the RO-Crate.

The server keeps each job's untruncated report for 30 minutes: `GET /jobs/{job_id}/report`
returns it as JSON and `POST /jobs/{job_id}/export` builds the RO-Crate from it. The copy
sent to the browser omits statevectors of circuits over 14 qubits. `POST /export` builds a
crate from a report in the request body (1 MB limit), for runs loaded from history.

## Architecture

Three tiers, with Nginx as the only public-facing service.

**Nginx** — reverse proxy and static file server. Serves the frontend and proxies API
requests to the backend. The API is never exposed directly.

**rosetta-api** — orchestration, circuit generation, and comparative analysis. FastAPI under
Gunicorn/Uvicorn. Dispatches work to the runners, aggregates results, computes the agreement
and performance reports off the request path, and builds the RO-Crate exports.

**Runners** — 16 isolated simulator services, 14 enabled by default. Each implements the same
two-endpoint contract (`POST /run` for statevectors, `POST /run_measured` for sampled counts)
and returns the same set of fields.

| Enabled | |
| --- | --- |
| Qiskit Aer, Cirq, Qulacs, QuEST | PennyLane Lightning, PennyLane Default |
| qsim-Cirq, Qibo, Qrisp, myQLM | PyQuil, TorchQuantum, Quimb, cuQuantum |

Braket and ProjectQ ship with the stack but are disabled in `rosetta-api/config.py` because of
persistent backend errors. Re-enable either by setting `enabled=True` there and adding it to
`scripts/safe_boot.sh`.

The stack runs in two modes, selected by `EXECUTION_MODE`:

- `local` — Docker Compose. Runners are long-running HTTP services on an internal network.
- `kubernetes` — CSC Rahti. Runners are ephemeral Jobs spawned per request, exchanging
  results through S3.

## Getting started

Requires Docker Engine 20.10+ and Docker Compose v2.

```bash
git clone https://github.com/SeQuSoS-Project/qrosetta.git
cd qrosetta
cp .env.example .env      # then fill in your credentials
./scripts/safe_boot.sh    # or: docker compose up --build
```

The first build takes a while: it compiles dependencies for 16 separate containers.

- Web UI — http://localhost
- API reference — http://localhost/docs (Swagger) and `docs.html` for the written guide

`SECRET_KEY` must be set whenever `EXECUTION_MODE` is not `local`; the API refuses to start
without it. Locally, leaving it empty generates a random key per process.

### Deploying

```bash
./scripts/rahti_push.sh [namespace] [service ...]   # CSC Rahti (OpenShift)
./scripts/deploy.sh                                 # GCP Cloud Run: API
./scripts/deploy_frontend.sh                        # GCP Cloud Run: frontend
```

`rahti_push.sh` builds, tags each image with both its git hash and `:latest`, pushes, applies
the manifests, and waits for the rollout.

## Tests

```bash
cd rosetta-api
pip install -r requirements.txt -r tests/requirements.txt
pip install ../shared
PYTHONPATH=. pytest tests/unit/
```

`tests/integration/` holds live-stack checks that need the whole stack running. CI does not
run them; see the README there.

## Project layout

```text
.
├── docker-compose.yml       Orchestration, healthchecks, resource limits
├── nginx/                   Reverse proxy for the local stack
├── infra/                   Rahti manifests and the Cloud Run frontend image
├── rosetta-api/             The orchestrator
│   ├── main.py              Mounts routers only
│   ├── routers/             Request validation and HTTP shaping
│   ├── services/            Business logic, dispatch, analysis, export
│   ├── schemas/             Pydantic request/response models
│   ├── db/                  SQLAlchemy models and session handling
│   ├── static/              Web frontend
│   └── tests/unit/          Unit test suite (run by CI)
├── runners/<name>-runner/   One directory per simulator backend
├── shared/qrosetta_commons/ The benchmarking contract shared by every runner
├── scripts/                 Boot and deployment scripts
└── tests/integration/       Live-stack checks (need the stack up)
```

## Security

- Only Nginx is publicly reachable; runners expose no ports and the API is not on the public
  network.
- All containers run as an unprivileged `appuser`.
- Passwords are hashed with bcrypt and never logged or stored in plaintext; sessions are JWT.
- Every endpoint that reads or writes user data requires authentication and filters by the
  authenticated user.
- Circuit size, gate count, qubit count, upload size, and run fan-out are all capped
  server-side; public endpoints are rate-limited.
- All `requirements.txt` files pin exact versions, with a `requirements.lock` alongside.

## Contributing

See `CONTRIBUTING.md` for the full guide to adding a simulator backend or an algorithm
template.

## Citing

See `CITATION.cff`.
