# Changelog

User-visible changes to Quantum Rosetta, by release. The format follows
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); version numbers follow
[PEP 440](https://peps.python.org/pep-0440/). The measurement and analysis rules behind these
changes, each with its evidence, are in `DESIGN_DECISIONS.md`.

## [Unreleased]

Everything since v1.0.0, to be released as 2.0.0. Timings, memory figures, counts and agreement
labels from v1.0.0 are not comparable with this version: the measurement windows, the resource
limits, the counts keys and the statistics all changed (see Changed).

### Added

#### `qrosetta` command

- `qrosetta`, a command-line tool for Python 3.11 and newer with no dependencies outside the
  standard library: `./qrosetta` in a checkout, or the `qrosetta` wheel.
- Local stack commands: `start` (`--profile`, `--bind`, `-d` returns once the API is ready and the
  runners answer, `--no-cpu-quota` for rootless hosts without cpu delegation), `stop` (refuses
  while runs are in flight unless forced), `remove` (`--images`; `--data` and `--all` with
  `--confirm <project>`), `status`, `logs`, `build`, `doctor` (host checks, each with its fix),
  `profiles`, `config path|show`, `version` and `api` (raw requests).
- Release images by digest: `pull` and `images ls|verify|save|load`, checking the cosign signature
  when cosign is installed.
- Commands for a local or remote server: `info`, `backends`, `compilers`, `circuits`, `login`,
  `logout`, `whoami`, `run` (one circuit or a playlist; `--exclusive`, `--repeats`, `--compiler`,
  `--fail-on`, `--dry-run`), `wait`, `jobs`, `show summary`, `export crate|report` and `selftest`.
  Experimental: `show circuits|diff|artifacts|views` and `export figure|views`.
- `--json` on every command, with a versioned output schema per command
  (`qrosetta.cli/<command>@<n>`) and fixed exit codes.
- The command acts only on containers, networks, images and volumes that carry both the compose
  project label and its own ownership label. For anything else in the way it prints the command
  to run instead of acting.
- `start` recreates containers whose image or compose configuration changed; `status` shows the
  image each container runs.
- VS Code tasks for start, stop, remove and status.

#### Web page

- A workspace of Generate Circuits, Editor, Playlist and a Run footer; each group of run settings
  is a chip in the footer that opens its own popover.
- One searchable Quantum Algorithms menu over the algorithm templates, bundled examples, MQT Bench
  and QASMBench; Quick Load sets and a Bench popover that adds benchmark circuits to the playlist.
- Five result tabs: Summary (a headline naming the backends that differ, a per-backend table, then
  the evidence), Agreement, Performance, Circuits (the submitted, dispatched, executed and compiled
  circuit texts side by side, with a line diff between any two) and Exports.
- Exports tab: figure and table views with parameters, preview, caption and download (SVG, PDF,
  PNG; LaTeX, CSV, Markdown, HTML, XLSX), presets, and an RO-Crate builder that lists every file it
  will write.
- Read-only share links to a saved run's circuit texts, expiring after 1 to 90 days and revocable.
- Experiment sweeps over the preprocessing setting, downloaded as a bundle with a triage README and
  a manifest.
- The results area shows its layout before the first run, and a running job's status fills the
  table its result will use.
- `/#job=<id>` links open a job's results; the CLI prints one after `run`, `wait` and `selftest`.
- Optional auto-save of completed runs to a local folder, in browsers with the File System Access
  API.
- Keyboard, screen-reader and forced-colours support; narrow screens are usable.
- The written guide, `docs.html`, with the metric formulas, defaults, the submit-time checks and
  known backend issues.

#### Measurement and analysis

- Compile-only services: BQSKit, PyZX, MQT QMAP, Cirq transformers, staq, Q-Synth, Quartz and
  Synthetiq. Their output circuits are recorded, shown and exported, never simulated, timed or
  compared. Outputs up to 10 qubits are checked against the input's unitary with Qiskit, and a
  refusal names its reason. A compile-only run (`simulate: false`) accepts up to 24 qubits.
- `timing_repeats` (1 to 10): reported times are medians, with each repeat's sample, the mean and
  the standard deviation.
- Exclusive runs: each backend in its own phase, admitted only while nothing else runs on the
  server; the wait is recorded.
- Each run records CPU throttling, the CPUs it ran on and their maximum frequency, container CPU
  time over the simulation window, queue waits, and the overlapping runs of its own job and of
  other jobs. The server derives timing caveats from these and the page shows them.
- Measured comparisons: a `measured_assessment` per pair (`consistent_within_shot_noise`,
  `inconclusive_low_shots`, `ambiguous`, `distinguishable`, `not_comparable`) from chi-square and
  Williams-corrected G-tests under Benjamini–Yekutieli correction, with the test's power and a
  recommended shot count; exact conditional tests for sparse 2×2 tables; single-bit marginal
  tests under Holm correction.
- Statevector and measured pairs are compared in the basis their declared bit orders imply.
- Every new report records `pair_verdict` on each pair and per-backend counts; the server computes
  them for older reports (`GET /jobs/{id}/summary`, `GET /history/runs/{id}/summary`,
  `POST /summary`).
- A measured run always records a master seed (the caller's or a generated one); each backend
  gets its own derived seed, recorded as `runner_seed`.
- A self-test with known answers from an independent numpy reference (`GET /selftest`,
  `qrosetta selftest`), compared with each backend separately.
- Every result records the image it ran from (commit, build-file hashes, whether it was built
  locally or released, emulation); reports summarise them as `specimens` and carry
  `run_completeness`.

#### API

- `POST /plan`, the one run planner the page and the CLI use.
- `GET /jobs/{id}/report` and `POST /jobs/{id}/export` serve a job's full report and RO-Crate;
  `?gated=true` admits them only while no other run is being dispatched.
- `GET /jobs/{id}/circuit-texts`, `GET /publication/views`, `POST /publication/render`,
  `POST /jobs/{id}/publication/render`, `POST /experiments`, `GET /experiments/{id}/bundle`,
  share-link routes under `/history/runs/{id}/share-links` and `POST /shared/circuits`,
  `GET /compilers`, `GET /examples`, `GET /quickload`, `POST /timing-caveats`,
  `GET /jobs/{id}/selftest-result`.
- `GET /health` (the process answers) and `GET /ready` (the database and job storage work).
- `GET /config` publishes every limit the page checks, the default of every request field
  (`request_defaults`), a server handshake (`platform_version`, `api_levels`, features), status
  labels and the roles of summary outcomes.
- `?fresh=true` on `GET /runners` and `GET /compilers` probes the services, at most 6 times a
  minute per client and never while a run is being dispatched to them.
- `X-RateLimit-*` headers on rate-limited routes, and `Retry-After` on 429.
- Swagger UI at `/docs` and ReDoc at `/redoc`.
- The database schema is versioned with Alembic and upgraded at startup; a database created by an
  earlier version is adopted and stamped.

#### RO-Crate exports

- Crates hold the circuit each backend was sent (`dispatched_circuits/`) and executed, the compile
  input and compiled circuits (`tables/compiled_circuits.csv`), a `README.txt` written from the
  crate's own metadata, and a sha256 and size for every file.
- Crates record where the report came from (`server_job`, a saved run, or client-supplied); a
  supplied report's versions are marked "as supplied".
- A runner's `requirements.lock` is included only when its hash equals the one the image reports.
- Crates are named after the run and the UTC export time.

#### Deployment and packaging

- A release workflow that builds and self-tests every image, and on a release tag publishes the
  images to GHCR and the `qrosetta` wheel to PyPI. The myQLM, cuQuantum and BQSKit images are
  never published.
- An Apptainer launch wrapper for one runner or compiler job and an untested Slurm job template;
  runners and compilers read a payload from a file and write the result to one.
- `DESIGN_DECISIONS.md`, `CONTRIBUTING.md`, `THIRD_PARTY_NOTICES.md` (with the MQT Bench licence),
  `Licence.txt`, `CITATION.cff`, `.zenodo.json` and `codemeta.json`.
- `SECURITY.md`, `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1), `SUPPORT.md`, this changelog,
  issue forms and a pull request template.

### Changed

#### Measurement

- All 16 runners measure through one shared instrument. Compilation time (t0..t1) covers parsing,
  transpiling and building the SDK's executable object; simulation time (t2..t3) covers execution.
  Tallying counts, serialising the executed circuit and shaping results run outside both windows,
  and Qulacs, QuEST, qsim, Qiskit and cuQuantum convert circuits before t2.
- Each runner gets 1.0 CPU and 1 GiB of memory, its BLAS and OpenMP thread pools are pinned to one
  thread, and it executes one run at a time.
- `memory_usage_mb` is the kernel high-water mark (VmHWM) over the simulation window minus the
  baseline; `process_peak_rss_mb` is the simulating process's own peak.
- Counts keys are the circuit's classical bits in declaration order, on every backend. Statevectors
  are `2**declared qubits` long, in declaration order, including after optimisation passes that
  remove swaps.
- The default shot count is 8200 (was 1024).
- Raw fidelity is stored unrounded, and the agreement thresholds (fidelity 1e-5, phase 1e-6 rad,
  norm 1e-4, JS 0.01 nats, Hellinger 0.1) are sent with the request and recorded in the report.
- Every enabled backend runs by default.
- Statevector mode strips terminal measurements and refuses mid-circuit measurement, `reset` and
  `if`. In measured mode only backends that simulate mid-circuit measurement natively run it; the
  others return an error.
- The circuit changes the API makes (register flattening, the pytket round-trip, appended
  measurements, angle rounding) are listed as `API:` entries in every backend's
  `preprocessing_applied`.
- The qubit-permutation search covers up to 7 qubits.
- cuQuantum runs on cuStateVec on an NVIDIA GPU and is reported unavailable without one.
- Both Aer runners use `method="statevector"`; quimb's contraction-path search runs in the
  simulating process.
- With preprocessing on, qibo and quimb receive the `qelib1.inc` definitions of gates their
  parsers lack.

#### Circuits

- Submitted circuits are checked before they run: header, declarations, indices, gate names,
  arity, parameters, broadcasts, opaque calls, block comments and non-ASCII text. Each refusal
  names its line.
- Gate parameters must be finite, with magnitude at most 1e6. User gate names that a backend's
  parser treats specially are refused. A circuit may make at most 4,096 calls of user-defined gates
  from inside gate definitions and 200,000 gate applications in all.
- Circuits are prepared in a separate process with a 1024 MiB memory limit and a 120 s time
  limit; bundled circuits known to exceed them are refused before they are sent.

#### API and server

- Requests with unknown fields are refused with 422, and error responses carry `detail` only.
- Job reports are kept on disk; retention is set by `QROSETTA_JOB_TTL_SEC`, a playlist holds at
  most 400 circuits, and job storage has a disk budget (503 with `Retry-After` while it is full).
- Rate limits count per signed-in account, with a per-address ceiling on runs, exports and
  rendering; sign-in and registration count per address.
- The API runs FastAPI 0.136.3 on Starlette 1.7.0. Responses carry `Vary: Origin`, file responses
  answer range requests, and an empty sign-in field is a 422.
- A run lost without a result names the possible causes, or the recorded one, instead of
  "most likely out of memory".
- Kubernetes: at most `QROSETTA_K8S_MAX_CONCURRENT_JOBS` runner and compiler Jobs exist at once,
  Jobs run images by digest when the deployment records them (`QROSETTA_IMAGE_DIGESTS`), and
  payloads over 96 KiB go through S3.
- myQLM is not deployed on the hosted server, because its licence forbids use over a network;
  local stacks keep it.

#### Page and local stack

- nginx is published on `127.0.0.1:8080` (`QROSETTA_HTTP_BIND`) instead of port 80 on every
  interface.
- The page is ES modules with Tailwind CSS served from the nginx image; nothing loads from a CDN.
- Failed runs and unmeasured metrics show "—" instead of 0.
- Figures use the long backend names and the circuit's name, and slides are 16:9.
- The compose project is named `qsimulators`, and service images stop within a second.
- The page passes axe-core 4.14.0's WCAG 2.2 AA rules: white text on the yellow and emerald buttons
  is one shade darker, popover links and buttons, the mode checkboxes and the Bench rows are at
  least 24 px tall, the Backends table and the manual's tables take keyboard focus, the share page's
  links are underlined, and focus scrolls clear of the fixed notices.
- `README.MD` is now `README.md`.

### Removed

- `GET /download_latest_report`; use `GET /jobs/{id}/report`.
- The Configuration panel and the benchmark drawer; their controls are in the settings chips and
  the Playlist's Bench popover.
- python-jose: tokens are signed with PyJWT, and sessions from before the change stay valid.
- cuQuantum's fallback to CPU Aer.
- The `runners/` source mount into the API container.

### Fixed

- The Qrisp adapter returned an all-zero state and all-zero counts when the SDK call failed.
- Bit-order labels of several adapters were wrong, and Qiskit and cuQuantum (levels 2–3), PyQuil
  (1–2) and Cirq (2) returned permuted statevectors after optimisation.
- Six backends returned counts over all qubits instead of the measured bits, and parsers ordered
  classical registers alphabetically, so identical distributions scored JS = ln 2.
- Qubit limits counted only the first `qreg`.
- The configured runner timeout was ignored in local mode.
- torchquantum 0.1.8 crashed with NameError on u1, cu1, u2, cu2, toffoli, rc3x, rccx and other
  gates.
- PennyLane's warm-up ran inside its compilation window; PennyLane deleted gates written on a
  barrier's line; qibo deleted the statement after a `// barrier` comment.
- Two simultaneous submissions could swap gate definitions.
- Shot-noise power with unequal shot counts was overstated (8200 against 50 shots: reported 0.995,
  true 0.109).
- Correct measured pairs with a rare outcome, and near-deterministic circuits, were labelled
  inconclusive.
- A measured pair that matched only after an undeclared bit reversal was labelled as agreeing.
- Register broadcasts were miscounted when one register's name was a prefix of another's.
- 14-qubit statevectors were replaced by the size placeholder in the page.
- pytket wrote every multi-controlled X as `c4x`.
- The Quirk visualizer drew only h, x, y, z and cx, and turned comments into gates.
- A worker exception left its job `processing` forever, and a compile-only playlist in which every
  compile failed was reported as done.
- Cancelling a run freed its execution slot while its process still ran, and a runner worker killed
  mid-run left the run's process alive.
- `DELETE /auth/me` failed with a foreign-key error on PostgreSQL.
- Server errors (500) for a malformed `Content-Length`, a non-UTF-8 JSON body, NaN or a field of the
  wrong type in a supplied report, and a registration that lost a race for its email are now 4xx.
- `POST /history/runs/{id}/export` dropped the requested figures and tables.
- Experiment bundles failed to build when a runner error was blank.
- The hosted frontend could not serve `docs.html`.
- Images could not be read by a container user other than `appuser`, as under Apptainer.

### Security

- Outside local mode the API refuses to start without `SECRET_KEY` instead of falling back to a
  built-in signing key.
- Untrusted data is escaped wherever the page writes HTML, and imported playlists are validated.
- Displayed text that holds a bidirectional control character or a right-to-left letter is
  isolated in a `<bdi>`, so an override in a runner error or an uploaded report cannot reorder the
  text around it.
- The 1 MiB request limit covers POST, PUT and PATCH, and nginx caps bodies at 5 MB, chunked ones
  included. Exception text is no longer returned to clients.
- Runner keys in supplied reports are validated and every ZIP member path is checked, so an export
  cannot write outside its crate.
- Rate limits key on an address the caller cannot set; sign-in is limited to 10 and registration to
  5 requests a minute per address, checked before the password.
- Outside local mode `bypass_limits` needs a signed-in account and lifts only the playlist and
  experiment caps.
- Only the account that submitted a job may save it, and a saved run may link only the caller's
  own circuit.
- Share-link tokens are stored as SHA-256 hashes and travel in the URL fragment and a POST body.
- Logout (page, `qrosetta logout`, `POST /auth/logout`) ends every session of the account on the
  server; `POST /auth/password` changes the password and ends earlier sessions too. Tokens must
  carry `exp`, `iat` and `sub`. A sign-in for an unknown email takes as long as a wrong password.
- Kubernetes runner and compiler pods mount no service-account token.
- Dependencies in the API image raised for advisories: anyio 4.14.2, certifi 2026.10.19, pyasn1
  0.6.4, urllib3 2.8.0, requests 2.33.1, Starlette 1.7.0; PyJWT replaces python-jose
  (PYSEC-2026-4298).
- Commits and pushes are scanned for credentials (gitleaks hooks and a CI job).

## [1.0.0] - 2026-06-17

First public snapshot. Do not reuse its results: its Qrisp adapter returned an all-zero state and
all-zero counts when the SDK call failed (fixed in 5bb0574, July 2026), and the bit-order labels of
several adapters were corrected after it. Use the newest release.

[Unreleased]: https://github.com/SeQuSoS-Project/QRosetta/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/SeQuSoS-Project/QRosetta/releases/tag/v1.0.0
