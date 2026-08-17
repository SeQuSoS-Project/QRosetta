# Adding a new simulator backend

QRosetta dispatches one OpenQASM 2.0 circuit to a fleet of "runners" — one small FastAPI service
per simulator SDK — and compares what comes back. Adding a new simulator means adding one more
runner that speaks the same contract as every other one. This guide walks through that contract
using the existing runners as reference; `runners/qibo-runner/` is a good short one to read
alongside this document.

## 1. Directory layout

Each runner lives in its own directory under `runners/`:

```
runners/<name>-runner/
├── main.py              # the runner itself
├── Dockerfile
├── requirements.txt      # direct dependencies, pinned to exact versions
└── requirements.lock     # full pip freeze of the built image, for reproducible builds
```

## 2. The contract: `process_run` and `process_run_measured`

A runner implements exactly two functions:

- `process_run(payload: dict) -> dict` — exact statevector simulation.
- `process_run_measured(payload: dict) -> dict` — shot-based measurement simulation.

Both receive the request payload as a plain dict (see `shared/qrosetta_commons/models.py`'s
`CircuitPayload`/`MeasuredCircuitPayload` for the exact fields: `circuit_data` is the OpenQASM 2.0
string; `optimization_level`; `apply_preprocessing`; `MeasuredCircuitPayload` additionally has
`n_shots` and `seed`). Both must return a result dict built from the shared helpers in
`shared/qrosetta_commons/helpers.py` — never assemble the result dict by hand:

```python
from qrosetta_commons.helpers import (
    MemoryMonitor, get_logger, check_qubits_limit,
    MAX_QUBITS_STATEVECTOR, MAX_QUBITS_MEASURED,
    with_sdk_versions, statevector_result, counts_result, runner_error,
    register_runner_endpoints, run_cli_main,
)

@with_sdk_versions
def process_run(payload: dict) -> dict:
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_STATEVECTOR)

        t0 = time.perf_counter()
        circuit, preprocessing_applied, transpiled_qasm = _compile(payload["circuit_data"], payload.get("optimization_level", 0))
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        with MemoryMonitor(interval=0.01) as monitor:
            t2 = time.perf_counter()
            statevector = _simulate(circuit)
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        return statevector_result(
            simulator="my-sdk", statevector=statevector,
            compilation_time=compilation_time, simulation_time=simulation_time,
            monitor=monitor, qubit_ordering="msb",  # verified, not assumed - see section 3
            preprocessing_applied=preprocessing_applied, transpiled_qasm=transpiled_qasm)
    except Exception as e:
        return runner_error("my-sdk", e)
```

`process_run_measured` follows the same shape, using `counts_result` instead and adding
`n_shots`/`seed` handling (see `runners/qibo-runner/main.py` for a short complete example, or
`runners/qrisp-runner/main.py` for one where the two endpoints use genuinely different native
methods).

**Always wrap the body in try/except and return `runner_error(simulator_name, exc)` on failure.**
A caught exception that gets turned into an honest error is a correct result. Do not catch an
exception and return a default or placeholder value instead — that reports a failure as a
success.

**Never construct the result dict's fields directly.** `statevector_result`/`counts_result`
compute `execution_time_sec`, `memory_usage_mb`, `process_peak_mb`, `theoretical_statevector_mb`,
and encode the statevector to the wire format. Every runner uses the same two builder functions
so the field names and formats stay identical across the fleet.

You do **not** need to add a warm-up run, retry logic, timeout handling, `n_shots`/gate-count
echoing, or CPU-time/process-peak-memory measurement yourself — every runner is invoked through a
shared wrapper (`run_isolated`/`run_with_uniform_measurement` in `helpers.py`) that adds a uniform
warm-up, hard wall-clock timeout, and additive resource-usage fields on top of whatever your
`process_run`/`process_run_measured` returns. Just implement the SDK-specific compile+simulate
logic and return one of the two result-builder calls.

The rest of `main.py` is two lines, identical across every runner:

```python
from fastapi import FastAPI

app = FastAPI(title="My-SDK Runner")

# ... process_run / process_run_measured defined above ...

register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "My-SDK")
```

`register_runner_endpoints` wires `process_run`/`process_run_measured` to the `POST /run` and
`POST /run_measured` HTTP endpoints (served by the `gunicorn`/`uvicorn` command in the
Dockerfile). `run_cli_main` additionally supports invoking the runner as a one-shot CLI command
with `--endpoint run|run_measured --payload '<json>'` (used for local debugging) or
`--s3-job-id <id>` (the path Kubernetes deployments use, fetching the payload from and uploading
the result to object storage).

## 3. Qubit ordering must be verified empirically, not assumed

Every result declares `qubit_ordering` as `"msb"` or `"lsb"` — whether qubit 0 is the
most-significant or least-significant bit of the statevector index / counts bitstring. SDKs
disagree on this, and some SDKs use one convention for statevectors and the *other* for
measurement counts.

