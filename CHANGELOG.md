# Changelog

User-visible changes to Quantum Rosetta, by release. The format follows
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); version numbers follow
[PEP 440](https://peps.python.org/pep-0440/). The measurement and analysis rules behind these
changes, each with its evidence, are in `DESIGN_DECISIONS.md`.

## [Unreleased]

Everything since v1.0.0, to be released as 2.0.0. Timings, memory figures, counts and agreement
labels from v1.0.0 are not comparable with this version: the measurement windows, the resource
limits, the counts keys and the statistics all changed (see Changed).

In short: every backend now measures through one shared instrument under the same CPU, memory and
thread limits; measured comparisons are statistical tests with stated power instead of distance
thresholds alone; eight compile-only services sit beside the 16 simulators; a self-test checks each
backend against answers no backend computes; `qrosetta` installs from PyPI and runs the stack from
signed images on GHCR; and every result records the image, commit and host conditions it ran under.

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

- **Recent runs** in the page header for signed-out users opens this browser's list of runs the
  server still keeps; times in that list and in the Exports panel show the date when it is not today,
  and the Exports panel uses the server's retention time instead of a fixed 30 minutes.
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
- The written guide, `docs.html`, with the metric formulas, defaults and the submit-time checks.

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
  tests under Holm correction. With every backend correct, 0.6–1.1 % of runs show a full-table
  flag and 3.9–4.8 % show at least one flag of either family (each family at α 0.05); in fault
  injection every measured fault of total variation 0.02 or more was flagged (`DESIGN_DECISIONS.md`,
  False-flag figures).
- Statevector and measured pairs are compared in the basis their declared bit orders imply.
- Every new report records `pair_verdict` on each pair and per-backend counts; the server computes
  them for older reports (`GET /jobs/{id}/summary`, `GET /history/runs/{id}/summary`,
  `POST /summary`).
- A measured run always records a master seed (the caller's or a generated one); each backend
  gets its own derived seed, recorded as `runner_seed`.
- A self-test with known answers from an independent numpy reference (`GET /selftest`,
  `qrosetta selftest`), compared with each backend separately.
- `scripts/verify/`: known-answer checks of every `qelib1.inc` gate, built from its definition by a
  numpy reference, and qubit-relabelling, register-split and inverse relations, run through a
  server as a user.
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
- `GET /health` (the process answers) and `GET /ready` (the database and job storage work); every
  runner and compiler answers `GET /health` too.
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
- The GitHub release of a final version carries the wheel, the sdist, an SPDX SBOM and a source
  notice per published image, the OpenAPI description, the image list with verify commands,
  `SHA256SUMS` and a provenance bundle over all of them; the attached copies are checked before the
  release is published.
- Release images are scanned with Trivy: a CRITICAL vulnerability with a fixed version stops the
  release unless `.trivyignore` accepts it with a reason and a review date. A monthly workflow
  rebuilds every image without cache, self-tests and scans it.
- `scripts/requalify/requalify.sh`, which builds a runner or compiler image with its old and its new
  base from one commit and compares their outputs on a fixed-seed corpus, their self-tests and
  their timings. `--bump NAME==VERSION` raises named pins on an unchanged base.
- Published images are public on GHCR (`ghcr.io/sequsos-project/qrosetta-*`), signed with cosign
  by the release workflow, with build-provenance and SBOM attestations. Release candidates put the
  wheel on TestPyPI and make no GitHub release.
- The README describes installing from PyPI with the published images, with the host setup for
  Fedora (rootless podman) and Ubuntu (Docker); the sequence was run on fresh Fedora 45 and Ubuntu
  26.04 virtual machines with 2.0.0rc2.
- `docs/verification/`: the test plan with its threat model, the risk register, the ASVS 5.0
  assessment, and the completion report of the release criteria with their evidence.
- `docs/RELEASING.md`: release order, the files a version bump touches and the clean-machine checks.

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
- At most 1,024 classical bits over all `creg` declarations; register sizes, indices and
  `if` values of more than 30 digits, keywords as register or gate names, and a `//` comment that
  opens `/*` without closing it on the same line are refused.

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
- Every runner and compiler response is checked before use; a malformed one is that backend's
  error ("INVALID RESPONSE") and the rest of the job continues.
- A supplied report may hold at most 1,000 circuits and 48 backends per circuit, and a figure or
  table render waits at most 20 s for the renderer before answering 503.
- The page and `qrosetta` keep waiting for a job through an API restart (up to 5 minutes, with
  backoff); a job the restarted server no longer has is reported as lost (`qrosetta` exit 14,
  STATUS `job-lost`); `qrosetta wait` started while the API is down waits for its handshake the
  same way. nginx answers 502 and 504 with a JSON `detail`.
- `qrosetta` retries reads after a dropped connection or a 502, 503 or 504, never resubmits a run,
  and gives every container-engine call a timeout.

#### Images

- The API image runs Python 3.12. The runner images run Python 3.12 (Qibo 3.13) and the compiler
  images Python 3.13 (Q-Synth 3.12), except the disabled ProjectQ runner (3.10). In the API image
  and every moved image the base is pinned by digest, apt reads a fixed snapshot.debian.org date,
  and pip installs a lock with a hash for every package.
- Each moved runner and compiler image was requalified: on a fixed-seed corpus the old and the new
  image gave the same outputs (Cirq within its run-to-run variation; BQSKit's compiles, which vary
  run to run in either image, all pass their equivalence check) and the same self-test results.
  Timings changed: on the requalification circuits simulation times moved by −17 % (Cirq) to +9 %
  (myQLM) and compilation times by −40 % (Qibo) to +14 % (myQLM), so timings from earlier images
  are not comparable with these.
- The Qrisp, TorchQuantum and cuQuantum images no longer carry a compiler toolchain.
- The quimb runner image runs Python 3.12. Its simulation time varies by up to 2.7 times between
  runs of one circuit in either image (cotengra's unseeded contraction-path search), so compare
  quimb timings only over several runs with `timing_repeats` of at least 5.
- Every published runner and compiler image serves with FastAPI 0.136.3 and Starlette 1.7.0, as
  the API does, and takes the fixed versions of anyio, certifi, urllib3, PyJWT, pillow,
  cryptography and other packages outside the SDKs; each image was requalified and gives the same
  outputs. The myQLM, cuQuantum and BQSKit images, which are built on the user's machine, take the
  same versions. The Cirq, qsim and TorchQuantum images use setuptools 81.0.0, the last release
  with `pkg_resources`; the Python 3.13 images uninstall pip after installing their lock.
  Vulnerabilities left in the images are listed in `docs/RELEASING.md`.
- The nginx images no longer contain curl or nginx's optional dynamic modules (geoip, image
  filter, njs, xslt), which nginx never loaded.

#### Page and local stack

- The nginx images run as uid 101 on `nginxinc/nginx-unprivileged` 1.31.7 (Alpine 3.24), pinned by
  digest, and listen on 8080 inside the container; the published address is unchanged.
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
- Swagger UI at `/docs` is served from a vendored copy; ReDoc at `/redoc` loads from jsDelivr with an
  integrity hash.

### Removed

- `GET /download_latest_report`; use `GET /jobs/{id}/report`.
- The Configuration panel and the benchmark drawer; their controls are in the settings chips and
  the Playlist's Bench popover.
- python-jose: tokens are signed with PyJWT, and sessions from before the change stay valid.
- cuQuantum's fallback to CPU Aer.
- The `runners/` source mount into the API container.

### Fixed

- The API's container healthcheck allows 120 s for a first start (it allowed about a minute), so a
  slow first start on a new machine no longer stops `qrosetta start` with "container rosetta-api is unhealthy".
- When the API container fails its health check, `qrosetta start` prints the last health-check
  output and the last 20 lines of the API's log; it used to guess a cold page cache.
- `qrosetta doctor`'s fix for a port in use also says that later commands keep using the old port
  until `[lifecycle] bind` names the new one in the config file; `start --bind` alone is not kept.
- `qrosetta doctor` and the missing-Compose error name the install step for the host's distribution
  (from `/etc/os-release`: apt on Ubuntu and Debian, dnf on Fedora, the Compose plugin binary on RHEL
  with podman); they suggested apt on every host.
- An experiment bundle whose label has non-ASCII characters could not be downloaded (500).
- RO-Crates use the Workflow Run context next to the RO-Crate 1.1 context, so the `sha256` key of
  every File is defined; the crates pass rocrate-validator's Process Run Crate 0.5 profile at
  REQUIRED level (`scripts/verify/validate_crates.sh`).
- At optimization levels 1 and 2 the Qibo adapter no longer fuses a circuit that defines gates; it
  says so in `preprocessing_applied`.
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
- Every response carries a Content-Security-Policy, `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: no-referrer`, `Cross-Origin-Opener-Policy: same-origin` and
  `X-Frame-Options: DENY`; the pages hold no inline script, event handler or style.
- A POST, PUT, PATCH or DELETE from a page on another site is refused (403), and JSON routes read a
  body only with a JSON `Content-Type` (415).
- Deleting an account needs its password.
- X-Forwarded-For is read only from the proxies in `QROSETTA_TRUSTED_PROXIES` (by default nginx in a
  local stack), so a runner or compiler cannot choose its rate-limit key.
- The job spill directory must belong to the API's user; it is recreated with mode 0700 at startup,
  and only files the process wrote are read back.
- Image builds leave out databases, `data/` directories, env files and `node_modules`; no secret was
  found in any of the 24 images.
- Request bodies are counted as they arrive, so a chunked body stops at the 1 MiB limit without nginx
  in front.
- Crates and experiment bundles that hold a bundled MQT Bench or QASMBench circuit carry that suite's
  licence.
- Dependencies in the API image raised for advisories: anyio 4.14.2, certifi 2026.10.19, pyasn1
  0.6.4, urllib3 2.8.0, requests 2.33.1, Starlette 1.7.0; PyJWT replaces python-jose
  (PYSEC-2026-4298).
- Commits and pushes are scanned for credentials (gitleaks hooks and a CI job).
- Registration and password change refuse the 2,086 most common passwords of 8 or more
  characters (SecLists, MIT).
- Access tokens carry `aud=qrosetta-api`, which the server requires; tokens issued before the
  change are refused once.
- `SECRET_KEY` must be at least 32 bytes; S3 storage and Kubernetes mode need `S3_ACCESS_KEY` and
  `S3_SECRET_KEY` (the `minioadmin` default is gone).
- Saving, renaming and deleting saved circuits and runs is rate-limited (60 a minute per account,
  240 per address), and exporting a saved run counts as an export.
- An account keeps at most 1,000 saved runs and 1,000 saved circuits (`GET /config` `limits`).
- The account menu has Change Password; Logout clears the account's recent jobs in this browser.
- A security log (`rosetta-security-events`, JSON lines) records sign-ins, failed sign-ins,
  registrations, sign-outs, password changes, account deletions, 401/403 answers, cross-site
  refusals and rate-limit hits, without passwords, tokens or bodies.
- Every container drops all Linux capabilities, runs with `no-new-privileges` and is limited to
  1,024 processes; the Cloud Run frontend and the Rahti route send HSTS; nginx declares UTF-8.
- Locally built images no longer pick up `export/` and `experiments/` directories below the
  repository root.

## [1.0.0] - 2026-06-17

First public snapshot. Do not reuse its results: its Qrisp adapter returned an all-zero state and
all-zero counts when the SDK call failed (fixed in 5bb0574, July 2026), and the bit-order labels of
several adapters were corrected after it. Use the newest release.

[Unreleased]: https://github.com/SeQuSoS-Project/QRosetta/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/SeQuSoS-Project/QRosetta/releases/tag/v1.0.0
