June 10

Suppose i select a bunch of parameters in config panel like simulators. If i close the sliding window and open it again, they get reset to default. Same with other panels, probably.

If the stavevector is too big (like QFT 16 qubit) the browser cannot download it. How do we handle this?
Export failed: Results too large to export with statevectors. Uncheck 'include statevectors' and try again.

Also, if we switch between measured and statevector mode, the qubit count in the generate circuit field goes back to perhaps default

RO-Crate export failed: Error: Results too large to export with statevectors. Uncheck 'include statevectors' and try again.
    exportRoCrate https://rosetta-frontend-652754634999.us-central1.run.app/js/utils.js?v=1.0.9:258
    onclick https://rosetta-frontend-652754634999.us-central1.run.app/:1

In the RAW Json tab, we should rename it. Also in the Author Field, Affiliation, and the checkbox for downloading the statevector seems to be persistent across runs. Also the Author field for some reason copied in something i had inside my clipboard.

Do not use the word "workaround" as it sounds... hacky. Just remove it.

June 3
Add acknowledgements for the benchmarks, citations and links where appropriate without ruining the UI look


June 2
For each runner, whatever code preprocessing is being done to the circuit that is sent, we need to RECORD it for the ROCrate. Also the FLOW of how they are executed in EACH runner.
SAME for MQTBench

ADD A STOP RUN BUTTON
Resolve: rosetta-api                 | SECRET_KEY is using the insecure default value. Set the SECRET_KEY environment variable before deploying to production.

May 27 2026

HTTP error! Status: 422 . Details: {"detail":[{"type":"int_type","loc":["body","runner_config","qiskit"],"msg":"Input should be a valid integer","input":[0,0,0,0]}]} 

Ran 4 qiskits

----------------
May 26 - 2026 - IDEAS
Choose which runners run first
Choose to run same runner many times with different opt levels - Self comparison!


