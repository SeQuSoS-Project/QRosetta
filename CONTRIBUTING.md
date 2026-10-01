# Adding a new simulator backend

QRosetta dispatches one OpenQASM 2.0 circuit to a fleet of "runners" — one small FastAPI service
per simulator SDK — and compares what comes back. Adding a simulator means adding one more
runner that speaks the same contract as every other one. `runners/qibo-runner/main.py` is a
short complete example to read alongside this guide.

## 1. Directory layout

Each runner lives in its own directory under `runners/`:

```
runners/<name>-runner/
├── main.py              # the runner itself
├── Dockerfile
├── requirements.txt      # direct dependencies, pinned to exact versions
└── requirements.lock     # full pip freeze of the built image, for reproducible builds
```

The directory name must equal the hostname in the runner's `base_url` in `config.py`
(`http://<name>-runner:8000` lives in `runners/<name>-runner/`). The exporter and the
Kubernetes dispatcher derive the directory and image name from that hostname, and
`rosetta-api/tests/unit/test_runner_registry_sync.py` fails when they differ.

## 2. The contract: `process_run` and `process_run_measured`

A runner implements two functions:

- `process_run(payload: dict) -> dict` — statevector simulation.
- `process_run_measured(payload: dict) -> dict` — shot-based measurement simulation.

Both receive the request payload as a plain dict (see `shared/qrosetta_commons/models.py`
`CircuitPayload` / `MeasuredCircuitPayload`): `circuit_data` is the OpenQASM 2.0 text,
plus `optimization_level` and `apply_preprocessing`; the measured payload adds `n_shots`
and `seed`, the runner's own seed derived by the API from the run's master seed. Both
delegate to the shared measurement instrument in `shared/qrosetta_commons/helpers.py`,
`run_statevector_job` / `run_measured_job`, and supply only the SDK-specific steps as
callbacks:

```python
from qrosetta_commons.counts import prepare_final_state_sampling, prepare_statevector_qasm
from qrosetta_commons.helpers import (
    CompileResult, _draw_statevector_samples, declare_sdk_packages, get_logger,
    register_runner_endpoints, run_cli_main, run_measured_job, run_statevector_job,
    with_sdk_versions,
)

declare_sdk_packages("my-sdk", "numpy")   # pip names from requirements.txt

_PRECISION = "complex128"                 # the dtype the SDK actually simulates in


def _compile(payload: dict) -> CompileResult:
    qasm, notes = prepare_statevector_qasm(payload["circuit_data"])
    circuit, applied = _parse(qasm, payload.get("optimization_level", 0))
    return CompileResult(circuit=circuit, n_qubits=circuit.num_qubits,
                         preprocessing_applied=notes + applied, precision=_PRECISION)


def _serialize(compiled: CompileResult) -> str:
    return _to_qasm(compiled.circuit)


@with_sdk_versions
def process_run(payload: dict) -> dict:
    def execute(compiled, _payload):
        return _simulate(compiled.circuit)

    return run_statevector_job(
        simulator="my-sdk", payload=payload, logger=logger, compile_fn=_compile,
        serialize_fn=_serialize, execute_fn=execute, qubit_ordering="msb",
        precision=_PRECISION)


@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    def compile_step(payload):
        qasm, layout, notes = prepare_final_state_sampling(payload["circuit_data"])
        circuit, applied = _parse(qasm, payload.get("optimization_level", 0))
        return CompileResult(circuit=(circuit, layout), n_qubits=circuit.num_qubits,
                             preprocessing_applied=notes + applied, precision=_PRECISION)

    def serialize(compiled):
        return _to_qasm(compiled.circuit[0])

    def execute(compiled, payload):
        circuit, _layout = compiled.circuit
        return _draw_statevector_samples(_simulate(circuit), payload["n_shots"], payload.get("seed"))

    def shape_counts(samples, compiled, _payload):
        _circuit, layout = compiled.circuit
        return layout.counts_from_qubit_samples(samples, layout.qubit_positions("msb"), "msb"), "sv_sample"

    return run_measured_job(
        simulator="my-sdk", payload=payload, logger=logger, compile_fn=compile_step,
        serialize_fn=serialize, execute_fn=execute, postprocess_fn=shape_counts,
        qubit_ordering="msb",
        precision=_PRECISION)
```

