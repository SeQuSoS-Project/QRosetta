As of 31-3-20206:
1. The first simulation after loading up the projects internally gives bad results. It should be discarded




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