To determine your runner's actual convention: build a circuit that applies a single X gate to
qubit 0 (and nothing else) on an n-qubit register, run it through your `process_run`, and check
which index of the returned array is nonzero. If it's index `2^(n-1)`, qubit 0 is the
most-significant bit (`"msb"`). If it's index `1`, qubit 0 is the least-significant bit
(`"lsb"`). Do the equivalent check for `process_run_measured` independently — do not assume it
matches the statevector endpoint's convention just because the SDK is the same.

## 4. Preprocessing

If your runner needs to transform the incoming QASM before simulating it (stripping
barriers, rebasing gates to a supported set, decomposing unsupported instructions), gate that
behind `payload.get("apply_preprocessing", True)` and record every applied transform as a
plain-language string in the `preprocessing_applied` list passed to `statevector_result`/
`counts_result`. This list is shown to the user and included in the exported provenance —
each entry should say what the transform does, not just its name.

## 5. Dockerfile

Follow the existing pattern (`runners/qibo-runner/Dockerfile` is a minimal example):

- Pin the base image by digest: `FROM python:3.10-slim@sha256:...` (or whichever tag/digest your
  SDK actually needs — check its own supported Python versions first).
- Create and switch to a non-root user (`appuser`), with `HOME=/home/appuser` and group
  permissions set so the image also runs correctly under OpenShift's arbitrary-UID model.
- Install from `requirements.lock`, not `requirements.txt`, for the reproducible build.
- Install the shared `qrosetta_commons` package from `shared/` as a separate step, after your
  SDK's own dependencies.
- End with the same `gunicorn` + `uvicorn.workers.UvicornWorker` command line the other runners
  use.

If your SDK needs system packages (a C++ toolchain, BLAS, OpenMP, etc.), install them via
`apt-get` before the `pip install` steps, and pin the specific packages needed rather than
installing broad build tool groups speculatively.

## 6. `requirements.txt` and `requirements.lock`

`requirements.txt` lists your runner's *direct* dependencies with exact pins (SDK, `fastapi`,
`uvicorn[standard]`, `psutil`, `gunicorn`, plus whatever your SDK needs). `requirements.lock` is
the full `pip freeze` output of a container actually built from that `requirements.txt` — generate
it by building the image once, then running `pip freeze` inside it, and commit the result with a
comment noting the date it was generated. This is what makes the build reproducible: the
Dockerfile installs from the lock file, not the loose direct-dependency list.

## 7. Registering the runner

A runner has to be listed in five places. `config.py` is the only one the application reads at
runtime; the rest are build and deployment lists, and a runner missing from any of them is
silently excluded from that path rather than failing loudly.

| File | What it controls | Missing it means |
| --- | --- | --- |
| `rosetta-api/config.py` — `get_runner_services()` | Canonical id, URL, capabilities, enabled flag | The API never dispatches to it |
| `docker-compose.yml` | The local container | Nothing to dispatch to locally |
| `scripts/safe_boot.sh` — `RUNNERS` | The local boot order | Excluded from every local boot |
| `scripts/rahti_push.sh` — `SERVICE_MAP` | The pushed image | Kubernetes Jobs cannot pull it |
| `tests/integration/test_runner_contract_asymmetric.py` — `ACTIVE_STATEVECTOR_RUNNERS` | Contract coverage | Never contract-tested |

**`rosetta-api/config.py`**, inside `get_runner_services()`, add an entry keyed by your runner's
short id (this id is what appears everywhere in results, config, and the UI):

```python
"my-sdk": {
    "base_url": self.MY_SDK_RUNNER_URL,
    "capabilities": ["statevector", "measured_native"],  # or "measured_sampled" if you derive
                                                          # counts from the statevector rather
                                                          # than sampling shots natively
    "enabled": True,
    "optimization_levels": {
        0: "No optimization",
        1: "Describe what level 1 actually does for this SDK",
    },
},
```

and add the corresponding `MY_SDK_RUNNER_URL: str = "http://my-sdk-runner:8000"` field near the
other `*_RUNNER_URL` settings.

**`docker-compose.yml`**, add a service block (copy an existing runner's block and adjust the
paths/name):

```yaml
my_sdk_runner:
  build:
    context: .
    dockerfile: ./runners/my-sdk-runner/Dockerfile
  container_name: my-sdk-runner
  networks:
    - isolated_net
  deploy:
    resources:
      limits:
        cpus: "0.5"
        memory: "512M"
```

Runners are internal-only — not exposed to the host or through nginx — the API reaches them over
the compose network by container name.

## 8. Testing before you're done

- `docker compose build my_sdk_runner && docker compose up -d my_sdk_runner`, then exercise both
  endpoints directly against a small circuit (Bell state or similar) and read the actual response
  — confirm `error` is `null`, the statevector/counts look correct, and `qubit_ordering` matches
  what you verified in step 3.
- Add your runner's id to `ACTIVE_STATEVECTOR_RUNNERS` in
  `tests/integration/test_runner_contract_asymmetric.py` — one list drives both the statevector and the
  measured check — and run it against the live stack. This test is
  deliberately asymmetric (not a Bell/GHZ state) — a symmetric smoke test can pass even when a
  runner silently returns the all-zeros state or has its bit-order label backwards, so this is the
  test that actually catches that failure mode.
- Run the full unit suite (`pytest rosetta-api/tests/unit`) to confirm nothing else broke.