The instrument runs, in order: the qubit-limit check; `compile_fn` between t0 and t1
(`compilation_time_sec`); `serialize_fn` outside the timed windows (it captures
`transpiled_qasm`, the circuit the backend executes); `pre_execute_fn` (e.g. seeding a global
RNG) under the memory monitor but outside the clock; `execute_fn` between t2 and t3
(`simulation_time_sec` and `simulation_cpu_time_sec`); and `postprocess_fn` outside the
window. If `compile_fn` mutates the circuit (adds `save_statevector`, rebases in place), set
`CompileResult.transpiled_qasm` yourself so the captured text matches what ran, or mutate a copy
and serialise the original in `serialize_fn`. Gate count and depth come from `transpiled_qasm`;
if that text does not reflect what executes (PennyLane decomposes `QubitUnitary` only in the text),
pass `gate_metrics_fn(compiled)` returning `(gate_count, depth, basis)`. Keep every thread and process
inside the simulating process: work in a worker pool escapes the CPU and memory measurement, and the
results flag it (`simulation_cgroup_cpu_time_sec` above `simulation_cpu_time_sec`). Build the SDK's
executable object in `compile_fn` where the SDK allows it.

Return values:

- `run_statevector_job`: `execute_fn(compiled, payload)` returns the backend's raw output.
  With a `postprocess_fn(raw, compiled, payload)`, that function returns the statevector;
  without one, `execute_fn` returns it. It must hold `2**n` amplitudes for the `n` declared
  qubits, or the run fails.
- `run_measured_job`: with a `postprocess_fn`, it returns `(counts, sampling_method)`;
  without one, `execute_fn` does. `sampling_method` is `"native"` when the SDK sampled the
  shots itself, `"sv_sample"` when they were drawn from a computed statevector, and
  `"tn_sample"` when they were sampled from tensor-network amplitudes (quimb).

Drawing shots belongs in `execute_fn`; building the counts histogram belongs in
`postprocess_fn`. `rosetta-api/tests/unit/test_counts_histogram_boundary.py` finds the
function passed as `execute_fn=` in each job call (any name, or a lambda), follows the
module functions it calls, and fails on `np.unique`, `bincount`, `Counter`, `value_counts`,
`get_counts`, the `counts_from_*` helpers, or a loop that tallies into a dict.

`declare_sdk_packages(*names)` registers the pip distributions whose installed versions
every result reports as `sdk_versions` (a name with no installed distribution reports
`"not installed"`). Call it once at module level. `test_runner_registry_sync.py` checks that
every runner calls it and that each name is pinned in its `requirements.txt` (or, for a
dependency the SDK pulls in, its `requirements.lock`).

Do not time, monitor memory, check qubit limits or build the result dict yourself. The
instrument assembles the result with `statevector_result` / `counts_result` (or
`runner_error` on any exception), so every backend returns the same fields: split timings,
`memory_usage_mb` and `process_peak_mb` from the kernel high-water mark with
`memory_method`, `precision`, `thread_env`, `preprocessing_applied` and `transpiled_qasm`.
`@with_sdk_versions` adds `sdk_versions`, `runner_code_sha256` (sha256 of this `main.py`
followed by every `.py` file of the installed `qrosetta_commons`, in path order) and
`device`: `"CPU"` unless the runner passes `device=` to the job call or sets
`result["device"]` itself. A GPU runner must report `"GPU"`.

Every runner is invoked through `run_isolated` / `run_with_uniform_measurement`, which add one
discarded warm-up run, a hard wall-clock timeout, and the whole-process fields
(`cpu_time_sec`, `process_peak_rss_mb`, `metric_scope`, gate count and depth from
`transpiled_qasm`).

The rest of `main.py` is the same in every runner:

```python
from fastapi import FastAPI

app = FastAPI(title="My-SDK Runner")

# ... process_run / process_run_measured defined above ...

register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "My-SDK",
                 qubit_ordering_statevector="msb", qubit_ordering_counts="msb")
```

