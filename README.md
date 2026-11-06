# Quantum Rosetta

Quantum Rosetta (QRosetta) runs one OpenQASM 2.0 circuit on up to 14 quantum simulator backends
and records, for each backend, the compilation and simulation time, memory, CPU use and output,
and, for each pair of backends, whether their outputs agree. Each backend runs in its own
container with its own pinned SDK and the same measurement code. Every result exports as an
RO-Crate 1.1 archive with the submitted circuit, the circuit each backend executed, the metrics,
the seeds and the SDK versions. A run can also send its circuit to eight compile-only services
(BQSKit, PyZX, MQT QMAP, Cirq, staq, Q-Synth, Quartz, Synthetiq), whose output circuits are
recorded and exported but never simulated or compared.

QRosetta is developed by the [Quantum Programming and Algorithms (QPA) Research
Group](https://users.jyu.fi/~mhaghpyz/#qpa) at the [University of Jyväskylä](https://www.jyu.fi/en),
Finland.

## Requirements

The local stack needs:

- Linux on x86_64. Other hosts start only with `qrosetta start --allow-emulation`, and their
  timings are not comparable.
- An engine: rootless podman 4.7 or later (podman added `podman compose` in 4.7.0), or Docker
  Engine.
- Docker Compose v2 as the compose provider: `docker compose version` or `podman compose version`
  prints "Docker Compose version v2..." or later. podman-compose 1.x does not work.
- Python 3.11 or later for the `qrosetta` command, which uses only the standard library.
- Disk space for the images of the chosen profile (see [Profiles](#profiles)) and memory for the
  running services (see [Memory, disk and finished jobs](#memory-disk-and-finished-jobs)).

The `qrosetta` command also runs on macOS and Windows, where it can talk to a Quantum Rosetta
server elsewhere (`--server URL`).

## Installing from PyPI

The `qrosetta` package holds the command and the release manifest, which names every published
image by digest. The images come from `ghcr.io` with `qrosetta pull`.

### Fedora

Tested on Fedora 45 with podman 6.1.3.

```bash
sudo dnf install podman docker-compose pipx
systemctl --user enable --now podman.socket
pipx ensurepath          # then open a new terminal
pipx install qrosetta
```

Docker Compose reaches rootless podman through `podman.socket`; `qrosetta doctor` fails the
`podman_socket` check until it runs.

### Ubuntu with Docker

Tested on Ubuntu 26.04 with Docker 29.1.3.

```bash
sudo apt install docker.io docker-compose-v2 pipx
sudo usermod -aG docker $USER   # then log out and in again
pipx ensurepath
pipx install qrosetta
```

Membership of the `docker` group is equivalent to root on that host.

### Ubuntu with podman

Tested on Ubuntu 26.04 with podman 5.7.0.

```bash
sudo apt install podman
sudo apt install --no-install-recommends docker-compose-v2 pipx   # without docker.io
systemctl --user enable --now podman.socket
pipx ensurepath
pipx install qrosetta
```

### Debian

Tested on Debian 13 with podman 5.4.2.

```bash
sudo apt install podman pipx
sudo apt install --no-install-recommends docker-compose   # Debian's package is Compose v2
systemctl --user enable --now podman.socket
pipx ensurepath
pipx install qrosetta
```

Debian's cloud images lack `dbus-user-session`; without it every podman call prints a warning
about falling back to the cgroupfs manager. The stack runs the same either way.

### RHEL 10, AlmaLinux 10 and Rocky Linux 10

Tested on RHEL 10.2 with podman 5.8.2 and on RHEL 10.1 and AlmaLinux 10.1 with podman 5.6.0. RHEL
packages neither Docker Compose nor pipx, so install Compose as a plugin binary and `qrosetta`
into a virtual environment:

```bash
sudo dnf install podman
systemctl --user enable --now podman.socket
mkdir -p ~/.docker/cli-plugins
# save docker-compose-linux-x86_64 from https://github.com/docker/compose/releases as
# ~/.docker/cli-plugins/docker-compose, check it against the release's .sha256 file, then:
chmod +x ~/.docker/cli-plugins/docker-compose
python3 -m venv ~/.local/share/qrosetta
~/.local/share/qrosetta/bin/pip install qrosetta
mkdir -p ~/.local/bin && ln -sf ~/.local/share/qrosetta/bin/qrosetta ~/.local/bin/qrosetta
```

The same `pip install` with `--upgrade` updates it.

### On every distribution

- Over SSH, run `sudo loginctl enable-linger $USER` once before the first `start`. Without it,
  logging out removes `/run/user/<uid>` and the lifecycle token in it: the stack keeps running,
  but `doctor` and `selftest` fall back to cached availability, and `remove` cannot record its
  host load.
- To check image signatures, install cosign: take `cosign-linux-amd64` from
  https://github.com/sigstore/cosign/releases, check it against that release's
  `cosign_checksums.txt`, and put it on the `PATH` as `cosign`. None of these distributions
  packages it. `qrosetta pull` checks each signature when `cosign` is on the `PATH`, and
  `--require-signature` refuses an image it cannot verify.
- In a virtual machine `selftest` warns once per runner that its timings are not comparable with
  runs on physical hardware.

## Profiles

A profile is a set of services; the web server (nginx) and the API are added to every profile.
`qrosetta profiles` lists them.

| Profile | Services | Images | Size after `pull` (GB) | Download (GB) | Not published, build from a checkout |
|---|---|---|---|---|---|
| `minimal` | Qiskit, Qulacs, Cirq | 5 | 2.7 | 0.85 | none |
| `cpu` | the 13 CPU simulators | 15 | 11.7 | 3.6 | myQLM (1.3 GB) |
| `gpu` | `cpu` plus cuQuantum | 16 | 11.7 | 3.6 | myQLM and cuQuantum (5.1 GB) |
| `compilers` | the eight compile-only services, no simulator | 10 | 3.9 | 1.3 | BQSKit (0.5 GB) |
| `full` | every enabled service | 24 | 14.6 | 4.6 | all three (5.6 GB) |

Use `minimal` to try the software, `cpu` or `full` for comparisons across simulators, and
`compilers` to test compile-only services. A profile and service names combine: `qrosetta pull
--profile compilers qiskit` and `qrosetta start -d --profile compilers qiskit` add one simulator to
the compilers. A compile-only run needs no simulator (`qrosetta run FILE --compile-only --compiler
pyzx=all`).

myQLM, cuQuantum and BQSKit are not published, because their licences do not allow the project to
distribute their images (`THIRD_PARTY_NOTICES.md`). They need a checkout and `qrosetta build`.
cuQuantum also needs an NVIDIA GPU; without one it is listed as unavailable and never dispatched.

Sizes are in GB (10^9 bytes), measured on 2026-11-04 for the 2.0.0rc4 images. "Size after
`pull`" is the uncompressed layer size with the base-image layers counted once and every other
layer once per image. "Download" is the sum of the distinct compressed layers the registry sends.
A checkout that builds all 24 images uses about 19 GB, because local builds share more layers.

## First run

```bash
qrosetta doctor                       # host checks; each problem comes with its fix
qrosetta pull --profile minimal       # API, nginx, Qiskit, Qulacs and Cirq, by digest
qrosetta start -d --profile minimal   # returns when the API and the runners are ready
qrosetta selftest                     # known-answer checks; results under ./qrosetta-results
```

`start -d` waits up to 180 s for the API and every started runner and compiler, then prints where
the server runs:

```text
✓  Quantum Rosetta is running at http://localhost:8080  (this computer only)
     Manual    http://localhost:8080/docs.html
     API docs  http://localhost:8080/docs

Next step:  open http://localhost:8080 in a browser, or run `qrosetta selftest`
```

`qrosetta status` begins with the same lines. Open the address in a browser: the page starts with
a GHZ circuit in the editor; press Run and read the Summary tab. The manual's Quickstart
(`docs.html#quickstart`) goes through a first statevector run and a first measured run. From the
command line:

```bash
qrosetta run algorithm:ghz:3 -m statevector,measured
qrosetta show summary                 # the server's verdicts for the newest result
qrosetta export crate                 # its RO-Crate
```

`selftest` compares every started backend with answers computed independently of any SDK and
checks the host conditions that affect timings. It exits 0 when no check fails and names each
backend outside the started profile as "not started in this stack".

### Address and port

The web server is published on `127.0.0.1:8080`, so only this computer can reach it. When another
program holds port 8080 and no address was chosen, `start` publishes on the first free port from
8081 to 8089 on 127.0.0.1 and prints `Port 8080 is in use by another program; using 8081.`
It records the port for the project; `status`, `run` and the other commands find the server
there, and `qrosetta remove` forgets it. An address is chosen with `start --bind ADDR:PORT`,
`QROSETTA_HTTP_BIND` in the environment (or in a checkout's `.env`), or `bind` under
`[lifecycle]` in the config file; a chosen address that is in use stops `start`.

In local mode any client may lift the circuit-size, gate-count and experiment-size limits
(`bypass_limits`). Publish the server on other interfaces only on a network you trust, for
example `--bind 0.0.0.0:8080` (every IPv4 interface). The connection is plain HTTP. Ports below
1024 need a rootful engine. With every interface published, the banner adds a Network row with
this host's name and address.

## What a run records

Each backend runs the circuit once as a discarded warm-up, then `timing_repeats` times (1 to 10,
default 1); with more than one repeat the times are medians, with the samples beside them.

| Field | Meaning |
| --- | --- |
| `compilation_time_sec` | Wall clock from t0 to t1: parse the QASM, transpile, build the backend's native circuit |
| `simulation_time_sec` | Wall clock from t2 to t3: run the circuit and return the statevector or the shots |
| `simulation_cpu_time_sec` | CPU time of the simulating process from t2 to t3 |
| `cpu_time_sec` | CPU time of the whole runner process: start, SDK import, warm-up and timed runs |
| `memory_usage_mb` | Peak resident memory minus baseline over the simulation window (kernel VmHWM), in MiB |
| `process_peak_rss_mb` | Peak resident memory of the simulating process over its whole life, in MiB |
| `theoretical_statevector_mb` | Size of a dense statevector at the backend's precision: 2^N × 16 bytes (complex128) or 2^N × 8 bytes (complex64), in MiB |
| `precision` | Amplitude type the backend simulated in: complex128, or complex64 for qsim, Qrisp, TorchQuantum and Cirq's measured path |

Every runner has a 1-CPU quota and 1 GiB of memory and runs single-threaded (`OMP_NUM_THREADS`,
`MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `NUMEXPR_NUM_THREADS` and `NUMBA_NUM_THREADS` set to 1).
Each result records CPU-quota throttling and container CPU time over its simulation window, the
CPUs it ran on, and the runs that overlapped it. For timings meant for comparison, use exclusive
runs (`exclusive: true`, `qrosetta run --exclusive`: one backend at a time, no other run on the
server), at least three jobs with `timing_repeats` of 5; the manual's "Timing and memory
methodology" section gives the protocol.

Statevector pairs agree when their fidelity is at least 1 − 10⁻⁵, compared directly or after the
bit reversal their declared qubit orders imply; a match found only after another qubit
permutation counts as a disagreement. Measured pairs are compared by Jensen–Shannon divergence and
Hellinger distance, with a chi-square test and a G-test (Benjamini–Yekutieli correction across
pairs). A measured pair is reported consistent only when neither test is significant and the
power to detect a total-variation distance of 0.05 is at least 0.8; otherwise the report gives the
shot count that would reach it. The default is 8,200 shots per backend, enough for up to 16
outcomes with 14 backends. QRosetta reports disagreements and does not decide which backend is
wrong.

A measured run records a master seed, and each backend gets its own seed derived from it, so no
two backends draw the same shot sequence. Every change the API makes to a circuit before dispatch
is listed with an `API:` prefix in each result's `preprocessing_applied`, and each dispatched
circuit is written to the RO-Crate. The page's copy of a report omits statevectors of circuits
over 14 qubits; the server's full report keeps them. A crate holds each statevector's sha256 and
length, and the statevectors themselves when asked (`qrosetta run --statevectors`, or the option
on the page's Exports tab).

The manual (`docs.html` on a running server, or
[rosetta-api/static/docs.html](https://github.com/SeQuSoS-Project/QRosetta/blob/main/rosetta-api/static/docs.html)
in the repository) describes every field, label and threshold.
[DESIGN_DECISIONS.md](https://github.com/SeQuSoS-Project/QRosetta/blob/main/DESIGN_DECISIONS.md)
gives each measurement and analysis rule with the evidence for it.

## Stopping and removing

```bash
qrosetta stop                                    # standby: containers stopped; images and data kept
qrosetta start -d                                # back from standby in about 10 s
qrosetta remove                                  # remove containers and networks; keep images and data
qrosetta remove --images                         # also remove the images
qrosetta remove --data --confirm qsimulators     # also delete the database and saved runs
qrosetta remove --all --confirm qsimulators      # containers, networks, images and data, listed first
```

`stop`, `remove`, `build`, `pull`, and a `start` that adds or recreates services of a running
stack, are refused while the server reports runs in flight; `stop --force`, `remove --force` and
`--yes` on the others go ahead. A job in progress is lost when the API container stops.

`start` in the foreground (without `-d`) follows the logs. Ctrl-C asks "Keep on standby or
remove?" and takes standby after 10 s without an answer; SIGTERM and SIGHUP (sent by VS Code
when a task stops) put the stack on standby. `--on-exit standby|remove|ask` or
`QROSETTA_ON_EXIT` sets the action. In VS Code, *Terminal → Run Task → Quantum Rosetta: start*
(`.vscode/tasks.json` in a checkout) runs it in a terminal panel.

The database (accounts, saved circuits, run history) and the saved run reports are in the
volume `qsimulators_rosetta_db_data`, which only `--data` and `--all` delete. Results directories,
the config file and qrosetta's state and cache directories stay in every case.

`qrosetta` acts only on objects that carry its project's labels: containers and networks with
`com.docker.compose.project` and `org.qrosetta.project`, images with `org.qrosetta.image.project`
and `org.qrosetta.service`, and the data volume by its compose name and labels. It removes them by
ID and never prunes. For anything else in the way it prints the command that would remove it and
leaves it alone. The project is `QROSETTA_PROJECT` (default `qsimulators`).

## Memory, disk and finished jobs

Limits per container: each runner 1 CPU and 1 GiB, each compile-only service 2 CPUs and 2 GiB,
the API 0.5 CPU and 2 GiB, nginx 0.2 CPU and 128 MiB. Idle after a few hours of use, the 24
containers of `full` used 3.6 GiB and the five of `minimal` 1.0 GiB, page cache included
(`qrosetta status`, 2026-11-04). On standby the containers hold no memory.

The API keeps finished jobs so that the page and `qrosetta` can fetch their reports and crates.
`start` and `status` print the four bounds, which are set under `[lifecycle]` in the config file:

| Key | Default | Environment variable | Meaning |
|---|---|---|---|
| `jobs_kept` | 200 | `QROSETTA_JOB_MAX_KEPT` | finished jobs kept |
| `job_storage` | `"4GiB"` | `QROSETTA_JOB_SPILL_MAX_MIB` | disk for untruncated reports, inside the API container |
| `job_memory` | `"512MiB"` | `QROSETTA_JOB_MEMORY_MAX_MIB` | API memory for finished jobs |
| `job_retention` | `"24h"` | `QROSETTA_JOB_TTL_SEC` | longest time a finished job is kept |

When there are more than `jobs_kept` jobs, or their memory exceeds `job_memory`, the oldest jobs
that finished more than 30 minutes ago are removed; a sweep every 10 minutes applies the bounds.
Jobs younger than 30 minutes are never removed, so a burst of large jobs can take the API past
`job_memory` until they age. A kept job holds about 0.3 MiB of API memory for a 5-qubit circuit on
5 backends, 1.3 MiB for an 18-qubit statevector circuit on 14 backends, and 21 MiB for a
24-qubit measured circuit on 14 backends at 8,200 shots with a spread-out distribution. One
18-qubit statevector job on 14 backends takes 79 MB of job storage. Stopping or recreating the
API container removes every kept job; save a run to keep it.

```bash
qrosetta config path       # the config file; `qrosetta config init` writes a commented template
# [lifecycle]
# jobs_kept = 500
# job_storage = "16GiB"
# job_memory = "1GiB"
# job_retention = "48h"
```

The environment variables override the file. `start` recreates the API with new values.
`doctor` warns when `job_memory` is 1,536 MiB or more, which leaves the API less than 512 MiB for
its own work.

### CPU quota

A rootless engine sets the runners' CPU quota only when systemd delegates the cgroup `cpu`
controller to your user. `doctor` checks it, and on a host without it `start` stops and names the
systemd drop-in that delegates it (sudo and a reboot). `start --no-cpu-quota` runs every service
without its CPU limit instead, through a compose override that removes only
`deploy.resources.limits.cpus` (memory limits stay; it needs Docker Compose 2.24 or later). The
choice is kept for later starts until `start --cpu-quota`; `[lifecycle] cpu_quota = false` makes it
the default. Results from such a stack record `cpu_quota_cores` as null and carry the "no CPU
quota" timing caveat, and their timings are not comparable with runs under the quota.

## Building from a checkout

```bash
git clone https://github.com/SeQuSoS-Project/QRosetta.git
cd QRosetta
./qrosetta doctor
./qrosetta build --profile minimal   # or ./qrosetta build for every enabled service
./qrosetta start -d --profile minimal
./qrosetta selftest
```

`./qrosetta` runs the command from the checkout and takes the same commands as an installed
`qrosetta`; `pull` is for installed mode and `build` for a checkout. A full build installs the
dependencies of 24 images and compiles staq, Synthetiq and Quartz from source. It is the only way
to get myQLM, cuQuantum and BQSKit.

`start` never builds. It names services without an image and starts the rest. It recreates a
container whose image was rebuilt or whose compose configuration changed (for example after a
`git pull`), and prints each one with the reason. `.env` (from `.env.example`) is needed only for
a shared server; a local stack runs without it. Braket and ProjectQ are disabled in
`rosetta-api/config.py` because of persistent errors; enabling one means setting `enabled=True`
there and adding it to `scripts/safe_boot.sh`.

To deploy a shared server, the repository has the scripts for the authors' own instance
(Kubernetes mode on CSC Rahti with `scripts/rahti_push.sh`, a frontend on Google Cloud Run with
`scripts/deploy_frontend.sh`), which need adapting to another cluster. Outside local mode the API
refuses to start without `SECRET_KEY`.

## Command reference

`qrosetta help all` lists every command and `qrosetta COMMAND --help` gives its options and
examples. Commands marked experimental may change between minor releases.

| Command | Purpose |
|---|---|
| `doctor` | host checks, each with its fix |
| `pull` | pull the release's images by digest, checking digests, labels and, with cosign, signatures (installed mode) |
| `build` | build images from a checkout |
| `start` | start the stack, or add services to a running one |
| `status` | services, state, memory, image provenance and address |
| `logs` | container logs |
| `stop` | standby: stop the containers, keep everything |
| `remove` (`rm`) | remove containers, pods and networks; with options, images and data |
| `profiles` | profiles and their services |
| `images list` (`ls`) | this stack's images: missing, pulled, loaded, built or unknown, with sizes |
| `images verify` | check each image's labels, commit and build identity; in installed mode also its digest and signature |
| `images save` (experimental) | write this stack's images to a directory of archives, for a machine without registry access |
| `images load` | load archives written by `images save`, checked against their index |
| `run` | plan through the server, run the jobs, follow them and save their results |
| `wait` | follow detached jobs and save them |
| `jobs list` (`ls`) | the jobs this computer submitted, with their server status |
| `jobs status` | one job's status |
| `selftest` | known-answer and environment checks of the backends, with reports and crates saved |
| `show summary` | a result's outcomes, per-backend counts and caveats |
| `show circuits`, `show diff`, `show artifacts`, `show views` (experimental) | a result's circuit texts, a diff of two of them, its figures and tables, the export views |
| `export crate` | a result's RO-Crate ZIP |
| `export report` | a result's full report JSON |
| `export figure`, `export views` (experimental) | one figure or table of a result; the export views as JSON |
| `info` | the server's version, API levels, features, run gate, request defaults and limits |
| `backends` | the server's simulators: availability, levels, device, precision, bit order and profiles |
| `compilers` | the server's compile-only services: availability, levels, profiles and versions |
| `circuits algorithms`, `examples`, `mqt`, `qasmbench` | circuit catalogues (`algorithm:ID:QUBITS`, `example:NAME`, `mqt:ALGORITHM:QUBITS`, `qasmbench:NAME`) |
| `circuits get` | one circuit's OpenQASM 2.0 text |
| `login`, `logout`, `whoami` | sign in, sign out on the server, show the account |
| `api` | one raw request to the server |
| `config path`, `config show` | the config file's path; the effective settings and their sources |
| `config init`, `config edit` (experimental) | write a commented template; open the file in `$VISUAL` or `$EDITOR` |
| `version` | command version, install mode, release manifest and server version |

Global options: `--json` (one JSON object on stdout), `--server URL|NAME`, `--config FILE`,
`--project-dir DIR`. Data goes to stdout; progress, warnings and errors to stderr. Exit codes: 0
done; 3 to 9 the command ran and reports an outcome (for example 5 a failed job, 9 a failed
self-test; `run` exits 3 on a difference only with `--fail-on differs`); 10 and above a problem,
and the last line names the fix (15 refused because runs are in flight, 16 an engine or image
problem, 17 a failed `doctor` check).

The release manifest lets `pull`, `images verify` and `images load` check every image against the
published digest. `qrosetta images save -o DIR` and `qrosetta images load DIR` move images to a
computer without registry access. `qrosetta` uses the first of docker and podman whose `info`
answers; `QROSETTA_ENGINE=docker|podman` or `[lifecycle] engine` chooses one.

## Security

Report vulnerabilities privately as
[SECURITY.md](https://github.com/SeQuSoS-Project/QRosetta/blob/main/SECURITY.md) describes, never
in a public issue. Only nginx is reachable from outside the stack; the API and the runners are on
an internal network and the runners publish no port. Every container runs as an unprivileged
user. Passwords are stored as bcrypt hashes, signing out ends every session of the account, and
pages from other sites cannot send state-changing requests.

## Contributing and support

[CONTRIBUTING.md](https://github.com/SeQuSoS-Project/QRosetta/blob/main/CONTRIBUTING.md) covers
adding a simulator backend or compile-only service, the tests, and the release workflow.
[SUPPORT.md](https://github.com/SeQuSoS-Project/QRosetta/blob/main/SUPPORT.md) says where to ask
and what to attach. Contributors follow the
[Code of Conduct](https://github.com/SeQuSoS-Project/QRosetta/blob/main/CODE_OF_CONDUCT.md).

## Versions

Each release is a git tag, and
[CHANGELOG.md](https://github.com/SeQuSoS-Project/QRosetta/blob/main/CHANGELOG.md) lists what
changed. `v1.0.0` (June 2026) was the first public snapshot. Do not reuse its results: its Qrisp
adapter returned an all-zero state and all-zero counts when the SDK call failed (fixed in July
2026), and the bit-order labels of several adapters were corrected after it.

## Citing

Cite the version you used (`qrosetta version` prints it). The metadata is in
[CITATION.cff](https://github.com/SeQuSoS-Project/QRosetta/blob/main/CITATION.cff), which GitHub
offers as "Cite this repository"; `.zenodo.json` and `codemeta.json` give the same title, authors,
version and licence.

## Licence

Apache License 2.0 ([LICENSE](https://github.com/SeQuSoS-Project/QRosetta/blob/main/LICENSE)).
Bundled benchmark circuits and other third-party files keep their own licences, listed in
[THIRD_PARTY_NOTICES.md](https://github.com/SeQuSoS-Project/QRosetta/blob/main/THIRD_PARTY_NOTICES.md).
RO-Crates the server builds declare their contents under CC BY 4.0.

## Authors and contact

Shaswato Sarker, Majid Haghparast and Tommi Mikkonen, University of Jyväskylä.

Questions and support: <info@qrosetta.dev>. Principal investigator: Majid Haghparast
<majid.m.haghparast@jyu.fi>.

This work was supported by Business Finland through the project SeQuSoS (grant 112/31/2024) and
by the Research Council of Finland through the project Profi 8 – qSIME (grant 365343).
