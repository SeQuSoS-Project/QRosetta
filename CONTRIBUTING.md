# Adding a new simulator backend or compile-only service

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
- Install from `requirements.lock`, not `requirements.txt`, for the reproducible build. A lock with
  hashes is installed with `pip install --no-cache-dir --require-hashes -r requirements.lock`, and
  `shared/` with `--no-deps --no-build-isolation --no-index` (nothing fetched).
- Point apt at the Debian snapshot before any `apt-get`: declare `ARG DEBIAN_SNAPSHOT=<the value in
  release/debian-snapshot.conf>` and rewrite `/etc/apt/sources.list.d/debian.sources` to
  `https://snapshot.debian.org/archive/debian/${DEBIAN_SNAPSHOT}` and `.../debian-security/...` with
  `Check-Valid-Until: no`, as `rosetta-api/Dockerfile` does. `test_reproducible_builds.py` checks both
  rules; `safe_boot.sh` and `scripts/release/image.sh` pass the file's value as the build argument.
- Install the shared `qrosetta_commons` package from `shared/` as a separate step, after your
  SDK's own dependencies.
- End with the same `gunicorn` + `uvicorn.workers.UvicornWorker` command line the other runners
  use.
- Copy the Dockerfile and `requirements.lock` to `/usr/local/share/qrosetta-build/`, and end with
  the `ARG QROSETTA_GIT_SHA` / `QROSETTA_IMAGE_SOURCE` / `QROSETTA_RELEASE` lines and the `RUN`
  that writes `/usr/local/share/qrosetta-image/identity`, before `USER appuser`, as the other
  runners do (results report them as `build_files` and `image_identity`; crates include the lock
  file only when its hash matches). Pass the source and release as build arguments in the compose
  block, never as `ENV`. `rosetta-api/tests/unit/test_image_identity.py` checks both.
- Do not install curl or wget.

If your SDK needs system packages (a C++ toolchain, BLAS, OpenMP), install them via `apt-get`
before the `pip install` steps, and pin the specific packages needed.

## 6. `requirements.txt` and `requirements.lock`

`requirements.txt` lists your runner's direct dependencies with exact pins (SDK, `fastapi`,
`uvicorn[standard]`, `psutil`, `gunicorn`, plus whatever your SDK needs). `requirements.lock` is
the full `pip freeze` output of a container built from that `requirements.txt`: build the image
once, run `pip freeze` inside it, and commit the result with a comment noting the date. The
Dockerfile installs from the lock file, and every exact pin in `requirements.txt` must have the
same version in the lock (`test_requirements_lock_sync.py`). Dependabot does not read lock files,
so a pull request of its that changes a `requirements.txt` fails that test until the lock is
regenerated; for a runner or compiler it carries the label `sealed-image` and needs the image
requalified (`DESIGN_DECISIONS.md`, Supported Python and base images) before it is merged.

`scripts/release/compile_lock.sh <service-dir> <base-image@sha256:...>` regenerates a lock with
sha256 hashes: pip-tools runs pip's resolver inside the base image, with the current lock as
constraints, so a pin moves only when `requirements.txt`, the base image's Python or a hand edit of
the lock forces it. To move one package, edit its version in the lock and run the script. The API's
lock is generated this way; runner and compiler locks move to it when their image is requalified.

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
    "precision": {"statevector": "complex128", "measured": "complex128"},
    "qubit_ordering": {"statevector": "msb", "measured": "msb"},
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
`precision` and `qubit_ordering` repeat, per endpoint, the values your `main.py` passes to
`run_statevector_job` / `run_measured_job` (or `CompileResult(precision=...)`); use `None`
for a value the runner computes at run time. `tests/unit/test_registry_precision_ordering.py`
compares them with the source, and `GET /runners` publishes them.

