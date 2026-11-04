# Test plan for v2.0.0

Version 1, 2026-10-28 (task V0 of the verification campaign). Risks are numbered as in
`risk-register.md` (R1-R30). Task ids: V1-V9 are the verification campaign, A1-A13, B1-B4 and C1 the
overnight polish plan; both plans are in the private notes, and their results will be summarised in
`completion-report.md` (task V9). Section 8, the threat model, is a draft for the owner to check.

## 1. Test items

Quantum Rosetta at version `2.0.0.dev0` on the branch that becomes the v2.0.0 tag: the API
(`rosetta-api/`), nginx and the page (`rosetta-api/static/`), the shared instrument
(`shared/qrosetta_commons/`), the 16 runner and 8 compiler images, the `qrosetta` CLI (`qrosetta_cli/`)
and the release workflow (`.github/workflows/release-images.yml`).

## 2. Scope

In scope, tested:

1. Local mode (Docker Compose) on Linux, with rootless podman 5.x and Docker Compose v2 as provider (the
   reference host: EL10, SELinux enforcing) and with Docker Engine and Compose v2.
2. The CLI: stack commands on Linux; client commands on Linux, macOS and Windows (the CI matrix, Python
   3.11-3.15).
3. The page in current Firefox and Chromium, including the share page and the docs pages.
4. Exports (RO-Crate, report JSON, publication figures and tables) and client-supplied reports.
5. The release workflow, statically (`test_release_workflow.py`, `test_release_manifest.py`) and through
   one rc rehearsal (owner).

Experimental, not tested in this campaign, stated as such in the v2.0.0 release notes unless the owner
decides otherwise (R24):

6. Kubernetes mode (`EXECUTION_MODE=kubernetes`, Rahti). Unit tests of the Job spec and dispatch
   (`test_k8s_dispatch.py`, `test_k8s_job_slots.py`) run in CI; nothing runs against a cluster.
7. Apptainer and Slurm (`scripts/roihu/`).

Out of scope: the cuQuantum GPU path on hosts without an NVIDIA GPU (reported unavailable, which is
tested); the disabled braket and projectq runners; publishing (owner only).

## 3. Test levels and where they run

| Level | What | Where |
|---|---|---|
| Unit and static | `rosetta-api/tests/unit/` (pytest-xdist), type gate (`scripts/check_frontend_types.sh`), parity harnesses, OpenAPI CLI contract, gitleaks | CI on every push |
| CLI | bare `cli` job (Python 3.11-3.15; client half also on macOS and Windows) | CI |
| Integration, live | `tests/integration/` against a running stack; V3 adds a CI job with nginx, API, qiskit, qulacs and cirq, and an E2E smoke test through nginx and `./qrosetta` | locally today; CI after V3 |
| Known answers and metamorphic relations | `GET /selftest`; V4 per-gate table, relabelling, inverse, register split, null effect, cross-mode | live stack |
| Equivalence | `scripts/harness_bench/equivalence.py`, `prep_equivalence.py`, `scripts/adapter_paths/compare_paths.py`, B2 requalification harness | before any change to analysis, preparation or an image |
| Security | V5 (authorization matrix, JWT, rate-limit spoofing, scanners), V2 (headers, XSS), V6 (fuzzing, ReDoS) | in process and against the live stack as a user |
| Failure injection | V7 (fake runners, killed prep worker, spill budget, API restart, clock skew) | in process overnight; on the real stack by people |
| Statistical | V8 (Monte Carlo of false-flag and power figures, p-value calibration, mutation score) | offline, CPU heavy, never beside a timing measurement |
| Exploratory and acceptance | five charters, clean-VM installs, upgrade from v1.0.0, screen-reader and keyboard passes | people (campaign, "For people") |

## 4. Entry criteria

A task starts only when:

1. Its branch is created from `overnight/integration` (or the release branch later), and at that commit
   the unit suite and the type gate pass. The two load-sensitive tests
   (`test_memory_monitor_captures_spike`, `test_circuit_preparation_does_not_block_the_event_loop`) count as
   passing when they pass on a rerun alone.
2. For live tasks (V3 locally, V4, V5): `GET /config` on http://127.0.0.1:8080 answers and `GET /runners`
   lists the enabled runners as available. The task uses the stack as a user only: one job at a time, a
   test account `overnight-<task>-<random>@example.invalid` deleted at the end, no `bypass_limits`.
3. For timing work (B2, B3, V8 timing parts): no image build, scanner or V4/V6/V7/V8 job runs at the same
   time, and the load average is recorded before and after.
