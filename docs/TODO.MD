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