`register_runner_endpoints` serves `process_run` / `process_run_measured` as `POST /run` and
`POST /run_measured` (through the `gunicorn`/`uvicorn` command in the Dockerfile).
`run_cli_main` also runs the runner as a one-shot command:

- `python main.py --endpoint run|run_measured --payload '<json>'` runs one job with the
  warm-up and prints the result;
- `python main.py --s3-job-id <id> --endpoint ...` is the Kubernetes path;
- `python main.py --self-test` runs the contract probes (section 3) and exits non-zero if
  any fails.

### Helpers for classical bits and measurements: `qrosetta_commons.counts`

A counts key holds every declared classical bit, in creg declaration order, with no
separators; `"lsb"` puts flat clbit 0 rightmost, `"msb"` leftmost; an unmeasured bit reads 0.
Use these helpers, which implement that contract, instead of reading measurements yourself:

- `prepare_statevector_qasm(qasm)` → `(qasm, notes)`: terminal measurements removed for
  `process_run`; raises for mid-circuit measurement, reset or `if`.
- `prepare_final_state_sampling(qasm)` → `(qasm, layout, notes)`: for runners that draw
  shots from a final state; a circuit without measure statements reads out every qubit.
- `parse_measurement_layout(qasm)` → `MeasurementLayout`: which qubit each classical bit
  holds, for runners that sample natively.
- `MeasurementLayout.counts_from_qubit_samples` / `counts_from_qubit_counts` (sampled
  basis-state indices or an index histogram), `counts_from_register_keys` (backends that
  key by register, like Aer), `counts_from_pytket_result` (pytket backends): turn backend
  output into contract keys. Call them from `postprocess_fn`.
- `statevector_in_declaration_order(...)`: reorder a statevector from a backend's qubit order
  (pytket sorts registers alphabetically) to declaration order.

`helpers._counts_from_samples` keys by qubit index over all qubits, which is not the counts
contract; do not use it in a runner.

### Which circuit text each runner receives

The `capabilities` entry in `config.py` puts the runner in a dispatch group, and the API
prepares one circuit text per group:

| Group | `apply_preprocessing=True` | `apply_preprocessing=False` |
| --- | --- | --- |
| `statevector` (`process_run`) | terminal measurements removed, qregs merged in declaration order, pytket parse/re-emit with barriers removed | terminal measurements removed, otherwise as submitted |
| `measured_native` | qregs merged, pytket parse/re-emit with barriers removed, measure-all appended if the circuit has no `measure` | as submitted, measure-all appended if it has no `measure` |
| `measured_sampled` | qregs merged, pytket parse/re-emit with barriers removed | as submitted |

The pytket round-trip inlines custom `gate` definitions, rewrites gates into pytket's QASM
gate set (e.g. `u` becomes `u3`, angles as multiples of pi) and expands register broadcasts.
With preprocessing off, a runner receives custom gates, `u`, `u0` and broadcasts verbatim,
so a runner that passes `/compare` can still fail `/compare_measured` on the same circuit
with preprocessing off. Every API change is listed in the report's `dispatched_circuits` and
prepended (prefix `API:`) to each result's `preprocessing_applied`.

## 3. Qubit ordering and the self-test

Every result declares `qubit_ordering` as `"msb"` or `"lsb"`: whether qubit 0 is the
most-significant or least-significant bit of the statevector index, and whether flat
classical bit 0 is the leftmost or rightmost character of a counts key. SDKs disagree, and
some use one convention for statevectors and the other for counts.

`python main.py --self-test` (inside the container, or anywhere the SDK is installed) runs
the probes in `shared/qrosetta_commons/contract_probes.py` through your `process_run` /
`process_run_measured` in-process and prints `PASS` / `FAIL` per probe:

- a one-hot statevector on a register with idle qubits: `2**n` amplitudes, weight on the
  index the declared label implies;
- counts probes: classical-bit order, swapped bits, creg declaration order, an unmeasured
  creg, unmeasured bits inside and before other cregs, a measured subset, and mid-circuit
  measurement (simulated or refused with the standard message);