4. Scanner and tool images are pinned by digest and mount none of the stack's volumes.

Suspension: a task stops and reports when it would need to start, stop, rebuild or prune the stack, change
a sealed timed window without old-vs-new evidence, or make an owner decision (polish plan, rules 3, 5, 10).

## 5. Exit criteria for v2.0.0

Proposed; the owner confirms. Copied from the verification campaign.

| # | Criterion | Covered by |
|---|---|---|
| E1 | Every MUST in the campaign run, with evidence; 0 open Critical or High defects; every open Medium fixed or listed as a known issue with a workaround in the release notes. | V1-V8 (defects in `defects.md`); V9 maps each to evidence |
| E2 | Unit suite, type gate, gitleaks and a CI integration job green on the tagged commit; images built from the tag, never `-dirty`. | V3 (integration job); C1 (full check of the integration branch); A10 (release checklist); existing CI |
| E3 | OWASP ASVS 5.0 Level 1: every requirement Pass or N/A with a reason; the listed Level 2 chapters (V2, V4, V5, V7, V8, V9, V13, V15, V16) have no Fail without a written accepted-risk entry. | V5 and V2 cover the requirements named in the QA report (JWT, authorization, logout, headers, decompression, generic errors). The full Level 1 checklist has no task tonight: open, owner to schedule |
| E4 | No Critical or High dependency or image vulnerability with a fix available, unless accepted in writing. | V5 (pip-audit, Trivy incl. secrets, triage); A7 (Trivy and Dependabot in CI); A8; B1, B3 |
| E5 | ZAP baseline: no unexplained High or Medium alert. BOLA/IDOR matrix: 100% of id routes, 0 failures. | V5 (ZAP baseline, matrix with coverage assertion); V2 (the header fixes ZAP would flag) |
| E6 | Fuzzing: at least 8 CPU-hours across the harnesses with 0 unexplained crashes or timeouts. | V6 (>= 2 CPU-hours on harness 1 overnight; the remaining hours later) |
| E7 | Known-answer gate table and metamorphic relations pass on every backend, or each failure is a documented upstream defect. | V4 |
| E8 | Upgrade from a v1.0.0 database and clean installs on two distributions succeed from the README alone. | A1 (migrations); people: clean VMs (Fedora/RHEL with rootless podman, Ubuntu LTS with docker) and the upgrade with real data |
| E9 | `qrosetta selftest` PASS on the release images on a reference host. | C1 (on images built from the integration branch); the rc rehearsal (owner, A10 checklist) |
| E10 | axe: 0 serious or critical issues; keyboard-only pass complete. | A12 (axe-core, or a static review if no headless browser); people: keyboard and screen-reader pass |

## 6. Risks to exit criteria

| Risk rows | Exit criterion |
|---|---|
| R1-R3, R5 | E7, E9 |
| R4 | E2, E9 |
| R6 | E8 |
| R7-R9, R11-R15, R27-R29 | E1, E2, E6 |
| R10, R26 | E4 |
| R16, R19-R23, R25 | E3, E5 |
| R17 | E2, E9 |
| R18 | none: proposed as a new criterion ("three fixture crates validate against the Process Run Crate profile at REQUIRED level") |
| R24 | none while Kubernetes mode is experimental |
| R30 | E10 |

## 7. Deliverables

`risk-register.md` and this plan (V0); `defects.md` and session sheets (private notes); per-task reports;
`completion-report.md` (V9), attached to the release.

## 8. Threat model (draft for the owner)

### 8.1 Data flow and trust boundaries

```mermaid
flowchart LR
  subgraph TB1["TB1 browser / internet"]
    B[Browser: page, share page]
  end
  subgraph HOST["TB5 host user"]
    CLI[qrosetta CLI]
    TOK[(lifecycle.token 0644 in 0700 dir)]
    CRED[(credentials.json 0600)]
    ENG[podman / docker engine]
  end
  subgraph PUB["public_net"]
    NG[nginx, published on QROSETTA_HTTP_BIND, default 127.0.0.1:8080]
  end
  subgraph ISO["isolated_net (internal: true)"]
    API[rosetta-api:8000]
    R[16 runners :8000]
    C[8 compilers :8000]
    PREP[prep worker process]
  end
  subgraph DATA["TB4 data at rest"]
    DB[(SQLite volume / PostgreSQL)]
    RS[(report store: local dir / S3)]
    SP[(spill dir /tmp/qrosetta-jobs)]
  end
  subgraph K8S["TB6 Kubernetes (experimental)"]
    KAPI[K8s API, Role job-manager]
    JOB[runner and compiler Job pods]
    S3[(S3 bucket: jobs/* and users/*)]
  end
  B -- "TB1: HTTP, JWT in localStorage" --> NG
  NG -- "TB2: X-Forwarded-For appended" --> API
  API -- "TB3: payload, no auth" --> R
  API -- "TB3: payload, no auth" --> C
  R -. "TB3 reverse: unvalidated JSON result" .-> API
  R -. "lateral: reachable, no auth" .-> API
  API --> PREP
  API --> DB
  API --> RS
  API --> SP
  CLI -- "TB7: HTTPS or loopback HTTP, Bearer token" --> NG
  CLI --> ENG
  CLI --> TOK
  TOK -- "bind mount, read on every request" --> API
  CLI --> CRED
  API -- "service-account token" --> KAPI
  KAPI --> JOB
  JOB -- "bucket-wide key" --> S3
  API --> S3
```

