# Integration tests

These require the **whole stack running** — they make real HTTP calls to `http://localhost`
and execute circuits on the actual simulator containers. They are deliberately not part of
the unit suite and CI does not run them: they need 16 built images and take minutes.

```bash
./scripts/safe_boot.sh          # or: docker compose up -d
python -m pytest tests/integration/
```

The unit suite, which CI does run on every push, lives in `rosetta-api/tests/unit/`.

## What each file is for

| File | Checks |
| --- | --- |
| `test_runner_contract_asymmetric.py` | **The important one.** Runs a deliberately asymmetric circuit through every enabled runner and checks the statevector and counts against the expected result. A symmetric smoke test (Bell, GHZ) passes even when a runner returns the all-zeros state or has its bit-order label backwards; this one does not. |
| `integration_test_live.py` | End-to-end smoke test through nginx: the stack is up and a comparison completes. |
| `test_opt_levels.py` | Each runner accepts its advertised optimization levels and reports the level it actually ran at. |
| `test_<sdk>_runner.py` | Per-backend checks for runners whose adapters needed particular attention. |

`ACTIVE_STATEVECTOR_RUNNERS` in `test_runner_contract_asymmetric.py` must list exactly the
runners marked `enabled` in `rosetta-api/config.py`. That is enforced by
`rosetta-api/tests/unit/test_runner_registry_sync.py`, so adding a backend without adding
it here fails the unit suite rather than silently going uncovered.
