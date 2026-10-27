# Integration tests

These require a **running stack** — they make real HTTP calls to
`http://localhost:8080` (set `QROSETTA_BASE_URL` for another address, for example when
`QROSETTA_HTTP_BIND` publishes nginx elsewhere) and execute circuits on the actual
simulator containers. They are not part of the unit suite.

```bash
./scripts/safe_boot.sh          # or: docker compose up -d
pip install -r tests/integration/requirements.txt ./shared
python -m pytest tests/integration/
```

CI (job `integration` in `.github/workflows/ci.yml`) builds nginx, the API and the qiskit,
qulacs and cirq runners from the commit, starts them with `docker compose`, and runs
`test_e2e_nginx.py`, `test_e2e_cli.py` and `test_runner_contract_asymmetric.py` against them.
The other files need the full stack and are run by hand.

| Variable | Effect |
| --- | --- |
| `QROSETTA_BASE_URL` | The stack's address (default `http://localhost:8080`). |
| `QROSETTA_TEST_RUNNERS` | A comma list: run only on these runners (for a stack that runs only some). The end-to-end tests default to `qiskit,qulacs,cirq`, the contract test to every active runner. |
| `QROSETTA_E2E_REQUIRE_CURRENT` | `1` requires the Origin, Content-Type, security-header, `/health`/`/ready`, password-on-deletion and sign-out checks. Without it the first five run only when `GET /config` lists the `readiness` feature and sign-out only when it lists `logout`, so the end-to-end test also passes against a server from before 2026-10-28. |

The end-to-end tests are a user of the stack: they create an account
`overnight-e2e-<random>@example.invalid` and delete it, run one job at a time, and never set
`bypass_limits`. A 429 is retried after its `Retry-After`.

The unit suite, which CI does run on every push, lives in `rosetta-api/tests/unit/`.

## What each file is for

| File | Checks |
| --- | --- |
| `test_runner_contract_asymmetric.py` | **The important one.** Runs a deliberately asymmetric circuit through every enabled runner and checks the statevector and counts against the expected result. A symmetric smoke test (Bell, GHZ) passes even when a runner returns the all-zeros state or has its bit-order label backwards; this one does not. |
| `test_e2e_nginx.py` | End-to-end through nginx: routing (`/`, `/docs` Swagger, `/docs.html` from disk, `/openapi.json`, unknown path → JSON 404); `/health` and `/ready`; security headers, a foreign Origin (403) and a non-JSON body (415); register and sign in; QFT-4 statevector (every amplitude 1/4) and measured on the chosen runners; the Summary (every pair agrees, every run returned); save; a share link read through `share.html`'s route, revoked, then 404; sign-out (`POST /auth/logout`), after which the old token gets 401 and a new sign-in works; account deletion (password required), after which the token, the login and the remaining link are refused. |
| `test_e2e_cli.py` | The same QFT-4 through `./qrosetta run` (both modes, `--fail-on differs,runs_without_output`), `show summary` from the saved file and from the server, and `export crate`. The CLI gets empty config, state and runtime directories. |
| `integration_test_live.py` | Older smoke test through nginx: the stack is up and a comparison completes. |
| `test_opt_levels.py` | Each runner accepts its advertised optimization levels and reports the level it actually ran at. |
| `test_compilers_live.py` | Every compile-only service is available and its image's `--self-test` passes; through the API every level compiles each self-test probe into text with the input's qubit count, text-counted metrics and, with Qiskit installed, the compile input's unitary (QMAP through its layout lines). Run it after any compiler version bump. |
| `test_<sdk>_runner.py` | Per-backend checks for runners whose adapters needed particular attention. |

`ACTIVE_STATEVECTOR_RUNNERS` in `test_runner_contract_asymmetric.py` must list exactly the
runners marked `enabled` in `rosetta-api/config.py`. That is enforced by
`rosetta-api/tests/unit/test_runner_registry_sync.py`, so adding a backend without adding
it here fails the unit suite rather than silently going uncovered.
