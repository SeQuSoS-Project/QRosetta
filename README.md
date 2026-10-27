# Quantum Rosetta

**Quantum Rosetta** runs one OpenQASM 2.0 circuit across many quantum simulator backends and
reports both what each backend cost and whether they agree with each other. Each backend runs
in its own container with its own pinned dependencies, behind a single benchmarking contract,
so results are comparable across SDKs that could not otherwise share a process.

QRosetta is developed by the [Quantum Programming and Algorithms (QPA) Research Group](https://users.jyu.fi/~mhaghpyz/#qpa) at the [University of Jyvaskyla](https://www.jyu.fi/en) in Finland.

Every result set exports as a self-contained RO-Crate 1.1 archive holding the original
circuit, the circuit the API dispatched to each backend, the circuit each backend executed,
the metrics, the counts (statevectors on request; otherwise their sha256 and length), the run
configuration and seeds, and the SDK versions that produced them.

The Circuits tab shows those circuit texts side by side with a line diff between any two of
them. A run can also send its circuit to compile-only services (BQSKit, PyZX, MQT QMAP, Cirq, staq, Q-Synth, Quartz, Synthetiq), which
return circuit text only: their output is recorded, shown and exported, but never simulated or
compared. A saved run can be shared through a read-only link that expires after 1 to 90 days; the
link shows the circuit texts only, and its owner can revoke it.

## What it measures

For each backend, per run:

| Metric | Meaning |
| --- | --- |
| `compilation_time_sec` | Wall clock, t0..t1: parse the QASM, transpile, build the backend's native circuit |
| `simulation_time_sec` | Wall clock, t2..t3: execute and return the statevector or draw the shots |
| `simulation_cpu_time_sec` | Process CPU time (all threads) over t2..t3 |
| `cpu_time_sec` | Process CPU time of the whole runner process: interpreter start, SDK import, warm-up, timed runs |
| `memory_usage_mb` | Peak RSS minus baseline RSS over the simulation window (kernel high-water mark, VmHWM) |
| `process_peak_mb` | Absolute peak RSS over the simulation window |
| `process_peak_rss_mb` | Peak RSS of the simulating process over its whole life; resources are ranked by this |
| `theoretical_statevector_mb` | `(2^N x 16) / 1024^2` for complex128, `(2^N x 8) / 1024^2` for complex64: a dense statevector at the backend's precision, for reference |
| `precision` | Amplitude dtype the backend simulated in (`complex128`, or `complex64` for qsim, Qrisp, TorchQuantum, Cirq's measured path) |

Each backend runs the circuit once as a discarded warm-up and then `timing_repeats` times
timed (1 to 10, default 1). With one timed run every timing is a single sample
(`timing_samples = 1`); with more, the time fields are medians and the per-run samples, mean
and standard deviation are recorded beside them. Every runner is started with five thread
variables set to 1: `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS`,
`NUMEXPR_NUM_THREADS` and `NUMBA_NUM_THREADS`. Each runner has a 1-CPU quota and 1 GiB of
memory. Every run records the CPU-quota throttling and container CPU time over
its simulation window, the CPUs it ran on, and how many other runs overlapped it. For timings meant
for comparison, use exclusive runs (`exclusive: true`, one backend at a time with no other run on the
server), at least three jobs with `timing_repeats` of 5; the manual's "Timing and memory
methodology" section gives the protocol. `memory_method` and `process_peak_rss_method` record `vmhwm`, or the fallback used
(`sampled_10ms`, `getrusage`) where the kernel counter is unavailable.

Across backends, per run, every pair gets an agreement label, computed in the basis the two
backends' declared qubit orderings imply. Statevector pairs agree directly, up to a global
phase, or after the bit reversal the declarations imply (an `lsb` against an `msb` backend),
when fidelity, stored unrounded, is at least 1 - `fidelity_tolerance` (default 1e-5).
`residual_disagreement` (including pairs that match only in the basis the declared orderings
do not imply, flagged `unaligned_basis_match`) and `agree_after_qubit_permutation` (up to 7
qubits) are disagreements. `agree_after_normalization` marks an agreeing pair whose input norm
was off, and `not_comparable` carries a reason. The tolerances used are recorded in every pair
record. Measured pairs are compared by Jensen-Shannon divergence (nats) and Hellinger
distance, with a chi-square and G-test of homogeneity, Benjamini-Yekutieli corrected across
pairs. A measured pair is consistent only when neither test is significant and the power to
detect a total-variation gap of 0.05, computed at α/(m·c_m) for m tested pairs
(c_m = 1 + 1/2 + … + 1/m), is at least 0.8. The shots this needs grow with the number of
outcomes and backends; the report computes the power for every pair and recommends a shot
count when it falls short. The default is 8200 shots per backend, enough for up to 16 outcomes with 14 backends (8199 needed) (`default_n_shots` in
`GET /config`).

The tool reports disagreements; it does not decide which backend is wrong. The manual
(`docs.html`, "Known backend issues") lists upstream SDK discrepancies testers have traced
against an independent reference, with circuits to reproduce them.

Measured runs record a master seed; each backend receives a `runner_seed` made of the first
4 bytes of `sha256(f"{master}:{runner_key}")`, read big-endian with the top bit cleared, so
no two backends draw the same shot sequence. Any change the API makes to the circuit before dispatch
is listed with an `API:` prefix in `preprocessing_applied`, and each dispatched circuit is
written to the RO-Crate.

The server keeps each finished job's untruncated report for 30 to 40 minutes (jobs older
than 30 minutes are removed by a sweep every 10 minutes): `GET /jobs/{job_id}/report` returns
it as JSON and `POST /jobs/{job_id}/export` builds the RO-Crate from it. The copy sent to the
browser omits statevectors of circuits over 14 qubits. `POST /export` builds a crate from a
report in the request body, for runs loaded from history; every request body is limited to
1,048,576 bytes, and the QASM text itself to 1,000,000 characters.

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

myQLM's simulator is in the proprietary `qat-*` packages (Bull myQLM EULA), which allow use
only on the licensee's own computers and forbid third-party use and transfer over a network.
It runs in a local stack; the Rahti deployment does not offer it and `rahti_push.sh` does not push it.

The web UI runs every enabled backend unless you deselect some in the Backends chip above the run button. The
cuQuantum runner is qiskit-aer-gpu 0.15.1 with cuStateVec enabled, on an NVIDIA GPU. On a host
without one, `GET /runners` marks it unavailable with a reason, the backend list shows it
greyed out, and it is not dispatched. Its kernels run on the GPU; its host-side work runs under
the same CPU quota as the other runners, so its times compare different hardware. Memory
fields are host RSS: GPU device memory is not measured, and GPU runs are not ranked by memory.

Braket and ProjectQ ship with the stack but are disabled in `rosetta-api/config.py` because of
persistent backend errors. Re-enable either by setting `enabled=True` there and adding it to
`scripts/safe_boot.sh`.

The stack runs in two modes, selected by `EXECUTION_MODE`:

- `local` — Docker Compose. Runners are long-running HTTP services on an internal network.
- `kubernetes` — CSC Rahti. Runners are ephemeral Jobs spawned per request, exchanging
  results through S3.

## Getting started

Requires Linux on x86_64, rootless podman 4.4+ (recommended) or Docker Engine 20.10+, with
Docker Compose v2 as the compose provider (see [Starting and stopping](#starting-and-stopping)),
and Python 3.11+. A full build needs about 25 GB of disk for the images.

```bash
git clone https://github.com/SeQuSoS-Project/QRosetta.git
cd QRosetta
./qrosetta doctor          # host checks, each problem with its fix
./qrosetta build           # builds every enabled service's image
./qrosetta start -d        # starts the stack; returns when the runners answer
./qrosetta selftest        # known-answer checks of every backend, results saved under ./qrosetta-results
./qrosetta run algorithm:ghz:3 -m statevector,measured
./qrosetta show summary    # the server's verdicts for the last run
```

The first build takes a while: it installs dependencies for 24 separate images, and compiles
staq, Synthetiq and Quartz from source. `./qrosetta build --profile minimal` builds the core
services plus Qiskit, Qulacs and Cirq. `.env` (copied from `.env.example`) is needed only to
deploy a shared server; a local stack runs without it.

- Web UI — http://localhost:8080. The page opens with a GHZ circuit ready; press **Run**, then
  read the Summary tab. The guide's Quickstart (`docs.html#quickstart`) walks through a first
  statevector and a first measured run.
- API reference — http://localhost:8080/docs (Swagger) and `docs.html` for the written guide

nginx is published on `127.0.0.1:8080`, so only this machine can reach it. In local mode any
client may skip the circuit-size, gate-count and experiment-size limits (`bypass_limits`), so
publish it on other interfaces only on a network you trust: set
`QROSETTA_HTTP_BIND` in `.env` or the environment, for example `QROSETTA_HTTP_BIND=0.0.0.0:8080`
(every IPv4 interface) or `QROSETTA_HTTP_BIND=192.0.2.10:80` (one address; ports below 1024
need a rootful engine). The integration tests read the address from `QROSETTA_BASE_URL`.

`SECRET_KEY` must be set whenever `EXECUTION_MODE` is not `local`; the API refuses to start
without it. Locally, leaving it empty generates a random key per process.

### Starting and stopping

`./qrosetta` (Python 3, standard library only) starts, stops and removes the local stack:

```bash
./qrosetta doctor                    # host checks, each problem with its fix
./qrosetta build [NAME ...]          # build images with scripts/safe_boot.sh (default: every enabled service)
./qrosetta build --profile minimal   # build the core services plus qiskit, qulacs and cirq
./qrosetta start                     # start in this terminal and follow the logs
./qrosetta start -d --profile minimal  # start in the background; return when its runners answer
./qrosetta status                    # state, memory and image per service, data disk use, URL
./qrosetta logs [NAME]               # follow the logs
./qrosetta stop                      # standby: stop every container, keep containers, images and data
./qrosetta remove                    # remove containers and networks; keep images and data
./qrosetta remove --images           # also remove the images (about 20 GB for a full build)
./qrosetta remove --data --confirm qsimulators   # also delete the database and saved runs
./qrosetta profiles                  # profiles and their services
./qrosetta info                      # server version, API levels, request defaults and limits
./qrosetta backends                  # simulators: availability, levels, precision, bit order, profiles
./qrosetta circuits algorithms       # circuit catalogs; `circuits get algorithm:ghz:3` prints one circuit
./qrosetta login                     # sign in; the token goes to ~/.local/state/qrosetta/credentials.json (0600)
./qrosetta api GET /runners          # one raw request to the server
./qrosetta help all                  # every command
```

Services are named by their registry keys (`qiskit`, `cirq-transformers`, `api`, `nginx`), taken
from the `org.qrosetta.id` label in `docker-compose.yml`; compose service and container names
are accepted too. Profiles come from the `org.qrosetta.profiles` labels. Data goes to stdout and
progress, warnings and errors to stderr; `--json` prints one JSON object instead. Exit codes:
0 = done; 10 and above = a problem, and the last line names the fix (16 an engine or image
problem, 15 refused because runs are in flight, 17 a failed `doctor` check). `stop`, `remove`,
`build`, and `start` when it adds or recreates services of a running stack, are refused while
the server reports runs in flight; `stop --force`, `remove --force`, `build --yes` and
`start --yes` go ahead.

`start` never builds. It names the services that have no image (`qrosetta build <service>`
builds one) and starts the rest; without the nginx or API image it starts nothing. A container
keeps the image it was created from when `build` puts a new image under its tag, and the
configuration it was created with when `docker-compose.yml` changes (a new volume, variable or
limit after a `git pull`). `start` recreates, with `compose up --force-recreate`, every requested
service whose container (running or on standby) was created from another image than the one now
under its tag, or whose `com.docker.compose.config-hash` label differs from what
`compose config --hash` gives its service, and prints each one with its reason: "image rebuilt"
with the commit of both images, "compose configuration changed", or both. The hash is computed
with the environment `start` gives compose, including the address from `--bind` or
`lifecycle.bind`, so a stack started with `--bind` is recreated on the default address by a
later `start` without it. `status` shows the commit of the image each container was created
from; when the tag now holds another image it names both, when the configuration changed it
says so, and it prints the `start` command that recreates those containers. When a foreground `start` stops, it runs the exit
action. On Ctrl-C it asks "Keep on standby or remove?" and takes standby
after 10 seconds without an answer. SIGTERM and SIGHUP, which VS Code sends when a task is
stopped or its terminal closed, put the stack on standby. `--on-exit standby|remove|ask` or
`QROSETTA_ON_EXIT` sets the action; without a terminal, `ask` means standby. Pressing Ctrl-C
again while the containers stop prints a warning; a third Ctrl-C stops waiting and lists the
containers still running.

On standby the containers are stopped and hold no memory; `start` brings them back in about
10 seconds. Running and idle, the 24 containers used 3.0 to 6.1 GiB (`qrosetta status`, page
cache included). `remove` keeps the images and the `qsimulators_rosetta_db_data` volume, which
holds the SQLite database (accounts, saved circuits, run history) and the saved run reports. Results of jobs that were not saved are lost
whenever the API container stops.

`qrosetta` acts only on what carries two labels for its project: compose's
`com.docker.compose.project` and `org.qrosetta.project`, which `docker-compose.yml` puts on every
container and network. An image must carry `org.qrosetta.image.project` and
`org.qrosetta.service` for the service it is named after, and no other tag; the data volume must
have the name and compose labels compose gave it (compose offers to recreate, and empty, a volume
whose labels change, so it carries no qrosetta label). Containers, networks, volumes and images
are stopped or removed by ID; a pod only when every container in it is the stack's. Anything else
is left alone, and `start`, `stop`, `remove` and `status` name it with the command that would
remove it. `start` refuses while another project's container holds one of the stack's fixed
container names, or while containers or networks of the project lack the qrosetta label.

The project is `QROSETTA_PROJECT` (default `qsimulators`). `qrosetta` passes it to compose with
`-p`, names the compose files with `-f`, and removes every `COMPOSE_*` variable from compose's
environment, so `COMPOSE_PROJECT_NAME` in the shell or in `.env` never redirects it to another
project. `--project-dir` or `QROSETTA_PROJECT_DIR` (formerly `QROSETTA_HOME`, still read with a
warning) points the command at another directory holding the compose file. The optional config
file `~/.config/qrosetta/config.toml` (`qrosetta config path`, `qrosetta config show`) holds the
server, engine, exit action and bind address; it holds no run setting.

Containers and networks created before these labels existed carry only the compose label, and
images built before them carry none. `qrosetta status` lists them; remove the containers and
networks once with the commands it prints (images and data stay), and `qrosetta start` creates
them again with the labels. `remove --images` removes only images built after the change; for
older ones it prints the `rmi` command.

Docker and podman both work. `qrosetta` uses the first of docker and podman whose `info`
answers (`qrosetta doctor` says which and why); `QROSETTA_ENGINE=docker|podman` or
`[lifecycle] engine` in the config chooses one. Either way the compose provider must be Docker
Compose v2: `docker compose version` or `podman compose version` prints "Docker Compose version
v2..." or later. On Ubuntu and Debian, `sudo apt install docker-compose-v2` (with podman add
`--no-install-recommends`, so docker.io is not pulled in). Elsewhere, with Docker install the
`docker-compose-plugin` package (https://docs.docker.com/compose/install/linux/); with podman,
download the `docker-compose` binary for your platform from
https://github.com/docker/compose/releases, save it as `~/.docker/cli-plugins/docker-compose` and
make it executable, and `podman compose` uses it. podman-compose 1.x is not supported.

In VS Code, *Terminal → Run Task → Quantum Rosetta: start* (`.vscode/tasks.json`) runs
`qrosetta start` in a terminal panel; stopping the task puts the stack on standby. The other
tasks run `stop`, `remove` and `status`.

### Deploying a shared server

A local stack needs none of this. The project's own hosted instance runs in `kubernetes` mode on
CSC Rahti, with the frontend on Google Cloud Run:

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
PYTHONPATH=.:../shared pytest tests/unit/
```

`PYTHONPATH` includes `../shared` so the working copy of `qrosetta_commons` is tested even
when an older copy is installed in the virtualenv.

`tests/integration/` holds live-stack checks that need the whole stack running. CI does not
run them; see the README there.

## Project layout

```text
.
├── docker-compose.yml       Orchestration, healthchecks, resource limits
├── qrosetta                 Start, stop and remove the local stack (runs qrosetta_cli/)
├── qrosetta_cli/            The command's package (standard library only)
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

## Contributors

- Shaswato Sarker - *University of Jyvaskyla*
- Majid Haghparast - *University of Jyvaskyla*
- Tommi Mikkonen - *University of Jyvaskyla*

## Contact

Majid Haghparast <<majid.m.haghparast@jyu.fi>>

## Acknowledgement

This work has been supported by the Business Finland through project SeQuSoS (Grants No. 112/31/2024), and Research Council of Finland through project Profi 8 - qSIME (Grants No. 365343).

## Contributing

See `CONTRIBUTING.md` for the full guide to adding a simulator backend or an algorithm
template, and `DESIGN_DECISIONS.md` for the measurement and analysis rules with the evidence
behind each.

## Versions

Each release is a git tag, and its release notes list what changed. `v1.0.0` (June 2026) was the first
public snapshot. Do not reuse its results: its Qrisp adapter returned an all-zero state and all-zero
counts when the SDK call failed (fixed in 5bb0574, July 2026), and the bit-order labels of several
adapters were corrected after it. Use the newest release.

## Licence

Apache License 2.0 (`LICENSE`). Bundled benchmark circuits and other third-party files keep their
own licences, listed in `THIRD_PARTY_NOTICES.md`.

## Citing

See `CITATION.cff`.
