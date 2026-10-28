# Design decisions

This file lists the rules that Quantum Rosetta's measurement instrument and analysis follow, each with the evidence that settled it. Several of these boundaries were moved back and forth during development; each entry records the rule in force and the measurement or failure that fixed it. A rule changes only with new empirical evidence, and that evidence is recorded here.

Dates are when the evidence was collected (YYYY-MM-DD). Where a unit test enforces a rule, the test file is named.

## Contents

- [Terms](#terms)
- [Timing and CPU](#timing-and-cpu)
- [Memory](#memory)
- [Scheduling, isolation and job handling](#scheduling-isolation-and-job-handling)
- [Simulator configuration](#simulator-configuration)
- [Sampling, seeds and statistics](#sampling-seeds-and-statistics)
- [Agreement analysis](#agreement-analysis)
- [Circuit handling and preprocessing](#circuit-handling-and-preprocessing)
- [Compile-only services](#compile-only-services)
- [Provenance and reproducibility](#provenance-and-reproducibility)
- [Security and accounts](#security-and-accounts)
- [Interface and API behaviour](#interface-and-api-behaviour)
- [Upstream behaviour not worked around](#upstream-behaviour-not-worked-around)

## Terms

A *runner* is the container that wraps one simulator SDK; a *backend* is a runner at one optimisation level. Every runner measures through the same sequence in [`shared/qrosetta_commons/helpers.py`](shared/qrosetta_commons/helpers.py) (`run_statevector_job` / `run_measured_job`):

```
check_qubits_limit -> t0 -> compile_fn -> t1              (compilation_time)
serialize_fn                                              (provenance, outside the window)
MemoryMonitor + gc.collect() -> pre_execute_fn -> probe -> t2 -> execute_fn -> t3 -> probe   (simulation_time)
postprocess_fn                                            (shaping, outside the window)
```

A runner supplies the callbacks (`compile_fn`, `execute_fn`, `pre_execute_fn`, `postprocess_fn`) and never writes the timing itself. Agreement is pairwise: every pair of backends is compared, and there is no consensus computation. Abbreviations: F = fidelity, TV = total variation distance, JS = Jensen–Shannon divergence (nats), BY = Benjamini–Yekutieli, BH = Benjamini–Hochberg, FWER = family-wise error rate.

## Timing and CPU

### Shots vs histogram

*Rule.* Drawing shots / executing is inside `t2..t3`; tallying into a histogram, `get_counts()`, relabelling keys is `postprocess_fn`. Where an SDK fuses sampling and tallying in one call (qibo `frequencies`, qrisp `run`, quimb `simulate_counts`, Aer C++ counts) it stays inside and is noted in `preprocessing_applied`.

*Evidence (2026-08-18).* Tallying alone was 9–39% of `simulation_time` for five runners. [`rosetta-api/tests/unit/test_counts_histogram_boundary.py`](rosetta-api/tests/unit/test_counts_histogram_boundary.py) fails on `get_counts(`, `Counter(`, `readout_counts` in any `execute_fn`.

### Compilation

*Rule.* Parsing, transpiling, rebasing, optimisation passes, and building the executable object (PennyLane tape + `dev.preprocess()`) are `compile_fn`.

*Evidence.* PennyLane previously built its tape inside `execute_fn`, charging optimisation passes to simulation for two backends only.

### Conversion outside the simulation call

*Rule.* The Qulacs, QuEST, qsim, Qiskit and cuQuantum adapters split the SDK call at its native routine. Conversion (`tk_to_qulacs`/`tk_to_quest` + backend checks; `QSimCircuit` + `translate_cirq_to_qsim`; Aer `_compile` + `assemble_circuits` + `generate_aer_config` in [`qrosetta_commons.aer_split`](shared/qrosetta_commons/aer_split.py)) is in `compile_fn`. `execute_fn` = state allocation + apply / `qsim_simulate_fullstate` / `qsim_sample_final` or per-shot `qsim_sample` / Aer `_execute_circuits`, with the SDK's seed handling. Result objects and global-phase restore are in `postprocess_fn` (QuEST measured keeps the phase before sampling). Each adapter pins the SDK version whose call it reproduces (`require_distribution_version`, `aer_split.require_aer`). [`rosetta-api/tests/unit/test_conversion_boundary.py`](rosetta-api/tests/unit/test_conversion_boundary.py) fails on a converting call or any loop over something other than `range()` in `execute_fn` and its callees (Qulacs measured: the readout bits through `implicit_qubit_permutation` are found in `compile_fn`). Braket and ProjectQ (disabled) are unchanged.

*Evidence (2026-10-02).* Old vs new on the [`scripts/adapter_paths/compare_paths.py`](scripts/adapter_paths/compare_paths.py) corpus (random qelib1 circuits, 1–10 qubits, opt 0–2, preprocessing on/off, measured with seeds 0/7/123456789 and mid-circuit for qsim): 0 differences in statevector bytes, counts and executed text. Cases = circuit × opt level × preprocessing, from ~350 distinct circuits of ≤ 40 gates and ≤ 10 qubits; qulacs 1,500, quest 1,500, qsim 2,200, qiskit 1,700, cuquantum 1,080 cases; many measured cases are identical refusals. A deep set of 24 statevector + 16 measured cases per backend, 500–3,000 gates, ≤ 16 qubits: 0 differences. Measured 4q × 2,200 gates, simulation ms old → new: qulacs 103 → 2.4, quest 35.9 → 2.6, qsim 49.8 → 1.9, qiskit 29.9 → 8.6, cuquantum 47.2 → 17.8. qsim measured totals −24% (record assembly now in postprocess); Qulacs QFT-16 measured total −17% (the old call copied and phase-corrected the statevector). A later timing check found that Qulacs measured still kept ~4–10 µs/gate of `_measured_bits` in the window (24.4 ms vs 3.5 ms statevector at 2,200 gates); fixed. Medians of 7 runs, 4q × 2,200 gates, simulation ms old → new: qulacs 28.1 → 2.2, quest 28.1 → 2.3, qsim 33.4 → 1.3, qiskit 36.6 → 1.9, cuquantum 49.6 → 12.5; totals within 3%. QFT-16 qsim simulation 15.1 → 4.0 ms. Before the split, 10–13 µs/gate of conversion sat inside the window.

### Warm-up caches

*Rule.* A cache the warm-up fills that would skip real work in the timed run is cleared in `pre_execute_fn` (quimb/cotengra optimisers).

*Evidence (2026-08-18).* The quimb timed run was 0.03–0.09 s cached vs 1.1–1.3 s cold at 14 qubits × 14 layers.

### Timing repeats

*Rule.* `timing_repeats` (1–10): after one warm-up, each repeat re-runs compile and execute; reported times are medians, with per-repeat samples, mean and stdev; memory and outputs come from the first repeat; the hard timeout covers all repeats.

*Evidence.* Single-sample timings cannot support performance claims: qrisp varied 8× across runs.

### CPU

*Rule.* `cpu_time_sec` = getrusage over the whole isolated process (start, imports, warm-up, timed run); `simulation_cpu_time_sec` = `process_time()` over `t2..t3`.

*Evidence.* A child that did no simulation reported 3.5 s CPU.

### Threads

*Rule.* `OMP/MKL/OPENBLAS/NUMEXPR/NUMBA_NUM_THREADS=1` for every runner in Compose and in Kubernetes Jobs; recorded as `thread_env`.

*Evidence.* Unpinned under `cpus: 0.5`, quest took 46–53 s on an 8-qubit circuit (2 ms pinned) and quimb was OOM-killed.

### CPU quota

*Rule.* Each runner container or Job has a 1.0-CPU quota (Compose `cpus: "1.0"`; Kubernetes requests 200m / limits 1000m, 5:1). Every window records `compilation_throttled_sec` / `simulation_throttled_sec` (cgroup `cpu.stat` throttled_usec read just outside the window), `simulation_involuntary_switches_samples`, `simulation_cpus`, and per process `cpu_environment` (CPU model, quota, affinity, `cpu_max_mhz` per CPU used). The UI tags a throttled run. The probe is `WindowProbe` in [`shared/qrosetta_commons/cpu.py`](shared/qrosetta_commons/cpu.py).

*Evidence (2026-10-01).* Qulacs in its own image, 10 timed runs × 3. Under 0.5 CPU, QFT-16 median 0.168 s, CV 19%, about 60% of the window throttled; unthrottled 0.060 s, CV 0.6%. QFT-12 under 0.5 CPU: CV 104% (6.8 ms vs 59 ms, the 50 ms quota stall). At 1.0 CPU single-threaded runs are never throttled (0 s, CV 0.5–2%); qrisp QFT-16 0.082 → 0.027 s.

### Hybrid cores

*Rule.* Runners are not pinned to a core type; the core is recorded (`simulation_cpus`, `cpu_environment.cpu_max_mhz`) and the user manual tells users to check it. Rootless podman has no cpuset controller, so pinning is not available locally.

*Evidence.* On an i9-13950HX, qulacs on an E-core (4.0 GHz max) vs a P-core (5.3–5.5 GHz): QFT-16 0.088 vs 0.060 s, QFT-12 12.2 vs 6.8 ms.

### Work outside the process

*Rule.* quimb's cotengra path search runs in-process: the runner maps `parse_parallel_arg('auto')` to no pool in every loaded cotengra module (cotengra 0.8.2 pinned); the search is otherwise quimb's default `auto-hq`. Every result records `simulation_cgroup_cpu_time_sec` (container CPU over the window); the UI tags a run "outside process" when it exceeds `simulation_cpu_time_sec` by ≥ 5 ms and ≥ 10%.

*Evidence (2026-10-01).* quimb QFT-16 with cotengra's default `parallel="auto"`: container CPU 4.43 s vs process CPU 0.48 s over a 4.46 s window, i.e. ~90% of the work in a forked worker whose CPU and memory were unmeasured. `AutoHQOptimizer(parallel=False)` alone was not enough: nested `random_greedy_optimize` calls inside `build_divide` create their own pool. With the module-level mapping, 6/6 runs had wall = process CPU = container CPU (e.g. 1.661/1.658/1.658 s) and no forked worker; the statevector equalled the pooled one to 1.5e-17.

## Memory

Units are MiB (1024²) throughout, although field names say `_mb`.

### Memory

*Rule.* `memory_usage_mb` = kernel VmHWM − baseline RSS over the simulation window (VmHWM reset via `/proc/self/clear_refs` on entry); `process_peak_rss_mb` = the simulating process's own VmHWM over its whole life. Fallback sampling is labelled in `memory_method`.

*Evidence (2026-08-18).* 10 ms sampling reported 0 MiB for a 32 MiB, 5 ms allocation; getrusage in a spawned child inherited the parent worker's 425 MiB.

### Mem Delta and allocator reuse

*Rule.* `memory_usage_mb` is left as the VmHWM delta; it can read near 0 when the warm-up's freed memory is reused (documented in the tooltip).

*Evidence.* A fixed `MALLOC_MMAP_THRESHOLD_=131072` made every allocation visible but slowed pennylane-default 3.3× (QFT-like 16q: 0.20 → 0.66 s), so it was rejected.

### Runner memory and nested gate calls

*Rule.* Every runner container has 1G locally (Kubernetes limit 1Gi). The API rejects circuits whose expansion makes more than 4,096 applications of user-defined gates from inside gate definitions (`MAX_NESTED_GATE_CALLS`, `limits.max_nested_gate_calls`; top-level calls not counted), as well as more than 200,000 gate applications ([`rosetta-api/services/validator.py`](rosetta-api/services/validator.py)). Bundled circuits are exempt.

*Evidence (2026-10-02).* 2-qubit binary-nested definitions, full runs (warm-up + timed) through the API, preprocessing off, `process_peak_rss_mb`: depth 11 (4,094 nested calls) PennyLane 704–709, cuquantum 585, qiskit 559; depth 12 (8,190) PennyLane 1,088–1,089, qiskit 889; depth 13 OOM-killed qiskit and both PennyLane runners at 512M. 8,192 top-level calls of one definition: PennyLane 341, cuquantum 640, qiskit 437. pytket keeps a box per application of a nested definition.

### API memory and job retention

*Rule.* The API container has 2G (Kubernetes limit 2Gi). Untruncated reports are pickled to `QROSETTA_JOB_SPILL_DIR` ([`rosetta-api/services/job_store.py`](rosetta-api/services/job_store.py)) instead of held in the worker. Batch tasks are spilled one by one as they finish, and `GET /jobs/{id}/report` streams JSON task by task. Experiments write result files per cell and keep only the fields the summary tables read; the bundle is `<spill>/<job>/bundle.zip`. Pickling, circuit preparation (the pytket round-trip), JSON encoding and ZIP building run in threads.

*Evidence.* One 18-qubit 14-backend statevector job peaks at 424 MiB in the API process; the 512 MiB worker was OOM-killed 3 times in 32 minutes under shared load and every in-memory job returned 404. 2026-10-07: 10 synthetic 18-qubit tasks (14 × 5.6 MB statevectors) added 751 MiB peak RSS before the change and 79 MiB after; 25 tasks add 80 MiB, and a 1.87 GB report download 156 MiB. Preparing a 9,900-call gate circuit blocked every request for 3.2 s locally (≈7 s at 0.5 CPU). 2026-10-21: `POST /jobs/{id}/export` streams from a spilled job: peak RSS growth for 6 tasks × 14 backends × 2^18 amplitudes with statevectors 1,575 → 106 MiB (134 → 7 s), without statevectors 461 → 89 MiB; crates content-identical on 290 cases.

## Scheduling, isolation and job handling

### One run per runner at a time

*Rule.* Each runner process executes one run at a time (`RUNNER_MAX_CONCURRENT`, default 1); `queue_wait_sec` is recorded and the hard timeout starts after the wait.

*Evidence.* Concurrent runs shared the 0.5-CPU quota (identical runs varied 2×) and two concurrent children exceeded 512 MiB (cirq SIGKILL).

### Cancelled runs and the execution slot

*Rule.* When the task awaiting `run_isolated` is cancelled, the parent SIGKILLs the child and its process group within one 0.2 s poll, waits up to `CANCEL_KILL_WAIT_SEC` (10 s) for it to be reaped, then re-raises; `ExecutionSlots` releases the slot only after that, and the cancelled run's result is discarded. Runs that are not cancelled take the unchanged path. Applies to runners and compile-only services; the one-job CLI path (Kubernetes/Slurm) has no slot. A worker killed outright (gunicorn SIGKILL after graceful_timeout, OOM kill) takes its child with it: the child's first act, before its process group, affinity, SDK import and warm-up, is `prctl(PR_SET_PDEATHSIG, SIGKILL)` plus a `getppid` check against the spawning worker's pid. The signal follows the forking thread, the executor thread that stays blocked in `_run_isolated_blocking` until the child returns or is killed. Subprocesses of the child are not killed in that case (staq and Synthetiq binaries; Quartz sets its own PDEATHSIG).

*Evidence (2026-10-27).* Before the change, cancelling a 30 s run released the slot at once and the next run started with the cancelled child alive (`rosetta-api/tests/unit/test_slot_cancellation.py`, 4 of 5 failing on the old code); after, the child is reaped 0.19–0.24 s after the cancel (Python 3.10 runner image and 3.12), and the next run never sees it. Recorded times old → new over 3 alternated rounds of 15 runs: compilation 1.098 → 1.096 ms, simulation 15.74 → 15.98 ms (median of round medians), identical result keys and statevector. With fastapi 0.115/uvicorn 0.30 a dropped client connection does not cancel the handler; a graceful-shutdown timeout does. When the worker that spawned a run was killed mid-run, the child was still alive 3 s later on the old code (6 of 6, Python 3.12 and the 3.10 qulacs image) and gone within 5 ms with the parent-death signal ([`rosetta-api/tests/unit/test_parent_death.py`](rosetta-api/tests/unit/test_parent_death.py)). Old → new over 3 alternated rounds of 15 runs with timing_repeats 3: compilation 1.052 → 1.043 ms, simulation 15.39 → 15.28 ms, whole-process CPU 160.5 → 161.1 ms (the old code's own range 160.2–161.1 ms), process peak RSS 45.39 → 45.40 MiB; the added call costs 27 µs of CPU and no memory.

### Exclusive runs and overlap

*Rule.* `exclusive` (request field / config checkbox): every backend runs in its own phase, admitted only when no other dispatch runs on the server (the gate in [`rosetta-api/services/run_registry.py`](rosetta-api/services/run_registry.py)); results record `exclusive`, `exclusive_wait_sec`. Every local result records `overlapping_runs` (own job) and `server_overlapping_runs` (other jobs). Default dispatch stays concurrent.

*Evidence (2026-10-01).* A Sequential QFT-16 next to two other jobs: qiskit 1.49× slower with `concurrent_runs=1`, 0 throttling, same `cpu_max_mhz`; busy hyperthread siblings gave 1.5–2× with all checks passing. Concurrent vs Sequential QFT-20: 2.3–3.3×, order flipped.

### concurrent_runs

*Rule.* `concurrent_runs` counts the runs of every dispatch wave in flight beside the run's own wave (`dispatch_wave`); measured sampled and native groups count each other.

*Evidence (2026-10-07).* Each group counted only its own wave.

### Overlap and phases

*Rule.* `overlapping_runs` uses the runner's `process_started_at`/`process_finished_at`. Measured runner groups share one phase plan (`effective_runner_phases`, recorded in crates).

*Evidence.* "Sequential" ran the two groups in parallel; response transfer counted as overlap.

### Host-load notice expiry

*Rule.* A host-load notice (`services/host_load.py`) expires `NOTICE_TTL_SEC` (30 s) after its last heartbeat measured on the monotonic clock; its start, end and expiry time, like every run interval in the registry, are wall-clock times. A step of the wall clock (NTP, a resumed laptop or VM) does not end an open notice.

*Evidence (2026-10-28, V7-07).* Expiry compared wall-clock times, so a forward step of the wall clock ended every open notice at once: with the clock moved 1 h forward and no time passed, `expire_due` ended a `build` notice that had just begun. The CLI's next heartbeat then got 404 and stopped, and runs during the rest of the build were not counted in `server_overlapping_host_load` (`test_v7_clock_skew.py::test_v7_07_a_wall_clock_step_does_not_end_a_host_load_notice`).

### Kubernetes job slots

*Rule.* In Kubernetes mode (CSC Rahti) at most `K8S_MAX_CONCURRENT_JOBS` (`QROSETTA_K8S_MAX_CONCURRENT_JOBS`, 3 on Rahti) runner/compiler Jobs exist at a time across the API process (`dispatcher_k8s.JOB_SLOTS` in [`rosetta-api/services/dispatcher_k8s.py`](rosetta-api/services/dispatcher_k8s.py)); a Job is created only when a slot is free, so its deadline starts then. The wait is `queue_wait_sec`, capped at `RUNNER_QUEUE_MAX_WAIT_SEC`; reports record `k8s_job_slots`. A run that never gets a slot, or whose pod the quota refuses until its timeout (read from the Job's FailedCreate events), is `timeout` + `never_started`, not `offline`. The setting is read only from `QROSETTA_K8S_MAX_CONCURRENT_JOBS`; a bare `K8S_MAX_CONCURRENT_JOBS` is ignored.

*Evidence (2026-10-07).* The project quota caps `limits.cpu` at 4; API 500m + runner Jobs at 1000m leave room for 3 pods. With all 14 Jobs created at once the rest were refused (`exceeded quota ... limits.cpu`), retried with backoff and hit their deadline before starting; quimb and qsim were reported offline in most runs.

### Kubernetes payload and pod states

*Rule.* Payloads over 96 KiB (`PAYLOAD_ENV_MAX_BYTES`) go through the S3 pending key instead of the `QROSETTA_PAYLOAD` environment variable. Pod states are reported by cause. Compile Jobs get 2Gi. Image digests are recorded (`QROSETTA_IMAGE_DIGESTS`).

*Evidence.* Found in a review of the Kubernetes dispatch path on 2026-10-07; no measurement was recorded.

### Unfinished jobs

*Rule.* Every worker records its task (`start_job`). A worker exception fails the job with the exception type only. Cleanup evicts an unfinished job once its worker task has ended and it is older than the TTL, never one whose worker is still running. A compile-only run in which no compile produced a circuit is `failed`, like a run where all runners failed.

*Evidence (2026-10-07).* An exception in `worker_batch_suite` left the job `processing` forever and the browser polled indefinitely. A compile-only playlist whose every compile errored completed as done.

### Runner and compiler responses

*Rule.* The API checks every runner and compiler response, over HTTP and from S3, before it uses it (`services/result_contract.py`): a JSON object of at most 256 MiB nested at most 32 levels, with no NaN or infinity, an `error` that is text, numeric metrics that are numbers or null, and, unless it is an error, the endpoint's own field (`statevector` text, `counts` mapping bit strings to non-negative integers, `transpiled_qasm` text). A response that fails is that backend's `error` ("INVALID RESPONSE", naming the rule it broke, never its content); the other backends of the job finish. HTTP bodies are read as a stream and reading stops at the cap; a malformed S3 result is not fetched again.

*Evidence (2026-10-28).* A runner that returned valid JSON that was not an object (`null`, a list) raised TypeError in the dispatcher, which ended the `gather` for every backend of the job and failed the whole job with the exception text; a malformed S3 result was fetched six times and then reported as "not found" (`test_v1_01_runner_response_contract.py`).

### Playlist length

*Rule.* A playlist holds at most 400 circuits (`MAX_BATCH_TASKS`, published as `limits.max_batch_tasks`). `bypass_limits` lifts it.

*Evidence (2026-10-27).* The two bundled suites together are 324 circuits: MQT Bench "Add all shown" gives 269, or 204 at the 18-qubit statevector cap, and QASMBench gives 55. A cap of 200 would have refused MQT Bench "Add all shown" on its own.

### Job storage budget

*Rule.* Stored job results may use at most `QROSETTA_JOB_SPILL_MAX_MIB` (10240) and must leave `QROSETTA_JOB_SPILL_MIN_FREE_MIB` (1024) free on the disk; both are published in `limits`. Over budget, a new run gets 503 with Retry-After. A playlist or experiment checks before writing each circuit or cell and fails with a message naming the limit, and its files are removed. A single-circuit report is always written, so jobs already running can overshoot the budget.

*Evidence.* An 18-qubit, 14-backend task stores about 78 MB, and the storage directory had no bound.

### Bundled circuits over the preparation limits

*Rule.* With preprocessing on, a bundled circuit whose recorded preparation peak ([`rosetta-api/benchmarks/preparation_peaks.json`](rosetta-api/benchmarks/preparation_peaks.json), measured by [`scripts/harness_bench/prep_peaks.py`](scripts/harness_bench/prep_peaks.py)) reaches the preparation memory limit is refused with 400 at submission, and the page names it before sending. `limits` publishes `prep_max_mib` and `prep_timeout_sec`. A circuit not in the table that exceeds either limit still fails as a job, with a message naming the limit and its value.

*Evidence (2026-10-27).* pytket 1.33.0, Python 3.12, one fresh process per circuit, two runs within 4 MiB of each other. grover-noancilla at 13, 14 and 15 qubits peaked at 598, 952 and 1,493 MiB, and above 2,048 MiB from 16 qubits. grover-v-chain at 13–16 qubits peaked at 517, 779, 1,192 and 1,861 MiB, and above 2,048 MiB from 17 qubits. Every other bundled circuit stayed at or below 392 MiB.

### API analysis threads

*Rule.* The API image sets `OMP/OPENBLAS/MKL_NUM_THREADS=1`.

*Evidence.* A measured analysis took 19.8 s with 2 BLAS threads and 1.9 s with 1.

## Simulator configuration

### Precision

*Rule.* Each runner reports `precision`. qsim, qrisp, torchquantum and the cirq measured path compute in complex64; the rest in complex128.

*Evidence.* qsim pairs sit at 1−F ≈ 1.1e-12; double-precision pairs at ≈1e-15.

### Aer method

*Rule.* Both Aer runners set `method="statevector"` and report `device`, `simulation_method`, `simulator_backend`.

*Evidence.* Automatic method selection ran the stabilizer method on Clifford circuits (GHZ-20: 0.016 MiB vs 16 MiB).

### Gate fusion

*Rule.* Not disabled; disclosed (Aer `gate_fusion` from result metadata; qsim default max_fused_gate_size 2) in `preprocessing_applied`.

*Evidence.* Aer fuses above 14 qubits at opt level 0 (qiskit grew 1.18× from 14 → 15 qubits vs qulacs 1.72×).

### No duplicate engines / cuQuantum

*Rule.* cuQuantum = qiskit-aer-gpu 0.15.1 with `cuStateVec_enable=True` on an NVIDIA GPU (Qiskit 1.4.4). Without a usable GPU it is unavailable (`GET /capabilities`, `/runners` `available:false`) and never falls back to CPU Aer. GPU passthrough is local-only (a local Compose override with `devices: [nvidia.com/gpu=all]`); Kubernetes uses `requires_gpu` + `QROSETTA_GPU_AVAILABLE`. Memory fields are host RSS; the GPU is not under the CPU quota.

*Evidence (decided 2026-09-30).* The CPU fallback was plain Aer, a second copy of the qiskit engine counted as an independent backend; there is no CPU build of cuQuantum.

## Sampling, seeds and statistics

### Seeds

*Rule.* Each runner key gets `derive_runner_seed(master, key)` ([`shared/qrosetta_commons/seeds.py`](shared/qrosetta_commons/seeds.py)), recorded as `runner_seed`; `results["seed"]` is the master. A measured run's master seed is never null: the API uses the caller's seed or generates one.

*Evidence.* A shared seed made sampled backends draw identical shots; detection at TV = 0.02 was 0.3% vs 5.7% with independent seeds.

### Counts keys

*Rule.* Keys are the circuit's classical bits as written by its own `measure` statements (never the full qubit register); flat clbit index = creg declaration order; `lsb` = clbit 0 rightmost, `msb` = leftmost; no spaces ([`shared/qrosetta_commons/counts.py`](shared/qrosetta_commons/counts.py)). Runners map the backend's bit identity back to declaration order.

*Evidence.* Six backends returned all qubits, the pytket and Qiskit parsers ordered cregs alphabetically, and Aer kept register spaces, so identical distributions scored JS = ln 2.

### Measure-all register

*Rule.* `qrosetta_commons.counts.measure_all_register` (`meas`, `meas0`, …) is placed after the declared cregs, identical for native and sampled backends.

*Evidence.* `creg c[2]` with no measure: Qiskit `0100` vs PennyLane `10`.

### Mid-circuit measurement

*Rule.* Backends that simulate it natively run it (Aer, cirq, qsim, qrisp); every other adapter returns an error. Sampling a final statevector for such a circuit is never allowed.

*Evidence.* Before: qsim/torchquantum/quimb showed no collapse, and myqlm gave 0.76/0.24 for a 50/50 bit.

### Measured verdicts

*Rule.* Each measured pair carries `measured_assessment` (`consistent_within_shot_noise`, `inconclusive_low_shots`, `ambiguous`, `distinguishable`, `not_comparable`); only `distinguishable` is a disagreement in the UI, and in measured mode the Summary groups pairs by this field alone.

*Evidence.* Shot noise at 10–20 shots was displayed as unexplained disagreement.

### Multiple testing and power

*Rule.* Benjamini–Yekutieli across the m comparable pairs (valid under the dependence of pairs sharing a backend's sample); a pair is distinguishable only if both χ² and G pass. Power and `recommended_shots_per_backend` at α/(m·c_m), df = tested bins − 1, w = TV. Outcomes with expected count < 5 are pooled; power is computed on the tested table at δ_tested = δ − min(P_pool, Q_pool) (the most TV pooling can hide; power = α′ when ≤ 0); not significant with power < 0.8 → `inconclusive_low_shots`. Default n_shots 8200. Noncentrality λ = 4·n_i·n_j/(n_i+n_j)·w² (`effective_total_shots` in [`rosetta-api/services/analysis/divergence/statistics.py`](rosetta-api/services/analysis/divergence/statistics.py)), equal to N·w² for equal shots; the marginal tests use the same.

*Evidence.* BH with raw-α power: 0.62 achieved vs 0.80 reported at 1570 shots; the per-run FDR was ~19.5% from clustered flags. BY Monte Carlo (14 backends): P(any false flag) 0–1.7%, per-pair power 0.91–0.93 at the recommended shots (4444/5435/6619/8199 for 2/4/8/16 outcomes). 2026-10-07: 8200 vs 50 shots was labelled consistent at a reported power of 0.995; the true power was 0.109. Monte Carlo rejection rates were 0.111/0.494/0.386 for 8200v50/8200v400/300v5000, against model 0.109/0.497/0.391.

### Power with unequal shots

*Rule.* λ = 4·nᵢ·nⱼ/(nᵢ+nⱼ)·w² (`effective_total_shots`).

*Evidence (2026-10-07).* 8200 vs 50 shots was called consistent at power 0.995; the true power was 0.109.

### Power after pooling

*Rule.* Power uses `power.delta_tv_tested` (see [Multiple testing and power](#multiple-testing-and-power)); with pooling, `recommended_shots_per_backend` is found by pooling the observed proportions at each candidate count (a lower bound when the support is larger than observed).

*Evidence (2026-10-01).* A 21-qubit circuit where PennyLane gives P(q20=1) = 0 and the rest 0.40 (TV 0.40) was `consistent_within_shot_noise` with power 0.994, because ~all outcomes were pooled into one bin. The default 8192 was 7 shots short of the 8199 needed for 16 outcomes with 14 backends.

### Rare outcomes

*Rule.* Rare outcomes are pooled only with each other. An undersized bin stays a column (expected ≥ 1, at least two common outcomes) or is left out (`untested_outcomes`, δ − max(P, Q)).

*Evidence.* Merging into a common bin made 6.8% of correct pairs inconclusive; now 0.

### Exact conditional test

*Rule.* 2×2 tables that fail the expected-count rule get exact hypergeometric p-values for χ² and G (`test_method` exact_conditional; equals Fisher only for equal rows). `degenerate` when both backends return the same single outcome; `not_tested` when one column is left after pooling. ANALYSIS_VERSION divergence-2026.10.08.3.

*Evidence.* Near-deterministic circuits went from 80–96% of correct pairs inconclusive to 0; false flags unchanged; known defects 100% detected.

### G-test

*Rule.* Williams' correction (`g_test.williams_q`).

*Evidence.* Uncorrected G rejected a true null in 95% of 65,536-bin tables at 1e6 shots; 15% corrected.

### Shot advice

*Rule.* No recommendation, and `resolvable_by_more_shots` null, above a Good–Turing unseen mass (share of shots in singletons) of 0.5 (`support_characterised`). Likewise when the lower bound is above δ/2, or when it comes from pooling with singletons. Recommendation = minimum × 1.1, rounded to 2 significant figures (`recommendation_margin`). Holm p-values are recorded; `significant_fwer` on distinguishable pairs.

*Evidence.* A 10 × n_shots artifact came from the pooling threshold; 67 of 728 pairs stayed inconclusive at the minimum, 0 of 728 at +10%. Earlier, at 22 qubits: recommended 167599, and a rerun gave the same inconclusive verdict with no recommendation. With one wrong backend among 14, correct-vs-correct pairs were flagged in 8–9% of runs under BY (1.5–2% with all correct).

### Single-bit marginal tests

*Rule.* A secondary, pre-specified analysis on every comparable measured pair with ≥ 2-bit keys: per classical bit a 2×2 table (counts of 0/1), chi-square + Williams G, Holm over all tested bits of all pairs at α (FWER), both required; expected count < 5 or constant in both → bit not tested. Output `marginal_assessment` + `metrics.marginal_test`; it never changes `measured_assessment` or its power calibration and never yields agreement. It is counted as a disagreement by the verdict rule (the pair's recorded `pair_verdict`, shown by the badges, the Agreement tab chip and the Summary block), in crates (`by_marginal_assessment`) and in experiment prevalence rows (`count_basis=marginal_assessment`). [`rosetta-api/services/analysis/divergence/marginals.py`](rosetta-api/services/analysis/divergence/marginals.py); ANALYSIS_VERSION divergence-2026.10.08.3.

*Evidence (added 2026-10-02).* BY was tried first. On a 22-qubit job with Qrisp wrong on 19 bits, ~228 true flags loosened BY and 5 correct-correct pairs were flagged; Holm on the same report kept all 13 Qrisp pairs and dropped the 5. Holm Monte Carlo (14 backends × 16 bits × 8200 shots, 40 runs): global null 1/40 runs with any flag; one backend +0.05 on 4 bits: 1/40 runs with a false flag on a correct pair, per-pair power 1.000.

### 1-bit keys

*Rule.* Measured pairs with 1-bit keys are compared directly (`basis_source` single_bit).

*Evidence.* They were previously labelled "after bit reversal".

### False-flag figures

*Rule.* 0.8–1.0% of runs with every backend correct. With one grossly wrong backend, 6.0–6.7% under BY and 2.7–3.3% that also pass Holm.

*Evidence.* 2000-run Monte Carlo per scenario.

## Agreement analysis

The default thresholds (fidelity 1e-5, phase 1e-6 rad, norm 1e-4, JS 0.01 nats, Hellinger 0.1) are the `AgreementThresholds` defaults in [`rosetta-api/schemas/benchmark.py`](rosetta-api/schemas/benchmark.py) and can be set per request.

### Fidelity tolerance

*Rule.* Raw fidelity is stored, never snapped; a pair agrees when F ≥ 1 − `fidelity_tolerance`; default 1e-5.

*Evidence.* `np.isclose`'s default `rtol=1e-5` had snapped every F ≥ 1−1e-5 to 1.0 while 1e-12 was recorded. 1e-5 is the tolerance that was effectively applied; experiments 1 and 2 recomputed: 0 labels changed.

### Phase tolerance

*Rule.* Default 1e-6 rad.

*Evidence.* complex64 backends showed φ ≈ 1e-8 rad on real-amplitude circuits, labelled as a global phase under 1e-12.

### Norm tolerance

*Rule.* Default 1e-4: flags genuinely unnormalised output, not complex64 rounding (~2e-6).

*Evidence.* qrisp at 5 qubits had norm 0.99999797.

### Bit order

*Rule.* Labels are set from a one-hot probe on a register with idle qubits, and statevectors are always `2**declared_qubits` long. cirq, qsim-cirq, braket, projectq are msb on both endpoints.

*Evidence.* cirq's earlier "lsb" came from tk_to_cirq dropping idle qubits.

### Label-aligned basis (both modes)

*Rule.* lsb × msb pairs are classified and tested after bit reversal, same-label pairs directly, 1-qubit pairs directly; the basis is chosen from the declared labels, never from the data. A match only in the other basis (`unaligned_basis_match`) or only after an undeclared permutation (`agree_after_qubit_permutation`) is a disagreement. Measured: a pair within the JS/Hellinger thresholds only in the other basis is `distance_exceeds_threshold` with `metrics.unaligned_basis_match`. ANALYSIS_VERSION divergence-2026.10.07.1.

*Evidence.* Measured: direct-first testing flagged 42 correct pairs (p ≈ 1e-188). Statevector: PennyLane's cu3 control/target swap mimicked a bit reversal and was labelled agree_directly against lsb backends. On 2026-10-07, msb {'01'} vs msb {'10'} had been labelled `agree_after_bit_reversal` while distinguishable.

### Permutation search implementation

*Rule.* The counts and statevector permutation searches score all permutations of a pair in one array pass from a cached index table (`_key_permutation_table`, `_qubit_permutation_gather`), with the loop's floating-point operations: Hellinger norms on freshly allocated rows (OpenBLAS `dot` can change the last bit with row alignment), JS squared as a numpy scalar. Any change to the analysis passes [`scripts/harness_bench/equivalence.py`](scripts/harness_bench/equivalence.py) with 0 differences against the previous release, else it bumps ANALYSIS_VERSION. The exhaustive search covers up to 7 qubits (`MAX_EXHAUSTIVE_QUBIT_PERMUTATION_QUBITS`); above it the result is `too_many_qubits`.

*Evidence (2026-10-21, commit b22e78b).* 200 counts + 100 statevector corpus cases bit-identical to the previous release in the API image; measured 7-bit report 49.4 → 2.9 s, statevector 7-qubit 1.87 → 0.47 s ([`scripts/harness_bench/LEDGER.md`](scripts/harness_bench/LEDGER.md)). A first version with array squaring and row-view dots differed in the last bit in 10 of 60 cases.

### Failed-run values

*Rule.* Unmeasured metrics are null in results and "—" in every table; matrices use null for pairs not compared.

*Evidence.* Failed runs printed as 0.000000 s; matrices used a -1 sentinel.

### One implementation of the verdict rule

*Rule.* Pair verdicts, per-backend counts and the Summary headline model are computed only in [`rosetta-api/services/analysis/divergence/verdicts.py`](rosetta-api/services/analysis/divergence/verdicts.py) and [`headline.py`](rosetta-api/services/analysis/divergence/headline.py). Every new report records each pair's `pair_verdict` and the report's `backend_verdicts`; the page and the figures read them. For an older or uploaded report the server computes them with the same function (`GET /jobs/{id}/summary`, `GET /history/runs/{id}/summary`, `POST /summary`). A change to the rule bumps the analysis version (divergence-2026.10.27.1).

*Evidence (2026-10-27).* The figure builder had a second, simpler copy of the rule that read only the top-level `measured_assessment`, without the page's fallbacks for older reports. The page's previous JavaScript, kept frozen as a test reference, and the Python rule gave the same verdict for all 21,837 pairs of 1,085 reports (13 recorded, 72 built by the analysis, 1,000 synthetic), with the same counts, runner statuses and headline models in all five headline kinds ([`rosetta-api/tests/unit/test_verdict_equivalence.py`](rosetta-api/tests/unit/test_verdict_equivalence.py)). On 200 reports (4,804 pairs) the analysis output differed only in the analysis version and the added fields.

### Run planning

*Rule.* One planner on the server ([`rosetta-api/services/plan.py`](rosetta-api/services/plan.py), `POST /plan`) turns a workspace into the exact requests a run sends and the problems that would make the server refuse them, as codes. The page submits the returned requests unchanged, and the command-line client uses the same endpoint, so both send identical requests for identical choices.

*Evidence (2026-10-27).* On 748 page workspaces covering every problem code, the server planner produced the same requests, refusal texts and request sizes as the page's former JavaScript planner, which was then removed.

### Fresh readiness probes

*Rule.* `GET /runners?fresh=true` (and `/compilers`) probes the services at most 6 times a minute per client, only for a signed-in account or the local lifecycle token, and reuses a result younger than 5 s. It never probes a service with a run in flight, and while an exclusive run holds or waits for the gate it returns the cached answers instead of probing.

*Evidence (2026-10-27).* Unbounded probes would add unrecorded load to the runners during other jobs' timed windows.

### Self-test known answers

*Rule.* The self-test (`GET /selftest`, evaluated by `GET /jobs/{id}/selftest-result`) runs fixed circuits with fixed settings and compares every backend with an expected answer computed by an independent numpy reference ([`rosetta-api/services/selftest/reference.py`](rosetta-api/services/selftest/reference.py)), pinned in [`rosetta-api/circuits/selftest/expected.json`](rosetta-api/circuits/selftest/expected.json). It never compares backends with each other, so it fails when every backend agrees on the same wrong answer. Statevectors must reach fidelity 1 − 1e-5 with the expected state in the backend's declared bit order; five classical-bit circuits must give their single expected key; GHZ-3 must stay on its support and within six standard deviations of balance. A virtual machine or a self-built image is a warning; emulation, an unknown image or a modified checkout is a failure.

*Evidence (2026-10-27).* The statevector circuit's expected state has fidelity at most 0.834 with any qubit reordering, 0.559 with bit reversal, at most 0.874 with a cx control and target swapped, and 0.795 with the rz sign flipped; single-precision rounding changes it by less than 1e-7. Six wrong states returned identically by every backend, which the agreement analysis labels as agreeing, and eight wrong counts-key cases all fail ([`rosetta-api/tests/unit/test_selftest_evaluate.py`](rosetta-api/tests/unit/test_selftest_evaluate.py)).

### Emulated images

*Rule.* Each runner and compiler result says whether its image ran under emulation: the machine the image's Python is built for, compared with the host's operating system and machine, which `qrosetta start` passes to the containers. The runner reads the host's values once at startup and removes them from its own environment before any simulation starts, so the simulating process sees exactly the environment it saw before. A stack started without `qrosetta start` records the host as unknown and the comparison as not made. An emulated result fails the self-test and carries a timing caveat.

*Evidence (2026-10-27).* Before, nothing recorded emulation, so the self-test skipped the check for every backend. Through the real launch path, the simulating process's environment is the one it had without the new values ([`rosetta-api/tests/unit/test_image_identity.py`](rosetta-api/tests/unit/test_image_identity.py)), and the recorded timings, memory, result fields and statevector of 45 runs per version did not change.

### Image identity and specimens

*Rule.* Each runner and compiler image records, at build time, whether it is a published release or built locally and from which commit, in a file inside the image (never an environment variable). The runner reads it once at startup and attaches it to each result after the simulation has finished. Every report and crate states whether all backends ran published images, all ran locally built ones, a mix, or unknown. A runner's dependency lock file is included in a crate only when its hash matches the hash the image itself reported.

*Evidence (2026-10-27).* Before, local results recorded the runner image as "not recorded", and crates attached lock files from the server's copy without checking them. A test captures the simulating process's environment through the real launch path and finds it identical to the runner server's, with the identity never read inside it ([`rosetta-api/tests/unit/test_image_identity.py`](rosetta-api/tests/unit/test_image_identity.py)).

### Integration tests in CI

*Rule.* The `integration` job of `ci.yml` builds nginx, the API and the qiskit, qulacs and cirq runner images from the commit with the repository's compose file and its resource limits, starts them with `docker compose`, and runs [`test_e2e_nginx.py`](tests/integration/test_e2e_nginx.py), [`test_e2e_cli.py`](tests/integration/test_e2e_cli.py) and [`test_runner_contract_asymmetric.py`](tests/integration/test_runner_contract_asymmetric.py) through nginx with `QROSETTA_E2E_REQUIRE_CURRENT=1`. It runs on every push and pull request, needs no secret, and sets no `bypass_limits`. The end-to-end tests check fixed answers as well as agreement: every QFT-4 amplitude has magnitude 1/4, every counts histogram sums to the report's `n_shots` over 4-bit keys, and the Summary reports every run returned and every pair agreeing. Without `QROSETTA_E2E_REQUIRE_CURRENT`, the Origin, Content-Type, security-header, readiness and password-on-deletion checks run only on a server whose `GET /config` lists the `readiness` feature, and the sign-out check (`POST /auth/logout`, then the old token gets 401 on `/auth/me` and `/history/runs`) only on one that lists `logout`. [`test_integration_ci_job.py`](rosetta-api/tests/unit/test_integration_ci_job.py) keeps the job's services, runner host names, test files and pinned test dependencies in step with the compose file and the tests.

*Evidence (2026-10-28).* Before, CI built no image and started no service: a broken nginx route, a runner returning the wrong state, or a change that stopped the CLI reading a server passed every job. Images built from `overnight/integration` (ab74a04) under their own names and started with the compose file on a second port: 13 passed in 54 s, all checks required. Against the running stack of 2026-10-27 (1fe3b11): the end-to-end file 3 passed and 2 skipped without the variable; with it, the readiness, browser-check and deletion tests fail, so the variable detects a server without those checks. The rebuild of the five images with a warm layer cache took 2 min 8 s on the development host.

### Timing caveats

*Rule.* One server function ([`rosetta-api/services/timing_caveats.py`](rosetta-api/services/timing_caveats.py)) decides every timing caveat shown with a result: throttling, work outside the measured process, runs sharing the machine, a single timed repetition, no CPU quota, mixed core speeds, a virtualised or emulated host. The page shows what it returns, and crates carry it.

*Evidence (2026-10-27).* The rules previously lived only in the page's JavaScript. Moving them gave 0 differences against that code on 351 saved and 20,000 synthetic reports ([`scripts/timing_caveats_equivalence/`](scripts/timing_caveats_equivalence/)).

### Summary headline

*Rule.* The headline is built from differing pairs only; inconclusive pairs are neither agreement nor difference. Kinds `named` / `camps` / `pairs` / `spread`. Sizes are taken against the backends not named (median and range of TV; lowest fidelity). BY-only pairs are counted apart. A chance caveat is shown for minority flags. Red only for named backends. [`rosetta-api/tests/unit/test_headline_cases.py`](rosetta-api/tests/unit/test_headline_cases.py), [`rosetta-api/tests/unit/test_headline_magnitude.py`](rosetta-api/tests/unit/test_headline_magnitude.py).

*Evidence.* Correct backends were named, a headline read as a lone ".", one said "other 7" when 13 agreed, and sizes were taken from pairs of two wrong backends.

## Circuit handling and preprocessing

With `apply_preprocessing=True` (the default) the API and the runners apply transforms some SDKs need to accept a circuit; every transform is listed in `preprocessing_applied`, API-side ones prefixed `API:`. The user manual's Preprocessing section ([`rosetta-api/static/docs.html`](rosetta-api/static/docs.html)) describes the flag.

### Statevector mode + measurements

*Rule.* The API strips terminal measurements once (recorded as `API:`) and rejects mid-circuit measurement, `reset` and `if` with 400.

*Evidence.* qiskit returned the collapsed state while others returned the pre-measurement state.

### Submit-time structure checks

*Rule.* [`rosetta-api/services/qasm_structure.py`](rosetta-api/services/qasm_structure.py) (called by `validate_request`) refuses, each with its line number:

- non-ASCII outside comments;
- a header other than exactly `OPENQASM 2.0;`;
- names that collide (one namespace for qreg/creg/gate/opaque; registers may not shadow U, CX or included qelib1 gates);
- an index out of range; an undeclared operand;
- an unknown gate, with suggestions;
- wrong arity or parameter count; a repeated qubit;
- empty statements; control characters;
- broadcasts over registers of different sizes;
- calls reaching an opaque gate;
- `/* */` comments (bundled circuits exempt);
- register names not starting a–z;
- use before declaration;
- a register size, index or if-value of more than 30 digits (checked before any is converted to an integer);
- a statement that does not start with a name (`,q[1];`, a stray `{ ... }`), at top level or in a gate body;
- a `}` with no open `{`, a `{` inside a gate body, or a `{` never closed;
- a `qreg` that is not a top-level statement;
- a register of size 0;
- a gate parameter of more than 1,000 characters;
- a `//` comment holding `/*` with no `*/` after it in the same comment (checked first, before any other pass removes comments).

Spaced indices `q [0]` are normalised with preprocessing on (`API:` note).

*Evidence.* `qreg q[1]; qreg q[2]` merged into a different circuit, and all backends agreed on it. An unequal broadcast was rewritten; opaque calls were dropped silently; block comments were silently removed. 328 bundled files pass. 2026-10-28: a 5,000-digit register size or index raised Python's integer-string limit (ValueError) and the route answered 500; `/visualize/quirk` read register sizes before validating (`test_v1_13_pathological_numbers.py`). 2026-10-28 (V6 fuzzing, `test_v6_fuzz_findings.py`): `OPENQASM 2.0;qreg q[3];creg meas[3];measure q[1]->meas[0];,q[1];` passed the structure check and raised AttributeError in `parse_measurement_layout` (500); `OPENQASM;gate {{}qreg q[3];...` hid the qreg from the structure check (no top-level qreg, so it returned early) while the qubit count read it, with the same 500. `// see /* here` ... `// */` was accepted, and the API's register merge and round-trip, which remove `/* */` before `//`, dropped every line in between from the dispatched circuit: `h q[0]` was missing from what every backend ran, and a `qreg r[30]` there was not counted against the qubit cap. 61,000 `creg z[0];` declarations, a never-called gate body of 199,000 statements and a 500,000-term parameter took 1.0, 1.9 and 2.1 s to validate on an E-core; each is now a 400 within 0.5 s.

### Expanded-gate broadcast width

*Rule.* A register operand counts as a broadcast only when the whole identifier is not followed by `[`. Register sizes come from the comment-free statements.

*Evidence (2026-10-07).* `qa[0]` matched the bare register `q`. With `qreg q[22]; qreg qa[2];`, 9,998 × `x qa[0]` counted as 219,958 applications and was rejected. `// qreg q[24];` changed the counted width.

### Gate statement count

*Rule.* `MAX_QASM_GATES` (10,000, `limits.max_qasm_gate_statements`) counts operation statements at top level and inside gate definitions; a gate or opaque definition with an empty body counts as one. The header, includes and register declarations are not counted.

*Evidence (2026-10-28).* Statements inside gate bodies were not counted, so a definition that is never called could hold the whole 1 MB (199,000 statements) and took 1.9 s to validate, 41,000 one-statement definitions 1.5 s. The largest bundled circuit by this count is grover-v-chain_n22 with 8,730 (1,199 at top level).

### Classical bits

*Rule.* The creg declarations of a circuit add up to at most `MAX_CLASSICAL_BITS` (1,024, `limits.max_classical_bits`); a size of more than 30 digits counts as over the limit. Checked right after the syntax check, before anything builds per-bit tables. Not lifted by `bypass_limits`.

*Evidence (2026-10-28).* `parse_measurement_layout` (validator, preparation, runners) builds a dictionary entry per classical bit: `creg c[10000000];` (65 bytes) took 15.8 s and 3.3 GiB in the validator, and Atheris found `creg ans[6666666668];` by exceeding its 1 GiB limit; the API container's limit is 2G. The largest bundled circuit declares 46 classical bits.

### Gate parameters

*Rule.* Every constant parameter (top level and inside gate bodies) must be a finite OpenQASM 2.0 expression with magnitude ≤ 1e6 (400 otherwise).

*Evidence.* pytket reduced rx(1e308) to rx(0) and all 14 backends agreed on the wrong state; rx(nan) gave NaN statevectors ranked fastest.

### Parameter expressions

*Rule.* A hand-written OpenQASM expression parser ([`shared/qrosetta_commons/qasm_expressions.py`](shared/qrosetta_commons/qasm_expressions.py)); Python keywords are valid parameter names.

*Evidence.* `lambda` was refused.

### Reserved gate names

*Rule.* User `gate`/`opaque` names that any runner's parser treats specially are rejected (400) in every mode ([`rosetta-api/services/reserved_gate_names.py`](rosetta-api/services/reserved_gate_names.py), read from the runner images); the pytket round-trip fails the job if a call became a barrier or a user gate lost its definition. Bundled MQT/QASMBench circuits are exempt.

*Evidence.* pytket turned `sleep`/`orderN`/`groupN` into barriers and replaced prefix-matching definitions of built-ins (`yyphase`, `fsim`, `iswap`): all 14 backends agreed on a wrong state.

### pytket in threads

*Rule.* Every pytket parse and write in the API runs under `PYTKET_LOCK` ([`rosetta-api/services/pytket_lock.py`](rosetta-api/services/pytket_lock.py)), called from `asyncio.to_thread`.

*Evidence.* pytket 1.33 keeps one global Lark parser. Two simultaneous jobs swapped gate definitions (6 of 8 trials) with every backend agreeing.

### pytket CnX names

*Rule.* After the round-trip the API renames pytket's `c4x` by operand count (cx/ccx/c3x/c4x), recorded as `API:`; wider is a RoundTripIntegrityError.

*Evidence.* pytket 1.33.0 writes every CnX as `c4x`; `c3x` became an invalid 4-operand `c4x`, rejected by 8/14 simulators and every compiler.

### Angle rounding in parsers and writers

*Rule.* tket (pytket 1.33) sets a parameter within 1e-11 half-turns of a multiple of π/4 to it (also `rz(1e-11)` → 0). The API predicts it (`qasm_expressions.tket_rounded_parameters`: top-level constants and parameters inside called definitions with each call's values; parameters tket derives while rebasing, e.g. cu1/crz half-angles, are not predicted and the note says so; the evaluator is shared with the validator) and records it as an `API:` note after the round-trip, or appends a note to runners with `builds_with_tket` when it dispatches text tket has not built. This is computed in the API, never inside a runner's timing window. Qiskit-written texts use `exact_qasm2_dumps` ([`shared/qrosetta_commons/qiskit_circuits.py`](shared/qrosetta_commons/qiskit_circuits.py); bypasses `pi_check(eps=1e-12)`); qsim's text uses `to_qasm(precision=16)`. PyZX: scientific-notation literals are rewritten as plain decimals (its parser rejects them); passes report the largest angle change from its rational phases (denominator ≤ 2^20), read through PyZX's own parser.

*Evidence (2026-10-02).* `rz(1.3e-13)` → 0 and `rz(3.14159265359)` → π in tket; `qasm2.dumps` wrote 1e-13 as 0 and π+1e-13 as π; Cirq's default precision 10 wrote `rz(1.3e-13)` as `rz(0)`; PyZX moved 0.123456789012345678 rad by 1.1e-9 rad (2.75e-9 worst over 2,000 random angles) and rejected `3.18e-06*pi`, which the round-trip writes for small angles.

### QASM edits are per statement

*Rule.* Runner-side rewrites split at `;`, `{`, `}` on comment-free text, never by line.

*Evidence.* PennyLane deleted gates sharing a line with `barrier`; qibo's regex deleted the statement after a `// barrier` comment.

### Missing qelib1 gates (qibo, quimb)

*Rule.* With preprocessing on, the qibo and quimb adapters insert the `qelib1.inc` definitions (Qiskit 2.5.2 copy in [`shared/qrosetta_commons/qelib1_qiskit.inc`](shared/qrosetta_commons/qelib1_qiskit.inc)) of the qelib1 gates their parser lacks, in the compile window (it is a transform the adapter needs), listed in `preprocessing_applied`; quimb gets `U` written as `u3`. With preprocessing off they are rejected, as before. staq uses the same helper. qibo does not get `cp`/`cu` (the round-trip never emits them; see [Upstream behaviour not worked around](#upstream-behaviour-not-worked-around)).

*Evidence (2026-10-02).* 0 failures, every gate F = 1 to 12 digits against Qiskit's Statevector on 31 qelib1 gates; through the API with preprocessing on, ch/csx/cswap/c3x 4-backend pairs all agree. qibo 0.3.1 raises TypeError executing any 2+-qubit user gate whose body uses its parameters.

### Implicit permutations

*Rule.* Swaps removed by relabelling are written back as gates in `compile_fn`: `restore_final_layout` for Qiskit transpiles, `replace_implicit_wire_swaps` for pytket passes before `tk_to_*`. TorchQuantum stays capped at level 2 (Qiskit 0.45.3 level 3 deletes swaps with no layout). [`rosetta-api/tests/unit/test_implicit_permutations.py`](rosetta-api/tests/unit/test_implicit_permutations.py).

*Evidence.* Qiskit and cuQuantum levels 2–3, PyQuil 1–2 and Cirq 2 returned permuted statevectors (72, 72, 176 and 88 cases); 0 after.

### Gate metrics

*Rule.* `gate_count`/`circuit_depth` come from `transpiled_qasm` unless the runner supplies `gate_metrics_fn` (PennyLane: executed-tape operations); `gate_metrics_basis` says which.

*Evidence.* PennyLane's `to_openqasm()` text decomposes `QubitUnitary`: QFT-12 read 1014 gates vs qiskit's 84.

### PennyLane executed text

*Rule.* `transpiled_qasm` holds the executed tape's operations only, one statement per tape operation, with qelib1 names (sx, sxdg, ch, cy, rxx, rzz, cu1, barrier). QubitUnitary and Rot are decomposed in the text only, up to global phase. Barriers are passed to `from_qasm`.

*Evidence.* The text reproduces PennyLane's statevector at levels 0, 1 and 3. Earlier, `dev.preprocess()` gave `qml.state()` explicit wires, and `to_openqasm(measure_all=False)` then wrote a `measure` per wire that never ran.

## Compile-only services

Compilers are separate from the simulators: their output is a circuit, which is shown and exported but not simulated, timed or compared. The adapters are under [`compilers/`](compilers/); the shared output checks are in [`shared/qrosetta_commons/compile_checks.py`](shared/qrosetta_commons/compile_checks.py).

### Compile-only services

*Rule.* Compilers are not runners: separate registry (`get_compiler_services` in [`rosetta-api/config.py`](rosetta-api/config.py)), output in `compiled_circuits`, never simulated, timed or compared. They run after the job's simulators, through `dispatch_to_runners` (gate, queue, hard timeout), on one recorded `compile_input` (`prepare_statevector_dispatch` of the submitted circuit); a measured circuit with mid-circuit measurement is `skipped`. `run_isolated(measured=False)` calls the processor once, without warm-up or timing. `simulate: false` (compile-only request) dispatches no simulator; the report has `simulated: false` and empty `raw_results`. Each image has `--self-test` (probe circuits, unitary check with the image's own SDK).

*Evidence (2026-10-01).* Running them beside timed runs would share the host with the measurement; a compile time would be a performance claim outside the instrument.

### Compiler pipelines offered

*Rule.* BQSKit levels 1–3 (one worker, seed 0, all-to-all, epsilon 1e-8); PyZX `full_reduce`+extract (1) and +`basic_optimization` of the extracted circuit (2); QMAP: Qiskit basis translation to u3+cx, then heuristic (0) / exact (1) mapping onto a linear chain.

*Evidence.* BQSKit level 4: 195 s on a 4-qubit, 6-gate circuit. PyZX 0.10.6 `basic_optimization(to_basic_gates())` changed the unitary of 31–90% of random 3-qubit circuits (`x; rx(0.7)` reproduces); full_reduce paths 0/450. QMAP 3.10 maps `cu3`/`cp` as `cx` without an error; after decomposition 40/40 random circuits were equivalent up to layouts, and all five live outputs of a test job were equivalent.

### Compilers not offered

*Rule.* GUOQ/wisq is not offered.

*Evidence.* Its search stops on wall-clock time only (the seed covers resynthesis partitions), so output depends on load; it needs Java 21 and a BQSKit server too.

### Compile-only qubit limit

*Rule.* A `simulate: false` request (single or playlist) is validated against `MAX_QUBITS_COMPILE` = 24, not the statevector cap; every other check is unchanged. Exposed as `max_qubits_compile` in `GET /config`. Compilers enforce `MAX_QUBITS_COMPILE` (env, default 24; [`qrosetta_commons.helpers`](shared/qrosetta_commons/helpers.py)). The API forwards all three caps to Kubernetes Jobs, and docker-compose passes them to api, runners and compilers ([`rosetta-api/tests/unit/test_qubit_cap_sources.py`](rosetta-api/tests/unit/test_qubit_cap_sources.py)).

*Evidence (decided 2026-10-07).* The 18-qubit cap protects runner memory from a 2^n statevector, which a compile-only run never builds. The limit is not unbounded: BQSKit's higher levels and Quartz (time about quadratic in gates) scale badly with width, and outputs above 10 qubits are not unitary-checked. 24 is the largest circuit the platform already accepts. Before, `compile_service` used `MAX_QUBITS_MEASURED` and Jobs received no caps.

### Compiler memory and concurrency

*Rule.* Compiler containers have 2G and 2.0 CPU with `COMPILER_MAX_CONCURRENT=2` (two single-threaded compiles at a time). BQSKit has 1: its `Compiler` binds ports 7472/7474 and a second concurrent compile failed with 'Server connection unexpectedly closed'. Compiles are not timed, so concurrency affects latency only. Kubernetes runs one compile per Job. Kubernetes compile Jobs: requests 200m/512Mi, limits 1000m/2Gi (`dispatcher_k8s.COMPILER_RESOURCES`). The project quota's `limits.memory` is 16Gi; API 2Gi + 3 × 2Gi fits.

*Evidence.* Cirq imports alone are 259 MiB per process, and the compile runs in a spawned child beside the gunicorn worker; a 12-level nested gate peaked at 432 MiB in the child and OOM-killed Cirq, staq and Q-Synth at 512M. 2026-10-02: one compile per service let a slow compile block other clients' compiles; two slots at 1G would not hold two such children beside the worker.

### Compiler basis translation

*Rule.* QMAP, Q-Synth and Quartz translate with `transpile(..., optimization_level=0, qubits_initially_zero=False)` ([`qrosetta_commons.qiskit_circuits`](shared/qrosetta_commons/qiskit_circuits.py)); every Qiskit-based equivalence check builds the operator from the u3/cx translation (`unitary_of`). Runners keep the default (they simulate from |0…0⟩).

*Evidence (2026-10-01).* The default treats an untouched qubit as a clean ancilla when decomposing MCX: 11-qubit `h q0..q2; c3x q0..q3` gave F = 0.743 for Q-Synth and Quartz, marked ok (unchecked above 10 qubits). Operator of a 2-qubit, 12-level nested gate: 602 MiB direct, 153 MiB flattened.

### Compiler output checks

*Rule.* Every BQSKit (tolerance 1e-6) and PyZX (1e-8) output up to 10 qubits is checked with Qiskit; "not checked above 10 qubits" otherwise. staq records its largest single-precision angle change. Raw SDK errors become `CompileRefused`.

*Evidence.* No separate measurement was recorded for this rule. It follows from cases recorded in other entries of this section, where a compiler returned a circuit with a different unitary and reported no error: PyZX 0.10.6 `basic_optimization(to_basic_gates())` changed the unitary of 31–90% of random 3-qubit circuits; QMAP 3.10 mapped `cu3`/`cp` as `cx`; Cirq 1.7.0 imported some `cu3` gates with a −1 phase on the control's \|1⟩ branch.

### Compiler inputs

*Rule.* BQSKit gets renamed qelib1 definitions of c3x, c3sqrtx, c4x, rc3x and u0, and wide user gates are flattened in operation order (never `Circuit.unfold`). Cirq gets rc3x's definition. QMAP exact is refused above 7 qubits, and identity-only qubits count as idle. Cirq level 1 sets final measurements aside. Compiled circuits carry no measurements. The CSV has `refusal_kind`, `refusal` and `reason`.

*Evidence (2026-10-08).* BQSKit's parser read c3x, c3sqrtx, c4x and rc3x as 4–5 qubit gates and u0 without its parameter. After the change, BQSKit levels 1–2 on those gates, nested and colliding definitions: all equivalent (process infidelity ≤ 2e-15); 30 random 4–6 qubit circuits with those gates at level 1: 0 failures. BQSKit 1.2.1's `Circuit.unfold(point)` changed the unitary when gates preceded the unfolded one (infidelity 0.146 on a 2-qubit example).

### Compiler refusals

*Rule.* An adapter raises `CompileRefused` (input it cannot compile correctly) or `OutputRejected` (output failed its check) ([`shared/qrosetta_commons/compile_errors.py`](shared/qrosetta_commons/compile_errors.py)); the record gets `refusal` + `refusal_kind`. Only those reach share links and the Summary tab; other compiler errors (tool exit status, stderr, SDK exceptions) stay out of share links.

*Evidence.* Refusal reasons were not visible on the share page or the Summary tab; error text is excluded from share links (see [Share links](#share-links)).

### Compiler gate metrics

*Rule.* Each compile record has `gate_count` (top-level statements), `circuit_depth` (greedy, barriers ignored), `gate_counts` (per name) and `multi_qubit_gate_count`; `tables/compiled_circuits.csv` in crates, `compiled_circuits.csv` + texts + compiler locks in experiment bundles. The user manual and tooltips say gate_count is not comparable across compilers.

*Evidence.* QFT-8 staq -O1 gave 40 gates vs 160–170 for others with the same 68 CX; staq -O1 79 vs Cirq 393 on one circuit.

### Compiler build provenance

*Rule.* Pip packages go in `sdk_versions`; programs an image builds from source are `native_components` (`declare_native_component` in [`shared/qrosetta_commons/compile_service.py`](shared/qrosetta_commons/compile_service.py): version, source URL + sha256, flags/patches, Quartz ECC hash). Each compiler image copies its build files (Dockerfile, `requirements.lock`, Quartz patch/generator/driver/ECC set) to `/usr/local/share/qrosetta-build/`; records carry their sha256 as `build_files`, and a crate includes the API's copy of a file only when the hash matches. `GET /compilers` reports these from each image's `/capabilities`. The Quartz ECC set is committed as a reference copy ([`compilers/quartz-compiler/Nam_complete_ECC_set.json`](compilers/quartz-compiler/Nam_complete_ECC_set.json)), checked against the Dockerfile's `ECC_SHA256` by a unit test.

*Evidence (2026-10-02).* Crates listed `staq==3.5`/`quartz==0.3.2` as pip pins, Quartz's ECC set, generator and patch were not in crates, and `GET /compilers` had no versions.

### QMAP output check

*Rule.* Every QMAP output is checked when produced: `// i` and `// o` must be full permutations, and up to 10 qubits the output read through them must have the input's unitary (Qiskit), else the compile is an error. Circuits with idle qubits are refused before mapping.

*Evidence (2026-10-01).* QMAP 3.10 writes the identity layout when a qubit is idle; an input-side idle check was bypassed with `id q[1]`, which QMAP removes before writing a wrong layout.

### PyZX input

*Rule.* creg declarations and comments are removed before PyZX parses; classical operations are refused.

*Evidence (2026-10-01).* `to_graph()` turned 3 creg bits into 3 extra qubits (`q[6]`). A comment containing "measure" was refused.

### Cirq compiler

*Rule.* Compiler id `cirq-transformers` (the runner is `cirq`); CZ target gate set only. A `cu3` with θ mod 4π in [2π, 4π) is refused at top level and inside gate bodies at any qubit count (found by walking Qiskit's parse into user definitions). The image sets `PYTHONHASHSEED=0` (all compiler images do); outputs ≤ 10 qubits are checked with Qiskit.

*Evidence.* Cirq 1.7.0 `circuit_from_qasm` imports such a `cu3` with a −1 phase on the control's |1⟩ branch; all other qelib1 gates imported correctly in a sweep; 0/200 random circuits were wrong otherwise. The sqrt-iSWAP target is not offered (QASM shows only its cx decomposition).

### staq compiler

*Rule.* Built with g++ from the sha256-pinned v3.5 tarball; -O1..-O3, no mapping. Gates of Qiskit's qelib1.inc missing from staq's library get Qiskit's definitions inserted (dependency order), listed in the passes; registers/gates named `r` or `cswap` are refused; a literal that float32 moves by > 1e-6, or below float32's smallest normal, is refused; outputs ≤ 10 qubits are accepted at process infidelity ≤ 1e-8 (value recorded).

*Evidence.* staq's lexer uses `std::stof`: angles are single precision (`rz(0.3)` → `rz(0.300000011920929)`); infidelity < 1e-14 on 360 outputs.

### Q-Synth compiler

*Rule.* `qsynth`: Qiskit → u3+cx, then `peephole_synthesis(slicing='cnot')` for cx-count (0) or cx-depth (1) on one register `q`, composed back onto the input's registers and final measurements. A slice that still timed out at its last solver call (recorded by wrapping `optimize_single_slice`) or an exhausted budget is an error. Runs in a private temp dir; python-sat 1.8.dev14 with `pip install --no-deps` (Q-Synth pins the removed 1.8.dev13).

*Evidence.* 0/50 non-equivalent, repeat runs byte-identical, < 1 s each on 3-qubit circuits.

### Quartz compiler

*Rule.* `quartz` level 0 only: Qiskit → h/x/rz/cx, then `Graph::greedy_optimize` with a Nam ECC set (3 qubits, 2 parameters, ≤ 3 gates) generated at image build and checked against a recorded sha256. Rational parameters (upstream default) with [`shift10-normalise.patch`](compilers/quartz-compiler/shift10-normalise.patch); angles go in as exact fractions of π; output = Quartz's gate lines renamed onto the input's registers (no `qasm2.dumps`). Barriers are removed, final measurements re-added, and mid-circuit measurement/reset/if refused. Quartz runs with PDEATHSIG so a timeout kills it; outputs ≤ 10 qubits are checked. Not offered: `Graph::optimize` (wall-clock bound), `rotation_merging`, the 4-gate ECC set.

*Evidence (2026-10-01).* Unpatched, 6/400 random circuits segfaulted (a bignum zero kept a leading limb, and `gcd` recursed 104k frames); patched, 0/400 crashed or were non-equivalent, repeat runs were byte-identical, and the ECC hash was identical across generations. The double-parameter build snaps angles within 1e-6 (`eps`) to π/4 multiples and deletes near-2kπ rotations, so it was rejected. `rotation_merging` ignores `x` sign flips: 79/303 non-equivalent. 4-gate set: 933 s on 32 cores, same gate counts on 8 circuits. Quartz drops `measure` silently. `qasm2.dumps` writes |θ| < 1e-12 as 0 and snaps within 1e-12 to simple π fractions. Time ≈ quadratic in gates: 3361 → 8 s, 8000 → ~50 s, 24k > 300 s.

### Synthetiq compiler

*Rule.* `synthetiq`, levels 0 (first circuit found, ≤ 1000 annealing runs; annealing energy = distance to the unitary, so T-count can rise) and 1 (lowest Synthetiq cost of up to 5 found, ≤ 2000 runs; fewer when the run cap ends the search). Clifford+T only (exact h/rz/cx translation; every rz within 1e-12 π/4-steps of a multiple, largest change listed, else CompileRefused), ≤ 3 qubits. One thread → one mt19937 stream seeded 0 per search (`seed(id + run*threads)`, one outer run); `--max-runs` from [`max-runs.patch`](compilers/synthetiq-compiler/max-runs.patch); a stop by `--time 280` with fewer circuits than asked is an error naming the limit; an empty circuit is returned without running Synthetiq (it segfaults on zero gates). Built at commit 59a0cc6 with `-O2`; Qiskit check on every output.

*Evidence (2026-10-02).* Toffoli → T-count 7 in 0.1 s; a 3-qubit run takes ~83 ms (435 runs/36 s for 1 circuit, 1451/122 s for 10). Fuzz over 60 random Clifford+T circuits: level 0 60/60 equivalent and byte-identical on repeat, level 1 59/60 (1 found 1 of 5 in 2000 runs). A follow-up check: 34 outputs equivalent; near-π/4 angles within 7.85e-10 rad had been rounded silently at the old 1e-9 tolerance, and empty circuits segfaulted.

## Provenance and reproducibility

### Provenance capture

*Rule.* `transpiled_qasm` is the circuit that executed, captured after every compile pass (pytket `get_compiled_circuit` runs a default rebase even at level 0). Serialisation runs in `serialize_fn` unless the circuit is mutated afterwards.

*Evidence (2026-08-18).* qulacs/quest/cirq/braket/projectq/qsim previously captured the pre-compile circuit.

### Image commit

*Rule.* Every image bakes `QROSETTA_IMAGE_GIT_SHA` at build (`--build-arg QROSETTA_GIT_SHA`); every runner and compiler result records `image_git_sha`; `git_sha` is the API image's. In Kubernetes mode (CSC Rahti), `QROSETTA_IMAGE_DIGESTS` (set by [`scripts/rahti_push.sh`](scripts/rahti_push.sh)) gives each image stream's digest, tag, source (pushed, or previous `:latest` retagged) and baked `image_git_sha`. Jobs run by digest, and `runner_image` records `registry/name@sha256:…`. A dirty checkout deploys as `<sha>-dirty` with a unique tag.

*Evidence.* On 2026-10-01, reports said `da8ced9-dirty` (the host checkout at boot) while the API ran 5abaa17 code and the runners older code. After a partial push, crates named `name:<HEAD>` for images built from older code.

### No source mounts on the API

*Rule.* The API reads `runners/` and `compilers/` from its image.

*Evidence (2026-10-01).* The read-only Compose mount of `./runners` over the API image's copy was unreadable by appuser under rootless podman, so crates never carried runner lock files.

### Report and crate source

*Rule.* Saved reports carry `saved_from` set by the server (`server_job` / `upload`); crates record `report_source` from the export route (`server_job`, the saved run's source, `client_supplied`), never from a report field.

*Evidence (2026-10-01).* Crates built by `POST /export` kept a forged `saved_from`, git SHA and version.

### Crates of supplied reports

*Rule.* Unless `report_source` is `server_job`: no actionStatus, versions only "as supplied", no lock files and no commit links. `#report-source` is a PropertyValue; an upload's `job_id` is kept as `source_job_id`. The repository link comes from `QROSETTA_REPOSITORY_URL`. Every File has sha256 and contentSize.

*Evidence (2026-10-08).* A client-supplied report could show a forged qiskit==9.9.9 as fact; commit links returned 404.

### Crate README

*Rule.* Every RO-Crate has `README.txt` at its root, written by [`rosetta-api/services/export_readme.py`](rosetta-api/services/export_readme.py) from the crate's own `ro-crate-metadata.json` after every other entity is in place: the report source, completeness, specimens and timing caveats as the root's PropertyValues state them, each top-level file with its description, each folder with its file count (names listed up to 40), the hash-check command and the software version and source commit. It is a File entity with `sha256` and `contentSize` like every other file and comes first in the root's `hasPart`. Nothing else in a crate changes; the same export gives the same README.

*Evidence (2026-10-27).* A crate explained itself only through JSON-LD and this repository's manual; the CLI spec (S13) asks for a reader who has neither.

### CSV cells in crates

*Rule.* CSV files in crates and experiment bundles hold values as recorded, without a quote prefix for cells that start with `=`, `+`, `-` or `@`; the crate README (tables folder) and the experiment README say so and tell the reader to import the files as CSV text.

*Evidence (2026-10-28, V6).* A prefix would change the data a CSV reader sees: negative numbers (`-0.5`) and SDK error texts that start with `-` would become text with a leading quote, and the publication tables would no longer equal the page's CSV (parity rule). The cells that a spreadsheet could read as a formula come from the run's own report: its circuit and run names, runner error texts and compiler refusals; a crate goes to the account that ran the job or uploaded the report.

### Image identity reported by the runner

*Rule.* Each runner and compiler image writes `/usr/local/share/qrosetta-image/identity` at build (`source`, `release`, `git_sha` from the build arguments `QROSETTA_IMAGE_SOURCE`, `QROSETTA_RELEASE`, `QROSETTA_GIT_SHA`; compose passes `built_locally`, a release pipeline passes `release`, a plain `docker build` leaves `unknown`) and copies its Dockerfile and `requirements.lock` to `/usr/local/share/qrosetta-build/`. The new values are build arguments and a file, never `ENV`, so the container's environment, and with it the environment the timed child inherits through `spawn`, is unchanged. The serving process reads the file, the build-file hashes, the container runtime's view (Apptainer path and sha256, podman's `/run/.containerenv`) and the `hypervisor` CPU flag once at startup ([`shared/qrosetta_commons/image_identity.py`](shared/qrosetta_commons/image_identity.py)) and adds `image_identity` and `build_files` to each result after the child has returned, beside `queue_wait_sec`; the Kubernetes and batch CLI paths add them after `run_with_uniform_measurement` returns. `runner_image` is the Job's image in Kubernetes mode, else the image the runtime showed the runner (`runner_image_basis`). Each result that ran gets `specimen` and the report `specimens`: `all_published` (one release), `all_built_locally`, `mixed`, `unknown` or `none_ran`, with per-backend detail, the image commits and a note when they differ or are `-dirty`. The roll-up uses only values the image baked. ([`rosetta-api/tests/unit/test_image_identity.py`](rosetta-api/tests/unit/test_image_identity.py), [`test_specimens.py`](rosetta-api/tests/unit/test_specimens.py))

*Evidence (2026-10-27).* Local results recorded `runner_image` "not recorded", and a crate could not say whether a backend ran a published image, a local build or a build from another commit. Through the real spawn path, the child's `os.environ` equals the serving process's environment and the child never reads the identity (`test_result_carries_identity_and_child_environment_is_unchanged`, measured and unmeasured). Images built before this change report `source` "not recorded" until rebuilt.

### Emulation recorded by the runner

*Rule.* Every runner and compiler result carries `image_identity.emulation` = `{emulated, image_arch, host_arch, host_os, method}` ([`shared/qrosetta_commons/image_identity.py`](shared/qrosetta_commons/image_identity.py)). `image_arch` is the ELF `e_machine` of the image's Python interpreter (64-bit machines only; `uname` inside an emulated container reports the emulated machine, so it cannot be used). `host_os` and `host_arch` come from `QROSETTA_HOST_OS` and `QROSETTA_HOST_ARCH`, which `qrosetta start` sets on every start from `platform.system()` / `platform.machine()` (an x86_64 Python on macOS reports `arm64` when `sysctl.proc_translated` is 1) and compose passes to every runner and compiler; `scripts/roihu/run_runner.sh` passes the node's `uname -s` / `uname -m`. The serving process takes both variables out of `os.environ` in its startup handler (`load`), before any child is spawned, and the one-job CLI paths do so right after parsing their arguments, before the self-test or the run; the values are kept in the process and stamped after the child returns, beside the rest of `image_identity`. `emulated` is `image_arch != host_arch` after aliasing (`arm64` = `aarch64`, `AMD64` = `x86_64`), and null when either is unknown, as under plain compose, Kubernetes or `safe_boot.sh` before it hands over to `qrosetta start`. The self-test's `host_emulation` check reads `cpu_environment.emulation`, else `image_identity.emulation` (PASS false, FAIL true, SKIP null; `selftest-2026.10.27.2`). `timing_caveats` adds `emulated_image` when `emulated` is true (`timing-caveats-2026.10.27.3`; no stored report has the field, so no stored report's caveats change). No in-container signal is used: in a fresh user, mount and PID namespace with its own procfs (what a rootless podman container gets), `/proc/sys/fs/binfmt_misc` is an empty directory on this host (kernel 6.12) while the host's own lists its handlers, so a qemu-user or Rosetta handler cannot be seen from inside a container and its absence proves nothing.

*Evidence (2026-10-27).* Through the real spawn path, with the two variables set before `load`, the child's `os.environ` equals the environment without them, measured and unmeasured (`test_host_environment_is_removed_before_the_child_is_spawned`). Old (main) and new code, 3 alternated rounds of 15 runs through `ExecutionSlots` (a Qiskit Aer 0.17.2 statevector processor on `run_statevector_job`, 16-qubit QFT, `timing_repeats` 3, pinned to one P-core, Python 3.12): compilation 35.55 → 35.41 ms, simulation 14.32 → 14.41 ms (the new code's round medians 14.35–14.43, the old's 14.14–14.42), whole-process CPU 714.2 → 712.5 ms, process peak RSS 136.88 → 136.89 MiB (median of round medians); result keys identical, `image_identity` differs only by `emulation`, one statevector across all 90 runs. A first series at host load 12 from other sessions read old 54.3/21.5 ms and new 36.6/15.0 ms; a control at load 3 with the same code twice gave the old/new/new-with-variables triple 34.5–35.9 / 13.9–14.5 ms, and the rerun above is the comparison. Reading the ELF header and the variables costs 37 µs, once per serving process at startup.

### Runner lock files in crates

*Rule.* A crate (and an experiment bundle) includes the server's copy of `runners/<runner>/requirements.lock` only when its sha256 equals `build_files["requirements.lock"]` in every result that runner's image returned. Otherwise the file is left out and the runner's entity, `provenance.json` `runner_lock_files` and the bundle manifest say why: no build-file hashes (image built before runners reported them), a different hash with the image's commit, no copy on the server, or no result from the image.

*Evidence (2026-10-27).* The exporter attached the API tree's lock file for every runner used and described it as the runner image's environment, with no check; in a stack of mixed builds that file did not describe the image that ran. Compilers already had the hash check (Compiler build provenance).

### Supported Python and base images

*Rule.* No image may run a Python or a base OS that reaches end of life within 12 months. [`release/eol.json`](release/eol.json) records the end-of-life dates, each with its source and the date it was read: CPython branches (devguide), Debian releases (end of LTS), Alpine releases, the Debian or Alpine release behind each pinned base-image digest (read from the image's `/etc/os-release`), and Qiskit's series support window. A month-only date counts from the first day of that month. [`scripts/release/eol.py`](scripts/release/eol.py) reads every Dockerfile in the repository, resolves global `ARG` defaults and stage references, and judges the final stage: Python from a `python:` base tag, else from a `python3.N` the Dockerfile installs, else from the table; the OS from the digest's table entry, else from a Debian codename or `alpineN.N` in the tag. A base it cannot place fails. Build stages and the Qiskit series pinned in each `requirements.lock` are printed, not judged: an SDK version is what an image measures, and changing one is an owner decision. [`rosetta-api/tests/unit/test_base_image_eol.py`](rosetta-api/tests/unit/test_base_image_eol.py) runs the guard on the real date, so an image fails from the day it enters the window. Images already inside are listed in the test's `EXPECTED_FAIL` with the reason, as strict expected failures: an image that becomes compliant fails until its entry is removed, and an image that newly enters the window fails until it is moved to a supported base or added to the list in a reviewed commit.

The target for a runner or compiler image is the newest CPython (3.13 first, else 3.12) for which every package in the image's lock has a build, never below 3.12. A runner or compiler image counts as part of the measurement, so its base changes only through requalification: the image is built twice from one commit, with the old and the new base, under test names (`localhost/qr-requal-<service>:old|new`); a fixed-seed corpus (random qelib1 circuits of 1–10 qubits at every offered optimisation level, preprocessing on and off, measured with seeds 0, 7 and 123456789, plus the self-test circuits) runs in both without network, and statevector bytes, counts, executed text, gate metrics, `preprocessing_applied` and `sdk_versions` must be identical, or every difference is listed (cirq is compared by fidelity, see cirq statevector bits; compilers by compiled text, gate metrics and `--self-test`); three fixed circuits are timed in alternated rounds on one pinned core. Only the base line and, where wheels force it, non-SDK transitive packages of the lock change; if the pinned SDK has no build for the target Python, the image stays and the gap is recorded. The evidence for each image is recorded as an entry in this file. [`scripts/requalify/requalify.sh`](scripts/requalify/requalify.sh) does all of this for one service. Runner cases go through `run_with_uniform_measurement(process_run[_measured], payload)` in one process per image, the function the command-line path and the isolated child call, and a few cases of each part also go through `main.py --endpoint` in a process each to show the two agree. Timings, memory, CPU and process times are excluded from the comparison by name; `runtime_environment` (Python and numpy versions) and the image identity fields are listed apart, since a new image changes them.

*Evidence (2026-10-27).* CPython 3.10 reached end of life on 2026-10-01 and 3.11 reaches it in 2027-10 (devguide, read 2026-10-27). On that day 18 images (the API, 15 runner images including the two disabled ones, and the BQSKit and PyZX compilers) ran 3.10 and 7 (quimb and the Cirq, QMAP, Q-Synth, Quartz, staq and Synthetiq compilers, with their build stages) ran 3.11, all on Debian 13 trixie, whose LTS ends 2030-06-30. The two nginx images run nginx 1.31.1 on Alpine 3.23, which reaches end of support on 2027-11-01, so they enter the window on 2026-11-01. Qiskit's 0.x series (qrisp, torchquantum) had security fixes guaranteed until 2025-02-15 and the 1.x series (PennyLane, pytket-qiskit, cuQuantum) until 2026-03-31.

### Reproducible image builds

*Rule.* Every Debian stage of every Dockerfile points apt at `snapshot.debian.org` before any `apt-get`: it declares `ARG DEBIAN_SNAPSHOT` with the default recorded once in [`release/debian-snapshot.conf`](release/debian-snapshot.conf) (passed again as a build argument by `scripts/safe_boot.sh` and `scripts/release/image.sh`) and rewrites `debian.sources` to `https://snapshot.debian.org/archive/debian/${DEBIAN_SNAPSHOT}` and `.../debian-security/${DEBIAN_SNAPSHOT}` with `Check-Valid-Until: no`, keeping the base image's own dated comment, which [`scripts/release/image_notice.py`](scripts/release/image_notice.py) reads as the base date. Every `pip install` either reads a hash-pinned lock with `--require-hashes` or installs a local path with `--no-deps --no-index`. A lock is generated by [`scripts/release/compile_lock.sh`](scripts/release/compile_lock.sh): pip-tools 7.6.2 runs pip's resolver inside the image's base, pinned by digest, with the previous lock as constraints, and writes every distribution file's sha256. [`test_reproducible_builds.py`](rosetta-api/tests/unit/test_reproducible_builds.py) checks the rules for every Dockerfile; images not yet moved are strict expected failures (runners and compilers until requalified, the nginx images until an Alpine rule exists).

*Evidence (2026-10-28).* Before, every image installed from `deb.debian.org` as of the build day and pip resolved transitive files without a hash check, so two builds of one commit could differ. With the API image's sources at `20261020T213255Z` (the archive date of its base digest), `apt-get update` from the snapshot succeeded and `apt-get -s upgrade` reported 0 packages to upgrade. Running `compile_lock.sh` a second time on its own output gave a byte-identical lock.

### API image on Python 3.12

*Rule.* The API image runs `python:3.12-slim` pinned by digest. 3.13 is not possible while numpy 1.26.4, scipy 1.14.0 and pytket 1.33.0, which the analysis and the circuit preparation use, publish no cp313 wheels. The API is outside the measurement, but its preparation and analysis produce results, so a change of its Python needs identical outputs: the preparation of every bundled circuit and template (`scripts/py312_check/dump_prepare.py`), the analysis corpus of `scripts/harness_bench/equivalence.py` (`dump_analysis.py`) and the unit suite inside the image.

*Evidence (2026-10-28).* Old image (python:3.10-slim 3.10.20) against new (python:3.12-slim 3.12.16, same commit): 1,456 preparation calls on 371 sources (20 refusals, 7 sources over the dump's size limit) gave byte-identical dumps (sha256 8143cd09…, as on 2026-10-21); 350 analysis cases (200 counts, 150 statevector) gave byte-identical 33,247,648-byte dumps (sha256 e8a4b788…); `prep_equivalence.py` compared 1,948 cases with 0 differences in each image. Unit suite inside the new image: 3,115 passed, 281 skipped, 50 xfailed. Trivy 0.76.0: CRITICAL with a fix 11 → 0, HIGH with a fix 97 → 0 (base digest with openssl 3.5.7-1~deb13u3 and perl-base +deb13u1; pillow 13.0.0, cryptography 50.0.2, oauthlib 4.0.0). Analysis time (`scripts/py312_check/pinned_bench.py`, one P-core, 3 alternated rounds of 5 repeats with a 1-minute load average below 3): statevector reports 5–14 % slower on 3.12 (6 qubits 70.6 → 80.4 ms, 7 qubits 478 → 545 ms), counts reports 1–7 % slower (7 bits 2.95 → 3.14 s), as on 2026-10-21. Image size 714 → 774 MB, from 3.12's larger bytecode files.

### Qulacs image on Python 3.12

*Rule.* The Qulacs runner image runs `python:3.12-slim` pinned by digest, with the apt snapshot and a hash-pinned lock (see Reproducible image builds). 3.13 is not possible while pytket 1.33.0, qulacs 0.6.5 and numpy 1.26.4 publish no cp313 wheels. It was requalified with `scripts/requalify/requalify.sh qulacs` (see Supported Python and base images).

*Evidence (2026-10-28).* Old image (python:3.10-slim, 3.10.20) against new (python:3.12-slim, 3.12.16), one commit. Corpus of 2,202 cases (900 random statevector, 900 random measured with terminal measurements, 300 with mid-circuit measurements, 24 + 24 deep circuits of 500–3,000 gates, 54 self-test circuit cases; levels 0–2, preprocessing on and off): every output field identical, including statevector bytes, counts, executed text, gate metrics, `preprocessing_applied`, `sdk_versions` and 726 identical refusals; `--self-test` identical (16 of 16 pass); 14 cases also through `main.py --endpoint` gave the same outputs. Lock: exceptiongroup dropped (needed below 3.11 only), setuptools 84.2.1 added; the image also loses `wheel` and moves pip 23.0.1 → 25.0.1 from the base. Timing on CPU 4 (a P-core), `--cpus 1.0`, 5 alternated rounds × 5 repeats, 1-minute load 1.9–3.8: simulation time within −6 % to +2 % on all six cells (statevector QFT-16 41.98 → 41.73 ms, measured 42.96 → 43.18 ms); compilation 5–12 % shorter on 3.12 (4 qubits × 2,200 gates 111.3 → 97.5 ms). Process peak RSS +8–10 MiB. Trivy 0.76.0, fixed CRITICAL/HIGH 7/78 → 1/6; the remaining ones are in anyio 4.14.1, starlette 0.38.6 and urllib3 2.7.0 of the runner's HTTP stack. Image 509 → 555 MB.

### Lint findings in the measured images

*Rule.* ruff, shellcheck and hadolint run in CI and fail only on findings above a recorded baseline ([`pyproject.toml`](pyproject.toml) `[tool.ruff.lint.per-file-ignores]`, [`scripts/lint/`](scripts/lint/)). Findings in runner and compiler code, in `shared/qrosetta_commons` and in their Dockerfiles are recorded, never fixed for the linter alone: a change there changes a measured image and goes through requalification (see Supported Python and base images). Elsewhere a lint fix must not change behaviour; one that does is a defect with its own regression test.

*Evidence (2026-10-28).* On the day the gate was added, ruff reported 31 findings in the measured trees (12 B905 `zip()` without `strict=`, 9 B904 `raise` without `from`, 5 UP033 `lru_cache(maxsize=None)`, 2 S104 for the servers' 0.0.0.0 bind, and one each of S607, S311 and UP012) and hadolint 72 in the runner and compiler Dockerfiles (pip cache directory, unpinned apt packages, non-numeric `USER`, `cd` in `RUN`, pipes without pipefail in build stages). Each would change the image: `strict=True` raises where `zip()` now stops at the shorter input, and every Dockerfile fix changes a layer.

### Static security analysis

*Rule.* `scripts/lint/check.sh semgrep` runs Semgrep (1.180.0 when the baseline was written; registry packs `p/python`, `p/javascript`, `p/security-audit`, `p/secrets`, `p/owasp-top-ten`) over the API, CLI, shared code, runners, compilers, scripts, nginx and Kubernetes files, and fails on a finding above [`scripts/lint/semgrep.txt`](scripts/lint/semgrep.txt), where each accepted line carries its reason. It is not part of `check.sh all`, because the rule packs come from the network. CI runs it in the `lint` job, in its own virtual environment, from [`scripts/lint/semgrep-requirements.txt`](scripts/lint/semgrep-requirements.txt): Semgrep and its 65 dependencies, each with the hashes of its Linux x86_64 CPython 3.12 wheels, installed with `--require-hashes --no-deps --only-binary=:all:`, every release at least 7 days old when pinned. ([`rosetta-api/tests/unit/test_supply_chain_workflows.py`](rosetta-api/tests/unit/test_supply_chain_workflows.py))

*Evidence (2026-10-28).* 379 rules on 845 files: 20 findings, all accepted with reasons (10 pickle uses on the API's own spill files and its preparation child's pipe, 3 `chmod 0700` reported as permission changes, the template `exec()`, one quoted `ALTER TABLE`, the Host header that only the Origin check reads, nginx's named location, the nginx image's root user and the Kubernetes pod without a securityContext, the last two open defects). No finding in the page's JavaScript. Semgrep cannot parse the `ARG X=` lines of 26 Dockerfiles; hadolint covers those. On 2026-10-28 a fresh virtual environment installed the pinned set in 7.2 s without a pip cache and `check.sh semgrep` took 9 s on the development host. Semgrep 1.180.0 to 1.182.1 all require `mcp==1.29.0` and `opentelemetry-api~=1.37.0`, which carry moderate advisories (GHSA-5h93-6whr-6q8j, GHSA-84m7-p3x7-pcfv, GHSA-rwrf-2pqf-9j8j, GHSA-w4fh-qvv9-3v23 in the MCP client and server transports; GHSA-xcq7-p3pf-p88h in tracestate parsing); CI runs `semgrep scan` only, which starts no MCP client or server and receives no request whose trace header would be parsed.

### Type checking and link checks

*Rule.* CI job `types` runs mypy (2.4.0, hash-pinned wheels in [`scripts/lint/mypy-requirements.txt`](scripts/lint/mypy-requirements.txt)) over `qrosetta_cli/` as Python 3.11 and `shared/qrosetta_commons/` as Python 3.10, with `check_untyped_defs`, `strict_equality`, `warn_unreachable` and the unused-ignore and redundant-cast warnings, and fails on an error above [`scripts/lint/mypy.txt`](scripts/lint/mypy.txt) (file, error code, count). mypy reads no installed package, so every environment checks the same code with third-party imports as `Any`. The CLI has no accepted error; the `qrosetta_commons` errors are recorded and not fixed for the checker alone (see Lint findings in the measured images). A weekly workflow, `links.yml` (also run on request), checks the links of the top-level documents, `docs/verification/` and the manual page with lychee 0.24.2, a release binary checked against its sha256 ([`scripts/lint/lychee.toml`](scripts/lint/lychee.toml)). It is not a pull-request check, because its result depends on other sites. [`test_lint_baseline.py`](rosetta-api/tests/unit/test_lint_baseline.py) checks the wiring.

*Evidence (2026-10-28).* mypy found 56 errors in the CLI and 32 in `qrosetta_commons`. Four of the CLI errors were one defect: `qrosetta wait --all` with no unfinished job ended in an internal error (AttributeError on `None`) instead of the not-found error `qrosetta wait` gives. The other 52 were annotations (implicit `Optional` dataclass fields, empty containers, a re-bound `except` name). None of the 32 in `qrosetta_commons` changes behaviour as far as review showed. lychee checked 235 links (194 unique) with fragments. The one failure was the research group's page, whose tab `#qpa` is selected by the page's script, so that URL is excluded. `gitlab.alpinelinux.org` timed out from the development host over IPv4 and IPv6 and stays in the check.

### Dependency updates and image scanning

*Rule.* Dependabot (`.github/dependabot.yml`) proposes weekly version updates, at least 7 days after a release, grouped per ecosystem and directory: GitHub Actions; pip for `rosetta-api/`, its tests and the root `pyproject.toml` (boto3 and botocore kept below 1.36.0, whose payload checksums CSC Allas, the S3 store, rejects); Docker base images for every Dockerfile, keeping the Python minor version. Runner and compiler pull requests carry the label `sealed-image` and are merged only after the image is requalified (Supported Python and base images); their `requirements.txt` gets no version updates, only security updates when those are enabled. Dependabot does not read `requirements.lock`, so a pin in `requirements.txt` that differs from the lock fails [`test_requirements_lock_sync.py`](rosetta-api/tests/unit/test_requirements_lock_sync.py). Every release image, and each month every such image rebuilt without cache, is scanned with Trivy from its container image pinned by digest (`scripts/release/image.sh scan`): a CRITICAL vulnerability with a fixed version fails the image unless `.trivyignore` lists it with its reason, who accepted it and a review date; HIGH and CRITICAL findings with a fix go to code scanning. Every image carries `org.opencontainers.image.{title,description,licenses,source,revision,version}` from [`scripts/release/oci_labels.py`](scripts/release/oci_labels.py); `licenses` is `Apache-2.0`, the licence of the project's code, and the description says the image also contains third-party software under other licences. No `created` label: it would change every image id on every build.

*Evidence (2026-10-27).* Dependabot's pip support reads `*.txt` and `*.in` requirement files, `setup.py`, `setup.cfg`, `pyproject.toml`, `Pipfile(.lock)`, `poetry.lock` and `pdm.lock` (dependabot-core `python/lib/dependabot/python/shared_file_fetcher.rb` and `file_fetcher.rb`), not `requirements.lock`; a requirements-only update would have tested one version in CI and shipped the lock's in the image. On 2026-03-19 75 of 76 `aquasecurity/trivy-action` tags, 7 `setup-trivy` tags and the Trivy 0.69.4 release and images were replaced with credential-stealing code for about 12 hours (Snyk, "Trivy GitHub Actions supply chain compromise"); the scan uses Trivy 0.76.0 by digest `sha256:2416d1f7…`, the same index digest on Docker Hub and GHCR on 2026-10-27, and no Trivy action.

### Workflow hardening

*Rule.* Every action in every workflow under `.github/workflows/` is pinned to a full commit with its release in a comment, and one action has one commit across all workflows. Each workflow sets `permissions: contents: read` at the top; a job that needs more names each extra permission with a comment saying what uses it (SARIF upload, image push, signing, PyPI trusted publishing). Every checkout sets `persist-credentials: false`. No workflow uses `pull_request_target` or `workflow_run`, and no `run:` script contains a `${{ }}` expression; values reach scripts through `env:`. zizmor (pedantic persona) and actionlint report nothing over the workflows. The CLI job's Python versions equal the package's `Programming Language :: Python :: 3.N` classifiers, its runner systems equal the `Operating System` classifiers, and its lowest Python is `requires-python`. `Licence.txt` is a byte copy of `LICENSE` (SoftwareX asks for the first name; GitHub, Scorecard and PEP 639 `license-files` read the second), checked by `cmp` in CI. [`test_supply_chain_workflows.py`](rosetta-api/tests/unit/test_supply_chain_workflows.py) checks all of this statically.

*Evidence (2026-10-28).* Tags are mutable: tj-actions/changed-files tags were repointed to a commit that printed runner secrets into build logs (CVE-2025-30066, March 2025), and 75 of 76 trivy-action tags were force-pushed on 2026-03-19. With `persist-credentials` left at its default, the checkout writes the job's token into the git configuration, where any later step and any uploaded workspace can read it (zizmor `artipacked`). Before this change zizmor 1.31.1 reported 25 findings in `ci.yml` (12 tag-pinned actions, 7 missing permission blocks, 6 checkouts keeping credentials) and 8 pedantic findings in the other workflows; after it, none.

### Release page

*Rule.* A final version's GitHub release is made by the release workflow, never by hand while the workflow can run: job `publish-release` creates it as a draft, attaches the files job `release-assets` collected, downloads the attached copies and checks them against `SHA256SUMS`, and only then publishes it. The files are the wheel and sdist PyPI received, one SPDX SBOM (`sbom-<id>.spdx.json`) and one source notice (`NOTICE-<id>.txt`) per published image, `openapi-<version>.json` written from the tagged code, `qrosetta-<version>-images.txt` (every published image by digest with its `cosign verify` and `gh attestation verify` commands), `SHA256SUMS`, and `qrosetta-<version>.intoto.jsonl`, the Sigstore bundle of one build-provenance attestation whose subjects are every file in `SHA256SUMS`. A pre-release tag gets no GitHub release (its images and TestPyPI wheel are published, and `release-assets` still runs, so a release candidate rehearses everything but the release page). Both jobs run only for a tag pushed to the public repository; the job that holds the OIDC token checks out no code and installs nothing, and only `publish-release` may write repository contents. A final tag stops in `plan` unless `CHANGELOG.md` has a dated section for its version, and no image is pushed unless the API description could be written. The order of a release and the clean-machine checks are in [`docs/RELEASING.md`](docs/RELEASING.md). [`test_release_workflow.py`](rosetta-api/tests/unit/test_release_workflow.py) and [`test_release_assets.py`](rosetta-api/tests/unit/test_release_assets.py) check it.

*Evidence (2026-10-28).* GitHub immutable releases lock a release's assets at publication, so assets attached afterwards are refused (GitHub Docs, "Immutable releases"). OpenSSF Scorecard's Signed-Releases check reads only release assets, and scores provenance (`*.intoto.jsonl`) above signatures; attestations in GHCR or GitHub's attestation store do not count. Zenodo archives every published GitHub release, and its handling of pre-releases was not verified, so none is made. actions/attest at the pinned commit writes the bundle as one JSON line, which `gh attestation verify --bundle` reads.

### Timing caveats

*Rule.* [`rosetta-api/services/timing_caveats.py`](rosetta-api/services/timing_caveats.py) derives `timing_caveats` per result and per report from recorded fields only: `shared_dispatch`, `overlapping_runs`, `server_overlapping_runs`, `throttled` and `compilation_throttled` (≥ 1% of the window), `unstable_repeats` (> 1.3× with ≥ 3 samples), `mixed_cores` (classes 10% apart), `outside_process` (≥ 5 ms and ≥ 10%), `single_timed_run`, `no_cpu_quota`, `virtualised_host`, `emulated_cpu`, `non_x86_64`, and across backends `cross_backend_core_speeds`, `cross_backend_cpu_quota`, `cross_backend_image_commits`. Each has a code, a sentence and its fields. It is the only implementation of the page's "throttled", "outside process", "unstable" and "mixed cores" tags and its "Before comparing times" list; the page renders the server's records, and asks `POST /timing-caveats` for a report stored without them. The rules carry `timing_caveats_version`, not `ANALYSIS_VERSION`: they change no agreement label, and bumping the analysis version would mark unchanged agreement evidence as changed. The publication tables keep their own unstable rule (`tables.py` / `artifact_formats.js`, under the parity test).

*Evidence (2026-10-27).* Against the JavaScript of 7e02220 ([`scripts/timing_caveats_equivalence/compare.py`](scripts/timing_caveats_equivalence/compare.py)): 351 saved reports (4,968 results, from play-test, Apptainer and Roihu runs) and 20,000 synthetic reports around every threshold (59,975 results): 0 differences in the four tags and the phrase list.

### Run completeness

*Rule.* Every finished job's report records `run_completeness` (`job_status`, `planned_tasks`, `recorded_tasks`, `tasks_with_results`, `stopped_early`, `reason`). The crate root states `#run-completeness`: `complete`, `partial`, `failed`, `not_recorded` (older reports) or `not_checked` (a report the server did not produce, such as the browser's copy exported after the server's copy expired); any value but `complete` is repeated in the root description.

*Evidence (2026-10-27).* A crate of a stopped playlist or of the browser's fallback copy read like a complete run: each execution was a Completed CreateAction and nothing stated the planned set.

### Citation metadata

*Rule.* `CITATION.cff`, `.zenodo.json` and `codemeta.json` (CodeMeta 3.0) give one title, version, licence, author list (names, affiliations, ORCIDs where given), repository, description and keyword list; the version is `qrosetta_cli.__version__`, so a release changes all four together; `pyproject.toml` names the same authors, licence and repository ([`rosetta-api/tests/unit/test_citation_metadata.py`](rosetta-api/tests/unit/test_citation_metadata.py)).

*Evidence (2026-10-28).* When a repository holds both `CITATION.cff` and `.zenodo.json`, Zenodo archives a GitHub release with `.zenodo.json` only (help.zenodo.org, "Describe your software"), so a correction made in one file alone does not reach the DOI record. Before this, neither file named a version.

### cirq statevector bits

*Rule.* cirq amplitudes can differ run to run by ~1e-17 (numpy 1.26 SIMD complex loops depend on buffer alignment). Left as is: disabling SIMD would slow cirq and bias timings. Compare replayed statevectors by fidelity, not sha256.

*Evidence.* 382/4096 amplitudes differed by ≤ 5.7e-17 on a 12-qubit circuit; bit-stable with NPY_DISABLE_CPU_FEATURES.

### Licences of bundled circuits in exports

*Rule.* An RO-Crate or experiment bundle that contains a bundled MQT Bench or QASMBench circuit (a playlist or experiment entry with `source` `mqt` or `qasmbench`, not literal text) also contains that suite's licence text under `licenses/`; in a crate the circuit's File entity names it as its `license` and says where the circuit comes from (mqt.bench 1.1.9; pnnl/QASMBench at commit 357b942). The crate's own licence (CC BY 4.0) stays on the crate. A circuit pasted into the editor is literal text and gets no licence file ([`rosetta-api/services/bundled_licences.py`](rosetta-api/services/bundled_licences.py), [`rosetta-api/tests/unit/test_bundled_licences.py`](rosetta-api/tests/unit/test_bundled_licences.py)).

*Evidence (2026-10-28).* Crates and experiment bundles copied bundled circuits verbatim and declared the whole crate CC BY 4.0. MIT asks that its notice accompany copies; the Battelle licence asks that redistributions retain its copyright notice and disclaimers. The 58 QASMBench files and their `LICENSE` have the git blob hashes of the files of the same names at pnnl/QASMBench commit 357b942 (2025-01-20) and differ from its parent in two files, so that commit is the version bundled.

### Source notice of a published image

*Rule.* Every image the release workflow publishes gets `NOTICE-<id>.txt`, written by [`scripts/release/image_notice.py`](scripts/release/image_notice.py) from the pushed image: its digest, the base image of the final stage, and each Debian source package at its installed version with its snapshot.debian.org address (nginx: each Alpine origin with its aports commit). The base image's archive date is the snapshot date Debian's official images write in a comment of their apt sources; an install date is printed only when an apt source line names snapshot.debian.org. The script reads the image through a created container that it removes and never starts ([`rosetta-api/tests/unit/test_image_notice.py`](rosetta-api/tests/unit/test_image_notice.py)).

*Evidence (2026-10-28).* Generated for all 21 release images from the local stack's builds: 87 to 149 Debian packages from 61 to 80 source packages per image (71 Alpine packages from 59 origins for nginx), base archive date 20260316T000000Z; six nginx.org packages in nginx have no aports commit and are named with their packager. The apt sources of every image point at deb.debian.org, so packages a Dockerfile adds (build-essential in qrisp, quimb and torchquantum; libgomp1 in quartz and synthetiq) have no recorded archive date until the Dockerfiles use a snapshot.

## Security and accounts

### Share links

*Rule.* Saved runs only; token `secrets.token_urlsafe(32)`, only its SHA-256 stored, shown once; expiry 1–90 days (default 30), ≤ 10 active per run, revocable. The token travels in the URL fragment and a POST body; the response is the `circuit_texts` allowlist ([`rosetta-api/services/circuit_texts.py`](rosetta-api/services/circuit_texts.py)) with `Cache-Control: no-store`, `Referrer-Policy: no-referrer`; 30/minute. A deactivated account, a deleted run or a deleted account ends every link.

*Evidence (designed 2026-10-01).* Jobs live 30 minutes and are not tied to an account; a GET path would put the token in access logs.

### Who may save a job

*Rule.* A job submitted with a valid token records the submitting account's user id (`JobTable` keeps it across replacements); only that account may save it (403). Anonymous jobs stay saveable by whoever holds the job id.

*Evidence.* Any account holding a job id could save it as its own run.

### Saved-run access and delete order

*Rule.* `POST /history/runs?circuit_id=` returns 404 unless the circuit belongs to the caller; this is checked before the report is stored. `delete_runs` and `delete_account` delete and flush the rows, then delete the stored reports, then commit, and roll back if either step fails. Account deletion sets `circuit_id` to NULL on other accounts' runs that name its circuits.

*Evidence (2026-10-07).* Any account holding a circuit UUID could link a run to it. On PostgreSQL, deleting that circuit's account (`DELETE /auth/me`) then failed on the foreign key after its S3 reports were already deleted, leaving run records without their reports.

### Client address

*Rule.* The client address (`security.client_address`, used by every rate-limit key and the exclusive-run slot) is `X-Qrosetta-Client-Ip` when the request carries the matching `QROSETTA_PROXY_TOKEN`; else the last X-Forwarded-For entry when the socket peer is a trusted proxy; else the socket peer. `QROSETTA_TRUSTED_PROXIES` lists the trusted proxies as comma-separated IP addresses, CIDR networks, host names or `*` (any peer). Unset, it is `nginx` in local mode (the compose service name, resolved on `isolated_net`) and `*` in Kubernetes mode; set and empty, no peer is trusted. A host name is resolved again when a peer outside the list sends X-Forwarded-For, at most once every 5 s, and the request waits at most 0.5 s for it, so a recreated nginx container is trusted at its new address. `GET /config` publishes nothing about the list. ([`rosetta-api/tests/unit/test_v5_06_trusted_proxies.py`](rosetta-api/tests/unit/test_v5_06_trusted_proxies.py))

*Evidence (2026-10-07).* The API keyed on X-Real-IP, which the router passed through from the caller, and the hosted frontend set it to its own peer, so every visitor through that frontend shared one key.

*Evidence (2026-10-28, V5-06).* From inside `pytket-qulacs-runner`, 12 failed sign-ins sent straight to `rosetta-api:8000`, each with a different X-Forwarded-For, all got 401 and none 429; without the header the 11th got 429. Every runner and compiler shares `isolated_net` with the API. nginx's address on that network is assigned per container (10.89.0.26 on the running stack), so the default names the service rather than an address. Kubernetes keeps `*` because the OpenShift router's source addresses are not fixed, so a runner Job pod there can still choose its key; set the router's network in `QROSETTA_TRUSTED_PROXIES` to close it.

### Rate-limit keys

*Rule.* A request whose bearer token has this server's signature, an unexpired `exp`, `iat`, `sub` and an integer `uid` is counted as `account:<uid>`; one carrying the local lifecycle token as `lifecycle`; every other request, including one with an expired, foreign or unsigned token, as `address:<client address>` ([`rosetta-api/services/security.py`](rosetta-api/services/security.py) `rate_limit_key`). The key function reads no database: a token of an account deactivated, deleted or signed out after it was issued keeps its account's count until it expires (30 minutes). Sign-in, registration and `POST /shared/circuits` are counted per client address only. Runs, exports, circuit lookups (every `limits.run_rate_limit` route) and the two publication render routes also count against a ceiling per client address, `limits.run_rate_limit_per_address` (60 a minute) and `limits.render_rate_limit_per_address` (240 a minute); a request must be within both, and the account's own limit is counted first, so an account over its limit does not use the ceiling. Counters are per route (`key_style="endpoint"`), not per URL. X-RateLimit-* report the limit with the fewest requests left. Fresh probes (`?fresh=true`) count per account, the lifecycle token as one client. The exclusive-run slot stays per client address. ([`rosetta-api/tests/unit/test_account_rate_limits.py`](rosetta-api/tests/unit/test_account_rate_limits.py))

*Evidence (2026-10-28).* Users behind one NAT shared every limit. Reading the account from the database on every limited request would block the event loop (the key function is synchronous) for at most one extra budget per deactivated account for at most 30 minutes; the signature check costs 14 µs per request against 3 µs for the address alone. Without the ceiling, registering accounts (5 a minute per address) would multiply an address's run budget without bound. Before this, slowapi's default `key_style="url"` counted each path separately, so `/jobs/<id>/export` and `/jobs/<id>/publication/render` had a separate budget per job id.

### Upload limit

*Rule.* Every POST, PUT and PATCH body is limited in the API itself (`MAX_UPLOAD_BYTES`, 4 MiB on `/plan`), whatever is in front of it: a Content-Length over the limit is refused at once, and a body without one (chunked) is counted as it arrives and refused with 413 at the first chunk over the limit. nginx's 5 MB cap is a second bound, not the only one.

*Evidence (2026-10-28).* The API checked only the Content-Length header, so a chunked body of any size reached the routes wherever nginx was not in front (a direct port, the Rahti `rosetta-api-route`) (`test_v1_04_chunked_upload_limit.py`).

### Cross-site requests

*Rule.* A POST, PUT, PATCH or DELETE that a browser sent from another site is refused with 403 `{"detail": "Requests from other sites are refused."}` before any route, body or rate limit runs ([`rosetta-api/routers/same_origin.py`](rosetta-api/routers/same_origin.py), the outermost middleware). With an `Origin` header the request passes when the origin is in `get_cors_origins()` (`http://localhost`, `http://127.0.0.1` and `CORS_ALLOW_ORIGINS`) or names the host and port the browser addressed: the `Host` header, or `X-Forwarded-Host` when the request carries the matching `QROSETTA_PROXY_TOKEN` (the Cloud Run frontend). The scheme is not compared, because the API sees plain http behind both TLS proxies; a Host without a port matches the origin's default port only. `Origin: null` and a value that is not an origin are refused. Without `Origin`, `Sec-Fetch-Site: cross-site` or `same-site` is refused and anything else (the CLI, curl, scripts) passes. GET, HEAD and OPTIONS are not checked. A JSON route answers 415 to a body without a JSON Content-Type ("Web framework versions"). Local nginx passes the browser's Host with its port (`$http_host`) and the frontend's nginx sets `X-Forwarded-Host`; a page served by an nginx image older than this rule gets 403 on every POST until the `nginx` image is rebuilt with the `api` image. OpenAPI declares 403 on every state-changing route and 415 on every JSON-body route. ([`rosetta-api/tests/unit/test_v1_03_cross_site_requests.py`](rosetta-api/tests/unit/test_v1_03_cross_site_requests.py))

*Evidence (2026-10-28).* With no Origin check and `strict_content_type=False`, a page on any site could start statevector, measured, playlist and experiment jobs on a local server (anonymous `bypass_limits` is allowed in local mode) with a POST that needs no preflight, loading the host during the user's timed runs, and sign a visitor in to an account of its choosing through the `/auth/token` form. Bearer-token routes were not reachable this way, since an `Authorization` header forces a preflight that CORS refuses. Of the 111 tests in the file, 101 fail on the old code; the 10 that pass check that same-origin, allowed-origin and no-Origin requests, reads and preflights still work. Refused requests use no rate-limit budget: 15 refused registrations from another site and 15 with `text/plain` leave the 5-a-minute budget whole. Fuzzing at 300 examples per operation (seed 0, 21,621 calls) gives 0 findings.

### Size of client-supplied reports

*Rule.* A report a client supplies (export, saved-run upload, summary, publication catalog and render) holds at most `MAX_REPORT_TASKS` circuits (1000), at most `MAX_TOTAL_RUNS` runner results, compiled circuits and divergence-report backends per circuit (matrices at most that wide), and at most that many backends' pairs in `pairwise_agreement` and `divergences_found`; GET /config `limits` publishes them as `max_report_tasks`, `max_report_runner_keys` and `max_report_pairs`. No server job produces more. A figure render from the publication routes waits at most `RENDER_LOCK_WAIT_SEC` (20 s) for the matplotlib lock and then answers 503 with Retry-After 10; crate builds wait without a limit.

*Evidence (2026-10-28).* `report_validation.py` had no count caps, the heatmaps draw n x n cells under one global lock with no timeout, and the render route allows 120 requests a minute, so one report with thousands of keys could hold every render for minutes (`test_v1_05_supplied_report_caps.py`).

### What the CLI trusts

*Rule.* The CLI reaches servers over http:// and https:// only (a server URL needs a host; its opener has no file, ftp or data handler), sends a token over plain HTTP only to loopback or a server with `allow_insecure_http`, and follows a redirect to another origin without the Authorization header. It names files and directories after a server's job id only when the id is a canonical UUID (else exit 12 `bad_job_id`, nothing written for it). `qrosetta images load` refuses an archive whose manifest.json RepoTags or OCI index name any tag other than the one qrosetta computes for that service, so `<engine> load` cannot retag another image.

*Evidence (2026-10-28).* urllib's redirect handler copied Authorization to the redirect target; `QROSETTA_SERVER=file:///...` passed the `://` check and reached urllib's FileHandler; `job_id` went into result paths unchecked; `<engine> load` applies tags embedded in an archive and the fake engine did not model it (`test_v1_06_cli_trust_boundaries.py`).

### Job spill directory

*Rule.* At startup an existing `QROSETTA_JOB_SPILL_DIR` must be a directory (not a link) owned by the API process's user; it is removed and created again with mode 0700, and the API does not start otherwise. The API unpickles only files this process wrote (`job_store._write_pickle` records each one); `pickle.load` and `pickle.loads` appear only in `job_store.py`, `prep_worker.py` (its own child's pipe) and `qrosetta_commons/helpers.py` (`test_v1_11_spill_dir_and_pickles.py` checks it).

*Evidence (2026-10-28).* `reset_spill_dir` ignored its own errors and `makedirs(exist_ok=True)` accepted a directory another user had created in a shared `/tmp`, so a pickle planted there would have been loaded by the API.

### Name fields

*Rule.* One combined validator per name type (`label_type`), never nested. A version-independent code-point list; blank names are refused.

*Evidence (2026-10-08).* pydantic 2.9.2 dropped nested validators: `RunHistoryUpdate(run_name='a\x00b')` passed.

### Database schema migrations

*Rule.* The schema is versioned with Alembic (`rosetta-api/migrations/`); the API upgrades to head in its startup handler, never on import ([`rosetta-api/db/migrate.py`](rosetta-api/db/migrate.py)), under a lock: an exclusive `flock` on `<database>.migrate-lock` for SQLite, `pg_advisory_xact_lock` for PostgreSQL. A database without `alembic_version` that holds any of the four tables is brought to revision `0001` (missing tables, nullable columns and indexes added; a missing non-nullable column stops startup) and stamped. `create_all` and `add_missing_nullable_columns` are gone. `test_db_migrations.py` checks that the baseline emits the models' DDL on SQLite and PostgreSQL and that autogenerate finds no difference from the models.

*Evidence (2026-10-28).* `add_missing_nullable_columns` added `run_histories.job_id` to databases created before it without the column's index: a copy of the local stack's database (54 users, 132 runs, 69 share links) had no `ix_run_histories_job_id`; adopting the copy added the index, kept every row, and left no difference from the models. Eight processes running the former import-time `create_all` on one new SQLite file at once: 19 of 20 trials had a process fail with `table users already exists`; the same with `upgrade_database`: 0 of 20. The unit tests' xdist workers all inherited the controller's `DATABASE_URL`, so this race broke collection on the integration branch. Four processes in `test_concurrent_starts_migrate_once` failed in 4 of 6 runs with the lock removed and passed in 5 of 5 with it.

### Regular expressions on submitted text

*Rule.* A regular expression applied to text a client submits (circuits, names, report fields) runs in linear time: no `\s*` or `.*?` that can scan to the end of the text from many start positions, and no ambiguous nested repeats. `scripts/fuzz/redos.py` lists every literal pattern in the API, the shared package, the runners and the compilers and times each on 1 MB adversarial inputs (methods as the code calls them); API-side ones stay under 1 s. Runner and compiler patterns are measured and recorded, and changed only with an image requalification.

*Evidence (2026-10-28, V6).* `^\s*OPENQASM` (MULTILINE, `search`) in the validator scanned every following blank line from every line start: 40,000 newlines took 1.7 s, a 1 MB body about 18 minutes of one API worker. `bare_circuit_name` (`/plan`, bodies up to 4 MiB) took 0.42 s on a name of 20,000 spaces and grows with the square. Runner side, with preprocessing off: 80,000 blank lines cost qibo's barrier removal 13.7 s and quimb's `p` rewrite 46.6 s (`defects-V6.md`).

## Interface and API behaviour

### Outcome names and roles

*Rule.* Every summary (`GET /jobs/{id}/summary`, `POST /summary`, saved runs) counts `outcomes`: each pair under its `pair_verdict` value, `no_comparison` (1 when no pair was compared) and `runs_without_output` (runs whose status is not ok, plus 1 for a circuit that never reached a runner); a playlist's are sums over its tasks. `outcome_roles` gives each name's role (difference, not_established, runs_without_output, agreement), published also as `GET /config` `summary_outcomes` with the analysis version. `qrosetta run --fail-on` maps a name to its exit code by role (3, 8, 4) and holds no list of names ([`rosetta-api/tests/unit/test_summary_outcomes.py`](rosetta-api/tests/unit/test_summary_outcomes.py)).

*Evidence (2026-10-27).* CLI spec v3 critique INT-M8: a final line reading "0 differ" when nothing was compared reads as agreement. A CLI copy of the verdict-to-exit mapping would be a second implementation of part of the rule, which is computed only in `verdicts.py`.

### Runner status label

*Rule.* The live Status cell for a dispatched run reads SENT (tooltip: includes any wait behind another job, recorded as queue_wait_sec).

*Evidence.* The API cannot see when the runner's slot frees; a 2-qubit Quartz compile waited 35 s behind another client's compile while shown RUNNING.

### Figures

*Rule.* Figures use the long display names (`RUNNER_DISPLAY_NAMES` in [`rosetta-api/static/js/runner_key.js`](rosetta-api/static/js/runner_key.js) ↔ `BACKEND_DISPLAY_NAMES` in [`rosetta-api/services/publication/theme.py`](rosetta-api/services/publication/theme.py)), and render requests send the circuit name. The slide canvas is fixed at 16:9.

*Evidence (2026-10-08).* A slide figure rendered at 4149 × 1956 px (2.12:1) titled "unnamed circuit", with legends reading qsim-cirq, pennylane-lightning.

### Quirk visualizer

*Rule.* Every gate is drawn with its matrix up to phase, or the request is refused. At most 16 qubits and 1,000 columns.

*Evidence.* Only h/x/y/z/cx were drawn, and comments became gates.

### Browser state

*Rule.* Every control has `autocomplete="off"` and state is reset on `pageshow`. Jobs are kept per account (pending/stopped 6 h, finished 30 min). Expiry uses the server clock (`iat`). Two columns from 1024 px. Modal dialogs use [`modal.js`](rosetta-api/static/js/modal.js); announcements go through [`announce.js`](rosetta-api/static/js/announce.js).

*Evidence.* The bypass-limits checkbox ticked itself after a reload; stopped jobs were lost; a run leaked across accounts; pages failed WCAG checks.

### API error contract

*Rule.* Every route declares the codes it raises ([`rosetta-api/tests/unit/test_openapi_contract.py`](rosetta-api/tests/unit/test_openapi_contract.py)). 422 means a schema failure; 400 means well formed but unsupported; 415 means a body without a JSON Content-Type on a JSON route. X-RateLimit-* headers, and Retry-After on 429. `expires_in`; `RunHistory.job_id`; JSON 413 from nginx; nginx compresses responses. Non-UTF-8 JSON bodies are 422 `json_invalid`; non-finite numbers in a client-supplied report are 400; file and page responses declare their real media types. [`scripts/api_fuzz/run_fuzz.py`](scripts/api_fuzz/run_fuzz.py) (Schemathesis, in process) checks the contract.

*Evidence (2026-10-21).* Fuzzing at 300 examples per operation, 17,412 calls: 0 findings after four fixes (media types, UTF-8 bodies, malformed supplied reports, and NaN stored in a saved run, which made every later read return 500).

### Error text sent to clients

*Rule.* Jobs, reports and responses carry an exception's message only when the API wrote it for the request: an HTTPException's detail, a ValueError (circuit resolution and preparation) or a PreparationFailed, and a full job store's reason. Any other exception reaches them as its type only (`Analysis failed (KeyError)`, `The experiment failed (MemoryError)`); its text and traceback go to the API log with the job id (`services/error_text.py`). Runner and compiler errors keep the SDK's message, which the page shows on purpose, with absolute file-system paths replaced by `<path>` (`qrosetta_commons.redact`); this runs in `runner_error`, `compiler_error` and the isolated child's error path, after the timed windows.

*Evidence (2026-10-28).* The job worker, the analysis step, the experiment worker and the bundled-file reader stored `str(e)`, so an OSError showed container paths (§13.3); only the batch path had been reduced to the type (`test_v1_02_exception_text.py`).

### Engine call timeouts

*Rule.* Every engine and compose command qrosetta runs has a timeout: 4 hours for builds and image transfers (build, pull, push, load, save, and `scripts/safe_boot.sh`), 15 minutes for commands that change containers, networks, volumes or tags (including `compose up`), 2 minutes for the rest. A command past its timeout is stopped and the qrosetta command exits 16 `engine_timeout`; the engine lock is released and the host-load notice ended on the way out. A heartbeat answered 404 (the server no longer holds the notice: it expired or the server restarted) stops the heartbeats with a warning, and no end is sent.

*Evidence (2026-10-28).* Engine calls had no timeouts apart from `info`, `--version`, `compose version`, cosign and sysctl, so a hung podman kept the engine lock while the heartbeat kept the host-load notice, and with it the run gate, open; heartbeat 404s were ignored (`test_v1_12_engine_timeouts.py`).

### CLI retries

*Rule.* The CLI repeats a request that starts no work on the server (GET, and POST to the export, summary, publication and plan routes) when it gets no answer, the transfer breaks off, or the server answers 502, 503, 504 or 429 with Retry-After of at most 30 s: up to three more times, after 1, 2 and 4 s; a download starts again from the beginning. A run (POST /compare, /compare_measured, /run_batch_suite, /experiments) is never sent twice. A download shorter than its Content-Length is a broken transfer. Waiting for a job rides out failed polls as in "Waiting through an API restart". Downloads give the server 330 s per socket operation (nginx's own read timeout), since a crate is built before its first byte.

*Evidence (2026-10-28).* `http.client.IncompleteRead` was not caught, so a dropped download ended `qrosetta run` as an internal error with no STATUS; `read(amt)` returned a short body without an error, so a cut-off download could be saved as complete; polls and downloads had no retry and a crate had 30 s to send its first byte (`test_v1_08_cli_transfer_retries.py`).

### Waiting through an API restart

*Rule.* The page and the CLI keep polling a job while the server gives no answer: a refused connection, or 502, 503 or 504 from the proxy (the page also retries any other error status). The next poll comes after 3, 6, 12, 24, then every 30 s, for up to 5 minutes from the first failed poll; the page shows that it is waiting for the server. A 404 for the job ends the wait: on the page as a terminal error that, after failed polls, says the restart lost the job; in the CLI as exit 14 `job_lost`, with STATUS `job-lost` in the job's directory (so `wait --all` does not wait for it again), the planned jobs not submitted, and `qrosetta run --request <plan.json>` as the hint. After 5 minutes without an answer the page stops waiting and keeps the job in its list of earlier runs, and the CLI exits 11 with `qrosetta wait job:<id>` as the hint. nginx answers a 502 or 504 it generates itself (the API cannot be reached, or did not answer in 330 s) with a JSON `detail`; a 502 or 504 the API sends passes through. Neither client shows an HTML error page as source: the page and the CLI name it as a proxy's error page.

*Evidence (2026-10-28, V7).* An API restart loses every job in memory, and while it restarts nginx answers with its HTML 502 page. The page stopped polling after 19.5 s with "Failed to fetch job status: 502", before the API was back, and a submit printed the HTML source. The CLI gave up after five failed polls (about a minute with its own retries), printed the HTML source, and on the restarted server's 404 exited 14 with no STATUS, so `wait --all` kept offering a job that no longer existed (`test_v7_api_restart.py`, `test_v7_cli_lost_job.py`). In `test_v7_live_restart.py` the API process, killed while `qrosetta run` waited and started again under uvicorn, answered `/health` 3.7 s later (2.8 s on its first start); a container recreate adds the engine's own start time. Five minutes covers that with room to spare, at the cost of one poll every 30 s.

### API compatibility for older CLIs

*Rule.* The routes the stable `qrosetta` commands read are held to a committed, normalised extract of `/openapi.json` ([`rosetta-api/tests/openapi_cli_baseline.json`](rosetta-api/tests/openapi_cli_baseline.json)). A change that removes a route, method, parameter or field, makes a request field required, narrows a request type or enum, changes a success status or media type, or lets a response field be missing or of a new type fails [`rosetta-api/tests/unit/test_openapi_cli_contract.py`](rosetta-api/tests/unit/test_openapi_cli_contract.py) unless the maximum of `API_LEVELS` (`GET /config` `server.api_levels`) was raised; the previous level stays served for 12 months. `GET /config`, `/runners`, `/compilers` and the circuit catalog routes document their responses with models in [`rosetta-api/schemas/listings.py`](rosetta-api/schemas/listings.py) that never filter them (`response_model` stays unset). The refresh command is in CONTRIBUTING.md.

*Evidence (2026-10-27).* CLI spec v3 S16: a pipx-installed CLI outlives server upgrades, and before this the five most-read routes documented no response schema, so a removed field would have shown up only as a CLI failure on a user's machine. Adding the documentation models left the status, headers and body bytes of 18 TestClient calls on those routes unchanged.

### Health and readiness

*Rule.* `GET /health` answers `{"status": "ok"}` from the API's event loop and reads nothing else; the compose healthcheck of `api` and the Rahti startup and liveness probes call it. `GET /ready` is 200 only when the database answers `SELECT 1` through the API's engine and the job spill directory takes a new file (`tempfile.TemporaryFile` there: O_TMPFILE where the file system has it, so no name is created, else a file unlinked as it is opened), and otherwise 503 with `detail` naming the failed checks; the Rahti readiness probe, `qrosetta start -d` and `qrosetta doctor` call it when `GET /config` lists the `readiness` feature. Each check runs on the readiness module's own two threads with a 2 s limit, a check still running is not started again, and a result less than 1 s old is reused. Neither route needs a sign-in or is rate-limited, and neither returns hosts, paths or exception text ([`rosetta-api/services/readiness.py`](rosetta-api/services/readiness.py), [`rosetta-api/tests/unit/test_health.py`](rosetta-api/tests/unit/test_health.py)). Rahti liveness allows 6 minutes without an answer, longer than gunicorn's 330 s worker timeout, because a restart loses every job held in memory. Runner and compiler images register `GET /health` beside `/capabilities`; it never waits for an execution slot.

*Evidence (2026-10-27).* The compose healthcheck polled `GET /algorithms`, a catalog route, so the API counted as healthy while its database or job storage failed, and nothing outside the API could tell. On the default executor a database connection that never answers would hold threads that the circuit preparation and report writing also take; with its own pool of two, three probes against a hanging check started it once (`test_a_hanging_database_check_times_out_and_is_not_started_twice`). The storage check makes the same call `job_store` makes to build exports, so it fails where that call fails (permissions, SELinux labels, a missing directory), for one open and one close.

### Web framework versions

*Rule.* The API runs FastAPI 0.136.3 on Starlette 1.7.0, the newest Starlette that supports the image's Python 3.10 (1.8 needs 3.11). The app sets `default_response_class=JSONResponse`, so response models are written by `json.dumps` with `allow_nan=False`, and `strict_content_type=True`, so a body is read as JSON only with an `application/json` (or `+json`) Content-Type; any other body sent to a JSON route, including one without Content-Type, is a 415 (see "Cross-site requests"; [`rosetta-api/tests/unit/test_web_framework.py`](rosetta-api/tests/unit/test_web_framework.py)). Runner and compiler images stay on FastAPI 0.115.0 and Starlette 0.38.6; the shared scaffolding registers its startup hook with `app.router.add_event_handler`, which both versions provide.

*Evidence (2026-10-27).* OSV lists seven advisories (CVEs) for Starlette 0.38.6. Three concern form parsing, which `/auth/token` uses (PYSEC-2026-1943, -1941, -249), and -249 (urlencoded form limits ignored) is fixed only in 1.3.1. FastAPI accepts Starlette 1.x from 0.133.0. FastAPI 0.137 turns `router.routes` into a tree, and 0.147–0.162 change how omitted, empty and null body and form values are read, so 0.136.3 is the last release before those changes. With FastAPI's default response class, 0.130 and later write response models with Pydantic's `dump_json`: a NaN becomes `null` where `json.dumps` raised (a 500), and 1e-05 is written `0.00001`. With both settings, 260 requests to the full app (every route, error bodies, form and Content-Type variants, static files, 429) differ from 0.115.0/0.38.6 only in: `Vary: Origin` on every response (Starlette 1.7 CORS); `Accept-Ranges: bytes` and 206 range responses on files; an empty login field is a 422 (missing field) instead of a 401; a bearer token with surrounding spaces is accepted; a login form of more than 1,000 fields is a 400 (the -249 fix). ZIP and PNG responses are no longer gzip-encoded by the API (Starlette 1.5 excludes those types). OpenAPI: the login form's `grant_type` pattern is anchored (`^password$`), password fields carry `format: password`, `RunHistoryResponse-Input`/`-Output` merge into `RunHistoryResponse`, `ValidationError` lists `input` and `ctx`, and the login route's 400 description names the field limit. Fuzzing at 300 examples per operation (seed 0, 20,718 calls) gives 0 findings on both versions; the status counts differ only for `POST /auth/token`, where more generated forms are 422 (empty fields, `grant_type` values that only contain `password`).

*Evidence (2026-10-28).* `strict_content_type=False` was kept on 2026-10-27 to accept clients that omit the header. No client does: the page sends `application/json` with every JSON body and a form only to `/auth/token`; the CLI sets the header in `Conn.request`, `Conn.download`, `export`, `figures`, `show`, `account` (form) and `hostload`; the experiment and harness scripts send JSON. A JSON body without Content-Type is what a page on another site can send without a CORS preflight (a `Blob` body or `navigator.sendBeacon`), and the API read it as JSON and started the job (`test_v1_03_cross_site_requests.py`, which fails on the old setting). The 415 comes from the validation handler: FastAPI passes the raw bytes as the body when it did not read JSON, so a non-empty bytes body in a validation error means the Content-Type was not JSON. The full unit suite (3,011 tests) passed unchanged with the setting on.

### Swagger UI served from this server

*Rule.* `/docs` loads Swagger UI (`swagger-ui-dist` 5.33.2) from unmodified copies in [`rosetta-api/static/vendor/swagger-ui/`](rosetta-api/static/vendor/swagger-ui/), served at `/vendor/` by nginx (from its image, cached as immutable) and by the API (a static mount); the sha256 of each copied file is in `manifest.json` there with the npm tarball's integrity hash. The page has no inline script: [`js/api_docs_main.js`](rosetta-api/static/js/api_docs_main.js) starts Swagger UI with FastAPI's default options and `validatorUrl: null`, and reads the OpenAPI address from a `data-` attribute, so the page runs under `script-src 'self'` ([`rosetta-api/tests/unit/test_swagger_ui_vendor.py`](rosetta-api/tests/unit/test_swagger_ui_vendor.py)). A version change replaces the directory, the manifest and `SWAGGER_UI_VERSION` in `routers/frontend.py` together. `/redoc` still loads ReDoc from jsDelivr.

*Evidence (2026-10-27).* The page loaded Swagger UI 5.17.14 from cdn.jsdelivr.net, so `/docs` could not render without access to that host, and FastAPI's page starts Swagger UI from an inline script. Headless Chrome with every host but 127.0.0.1 unresolvable, through nginx with `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'` and a `report-uri`: all 57 operations rendered, an expanded operation drew its example and responses table, and no violation was reported; `/redoc` under the same policy sent two reports. OSV lists no advisory for `swagger-ui-dist` 5.33.2. The bundle includes DOMPurify 3.4.16, for which OSV lists three advisories fixed in 3.4.17 (GHSA-c6gr-qvv4-5v3f, GHSA-cg2g-xh64-v4q7, GHSA-mrv2-3pqr-j5jr); each needs the XHTML parser mode, `SAFE_FOR_TEMPLATES` or `IN_PLACE`, and Swagger UI calls `sanitize` with none of them. 5.34.0, the newest release, bundles the same DOMPurify.

### Browser security headers

*Rule.* Every response carries `Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Cross-Origin-Opener-Policy: same-origin` and `X-Frame-Options: DENY`. The API sets them on everything it serves ([`rosetta-api/routers/security_headers.py`](rosetta-api/routers/security_headers.py), a header a route sets itself is kept); nginx sets the same values on the files it serves and its own error responses, and adds nothing to a proxied response that already has the header (`map $upstream_http_…` in both nginx configs, `add_header_inherit merge`). The policy depends on the response: the page and every other HTML file, `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; connect-src 'self'; font-src 'self'; frame-src https://quirk-e.dev; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'`; the share page, the same without connect, font, blob and frame sources and with `form-action 'none'`; `/docs`, the Swagger UI policy; `/redoc`, a policy of its own that allows ReDoc 2.1.5's script by its exact jsDelivr URL, its logo, a blob worker and `style-src 'unsafe-inline'` (ReDoc injects `<style>` elements); every other response (JSON, SVG, downloads, scripts), `default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'`. The pages have no inline script, event handler, `<style>` element or `style` attribute: `js/main.js` wires the controls of `index.html` with `addEventListener` from one table, and nothing but `dispatch`/`getState` is published on `window` ([`rosetta-api/tests/unit/test_inline_handlers.py`](rosetta-api/tests/unit/test_inline_handlers.py), [`test_security_headers.py`](rosetta-api/tests/unit/test_security_headers.py)). Styles set through the CSSOM (`element.style`) are allowed by `style-src 'self'`. Every template literal that builds markup escapes each interpolation with `_escapeHtml` (or `_artHtmlEscape`) unless the interpolation is on the reviewed list in [`test_html_sinks.py`](rosetta-api/tests/unit/test_html_sinks.py). Figures are sent with `Content-Disposition: attachment`.

*Evidence (2026-10-27).* The page had no policy, no `nosniff` and no framing protection; 51 inline handlers and two `<style>` blocks (index.html, docs.html) and an inline script (docs.html) would have been blocked. Headless Chrome 155 against nginx 1.31.1 (the pinned base image) with the API in process and a `report-uri` added to every policy: loading the page, Load, all six settings popovers, Bench, Auto-Gen, the Quirk view, sign-up and sign-in, a run in both modes with four compile-only services, all five result tabs, the Exports views, a share link opened in a new page, History and a saved run in all five tabs, the Delete Account dialog, the manual, `/docs` (57 operations) and `/redoc` (119 sections) produced 0 reports; a deliberately blocked image produced 1. `/redoc` under the Swagger policy sent 2 reports; with its own policy, 0.

### Sign-in token in local storage

*Rule.* The page keeps the bearer token in `localStorage` (`rosetta_token`), not in a cookie. The Content-Security-Policy above is the protection against script injection that could read it; the API takes the token only from the `Authorization` header, so a cross-site request carries no credential.

*Evidence (2026-10-27).* A cookie would make every API route a cross-site-request target and need CSRF tokens on all of them; an HttpOnly cookie protects the token but not the session, since injected script can call the API from the page. The stored-markup sweep (runner errors, preprocessing notes, SDK versions, devices, compiler refusals, run names and circuit comments carrying `<img onerror>`, `</script><script>`, `</text><script>`, `]]>` and U+202E) opened in every tab, History and the share page with the policy removed: payloads shown as text, 0 elements created from them, 0 scripts run.

### Account deletion needs the password

*Rule.* `DELETE /auth/me` takes `{"password": "..."}` in a JSON body and deletes nothing unless it matches (403 "Incorrect password", 422 without it); attempts are limited per account at the sign-in rate (`limits.login_rate_limit`). The page asks for the password in a Delete Account dialog.

*Evidence (2026-10-27).* A bearer token alone deleted the account, its runs and circuits: a token read from the browser, or a click on a framed page before framing was refused, was enough ([`test_auth_account_deletion.py`](rosetta-api/tests/unit/test_auth_account_deletion.py)). The CLI has no account-deletion command, and the route is not among those the CLI calls (`tests/openapi_cli_contract.py`), so no API level changes.

### Access tokens

*Rule.* The API accepts a bearer token only when it is signed with `SECRET_KEY` under HS256 and carries `exp`, `iat` and `sub` (PyJWT `algorithms=["HS256"]`, `options={"require": ["exp", "iat", "sub"]}`, [`rosetta-api/services/security.py`](rosetta-api/services/security.py) `decode_access_token`); an expired `exp` or an `iat` in the future is refused, and header fields (`kid`, `jku`, `x5u`, `jwk`) are never read. The `uid` claim must be the account now registered under `sub`, the account must have existed at `iat`, and `iat` must not be before the account's `tokens_valid_after`. A deleted account's token gets 401, a deactivated account's 403.

*Evidence (2026-10-28).* RFC 8725 §3.1, 3.2, 3.5, 3.10 and 3.11 as tests: `alg` none (both spellings), HS384 and HS512 with the server's key, RS256 and ES256 headers, another key, each required claim missing, `exp` one second past, `iat` 60 s ahead, string-typed `exp`/`iat`, a numeric `sub`, another account's `uid`, an empty signature, and `kid`/`jku`/`x5u`/`jwk` naming attacker keys: all refused, and no URL is fetched ([`test_v5_tokens.py`](rosetta-api/tests/unit/test_v5_tokens.py)). `get_current_user` had decoded without requiring `exp` or `iat`; the `iat` check further down refused a token without one, so no token was accepted wrongly.

### Sign-out and password change

*Rule.* `POST /auth/logout` sets the account's `tokens_valid_after` to the next whole second (`iat` has whole seconds), so every token issued to the account until then, in any browser or `qrosetta`, gets 401 on every route that requires a sign-in, and a route where a sign-in is optional treats the request as anonymous. A sign-in issues its token no earlier than `tokens_valid_after`, waiting up to one second right after a sign-out. `POST /auth/password` (current and new password; 403 when the current one does not match, nothing changed) does the same and answers with a new token. Both are limited per account at the sign-in rate. The page's Logout calls the route and signs out locally even when the server cannot be reached; `qrosetta logout` calls it when the server offers the `logout` feature and deletes the stored token either way. The rate-limit key reads no database, so a signed-out token still counts against its account's own limits until it expires ("Rate-limit keys").

*Evidence (2026-10-28).* Logout only forgot the token in the client: a copy stayed valid for its 30 minutes (OWASP ASVS 5.0 7.4.1). There was no way to change a password (ASVS 6.2.2). Tested on all 19 routes that require a sign-in, with three sign-in/sign-out cycles in a row each giving a working token ([`test_v5_tokens.py`](rosetta-api/tests/unit/test_v5_tokens.py)). Revision `0002` adds the nullable column.

### Sign-in for an unknown email

*Rule.* A sign-in for an email with no account checks the password against a bcrypt hash of a random password made once per process, so it takes as long as a wrong password for a real account; both answer 401 "Incorrect email or password". Registration still answers 400 "Email already registered" for a taken email: without email verification there is no other way to tell the user, and registration is limited to 5 a minute per client address.

*Evidence (2026-10-28).* In process, median of 30 sign-ins each: known email with a wrong password 166.8 ms, unknown email 4.6 ms before; after, 167.2 and 167.1 ms (bcrypt cost 12; the quieter of two runs, the other at host load 10). Through nginx on the running stack (the code before this change), medians of 4: 373 ms vs 5.8 ms. The difference told anyone which emails had accounts at 10 guesses a minute per address.

### Accessibility: WCAG 2.2 AA

*Rule.* The page, the share page and the manual are held to WCAG 2.2 level AA as axe-core checks it (rules tagged `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`, with `target-size` switched on). White text sits on backgrounds of at least 4.5:1, so the playlist and experiment colours of the Run button, the Playlist segment and the emerald Bench and bundle buttons use the 700 shade of their hue ([`test_accessibility.py`](rosetta-api/tests/unit/test_accessibility.py) `test_white_text_backgrounds_reach_4_5_to_1` reads the colours from the built `tailwind.css`). Popover header links and buttons (`.qr-header-link`, `.qr-action`), the mode checkboxes and the Bench rows are at least 24 CSS px tall. A table box that scrolls sideways (the Backends table, its placeholder, the manual's tables) is a named region with `tabindex="0"`. When focus lands on a control that the busy toast or the history-save notice covers, the control is scrolled to the middle of its scroll containers ([`notice_focus.js`](rosetta-api/static/js/notice_focus.js)); below 1024 px the page leaves 8rem under the footer while the history-save notice is shown. The greyed tab strip shown before a result is an inactive component, which WCAG 1.4.3 exempts from contrast. [`test_accessibility_browser.py`](rosetta-api/tests/unit/test_accessibility_browser.py) runs axe over 13 states when `QROSETTA_AXE_NODE_MODULES` names a `node_modules` with axe-core and playwright-core and Chrome is installed; CI skips it.

*Evidence (2026-10-28).* axe-core 4.14.0 in headless Chrome 155 over 33 page states (load, Load, the circuit picker, the six settings popovers, Bench, Auto-Gen, the Quirk view, sign-in, register, a filled playlist, the running view, all five tabs after a statevector run and after a measured run with four compile-only services, the Exports builder, a share link, History, the account menu, Delete Account, the share page, the manual), the API in process with crafted runner results. Before, at 1280×800: 6 WCAG rules failed on 26 elements, not counting the inactive tab strip (aria-required-children 1, label 1, color-contrast 4, scrollable-region-focusable 3, target-size 15, link-in-text-block 2); at 390×844 on 35 (also white on emerald-600 at 3.76:1, an indigo-500 hover at 4.27:1, red-600 on red-50 at 4.41:1, and seven of the manual's tables). After: 0 at both widths. A Tab walk with both fixed notices shown at 390×844 found 2 controls entirely hidden behind the history-save notice before and none after; the busy toast still covers the header's Docs link at the top of the page while a circuit is being prepared. WCAG 2.2's other additions: no control needs dragging (2.5.7); help is the header's Docs link and the footer's Contact link, in that order wherever they appear (3.2.6); registration signs in with the details just entered (3.3.7); sign-in uses `autocomplete` username/current-password with paste allowed and no cognitive test (3.3.8).

### Bidirectional text in the page

*Rule.* The page and the share page move every text node that holds a bidirectional formatting character (U+202A–U+202E, U+2066–U+2069, U+200E, U+200F, U+061C) or a right-to-left letter into a `<bdi>` element, when it is added and whenever it changes ([`bidi_isolation.js`](rosetta-api/static/js/bidi_isolation.js), `watchBidi(document.body)` in both entry points). The text and its own order are unchanged; its direction can no longer reorder the text beside it. It applies in the DOM only: the publication preview modules (`artifact_*.js`) build the same strings as the Python builders. The Circuits tab and the share page's owner-given names keep showing format characters as visible marks (`visibleFormatCharacters`).

*Evidence (2026-10-28).* Runner errors, preprocessing notes, SDK versions, devices, compiler refusals and uploaded report text were shown with U+202E active, so `‮gnp.exe‬` read as `exe.png` and an unterminated override could reorder the rest of its line (V2-05). `Label` fields already refuse these characters; runner and report text is not a label. In headless Chrome, a paragraph built from `Error: `, `‮gnp.exe` and ` (qulacs)` holds a `<bdi>` around the middle text and the same text content; plain text is not wrapped ([`test_accessibility_browser.py`](rosetta-api/tests/unit/test_accessibility_browser.py), [`test_bidi_isolation.py`](rosetta-api/tests/unit/test_bidi_isolation.py)).

## Upstream behaviour not worked around

The SDK behaviours below are reported by the comparison as disagreement. A workaround for only these backends would bias preprocessing, so none is applied.

- PennyLane `from_qasm` swaps control and target on `QubitUnitary` (cu3, custom gates).
- qibo `cu3` is controlled(e^{-i(φ+λ)/2}·U3). qibo: expressions on gate parameters raise TypeError.
- qrisp runs `cu1` as `crz`. qrisp 0.5's `QuantumCircuit.run()` returns all shots as |0…0⟩ on 12+-qubit circuits with a spread-out distribution (`h q[0]; ch q[0],q[k]` for k=1..11; the statevector path is correct). Qrisp 0.5.2: the definitions of cu1, cu3 and c3sqrtx differ from their matrices; csx acts as crx(π/2); the `run()` outcome cutoff; statevector truncation; qelib1's four-parameter `cu` is rejected.
- torchquantum's `qiskit2tq` uses register-local indices with several qregs, so the torchquantum adapter refuses multi-qreg circuits when `apply_preprocessing=False` (the API's register merge makes them work with preprocessing on).
- quimb 1.13.0 substitutes gate parameters by substring (`g(t, t2)` gives `rz(t2)` the value `t` followed by `2`); with preprocessing on, the round-trip inlines the definition first.
- cirq-core 1.7.0 imports rc3x as a MatrixGate it cannot write.
- Qiskit 0.45.3 level 3 deletes a trailing swap without recording a layout.
- BQSKit 1.2.1's `Circuit.unfold(point)` changes the unitary when gates precede the unfolded gate.