Trust boundaries:

- TB1 browser to nginx. Local mode publishes nginx on `127.0.0.1:8080` unless `QROSETTA_HTTP_BIND`
  names another address; Rahti puts a Cloud Run nginx in front that sets `X-Qrosetta-Client-Ip` with a
  proxy token.
- TB2 nginx to API. The API keys rate limits on the last X-Forwarded-For entry, which nginx appends.
- TB3 API to runners and compilers, both directions. Runners parse attacker-chosen QASM through
  third-party SDK parsers; the API reads their JSON without a schema, size or depth check (R7). Neither
  side authenticates the other, and every runner can reach the API and every other runner on
  `isolated_net`.
- TB4 API to database, report store and spill directory.
- TB5 host user to CLI, engine and the lifecycle token. The token authorises `POST /local/host-load` and
  `?fresh=true` probes.
- TB6 API to the Kubernetes API (Role `job-manager`: create, delete and patch Jobs; read pods and
  events; bound to the namespace's `default` service account) and Job pods to S3.
- TB7 CLI to a remote API (token from `QROSETTA_TOKEN` or `credentials.json`).

### 8.2 STRIDE

S spoofing, T tampering, R repudiation, I information disclosure, D denial of service, E elevation of
privilege. "Unverified" marks a threat read from the code or configuration and not yet tried. The
control and gap columns describe `main` on 2026-10-30.

| # | Boundary | STRIDE | Threat | Current control | Gap and risk row |
|---|---|---|---|---|---|
| T1 | TB1, TB2 | S | Forged JWT | `security.decode_access_token`: HS256 only, `exp`, `iat`, `sub` and `aud` required, header fields not read; uid and iat binding, `tokens_valid_after`; `SECRET_KEY` required outside local mode, guard tested (V1.9); local mode runs one worker | none open; RFC 8725 negative tests pass (V5, R23) |
| T2 | TB3 | S | A compromised runner calls `rosetta-api:8000` directly and sets its own X-Forwarded-For, so it chooses its rate-limit key | X-Forwarded-For read only from a peer in `QROSETTA_TRUSTED_PROXIES` (default `nginx` in local mode, `*` on Kubernetes), else the socket peer (`test_v5_06_trusted_proxies.py`) | Kubernetes keeps `*`; no internal authentication between runners and API (R19) |
| T3 | TB3 | T | A compromised runner returns a forged result for its own backend | verdicts attribute the difference to that backend; known answers in `GET /selftest` | only its own backend is affected unless T4 holds (R1, R19) |
| T4 | TB3 | T, I | A compromised runner intercepts API-to-runner traffic on the shared bridge and alters other backends' results | every service drops all capabilities (`cap_drop: [ALL]`, so no `NET_RAW`) and sets no-new-privileges (2026-11-02, ASVS 13.2.2) | R19: per-runner networks or internal authentication (ASVS 13.2.1 accepted for v2.0.0) |
| T5 | TB3 | E, D | A compromised runner calls other runners' `/run` past the gate, loading the host during other timed windows unrecorded; or fork-bombs, fills the disk | `RUNNER_MAX_CONCURRENT`=1 per runner; memory limit 1G, CPU quota 1.0 | process limit 1024 per service (2026-11-02); no read-only root or internal authentication (R19) |
| T6 | TB3 | E | From inside `isolated_net` a runner submits jobs with `bypass_limits` (anonymous in local mode) | RUN rate limit 10/min, keyed on the runner's own address (T2); a request without Origin passes the cross-site check | R19, R20 |
| T7 | TB1 | E, D | Local mode bound to a public address: anyone registers, runs with `bypass_limits`, reads job reports by id; no TLS, so tokens cross the network in clear | default bind is loopback; changing it is an explicit choice | R20: owner decides warn or refuse |
| T8 | TB1 | T, E | A page on another site POSTs a run to a local server without a CORS preflight | `routers/same_origin.py`: 403 for a state-changing request from a foreign Origin, `Origin: null` or Sec-Fetch-Site cross-site/same-site; JSON routes read a body only with a JSON Content-Type (415) | none open (R12) |
| T9 | TB1 | I | Stored XSS in the main page reads the JWT from localStorage; clickjacked `DELETE /auth/me` | CSP on every page (`script-src 'self'`; no inline script, handler or style), nosniff, `X-Frame-Options: DENY`; the escaping of every HTML sink pinned (`test_html_sinks.py`); `DELETE /auth/me` needs the password | token kept in localStorage (DESIGN_DECISIONS.md, "Sign-in token in local storage"; R21) |
| T10 | TB1, TB2 | I | Another account reads a saved run, circuit or share-link list; any holder of a job id reads that job's report, also an owned job's | `user_id` filters; owner check on save (403); uuid4 job ids; share tokens stored as SHA-256 | R22: V5 matrix; job ids also appear in nginx and gunicorn access logs (combined format) |
| T11 | TB2, TB3 | I | Raw exception text with container paths in responses and stored reports | `services/error_text.py`: only messages the API writes reach clients, other exceptions as their type; absolute paths in runner and compiler text replaced (`qrosetta_commons/redact.py`) | none open (R13) |
| T12 | TB2 | D | Crafted reports, chunked bodies, deep expressions, regexes on 1 MB input | 1 MiB body limit counted as the body arrives (chunked included); supplied-report caps (1,000 circuits, 48 backends); render lock wait 20 s; numbers over 30 digits and more than 1,024 classical bits refused; every API regex timed at 64 KB in CI; rate limits per account with a per-address ceiling | quadratic regexes in qibo, quimb, pyquil and staq adapters with preprocessing off (V6-R1..R3, sealed images; R14) |
| T13 | TB4 | T, E | A pickle planted in a pre-existing `/tmp/qrosetta-jobs` runs in the API | the spill directory must be the API user's own and not a link, and is recreated 0700 at startup; only files this process wrote are unpickled | none open (R27) |
| T14 | TB4 | I | Developer database or reports copied into a locally built image and exported with `qrosetta images save` | `.dockerignore` excludes databases, `data/` directories, env files, caches and `node_modules` at every depth (`test_build_context.py`); gitleaks over all 24 images found no secret (A13, 2026-10-28; repeated on 2026-11-04 over every layer of the images built from the 2.0.0rc4 Dockerfiles: 242 layers, 19.1 GB, 2,809 hits, all in third-party packages) | none open (R26) |
| T15 | TB5 | S | Another local user reads the lifecycle token | token file in a 0700 directory under `$XDG_RUNTIME_DIR` | a heartbeat 404 (token recreated under a running stack) ends the notice with a warning (V1.12, R28) |
| T16 | TB7 | I | The CLI sends the token to a redirect target, to any `--server`, or over plain http | http and https only; Authorization dropped on a cross-origin redirect; password refused over plain http to a non-loopback host; credentials 0600 | none open (R25) |
| T17 | TB5 | T, E | A crafted image archive applies its own tags on `images load`; a crafted crate ZIP exhausts memory | archive schema and sha256; an archive naming another tag refused; crate reads capped (member count, file list, metadata and text sizes) | none open (R25) |
| T18 | TB6 | T, I | A parser exploit in a Job pod uses the bucket-wide S3 key to read or forge user reports and other jobs' results | no service-account token in pods; payload in env or a pending key | R24: no NetworkPolicy, no per-job credentials; accepted only if Kubernetes mode is experimental |
| T19 | TB6 | E | A compromised API creates Jobs with any image in the namespace | Role limited to Jobs, pods and events | R24 |
| T20 | all | R | A failure or abuse cannot be traced across API, runner and pod logs | job id in some API log lines; per-result timestamps, exit codes, image identity | no request or correlation id; K8s pod logs deleted after 300 s (risk not in the register: proposed as R31 if the owner wants it tracked) |

### 8.3 Questions for the owner

1. Are the trust boundaries above the right ones, in particular TB3 treated as untrusted in both
   directions?
2. For v2.0.0: accept T2-T6 in writing with a note in the release, or harden runners first (a Wave B task
   after B3, with a timing re-measurement)?
3. Local mode on a non-loopback bind (T7): warn, refuse without a flag, or document only?
4. Kubernetes mode (T18, T19): experimental in v2.0.0?
