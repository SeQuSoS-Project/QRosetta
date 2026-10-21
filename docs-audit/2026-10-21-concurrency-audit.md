# Concurrency audit of the API process, 2026-10-21

Scope: shared mutable state of `rosetta-api` (one gunicorn worker: an asyncio loop, the
`asyncio.to_thread` / threadpool workers that run sync routes and spilled-report work, and
in Kubernetes mode one dispatch thread per Job). The measurement instrument in
`shared/qrosetta_commons/helpers.py` was read and probed but not changed.

Tests were run on Python 3.12.15 and 3.10.15 (the API and runner images use 3.10) with
numpy 1.26.4.

## Inventory

| State | Accessed by | Protection | Verdict |
|---|---|---|---|
| `job_manager.ACTIVE_JOBS` (`JobTable`) | written by loop coroutines (routes, workers, cleanup); read from threads by `_report_file`, export, publication and the history save | dict operations are atomic under the GIL; all writes are in the loop; `store` re-checks the job after its spill thread and removes the files of a job evicted meanwhile | safe; `test_job_table_concurrency.py` state machine |
| Spilled reports (`<id>.pickle`, `<id>/task-*.pickle`, `bundle.zip`) | written in threads, removed by `pop` in the loop, read in threads | temporary file + `os.replace`; an open file survives unlink; a missing file is `FileNotFoundError` -> 404 | safe; a read interrupted by eviction never returns a partial report (machine rule) |
| `expired_job_ids` / `_cleanup_old_jobs` | loop | no await between selection and `pop`; a job whose worker task runs is never selected | safe |
| A job's `runner_statuses` and `progress` | loop; Kubernetes dispatch threads write values | threads only assign keys the loop created before they start, so serialising in the loop never sees the dict change size | safe |
| `run_registry.REGISTRY` | loop (HTTP dispatch) | `threading.Lock` | safe; thread stress test |
| `run_registry.GATE` (`ExclusiveGate`) | loop | `asyncio.Condition` | defect 4, fixed; Hypothesis schedule test with cancellations |
| `run_registry._EXCLUSIVE_OWNERS` | loop (routes, workers) | `threading.Lock` | safe; one claim per client under 16 simultaneous claims. The claim is released when the worker ends, so it relies on the background task running |
| `routers/history._SAVE_LOCKS` | threadpool (sync route) | guard lock | defect 1, fixed |
| Share-link creation | threadpool, one DB session each | none before the fix | defect 3, fixed |
| Account registration | threadpool | unique constraint only | defect 2, fixed |
| Rate limiter (slowapi, `limits` 5.8 `MemoryStorage`) | loop and threadpool | per-key `RLock` in `limits` | safe; 80 simultaneous hits on 30/minute admit exactly 30 |
| `publication.theme._MPL_LOCK`, `figure_size` thread-local | render threads (routes, crate export) | the lock is held across `rc_context`, build and save | safe; renders at four sizes from eight threads match serial bytes (fails with the lock removed) |
| `publication.distributions._MEMO` | render threads | lock around get/put; compute outside it; hit only when the cached report is the same object | safe; holds up to 6 report objects alive |
| `PYTKET_LOCK` (`circuit_resolver`, `circuit_library`, `quirk_converter`) | threads via `asyncio.to_thread` | every pytket parse, write and template `exec` is lexically inside the RLock | safe; eight simultaneous round trips of circuits with user gates match serial output (fails with the lock removed) |
| `dispatcher_k8s.JOB_SLOTS` | dispatch threads | `BoundedSemaphore`; released only after a successful acquire | safe; peak concurrency equals the slot count, every slot is returned, a queue timeout releases nothing |
| `availability._cache` | loop | none needed | safe; concurrent probes may repeat a probe |
| `circuit_library._ALGORITHMS_CACHE`, `_EXEC_GLOBALS` | loop and threads | idempotent whole-dict assignment; `exec` under `PYTKET_LOCK`; templates use a private `random.Random` | safe |
| `lru_cache`s (`benchmark_library`, `qasm_structure._qelib1_signatures`, `qelib1_definitions`) | loop and threads | `functools.lru_cache`; tuples or read-only dicts | safe |
| Local report mirror (`storage`) | threadpool | new uuid path written before the DB row is committed | safe |
| `ExecutionSlots` (runner process, instrument) | runner loop | `asyncio.Semaphore` | admission is FIFO on 3.10.15 and 3.12 (probe); one latent race, reported below |

## Defects fixed

1. `415f166` History save lock. `_job_save_lock` dropped the lock of every job no longer in
   `ACTIVE_JOBS`, including one a save was holding. Saves that had read the report before
   the job expired then took a new lock each: four simultaneous saves stored four runs.
   The locks are now reference-counted.
2. `b46a028` Registration race. Two registrations of one email both passed the existence
   check; the second commit raised `IntegrityError` and the route answered 500. It now
   rolls back and answers 400.
3. `6ce9c15` Share-link cap. The active-link count and the insert were separate steps:
   six simultaneous requests at a cap of 2 created six links. Count, insert and commit now
   run under a process lock (one worker).
4. `45f0a1b` Gate release. `ExclusiveGate.release` changed its counts only after
   acquiring the condition's lock; a release cancelled while waiting for that lock left
   the gate exclusive, holding back every later dispatch. The counts now change before the
   first await and the notify runs in a shielded task.

## Reported, not fixed

- Measurement instrument (`helpers.ExecutionSlots.run`, off-limits): when the awaiting
  request is cancelled during `run_isolated`, the `finally` block releases the slot while
  the executor thread and its child process keep running until they finish or hit the
  hard timeout. The next queued run then executes beside the orphaned one, against the
  "one run per runner at a time" decision. Uvicorn does not cancel a handler when the
  client disconnects, so this needs a runner shutdown or a cancelling middleware to occur.
- Pre-existing test environment issue: `test_compile_adapters_inputs.py` imports qiskit
  without `importorskip`, and four tests in `test_compile_checks.py` need qiskit. qiskit
  2.5.2 requires numpy 2, so with the API's numpy 1.26.4 they cannot run (one collection
  error, four failures).