-----
May 26 - 2026 
 
 Critical Issues
  
  1. runner_config is silently dropped — per-runner optimization levels never apply

  Where: routers/benchmark.py:44,56 → job_manager.py

  worker_compare and worker_compare_measured are called without payload.runner_config. Even if it were passed, job_manager.py
  builds runner_payload without it (e.g. line 34-37, lines 83-87). Both HTTP and K8s dispatchers correctly read runner_config from
  the payload — but it's never poc login --token=sha256~Yj6pHl4hYsQUVcY6EQ3r2Mfmzn9kOYU9nTRrvaSv748 --server=https://api.2.rahti.csc.fi:6443ut in. The entire per-runner optimization feature is silently broken end-to-end.

  2. The RO-Crate export is architecturally unreliable

  Where: routers/export.py, utils.js:173-225

  The UI's "Export RO-Crate" button calls POST /export with the API's currentJobId, which looks up ACTIVE_JOBS — an in-memory dict.
   On any server restart (which Rahti's Recreate strategy guarantees on every deploy), the job is gone and the user gets a 404. The
   correct persistent export is POST /history/runs/{run_id}/export already implemented in history.py:156, but the UI never captures
   the DB run_id returned by saveRunToHistory.

  3. POST /export has no authentication

  Where: routers/export.py:17

  The endpoint has no get_current_user dependency. Anyone who can guess a UUID (job_id) can export another user's results. The
  history export endpoint at /history/runs/{run_id}/export is correctly authenticated.

  4. Statevector truncation corrupts ACTIVE_JOBS before export

  Where: job_manager.py:67-69

  Statevectors >16384 elements are replaced with a string in the aggregated_results list — which is the same object referenced by
  ACTIVE_JOBS. The local/S3 save on line 64 happens before this mutation, so history exports are safe, but the /export endpoint
  would serve the string sentinel instead of actual data when include_statevectors=True.

  5. save_report_to_disk not called in the measurement path

  Where: job_manager.py — run_single_circuit_comparison calls it (line 64), run_single_circuit_measurement does not

  In STORAGE_MODE=local, measurement runs are never persisted to disk, so they can't be replayed or audited. Statevector runs are
  saved; measurement runs aren't.

  6. ACTIVE_JOBS grows unbounded

  Where: job_manager.py:24, never cleared

  In local long-running mode, every job (including full result payloads with base64-encoded statevectors) stays in memory forever.
  A few dozen 18-qubit statevector runs would accumulate ~100MB+ in the dict.

  ---
  Easy, High-Value Additions

  A. Fix runner_config propagation (30 min, highest ROI)

  Pass payload.runner_config through the call chain: router → worker_compare/worker_compare_measured →
  run_single_circuit_comparison/run_single_circuit_measurement → include it in the runner_payload dict. Both dispatchers already
  handle it.

  B. Fix export to use history run_id instead of job_id (1 hour)

  In history.js:saveRunToHistory, capture the returned run_id from POST /history/runs. Store it in state. In
  utils.js:exportRoCrate, call POST /history/runs/{run_id}/export instead. This makes exports persistent, authenticated, and
  K8s-restart-proof — and eliminates the need for routers/export.py entirely.

  C. ACTIVE_JOBS TTL cleanup (20 min)

  A asyncio background task (started in main.py) that walks ACTIVE_JOBS every 10 minutes and removes completed/failed jobs older
  than 30 minutes. Keeps memory bounded.

  D. Add circuit pre-flight statistics to the UI (1 hour)

  C. ACTIVE_JOBS TTL cleanup (20 min)

  A asyncio background task (started in main.py) that walks ACTIVE_JOBS every 10 minutes and removes completed/failed jobs
   older than 30 minutes. Keeps memory bounded.

  D. Add circuit pre-flight statistics to the UI (1 hour)

  Parse qubit count and gate count from the QASM in app.js before submit and display them in the context bar. The server
  already enforces limits, but this lets users see "18q / 42 gates" before they run, which reduces wasted runs against the
   limits.

  E. Add save_report_to_disk to the measurement path (5 min)

  One line after aggregated_results is compiled in run_single_circuit_measurement, matching what the statevector path
  already does.

  ---
  Highest priority in order: A (runner_config is a broken feature users will rely on), then B+3 (security hole +
  architectural fix), then C and E (correctness and reliability).]

====
As of 28-4-2026:
Missing Import or lazy import for vqe (fixing), qft, random,

As of 14-4-2026:

=== K8s DISPATCHER REWORK — SESSION SUMMARY ===

ORIGINAL BUG: 1-2 random runners timeout per run despite pods completing successfully
and uploading results to S3 (Allas). Post-gather S3 recovery sweep was the old workaround.

WHAT WE CHANGED (all working and deployed):
- Payload delivery: eliminated S3 pending key entirely. Payload now sent via QROSETTA_PAYLOAD
  env var in the K8s Job spec. All 16 runner main.py files updated with env var read +
  S3 fallback for backward compat (local docker mode). Fixes cascading NoSuchKey crashes
  caused by Allas eventual consistency + backoffLimit=6 retries.
- Dispatch architecture: Phase 1 = poll K8s pod status only (no S3 calls during wait).
  Phase 2 = after pod Succeeded/timeout, fetch S3 result with exponential backoff (6
  attempts, up to 46s). RBAC fallback: if pod listing fails, poll S3 directly.
- K8s Job spec: backoffLimit=0 (no retries on crash), ttlSecondsAfterFinished=300.
- Image tagging: git hash tags (IMAGE_TAG=c22ed2e) instead of :latest only. rahti_push.sh
  pushes both :hash and :latest, sets IMAGE_TAG env var on the API deployment.
  imagePullPolicy: IfNotPresent — no re-download on every pod spawn.
- ThreadPoolExecutor sized to len(runner_urls) so all K8s jobs are created and polled
  concurrently, not in batches.

WHAT DID NOT WORK:
- Lowering pod CPU requests to 100m (from 500m) to allow all 14 pods to schedule
  simultaneously. Caused catastrophic failure — no pods spawned at all. Likely Rahti
  LimitRange or quota policy rejected the request/limit ratio. REVERTED.