- seed reproducibility: the same seed twice gives identical counts, a different seed
  gives different counts.

The probes send the probe text as written; the API's dispatch rewrites (section 2) are not
applied. The live-stack contract test in `tests/integration/test_runner_contract_asymmetric.py`
runs the same probes through the API.

## 4. Preprocessing

If your runner transforms the incoming QASM before simulating it (stripping barriers,
rebasing gates to a supported set, decomposing unsupported instructions), gate that behind
`payload.get("apply_preprocessing", True)` and record every applied transform as a
plain-language string in `CompileResult.preprocessing_applied`. A pass the adapter needs
regardless of the setting (the backend's default compilation pass, appending measurements)
is listed too, and its text says it runs regardless. Each entry should say what the
transform does, not only its name. Do not start entries with `API:`, which marks the API's
own changes.

When a pytket pass flattens registers (`FlattenRegisters`, part of several backends' default
compilation pass), pass `maxwidth=` to `circuit_to_qasm_str`, or a circuit whose cregs total
more than 32 bits fails in `serialize_fn`.

## 5. Dockerfile

Follow the existing pattern (`runners/qibo-runner/Dockerfile` is a minimal example):

- Pin the base image by digest: `FROM python:3.10-slim@sha256:...` (or whichever tag/digest your
  SDK needs; check its supported Python versions first).
- Create and switch to a non-root user (`appuser`), with `HOME=/home/appuser` and group
  permissions set so the image also runs under OpenShift's arbitrary-UID model.
- Install from `requirements.lock`, not `requirements.txt`, for the reproducible build.
- Install the shared `qrosetta_commons` package from `shared/` as a separate step, after your
  SDK's own dependencies.
- End with the same `gunicorn` + `uvicorn.workers.UvicornWorker` command line the other runners
  use.
- Do not install curl or wget.

If your SDK needs system packages (a C++ toolchain, BLAS, OpenMP), install them via `apt-get`
before the `pip install` steps, and pin the specific packages needed.

## 6. `requirements.txt` and `requirements.lock`

`requirements.txt` lists your runner's direct dependencies with exact pins (SDK, `fastapi`,
`uvicorn[standard]`, `psutil`, `gunicorn`, plus whatever your SDK needs). `requirements.lock` is
the full `pip freeze` output of a container built from that `requirements.txt`: build the image
once, run `pip freeze` inside it, and commit the result with a comment noting the date. The
Dockerfile installs from the lock file.

## 7. Registering the runner

A runner is listed in five places. `config.py` is the only one the application reads at
runtime; a runner missing from any of the others is silently excluded from that path.
`rosetta-api/tests/unit/test_runner_registry_sync.py` makes each omission fail loudly: it
checks all five lists against `config.py`, the directory name, the compose environment
block, `honours_seed`, and `declare_sdk_packages`.

| File | What it controls | Missing it means |
| --- | --- | --- |
| `rosetta-api/config.py` — `get_runner_services()` | Canonical id, URL, capabilities, enabled flag, seed honouring | The API never dispatches to it |
| `docker-compose.yml` | The local container | Nothing to dispatch to locally |
| `scripts/safe_boot.sh` — `RUNNERS` | The local boot order | Excluded from every local boot |
| `scripts/rahti_push.sh` — `SERVICE_MAP` | The pushed image | Kubernetes Jobs cannot pull it |
| `tests/integration/test_runner_contract_asymmetric.py` — `ACTIVE_STATEVECTOR_RUNNERS` | Contract coverage | Never contract-tested |

**`rosetta-api/config.py`**, inside `get_runner_services()`, add an entry keyed by your runner's
short id (this id appears everywhere in results, config and the UI):

```python
"my-sdk": {
    "base_url": self.MY_SDK_RUNNER_URL,
    "capabilities": ["statevector", "measured_native"],  # or "measured_sampled" when shots are
                                                          # drawn from a computed statevector
    "enabled": True,
    "honours_seed": True,   # required; False if the backend ignores the seed it is passed
    "optimization_levels": {
        0: "No optimization",
        1: "Describe what level 1 does for this SDK",
    },
},
```

