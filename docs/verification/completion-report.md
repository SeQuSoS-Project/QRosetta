# Verification completion report (interim, 2026-10-29; E9 updated 2026-10-30)

State of the exit criteria in [test-plan.md](test-plan.md) §5 after the overnight run of 2026-10-27/29 on
the branch `overnight/integration`. The criteria are still proposed; the owner confirms them. Evidence
files named below are in the run's audit directory (`docs/audits/2026-10-28-overnight/`, not tracked).
The risk register's status column was updated on 2026-10-30 from the same evidence.

| # | Criterion | State | Evidence or what is missing |
|---|---|---|---|
| E1 | Every MUST run; 0 open Critical/High; open Medium fixed or a known issue | Not met | MUSTs not run: V4 items 1-2 (known answers, qubit relabelling). Open Medium: V7-08 (a runner keeps a dead caller's run and its slot; fix touches the sealed scaffolding). V5-04 (nginx as root) is fixed by B4-nginx (nginx runs as uid 101). No open Critical or High. C1 confirmed V7-08 on the live stack and found D-C1-1 (Low: `qrosetta wait` started while the API is down exited on its handshake instead of waiting; fixed in 5e8dfa2). |
| E2 | Unit suite, type gate, gitleaks, CI integration job green on the tag; images from the tag | Partly | Suite on `overnight/integration`: 3683 passed, 0 failed; type gate 50/50; ruff, shellcheck, hadolint, mypy at baseline. The CI `integration` job (V3) has never run on GitHub; it passed 13/13 locally against images built from the branch. No tag yet. |
| E3 | ASVS 5.0 Level 1 all Pass or N/A; listed Level 2 chapters no unaccepted Fail | Not met | No checklist was filled. V5 covered authorization (BOLA matrix), session termination (`POST /auth/logout`), JWT validation and account enumeration. |
| E4 | No Critical/High vulnerability with a fix, unless accepted | Not met | API image 0 fixable CRITICAL/HIGH (B1). Runner and compiler images: anyio, starlette, urllib3 remain in every requalified image; SDK pins (qiskit 0.45.3/1.x, torch 2.2.2) need owner acceptance in `.trivyignore`. The release gate (A7) will refuse these. |
| E5 | ZAP baseline no unexplained High/Medium; BOLA matrix 100 % of id routes, 0 failures | Met on the branch | V5: ZAP FAIL 0 (its Medium alerts on the old stack are fixed by V2/A3); BOLA 20 id routes x 4 identities, 0 failures, with a coverage test. Rerun ZAP against a stack built from the branch. |
| E6 | Fuzzing >= 8 CPU-hours, 0 unexplained crashes or timeouts | Partly | V6: 4.28 CPU-hours on the validator (last 2.00 h on final code: 0 findings), grammar harness 56,500 programs, report fuzzer 505,201 requests; 15 API defects fixed. Short of 8 CPU-hours. |
| E7 | Known-answer table and metamorphic relations pass on every backend | Not met | V4 not run. The self-test's known answers pass in every requalified image (identical old vs new). |
| E8 | Upgrade from a v1.0.0 database; clean installs on two distributions from the README | Partly | A1: a v1.0.0-shaped SQLite database upgrades with data kept (unit test); a copy of the stack's database upgraded cleanly. No live PostgreSQL run; clean installs are for people. |
| E9 | `qrosetta selftest` PASS on release images on a reference host | Partly | C1 (2026-10-30): PASS on images built locally from e23b32f on the development host (22 image probes, 819 pairs agree, 0 FAIL; 14 WARNs per mode for local builds). Release images (GHCR) not built yet. |
| E10 | axe 0 serious/critical; keyboard-only pass complete | Met on the branch | A12: axe-core 4.14.0, 33 states at 1280x800 and 390x844, 0 critical, 0 serious; keyboard pass Run -> Summary complete. The local stack serves this page since the 2026-10-30 rebuild. |

Remaining work, in order: V4; the page parts of V7's runbook (a person at the browser); quimb; the per-image lock bumps for the remaining CVEs; V8; ASVS checklist.