CURRENT STATE:
- The original 1-2 timeout bug is believed fixed (env var payload + Phase 1/2 architecture).
- Pods still schedule in batches of ~3-4 due to 4 CPU quota (500m requests per pod +
  1 CPU limits). Causes a visible delay but runners do complete eventually.
- Deployment is live and working.

OPEN — TO INVESTIGATE NEXT SESSION:
- Why did 100m requests cause total pod spawn failure? Check Rahti LimitRange:
    oc get limitrange -n qrosetta -o yaml
  If LimitRange enforces a max request/limit ratio, we need to find the allowed floor.
- The real fix for slow scheduling is either: (a) request a quota increase from CSC,
  (b) find the minimum CPU request Rahti allows, or (c) accept batch scheduling as-is.
- Verify with a full run that the 1-2 timeout bug is fully resolved.
- Commit all current changes (dispatcher.py, 16 runner main.py files, rahti_push.sh).




------------------------

1. DONE: REMOVE legacy file suit.
2. DONE: Add download option for all RAW JSON
3. DONE: In the dropdown, add custom circuit option!
4. Check game plans
5. DONE: Add download full report option
6. stress test caused crash. add safeguards
Containers on CSC but frontend on Google?


NETWORK SECURITY
QRTODO Gemini, Fix compilation time and simulation time in ALL runners and then VERIFY
Send to LUMI
Number of gates for each simulator and total
VISUAL (Quirk e)

System Limits (FIX IT,  Error | Loading... )

CHECK 18-2-26:
IMPORT AND LOAD FIX, change from json to qasm2.0 or a mix
Creation of accounts (SECURE). projects, profiles, naming, credits
TIMEOUT settings in cloud for batch running and playlists, estimated credit costs (ProjectQ still times out at 60s)
When i click run on edit, then if i click other buttons, the spinning wheel disappears and keeps appearing if i keep click, and the process seems to abort, not sure though.

CHECK: Check if export qasm is safe: 

'''
Instead of trying to force the browser to navigate to a raw data string, I have updated 

exportQasm()
 (as well as 

exportPlaylist()
 and 

downloadRawJson()
) in 

utils.js
 to use the Blob API and Object URLs.

This safely creates a dedicated, temporary file object in the browser's memory and links the download anchor directly to it. This completely sidesteps browser security blocks and will reliably trigger the file download prompt for your QASM script (and JSON playlists)!
'''

implement folder selection for export qasm

CHECK: KEEPING BOTH RAHTI AND LUMI
Lumi for runners, Rahti for API and PVC database and simulations of lower qubit counts, Allas for storage, integrate HAKA login(?) or OpenID Connect(?), slurm jobs for runners.

CHECK: if GCR can serve multiple versions of the website

3-3-20206
✅ What We Have Done (Phases 1, 2, & 3 Complete)

    Authentication & Security: Full JWT login/registration system and a "Delete Account" feature are implemented.

    Data Persistence: The Hybrid Storage system (S3 + Local) is active. You can save, view, rename, and delete historical runs.

    Asynchronous Engine: The benchmark.py router has been refactored to use ACTIVE_JOBS and BackgroundTasks. The synchronous await calls were replaced with job IDs.

    Polling UI: The frontend app.js now has pollJobStatus logic to ping the server instead of waiting.

    Routing Fixes: The nginx.conf correctly includes the jobs endpoint in its routing whitelist.

⏸️ What Is Next (The "LUMI Bridge" - Paused)

    SSH Tunneling: Implementing the paramiko client to securely connect to lumi.csc.fi.

    Slurm Orchestration: Writing the Python logic to generate and submit #SBATCH scripts to the supercomputer queue.

    Apptainer Conversion: Creating definition files (.def) to convert your Docker images into the High-Performance Computing (HPC) compatible .sif format.



DEPLOY USER TO ALLAS/PUHTI/POUTA


What to do what running circuits without login in

