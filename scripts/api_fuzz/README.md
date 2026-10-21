# API fuzzing with Schemathesis

`run_fuzz.py` generates requests from the API's own `/openapi.json` and sends them to the
FastAPI app in process (ASGI). No container, runner or compiler is started: background
tasks are recorded instead of run, every runner is reported available, the rate limiter is
off and the database is in-memory SQLite.

Before fuzzing, one statevector, measured, playlist and experiment job run through the real
workers against a fake fleet (every runner returns the Bell state or Bell counts), and the
seeded account saves three runs, a circuit and a share link. Then:

- two examples in three put these ids into path and query parameters (`job_id`, `run_id`,
  `circuit_id`, `link_id`, example `name`, MQT Bench `algorithm`, QASMBench `circuit`) and
  the share token into `POST /shared/circuits`;
- one example in three also replaces generated circuits, runner ids, preset names, emails,
  login credentials, reports and artifact ids in the body by ones the API accepts, and half of
  those reports get one to three values replaced by odd JSON values (null, huge numbers,
  empty containers, long or path-like strings) or a key dropped;
- three calls in four carry the seeded account's bearer token; `DELETE /auth/me` gets a new
  account for each call;
- runs uploaded during fuzzing are named in later `run_id` parameters and share links.

Each operation is fuzzed in positive and negative generation mode with the checks
`not_a_server_error`, `status_code_conformance`, `content_type_conformance` and
`response_schema_conformance`. An uncaught exception in the app is reported as `exception`,
a call slower than `--slow-sec` as a slow call. A separate probe sends reports holding NaN
and Infinity (which the fuzzer's HTTP client cannot encode) and reads back any run that was
saved. Findings are grouped by operation, check, status and message, each with the first
request and a curl line.

Schemathesis is not in the CI requirements. Set up a separate venv; the unit-test
requirements pin numpy 1.26.4, and Schemathesis 4.32 needs pytest >= 8.4, so pytest is
raised to 8.4.2, which pytest-asyncio 0.23.7 accepts:

```bash
python3.12 -m venv ~/.tmp/fuzz-venv
~/.tmp/fuzz-venv/bin/pip install -r rosetta-api/requirements.txt -r rosetta-api/tests/requirements.txt ./shared
~/.tmp/fuzz-venv/bin/pip install schemathesis==4.32.3 pytest==8.4.2
```

Run from the repository root:

```bash
~/.tmp/fuzz-venv/bin/python scripts/api_fuzz/run_fuzz.py                        # 150 examples per operation and mode
~/.tmp/fuzz-venv/bin/python scripts/api_fuzz/run_fuzz.py --examples 300 --seed 7
~/.tmp/fuzz-venv/bin/python scripts/api_fuzz/run_fuzz.py --ops 'export|publication' --modes positive
~/.tmp/fuzz-venv/bin/python scripts/api_fuzz/run_fuzz.py --replay ~/.tmp/api-fuzz/fuzz_report.json
```

`--replay` resends the first request of each finding with the API's log lines shown, which
gives the server-side traceback of a 500. The database, stored reports, spill files and
`fuzz_report.json` (findings, slow calls, status codes and slowest call per operation) go to
`--workdir` (default `~/.tmp/api-fuzz`). The exit status is 1 when there is any finding,
slow call or 5xx in the probe. With the same `--seed` and `--examples` the generated requests
repeat; seeded job, run and circuit ids are fixed, share tokens are not. 300 examples per
operation and mode take about five minutes.