**`docker-compose.yml`**, add a service block (copy an existing runner's block):

```yaml
my_sdk_runner:
  build:
    context: .
    dockerfile: ./runners/my-sdk-runner/Dockerfile
    args:
      - QROSETTA_GIT_SHA=${QROSETTA_GIT_SHA:-unknown}
      - QROSETTA_IMAGE_SOURCE=${QROSETTA_IMAGE_SOURCE:-built_locally}
      - QROSETTA_RELEASE=${QROSETTA_RELEASE:-}
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
- Build and start the runner (`./qrosetta build my_sdk_runner && ./qrosetta start --detach
  my_sdk_runner`, which also starts nginx and the API). Runners expose no port and ship no curl, so exercise them from inside the
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

## Adding a compile-only service

A compile-only service returns circuit text, never a simulation result, so it is not a
runner: it lives in `compilers/<name>-compiler/`, is registered in `config.py`
`get_compiler_services()`, and its output goes to the report's `compiled_circuits`, which the
comparison never reads. `compilers/pyzx-compiler/main.py` is a short complete example.

`main.py` holds:

- one function per optimization level, `pipeline(qasm) -> (output_qasm, passes_applied)`,
  collected in `PIPELINES = {level: pipeline}`. `passes_applied` names every call that changed
  the circuit, with its arguments, including transforms the adapter needs before the
  compiler can run (QMAP's decomposition to `u3` and `cx`);
- `process_compile(payload)`, decorated with `@with_sdk_versions`, returning
  `run_compile_job(compiler="<id>", payload=payload, pipelines=PIPELINES)`;
- `equivalent(input_qasm, output_qasm) -> bool`, an independent check of the output unitary
  for the small self-test probes, using the image's own SDK;
- `register_compiler_endpoint(app, process_compile)` and, under `__main__`,
  `run_compiler_cli_main(app, process_compile, "<Name>", levels=sorted(PIPELINES), equivalent=equivalent)`;
- `raise CompileRefused(...)` (`qrosetta_commons.compile_errors`) for an input the adapter will not
  compile, and `raise OutputRejected(...)` when the output fails the adapter's own check. Their
  messages are shown on share links, so they describe the circuit, never the server; any other
  exception is an error kept out of share links;
- for a program built from source rather than installed with pip, one
  `declare_native_component(name, version, source_url, source_sha256, ...)` call with the build's
  flags or patches (see `compilers/staq-compiler/main.py`).

The Dockerfile copies itself, `requirements.lock` and any patch, build source or generated data
the build uses to `/usr/local/share/qrosetta-build/`; each record carries their sha256, and a
crate includes the server's copy of a file only when the hashes match.

Then add the service to `docker-compose.yml` (isolated network, no ports, the thread
variables, a CPU and memory limit), to the `COMPILERS` array of `scripts/safe_boot.sh` and to
`SERVICE_MAP` in `scripts/rahti_push.sh`; `tests/unit/test_runner_registry_sync.py` fails until
all of them agree with `config.py`. Pin `requirements.txt` and generate `requirements.lock` in
the base image the Dockerfile uses.

Before offering a level, run `python main.py --self-test` in the image and compile random
circuits through it with an independent equivalence check. Do not offer a pipeline that
changes the unitary of an input beyond its stated tolerance; record why in the manual's known issues instead.

## Changing the database schema

The tables live in `rosetta-api/db/models.py`; every change to them comes with an Alembic
revision in `rosetta-api/migrations/versions/`. The API runs `upgrade head` when it starts
(`rosetta-api/db/migrate.py`), so a deployed database follows the code without a manual step.
`tests/unit/test_db_migrations.py::test_models_and_migrations_agree` fails when the models and
the revisions disagree.

Write the revision against a scratch database at head, from `rosetta-api/`:

```bash
export DATABASE_URL=sqlite:///$HOME/.tmp/schema-scratch.db
PYTHONPATH=.:../shared python -m db.migrate
PYTHONPATH=.:../shared alembic revision --autogenerate --rev-id 0002 -m "add users display name"
```

Revision ids are sequential four-digit numbers (`0001` is the baseline), so two branches that
both add `0002` conflict visibly instead of creating two heads. Read the generated file before
committing it: autogenerate does not see renames (it writes a drop and an add) and does not
compare server defaults. Migrations run in batch mode (`render_as_batch`), which SQLite needs
for anything beyond adding a column; keep the generated `with op.batch_alter_table(...)` blocks.
A new column on an existing table is nullable, or carries a `server_default`, so rows already
stored get a value. Check the PostgreSQL SQL without a server:

```bash
DATABASE_URL=postgresql://user:pass@host/db PYTHONPATH=.:../shared alembic upgrade head --sql
```

Upgrade a database by starting the API or with `python -m db.migrate`; plain `alembic upgrade`
does not take the migration lock and fails on a database created before migrations existed.
A database created by `create_all` before migrations (v1.0.0 onwards) is brought to the
baseline first: missing tables, nullable columns and indexes are added, then it is stamped
`0001`. A missing non-nullable column stops startup with the column named.

## Changing a route the `qrosetta` command reads

Released `qrosetta` commands keep talking to newer servers, so the routes their stable commands
read (`CLI_ROUTES` in `rosetta-api/tests/openapi_cli_contract.py`) only change additively: new
routes, optional parameters and request fields, new response fields, new enum values in
responses. `rosetta-api/tests/openapi_cli_baseline.json` holds those routes as the last
refresh saw them, and `tests/unit/test_openapi_cli_contract.py` and the CI step "OpenAPI
contract for older CLIs" fail when the app removes a route, method, parameter or field,
makes a request field required, narrows what a request accepts, changes a success status or
media type, or lets a response field be missing or take a type it did not.

Such a change needs the maximum of `API_LEVELS` in `rosetta-api/services/server_info.py`
raised in a platform major release, with the previous level still served for at least
12 months. Then, or after an additive change, refresh the baseline from `rosetta-api/`:

```bash
PYTHONPATH=.:../shared python -m tests.openapi_cli_contract --write
```

It refuses to write over a breaking change whose API level was not raised. `--check` prints
every difference without writing. Run it after upgrading FastAPI or pydantic too: the
baseline is normalised (references inlined, titles and descriptions dropped), so a framework
upgrade that keeps the same fields reports nothing, and anything it does report is a change
older CLIs would see.

## Packaging the `qrosetta` command

The `qrosetta` package on PyPI holds `qrosetta_cli/` and nothing else: no dependencies, Python
3.11 or later, and a `qrosetta` console script. The API, the frontend, the runners and the
compilers ship as container images. `pyproject.toml` at the repository root describes the
package.

**Version.** `__version__` in `qrosetta_cli/__init__.py` is the platform version, and the
package takes its version from it. `PLATFORM_VERSION`'s default in `rosetta-api/config.py`
and `ARG QROSETTA_VERSION` in `rosetta-api/Dockerfile` repeat the number;
`tests/unit/test_release_version.py` fails when the three differ, so a version change edits all
three in one commit.

**Building the wheel locally.** Keep temporary files out of `/tmp`:

```bash
python3 -m venv ~/.tmp/qr-build
~/.tmp/qr-build/bin/pip install build==1.3.0
# Optional: a release manifest without image digests (needs PyYAML, pydantic, pydantic-settings)
python scripts/release/make_manifest.py --git-sha "$(git rev-parse HEAD)"
TMPDIR=~/.tmp ~/.tmp/qr-build/bin/python -m build --outdir ~/.tmp/qr-wheel .
python3 scripts/release/check_dist.py ~/.tmp/qr-wheel --version 1.0.0 --require-manifest
```

`check_dist.py` refuses a wheel with files outside `qrosetta_cli/`, another version, a
dependency, or without `LICENSE`, `THIRD_PARTY_NOTICES.md`, the JSON schemas or (with
`--require-manifest`) the manifest. The build leaves `build/` and `qrosetta.egg-info/` in the
checkout; both are ignored by git, as is the generated `qrosetta_cli/release/manifest.json`.

**Installed mode.** Install the wheel into a fresh virtual environment and run `qrosetta` from
outside the checkout. Without `--project-dir` or `QROSETTA_PROJECT_DIR`, and with the package
outside a checkout, `qrosetta` looks for no repository. Stack commands then need a release
manifest that names a published digest for every distributable image. Until one exists,
`start` and `status` exit 12 and print the source route (`git clone`, `./qrosetta build`,
`./qrosetta start`). With published digests, every stack command writes
`$XDG_STATE_HOME/qrosetta/compose.yaml` from the manifest: the repository's services with
`build` removed and each `image` set by digest, under the same compose project
(`QROSETTA_PROJECT`, default `qsimulators`) and ownership labels as a checkout. `start` names the
missing images with the `qrosetta pull` command that fetches them. `qrosetta images load DIR`
loads archives written by `qrosetta images save`; a loaded image has no repo digest, so it is
tagged `<project>-<compose service>:<release>`, accepted only when its config digest is the
`image_id` the manifest records, and the generated compose file names that tag for any service
whose image by digest is absent (`stack/installed.py`, `localise`).

**A release.** `.github/workflows/release-images.yml` runs on a tag `v<version>`, and the tag
must equal `__version__`, spelled as canonical PEP 440 (`check_dist.py --prerelease` refuses any
other spelling):

1. `plan` lists the images to build with `scripts/release/make_manifest.py --list-images`:
   every service in `docker-compose.yml` that `config.py` enables, except myQLM, cuQuantum and
   BQSKit, whose licences do not let the project distribute their images. It also records whether the
   version is a pre-release (`aN`, `bN`, `rcN` or `.devN`).
2. `images` builds each one with `scripts/release/image.sh` (build arguments
   `QROSETTA_GIT_SHA`, `QROSETTA_IMAGE_SOURCE=release`, `QROSETTA_RELEASE`) and runs its
   self-test: `main.py --self-test` for runners and compilers, an import of `main` for the API,
   `nginx -t` for nginx. Nothing is pushed. `image.sh` refuses to build without the
   `org.qrosetta.image.project` and `org.qrosetta.service` labels, by which an installed
   `qrosetta` recognises a pulled image as its stack's, and adds `org.qrosetta.third-party-notices`
   and the `org.opencontainers.image.*` labels of `scripts/release/oci_labels.py` (title,
   description, `Apache-2.0`, source repository, commit, version; `safe_boot.sh` adds the same to
   local builds). `image.sh scan` then scans the image with Trivy (container image pinned by
   digest): the SARIF report of HIGH and CRITICAL vulnerabilities with a fixed version goes to
   code scanning (job `scan-results`, public repository only), and a CRITICAL one with a fixed
   version fails the image, and so the release, unless `.trivyignore` lists it with the reason,
   who accepted it and a review date.
3. `publish-images` runs only when the repository variable `QROSETTA_PUBLISH_IMAGES` is `true`,
   on any version tag. It rebuilds each image, pushes it to
   `ghcr.io/<owner>/qrosetta-<container name>:<version>`, pulls it back by digest and self-tests
   it, signs it with cosign (keyless), attaches a build-provenance attestation, records its
   image id (the config digest from the registry manifest, which must equal the pulled image's
   id), and attaches an SPDX SBOM made by syft (`anchore/sbom-action`) as an attestation
   (`actions/attest-sbom`). It writes each image's source notice with
   `scripts/release/image_notice.py` (every Debian or Alpine source package at its installed
   version, with its source address) and uploads it as the artifact `notice-<id>`, and the SBOM
   as `sbom-<id>`; step 7 attaches both to the GitHub release (`THIRD_PARTY_NOTICES.md` says the
   notices are there). Step 2 also writes each notice on every run, and discards it, so a dry run
   fails when a notice cannot be written. The job waits for `openapi`, which writes the API
   description from the tagged code (`scripts/release/release_assets.py openapi`, with the API's
   locked dependencies on Python 3.10); no image is pushed when that fails.
4. `wheel` writes the manifest (with the pushed digests, image ids and the signing workflow's
   identity, if any), builds the sdist and the wheel, and checks them with `check_dist.py`
   against the tag.
5. A final version (`X.Y.Z`, `X.Y.Z.postN`) goes to PyPI through Trusted Publishing (environment
   `pypi`), and only when step 3 ran and succeeded, so no wheel on PyPI names an image that was
   not published; the job checks the wheel's version again before uploading. A pre-release tag
   goes to TestPyPI (environment `testpypi`) and never to PyPI.
6. `release-assets` (public repository, tag pushes only) collects the wheel, the sdist, the
   SBOMs, the notices, `openapi-<version>.json` and `qrosetta-<version>-images.txt` (written by
   `wheel` from the manifest: every image by digest with its `cosign verify` and
   `gh attestation verify` commands), writes `SHA256SUMS`, attests the provenance of every file
   in it and saves the bundle as `qrosetta-<version>.intoto.jsonl`, then verifies each file
   against the bundle. It checks out no code and installs nothing.
7. `publish-release` (final versions only, after the PyPI upload) creates the GitHub release as
   a draft with those files, the version's `CHANGELOG.md` section and GitHub's generated notes
   (categories in `.github/release.yml`), downloads the attached files again and checks them
   against `SHA256SUMS`, then publishes the release. A pre-release tag gets no GitHub release,
   so Zenodo does not archive it. `plan` refuses a final tag whose `CHANGELOG.md` section is
   missing or undated.

The order of a release, the files a version bump touches and the checks on a clean machine are
in `docs/RELEASING.md`.

`workflow_dispatch` is a dry run: the same image builds and self-tests, then a wheel versioned
`<release>.dev<run number>` with a manifest that names no digest goes to TestPyPI. Before the
first run, register `release-images.yml` as a trusted publisher of the `qrosetta` project on PyPI
and TestPyPI with those environment names, and create both environments in the repository
settings.

**Monthly rebuild check.** `.github/workflows/rebuild-check.yml` builds the same images from
scratch (`NO_CACHE=1`: no layer cache, base image pulled), self-tests and scans them, and pushes
nothing. It fails when a pinned package or base image can no longer be fetched, a self-test no
longer passes, or a CRITICAL vulnerability with a fix has been published since.

**Image archives without a registry.** On a machine that has pulled (or built) the images,
`qrosetta images save --profile minimal -o DIR` writes one archive per image and
`DIR/qrosetta-images.json`; `qrosetta images load DIR` on the target machine checks each archive
against the index before loading it. These archives are what the Zenodo record carries.

## Lint gates

The CI job `lint` fails only on findings that are not already recorded:

- `ruff check .` with the rules in `[tool.ruff]` of `pyproject.toml`: pyflakes (`F`), syntax
  errors (`E9`), bugbear (`B`), pyupgrade (`UP`, without the annotation-spelling rules) and bandit
  (`S`, outside tests). Findings present when the gate was added are listed per file in
  `[tool.ruff.lint.per-file-ignores]`: reviewed false positives with the reason, code in the
  measured images (runners, compilers, `shared/qrosetta_commons`), and an unreviewed baseline.
  Delete an entry when you fix its file; a new file gets no entry.
- `ruff format --check qrosetta_cli`; the rest of the tree is not formatted with ruff yet.
- `scripts/lint/check.sh`: shellcheck over `scripts/**/*.sh` and the git hooks, hadolint over
  every Dockerfile, compared with `scripts/lint/shellcheck.txt` and `scripts/lint/hadolint.txt`
  (file, code, count). A count above its line fails; a count below it is printed so you can
  lower the line. `scripts/lint/check.sh --write` rewrites both files.
- `scripts/lint/check.sh semgrep`: Semgrep from `scripts/lint/semgrep-requirements.txt` (every
  dependency pinned with its wheel hashes) with five registry rule packs, compared with
  `scripts/lint/semgrep.txt`, where each line gives its reason. The packs are fetched from the
  registry on every run and are not versioned, so a new rule can fail the job with no change in
  the repository: fix the finding or add it to `semgrep.txt` with the reason.

Locally, with the tools from `scripts/lint/requirements.txt` and a
[hadolint](https://github.com/hadolint/hadolint/releases) binary on `PATH` (or in `$HADOLINT`):

```bash
ruff check . && ruff format --check qrosetta_cli && scripts/lint/check.sh
python3.12 -m venv ~/.cache/qrosetta-semgrep
~/.cache/qrosetta-semgrep/bin/pip install --require-hashes --no-deps --only-binary=:all: \
    -r scripts/lint/semgrep-requirements.txt
SEMGREP=~/.cache/qrosetta-semgrep/bin/semgrep scripts/lint/check.sh semgrep
```

`.pre-commit-config.yaml` runs file checks (YAML, TOML, merge markers, files over 2 MB), ruff,
mypy over the CLI, codespell (`[tool.codespell]` in `pyproject.toml` lists the accepted words),
zizmor and the secret check below on each commit if you use [pre-commit](https://pre-commit.com):
run `scripts/install_hooks.sh` first, then `pre-commit install`, which replaces only the pre-commit
hook.

Code that runs inside a timed window, and the images that carry it, is not changed to satisfy a
lint rule; its findings stay in the baseline until the image is next requalified.

Workflows are checked by the CI job `actionlint` (actionlint with ShellCheck, then
[zizmor](https://docs.zizmor.sh) from `scripts/lint/zizmor-requirements.txt`) and by
`test_supply_chain_workflows.py`. When you add an action, pin it to the full commit of a release at
least 7 days old, with `# vX.Y.Z` after it, and use the commit the other workflows already use for
that action. Keep `permissions: contents: read` at the top, give a job only the extra permissions
it uses with a comment saying why, set `persist-credentials: false` on every checkout, and pass
`${{ }}` values to scripts through `env:`. Locally: `zizmor --persona pedantic .` from the
repository root (add `--offline` without a GitHub token).

The CI job `types` runs mypy 2.4.0 (`scripts/lint/mypy-requirements.txt`, hash-pinned) through
`scripts/lint/check.sh mypy` over `qrosetta_cli/` and `shared/qrosetta_commons/` (the latter as
Python 3.10), with `[tool.mypy]` in `pyproject.toml`. It does not read installed packages, so a run
on your machine sees what CI sees. The baseline `scripts/lint/mypy.txt` holds only
`qrosetta_commons` errors; new CLI code meets every enabled check. Locally: `pip install
mypy==2.4.0`, then `scripts/lint/check.sh mypy`.

The workflow `links.yml` checks the links in the top-level documents, `docs/verification/` and
`rosetta-api/static/docs.html` with [lychee](https://lychee.cli.rs) every Monday and on request, not
on pushes, because it depends on other sites. Settings and the one excluded URL are in
`scripts/lint/lychee.toml`, which also gives the local command.

The unit job on Python 3.12 also records line coverage (`[tool.coverage]` in `pyproject.toml`)
and uploads `coverage.xml` as the artifact `coverage-unit-py3.12`. There is no threshold.

## Secrets and private files

Run `scripts/install_hooks.sh` once after cloning. It installs a pinned, checksum-verified
gitleaks and two hooks that apply to every branch and worktree of the clone:

- pre-commit refuses staged credential files (`.env`, OpenStack RC files, keys, kubeconfigs,
  `infra/rahti/secret-*.yaml` other than templates), the private directories `.gitignore`
  excludes (`docs/`, `export/`, `latex/`, `CLAUDE.md`, `.claude/`), and any secret gitleaks finds
  in the staged changes;
- pre-push runs the same checks over every commit being pushed.

CI repeats both checks over the whole history. Credentials belong in `.env` locally and in the
`rosetta-secrets` secret on Rahti, never in notes or scripts. A false positive gets an allowlist
entry in `.gitleaks.toml`, not `--no-verify`.