and add the `MY_SDK_RUNNER_URL: str = "http://my-sdk-runner:8000"` field near the other
`*_RUNNER_URL` settings. `honours_seed` has no default: results record it as
`seed_honoured`, so a runner that ignores its seed must say `False` (braket does).

**`docker-compose.yml`**, add a service block (copy an existing runner's block):

```yaml
my_sdk_runner:
  build:
    context: .
    dockerfile: ./runners/my-sdk-runner/Dockerfile
  container_name: my-sdk-runner
  environment:
    - OMP_NUM_THREADS=1
    - MKL_NUM_THREADS=1
    - OPENBLAS_NUM_THREADS=1
    - NUMEXPR_NUM_THREADS=1
    - NUMBA_NUM_THREADS=1
    - RUNNER_MAX_CONCURRENT=${RUNNER_MAX_CONCURRENT:-1}
  networks:
    - isolated_net
  deploy:
    resources:
      limits:
        cpus: "1.0"
        memory: "512M"
```

Runners are internal-only: no exposed ports, reached by the API over `isolated_net` by
container name. The five thread variables pin every runner to one thread, as the Kubernetes
Job spec does; results record them in `thread_env`. `RUNNER_MAX_CONCURRENT` is how many runs
one runner executes at once (default 1; further requests queue and report
`queue_wait_sec`).

**Display names.** The UI shows the raw canonical id unless you add a label to both
registers: `rosetta-api/static/js/config.js` `RUNNER_DISPLAY_NAMES` (long, vendor-qualified,
for the config panel) and `rosetta-api/static/js/status_cards.js` `_RUNNER_NAMES` (short, for
the status cards). Add a row for the backend's statevector and measured bit order to the
table in `rosetta-api/static/docs.html` (`#bitorder`).

## 8. Testing before you're done

- Unit suite, from the repository root:

  ```bash
  cd rosetta-api && PYTHONPATH=.:../shared pytest tests/unit
  ```

  `PYTHONPATH` must include `../shared`: an older `qrosetta_commons` installed in the
  virtualenv otherwise shadows the working copy.
- Build and start the runner (`docker compose build my_sdk_runner && docker compose up -d
  my_sdk_runner`). Runners expose no port and ship no curl, so exercise them from inside the
  container:

  ```bash
  docker compose exec my_sdk_runner python main.py --self-test
  docker compose exec my_sdk_runner python main.py --endpoint run_measured \
    --payload '{"circuit_data": "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[2];\ncreg c[2];\nh q[0];\ncx q[0],q[1];\nmeasure q[0] -> c[0];\nmeasure q[1] -> c[1];\n", "n_shots": 1000, "seed": 1}'
  ```

  Read the result: `error` is null, the statevector has `2^n` amplitudes, the counts sum to
  `n_shots`, `precision` and `device` are right, and `sdk_versions` lists the SDK.
- Add your runner's id to `ACTIVE_STATEVECTOR_RUNNERS` and run
  `tests/integration/test_runner_contract_asymmetric.py` against the live stack
  (`./scripts/safe_boot.sh`). It sends the self-test probes through the API, so the runner
  receives the rewritten circuit text of section 2.

### Where silent integrity bugs hide

The unit suite and the self-test do not catch everything. Check these by hand:

- Work outside `t2..t3`. Simulating inside `compile_fn` reports a near-zero
  `simulation_time_sec` and memory delta; building counts inside `execute_fn` charges
  bookkeeping to the simulation.
- Lazy or asynchronous results. A GPU or JIT backend may return before the computation
  finishes; `execute_fn` must return materialised output (call `.result()`, synchronise,
  copy to host), or the timing measures only the launch.
- Ignored seeds. If the backend samples from a global RNG, seed it in `pre_execute_fn`; if
  it cannot be seeded, set `honours_seed: False`.
- Provenance. `transpiled_qasm` must be the circuit that ran, every transform must appear in
  `preprocessing_applied`, `precision` must name the dtype the backend simulated in, and
  `declare_sdk_packages` must name every package whose version changes results.
