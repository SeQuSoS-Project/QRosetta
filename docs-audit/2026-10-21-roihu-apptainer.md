# Roihu and Apptainer: research and local compatibility test

Date: 2026-10-21. Scope: what Quantum Rosetta needs to run on CSC Roihu (Slurm + Apptainer). Nothing in the runners, compilers, images, requirements or the measurement instrument was changed; this file is the only change.

Sources: docs.csc.fi and csc.fi pages read on 2026-10-21. WebFetch returns a model's summary of a page, so quoted sentences are near-verbatim; check the wording on the page before quoting it formally. Pages marked (checked) were read a second time directly for this report: the container overview, FirecREST, usage policy, throughput and Jupyter/RStudio tunnelling pages.

## 1. Roihu facts

### 1.1 Hardware

| Fact | Value | Source |
|---|---|---|
| System | Bull BullSequana XH3000. Opened to researchers in June 2026, life cycle about six years | https://csc.fi/en/our-expertise/high-performance-computing/roihu-supercomputer/ |
| CPU nodes, type M | 414 nodes: 2 × AMD Turin 9965 (2 × 192 cores, 2.25 GHz), 768 GiB, 0.96 TB NVMe | https://docs.csc.fi/computing/systems-roihu/ |
| CPU nodes, type L | 72 nodes: same CPUs, 1536 GiB | same |
| CPU nodes, type XL | 4 nodes: 2 × AMD Turin 9555 (2 × 64 cores, 3.2 GHz), 6144 GiB, 15.36 TB NVMe | same |
| Visualisation nodes, type V | 4 nodes: 2 × AMD Turin 9335 (2 × 32 cores) and 2 × NVIDIA L40, 384 GiB | same |
| GPU nodes | 132 nodes, each 4 × NVIDIA GH200 (Hopper GPU + 72-core Grace **ARM** CPU), 4 × 120 GiB CPU memory + 4 × 96 GiB HBM | same |
| ISA | CPU side x86_64 (Zen 5, AVX-512); GPU side aarch64. Separate login nodes `roihu-cpu.csc.fi` and `roihu-gpu.csc.fi`; software built on one side does not run on the other | https://docs.csc.fi/computing/connecting/ , https://docs.csc.fi/support/faq/roihu/ |
| OS | RHEL 9 | https://docs.csc.fi/computing/systems-roihu/ |
| SSH | Key must be signed in MyCSC (24 h certificate); plain `authorized_keys` and passwords do not work | https://docs.csc.fi/computing/connecting/ |

### 1.2 Slurm partitions

From https://docs.csc.fi/computing/running/batch-job-partitions/. Allocation type R = cores and memory chosen independently; N = whole nodes; C = memory tied to cores; G = CPU and memory tied to GPUs.

| Partition | Type | Max time | Nodes | Per job / node | Notes |
|---|---|---|---|---|---|
| `test` | R | 15 min | 1–2 | ≤ 384 cores, ≤ 744 GiB per node | testing only, higher priority |
| `small` | R | 72 h | 1 | ≤ 384 cores, ≤ 1500 GiB | M and L nodes; shared with other jobs |
| `medium` | N | 36 h | 1–6 | full nodes | billed per node |
| `large` | N | 36 h | 6–60 | full nodes | needs a scalability test (https://docs.csc.fi/accounts/how-to-access-roihu-large-partition/) |
| `longrun` | R | 10 days | 1 | ≤ 192 cores | |
| `hugemem`, `hugemem_longrun` | C | 36 h / 10 days | 1 | ≤ 128 cores, ≤ 6037 GiB | XL nodes |
| `interactive` (`sinteractive`) | R | 36 h | 1 | ≤ 32 cores, ≤ 64 GiB | |
| `gputest` | G | 15 min | 1–2 | 1–4 GH200 | |
| `gpumedium` | G | 36 h | 1 | 1–4 GH200 | 72 cores + 212 GiB per GPU |
| `gpularge` | G | 36 h | 1–10 | 4 per node | scalability test |
| `gpuinteractive` | G | 12 h | 1 | MIG slices planned, currently full GPUs | |
| `vizinteractive` | G | 12 h | 1 | ≤ 2 L40 | the only x86 GPUs |

GPUs are requested with `--gres=gpu:gh200:<n>` or `--gres=gpu:l40:<n>` (https://docs.csc.fi/computing/running/creating-job-scripts-roihu/). Max running and max submitted jobs per user: not documented as numbers; CSC says to check with `sacctmgr show assoc user=$USER format=Account,Partition,MaxJobs,MaxSubmit -p` (https://docs.csc.fi/computing/running/throughput/, checked). Max array size: not documented. Each array element counts as one job toward the limits (https://docs.csc.fi/support/faq/why-does-my-batch-job-fail/).

### 1.3 Accounting

| Fact | Source |
|---|---|
| `--account=<project>` is required; without it submission fails with AssocMaxSubmitJobLimit | https://docs.csc.fi/computing/running/creating-job-scripts-roihu/ |
| small/test/interactive/longrun: max(0.75 BU per core-hour × cores, 0.375 BU per GiB-hour × memory); medium/large: 288 BU per node-hour; GPU partitions: 200 BU per GPU-hour; `$TMPDIR` free | https://docs.csc.fi/computing/hpc-billing/ |
| An undersubscribed full-node job is billed as a full node | https://docs.csc.fi/computing/running/creating-job-scripts-roihu/ |
| Existing projects and their BUs can be used on Roihu once Roihu is added to the project in MyCSC | https://docs.csc.fi/support/faq/roihu/ |

For scale: one single-core, 1 GiB run on `small` costs max(0.75, 0.375) = 0.75 BU per hour, so a 14-backend circuit at about one minute per backend is about 0.2 BU. An `--exclusive` full node on `medium` is 288 BU per hour.

### 1.4 Containers

| Fact | Source |
|---|---|
| Apptainer is installed on login and compute nodes and needs no module | https://docs.csc.fi/apps/nextflow/ |
| "On Roihu, we can build containers on login nodes and compute nodes"; build on the side (CPU/GPU) where it will run | https://docs.csc.fi/computing/containers/overview/ (checked) |
| Builds use "Apptainer fakeroot mode without unprivileged user namespaces"; some privileged package-install commands fail | same (checked) |
| `apptainer build container.sif docker://...` pulls from a registry and converts to SIF | same (checked) |
| Bind paths are not automatic: pass `--bind=/users,/projappl,/scratch,$TMPDIR,...` or `--bind=$(csc-common-bind)` | same (checked) |
| Default cache `$HOME/.apptainer` can exceed the 15 GiB home quota; set `APPTAINER_CACHEDIR` to scratch or `$TMPDIR`; Lustre must not be the temp dir | same (checked) |
| CSC base images (Rocky Linux 9, CPU and GPU) are on the Satama registry `satama.csc.fi` | same (checked) |
| Tykky (`module load tykky`; `wrap-container`, `pip-containerize`) is available on Roihu | https://docs.csc.fi/computing/containers/tykky/ |
| For high throughput, run the task-farming tool inside one long-running container, not one container per task | https://docs.csc.fi/computing/running/throughput/ (checked) |
| Installed Apptainer version | not documented |
| Whether Apptainer is setuid-installed | not documented. "Fakeroot mode without unprivileged user namespaces" suggests a setuid install, which matters for §2.3 |
| Whether `oci-archive://` builds work, and whether `docker://` builds need `--fakeroot` | not documented |

### 1.5 Network

| Fact | Source |
|---|---|
| Compute nodes reach the internet through NAT gateways 86.50.172.4 and .5 (addresses listed; the policy itself is not stated) | https://docs.csc.fi/support/faq/roihu/ |
| "compute nodes are inaccessible via the Internet" | https://docs.csc.fi/support/tutorials/rstudio-or-jupyter-notebooks/ (checked) |
| "SSH tunnelling is not yet enabled on Roihu" | same (checked) |
| Allas endpoints work in all Roihu sessions including batch jobs; Roihu defaults to S3 | https://docs.csc.fi/data/Allas/allas-roihu/ |
| "Do not apply for new Allas quota in your project"; LUMI-O is advised for new object storage | https://docs.csc.fi/support/tutorials/roihu-data-preparation/ |
| HTTP proxy settings for compute nodes | not documented |

### 1.6 Filesystems

From https://docs.csc.fi/computing/disk/ unless noted. Nothing is backed up.

| Area | Path | Quota | Files | Cleaning |
|---|---|---|---|---|
| home | `/users/<user>` | 15 GiB | 150,000 | none |
| projappl | `/projappl/<project>` | 15 GiB | 150,000 | none |
| scratch | `/scratch/<project>` | 250 GiB | 500,000 | files unused for 180 days |
| `$TMPDIR` (local NVMe, set in every job, deleted at job end) | node-local | login 80 GB; R jobs 20 GiB; N jobs 600 GiB; G jobs 150 GiB | | job end |
| `$LOCAL_SCRATCH` (`--gres=nvme:`) | XL nodes only | up to 13,000 GB, billed | | job end |

Quota increases are requested in MyCSC; extensions from Puhti/Mahti do not carry over (https://docs.csc.fi/support/tutorials/roihu/). Fourteen runner SIFs at 150–400 MB each (§2) fit in projappl.

### 1.7 Login nodes and interactive services

| Fact | Source |
|---|---|
| Login nodes: only "light" work, i.e. one-core jobs that finish in minutes and use under 1 GiB; others "will be terminated without warning" | https://docs.csc.fi/computing/usage-policy/ (checked) |
| "Do not start an MCP server, a reverse tunnel or a similar service on Roihu"; "no tight polling loops of `squeue` or `sacct`"; "Avoid excessive amounts of Slurm jobs"; "no bursts of test jobs" | same (checked) |
| A long-running web service on a login node | no page allows it, and the light-work rule excludes it |
| `sinteractive` uses the `interactive` partition (≤ 32 cores, 36 h) | https://docs.csc.fi/computing/running/interactive-usage/ |
| SSH to a compute node only while you have a job on it | https://docs.csc.fi/computing/connecting/ |
| Web interface www.roihu.csc.fi (Jupyter, VS Code, Desktop, ...), sessions ≤ 16 h, in interactive/small/test/gpu* partitions; custom web services not covered | https://docs.csc.fi/computing/webinterface/ |
| FirecREST REST API `https://api.roihu.csc.fi/v1/` for Slurm jobs, files and transfers | https://docs.csc.fi/computing/firecrest/ (checked) |
| Robot accounts are for "CI pipelines or building web applications", consume the project's allocation, and only project managers and vice managers can request one; a web application must have "guardrails, input validation and user authorization" | https://docs.csc.fi/computing/firecrest/ , https://docs.csc.fi/computing/usage-policy/ (checked) |
| "Robot accounts may only execute applications, scripts, binaries and API calls explicitly defined by project members" | https://docs.csc.fi/computing/usage-policy/ (checked) |

### 1.8 CPU binding, memory and cgroups

| Fact | Source |
|---|---|
| `--ntasks` × `--cpus-per-task` gives the cores; each task gets its own set of cores; `srun --cpu-bind=none` turns binding off | https://docs.csc.fi/computing/running/creating-job-scripts-roihu/ , https://docs.csc.fi/support/tutorials/affinity/ |
| `--mem` is per node, `--mem-per-cpu` per core; a job that exceeds its memory is terminated | https://docs.csc.fi/computing/running/creating-job-scripts-roihu/ |
| Full-node examples use 384 tasks per node (physical cores) | https://docs.csc.fi/computing/running/example-job-scripts-roihu/ |
| SMT state, `--hint=nomultithread`, `--threads-per-core`, cgroup v1 vs v2, whether cores are constrained by cpuset or by a CFS quota | not documented |

### 1.9 Many small jobs

| Fact | Source |
|---|---|
| More than 20 short tasks (under about 30 min) on one node should be packed into one job; plain jobs or arrays suit tasks over about 30 min | https://docs.csc.fi/computing/running/throughput/ (checked) |
| Recommended tools: HyperQueue, Snakemake, Nextflow, GNU parallel/xargs, Python multiprocessing | same (checked) |
| HyperQueue 0.25.1 on Roihu-CPU and Roihu-GPU (`module load hyperqueue`), "the recommended way" for HTC; use a job-specific `HQ_SERVER_DIR`, avoid the automatic allocator | https://docs.csc.fi/apps/hyperqueue/ |
| GREASY | not documented for Roihu; https://docs.csc.fi/apps/greasy/ returns 404 |

Each Quantum Rosetta run is seconds to minutes, so 14 backends × N circuits falls under the "pack into one job" rule. One sbatch per run, as the Rahti design does with K8s Jobs, would break it.

### 1.10 Puhti/Mahti retirement

Puhti compute closed on 31 July 2026, Mahti compute on 31 August 2026, and both systems' login nodes and storage on 15 October 2026. Nothing was copied to Roihu automatically. Roihu's projappl and scratch are new areas (https://docs.csc.fi/support/faq/roihu/, https://docs.csc.fi/computing/systems-roihu/). A new project starts with empty Roihu areas, cannot fall back to Puhti, and is told not to apply for new Allas quota (§1.5).

## 2. Local Apptainer test

### 2.1 Setup

- Apptainer 1.5.4 (release of 2026-09-22), installed unprivileged with that tag's `tools/install-unprivileged.sh -d el9 -v 1.5.4` into `~/.local/apptainer` (155 MB). The default `el8` source failed: `fakeroot-libs not found` in EPEL 8.
- Host: EL10, kernel 6.12, cgroup v2, i9-13950HX (hybrid). Unprivileged user namespaces are enabled, so this install runs without setuid. Roihu apparently does not allow them (§1.4).
- Images: `localhost/qsimulators-pytket_qulacs_runner:latest` (c38548d20bed) and `localhost/qsimulators-pytket_qiskit_runner:latest` (a9884bbda44b), both baked with `QROSETTA_IMAGE_GIT_SHA=4dc46aa`. `podman inspect`: user `appuser`, WorkingDir `/home/appuser/app`, no entrypoint, CMD `sh -c gunicorn main:app ...`.
- Conversion: `podman save --format oci-archive`, then `apptainer build x.sif oci-archive://x.oci.tar`. The first build failed in `mksquashfs` under the bundled proot: "the current temporary directory (/tmp) is mounted with no execution permission". It worked with `PROOT_TMP_DIR` set to `~/.tmp/apptainer-test/tmp`. SIF sizes: qulacs 156 MB, qiskit 234 MB.
- Run command: `apptainer exec --containall --cleanenv [--writable-tmpfs] --pwd /home/appuser/app --env OMP_NUM_THREADS=1 ... x.sif python main.py <args>`. The `--env` list is the runner `environment:` block of `docker-compose.yml`: the five `*_NUM_THREADS=1` variables plus `MAX_QUBITS_STATEVECTOR=18` and `MAX_QUBITS_MEASURED=24`.
- Payloads: Bell circuit, `/run` (statevector) and `/run_measured` (1000 shots, seed 1234), `timing_repeats` 3. A 16-qubit, 1410-gate statevector circuit was used for the CPU fields.
- Reference: `podman run --rm --cpus 1.0 --memory 1g` with the same environment and payload.
- The host's load average was 22–27 during the tests, so the timings in §2.2 are not benchmark numbers. Only the presence and meaning of the fields are compared.

### 2.2 Results

"wt" = `--writable-tmpfs`; "ro" = without it, so the root filesystem is read-only.

| Image | Mode | Check | Result |
|---|---|---|---|
| qulacs | wt | `--self-test` | pass, 0 of 16 probes failed |
| qulacs | ro | `--self-test` | pass, 0 of 16 |
| qulacs | wt / ro | `/run` Bell | ok; statevector sha256 identical to podman (b3acf7368c22…), msb, complex128 |
| qulacs | wt / ro | `/run_measured` Bell | ok; counts `{'00': 490, '11': 510}`, identical to podman |
| qiskit | wt | `--self-test` | pass, 0 of 16 |
| qiskit | ro | `--self-test` | pass, 0 of 16 |
| qiskit | wt / ro | `/run` Bell | ok; statevector identical to podman (ef13b595a246…), lsb, complex128 |
| qiskit | wt / ro | `/run_measured` Bell | ok; counts `{'11': 487, '00': 513}`, identical to podman |
| both | ro | writes outside `$TMPDIR` | none failed. With `--containall`, `/tmp` and `$HOME` are 64 MiB tmpfs mounts. pytket writes `$HOME/.config/pytket/config.json`; qiskit also writes `$HOME/.cache/python-entrypoints/<hash>`. Without `--containall` these land in the real home directory |
| both | any | user id | runs as the host uid (460238), not `appuser`. Works here because user-namespace squashfuse shows every file as owned by the caller. See §2.3 for a uid that is neither 1000 nor in group 0 |
| both | any | `image_git_sha` | recorded as `4dc46aa`; survives the SIF conversion |
| both | any | `memory_method`, `process_peak_rss_method` | `vmhwm` in Apptainer and podman; `/proc/self/clear_refs` is writable |
| both | any | `cpu_environment.cpu_quota_cores` | Apptainer **null**, podman 1.0 |
| both | any | `cpu_environment.memory_limit_mib` | Apptainer **null**, podman 1024 |
| both | any | `compilation_throttled_sec`, `simulation_throttled_sec` | Apptainer **0.0**; podman 0.0. Apptainer reads the host root cgroup's `cpu.stat`, whose `throttled_usec` is always 0. The value claims "never throttled" where nothing was measured |
| qulacs | 16q `/run` | `simulation_cgroup_cpu_time_sec` vs `simulation_cpu_time_sec` | Apptainer 0.429 s vs 0.067 s; podman 0.0716 s vs 0.0708 s |
| qiskit | 16q `/run` | same | Apptainer 1.149 s vs 0.154 s; podman 0.1667 s vs 0.1665 s |
| both | inside a systemd scope with CPUQuota=100 %, MemoryMax=1G (standing in for a Slurm job cgroup) | quota, memory limit, cgroup CPU | still null / null / host-wide (qiskit 12.0 s cgroup CPU in a 0.38 s window). The scope's own `cpu.max` (`100000 100000`) and `memory.max` (1073741824) were readable inside the container at `/sys/fs/cgroup/<path from /proc/self/cgroup>/` |
| both | same, plus `taskset -c 5` | `cpu_affinity`, `simulation_cpus` | `[5]` and `[5]`; affinity is reported correctly |
| both | `--containall`, no `--env` | `thread_env` | all five variables null. `--containall` implies `--cleanenv`, so host variables do not pass; `APPTAINERENV_OMP_NUM_THREADS=1` and `--env` both work |
| both | `exec` without `--pwd` | start-up | fails: `can't open file '/home/sarkers/main.py'`. `exec` starts in `$HOME`, not the image WorkingDir |
| qulacs | `apptainer run` | default command | starts gunicorn listening on 0.0.0.0:8000 in the host network namespace. On a login node this opens a port; never use `run` |
| qulacs | `--payload` with a 180 KB payload | argv | `OSError: [Errno 7] Argument list too long`. Linux caps one argument or one environment string at 128 KiB (MAX_ARG_STRLEN), and `MAX_QASM_SIZE` is 1 MB |
| both | stdout | result parsing | the result JSON is the last line of stdout, after the INFO log lines on the same stream |
| qulacs | `--s3-job-id` with no S3 settings | S3 path | `TypeError` in botocore's bucket check (`S3_BUCKET_NAME` unset). boto3/botocore 1.35.99 are in the image |

The "outside process" tag (`render_helpers.js` `outsideProcessText`) fires when cgroup CPU exceeds process CPU by at least 5 ms and at least 10 %. Under Apptainer, every run long enough to clear 5 ms would carry it, and the rest of the node's load would decide the value.

### 2.3 Foreign uid (simulated with podman)

In the image, `/home/appuser` is owned by 1000:0 with mode 770, and `/home/appuser/app/main.py` by 1000:0 with mode 664. `unsquashfs -lln` shows the same in the SIF. My unprivileged install shows every file as owned by me, so it did not reproduce this. A setuid Apptainer mounts the squashfs with its stored owners. A Roihu user would then be neither uid 1000 nor in group 0, and the "other" bits on `/home/appuser` are 0. Test with `podman run --user 12345:12345`:

- `python /home/appuser/app/main.py --self-test` fails with `[Errno 13] Permission denied`.
- `import pytket` fails with `PermissionError: '/home/appuser/.config/pytket/config.json'` while `HOME=/home/appuser`. In Apptainer this second failure does not occur, because `HOME` is replaced by the host user's.
- With `--user 12345:0` (the Rahti/OpenShift case) the self-test passes. The `chgrp 0` + `g=u` in the Dockerfiles was written for that case.

On Roihu this is probably a blocker. Confirm it with one command before planning around it: `apptainer exec qulacs.sif ls /home/appuser/app`.

### 2.4 Resource limits under Slurm

- Compose and Rahti limit a runner with a CFS quota (`cpus: "1.0"`, K8s limit 1000m) and a 1 GiB memory limit. Slurm's cgroup/v2 layout puts user processes under `/sys/fs/cgroup/system.slice/slurmstepd.scope/<job>/step_<n>/user/task_<id>`, where `<job>` is the SLUID, or `job_<id>` with `CgroupJobIdPaths=yes` (https://slurm.schedmd.com/cgroup_v2.html). That page does not say which level gets `cpuset` versus `cpu.max` or the memory limit. My expectation, unverified, is that `--cpus-per-task=1 --mem=1G` with `ConstrainCores`/`ConstrainRAMSpace` gives a one-core cpuset and a `memory.max` and no `cpu.max`. Roihu's cgroup version and settings are not documented. If that holds:
  - `cpu_quota_cores` would be null even when read from the right cgroup.
  - `*_throttled_sec` would be a true 0, because a cpuset does not throttle.
  - The limit on CPU is the cpuset, which `cpu_affinity` already records.
  - The §3.4 "CPU quota" evidence (50 ms quota stalls at 0.5 CPU, none at 1.0) was measured under CFS, so Roihu and Rahti timings come from different CPU limits. A report should say which limit applied.
- If the memory limit sits on the job or step cgroup while the task cgroup reads `max`, reading only the process's own cgroup is not enough. The reader has to take the smallest value up the hierarchy.
- `simulation_cgroup_cpu_time_sec` from the own task cgroup would be correct. One task per backend keeps each backend's CPU apart. Several backends in one task cgroup (one `srun` running them in turn) do not overlap in time, so the window is still clean.
- `server_overlapping_runs` cannot see other users' jobs on a shared `small` node. They share L3 cache and memory bandwidth, the effect the Exclusive row of §3.4 measured. Only `--exclusive` on a full node (288 BU per hour on `medium`) removes it.
- SMT: if it is on and Slurm hands out hardware threads, two jobs could share a physical core. CSC does not document it. Check on Roihu with `lscpu` and `scontrol show node`.
- The CLI path (`run_cli_main`) runs in-process without `run_isolated`. There is no hard timeout, so Slurm `--time` becomes the limit, and a timeout appears as a killed job, not as a `timeout` result. `queue_wait_sec` is set to 0.0, so Slurm pending time would not be recorded.

## 3. Changes the images or the CLI path would need (owner to decide; none made)

1. **cgroup reads.** `shared/qrosetta_commons/cpu.py` reads `/sys/fs/cgroup/cpu.max`, `cpu.stat` and `memory.max` at the mount root. That is correct in a container with a cgroup namespace (podman, K8s). Under Apptainer, which creates none, it reads the host root. The fix is to resolve the path from `/proc/self/cgroup` and take the smallest limit up the hierarchy, and to report null instead of 0.0 for throttling when no `cpu.max` exists. This is an instrument change, so per §3.4 it needs its own evidence row.
2. **File permissions.** `/home/appuser` is 770, owned 1000:0. Either make the app tree world-readable (`chmod -R o+rX /home/appuser` or install under `/opt`), or confirm on Roihu that Apptainer there is not setuid. Same question for every runner and compiler image.
3. **Payload and result files.** Add `--payload-file <path>` and `--result-file <path>` to `run_cli_main`. A 1 MB QASM cannot go through argv or an environment variable (128 KiB per string), and the result currently shares stdout with the logs.
4. **Launch wrapper.** Needs `--pwd /home/appuser/app` and `--env` for the seven compose variables (thread pins and qubit caps). Set `HOME` to `$TMPDIR` or use `--containall` so the pytket and qiskit caches do not land in `/users/<user>`. Never use `apptainer run`. This can be a job-script template; the images need no change for it.
5. **Provenance.** Record the SIF's sha256, and the source OCI digest, as the counterpart of `runner_image` (`registry/name@sha256:…`). Also record `SLURM_JOB_ID`, partition, node name and the cpuset. Today none of these are in a CLI-path result.
6. **Time limits.** Decide whether a Slurm kill (time or memory) maps to `timeout` / `error` with `dispatch_status`. Decide whether the CLI path should get `run_isolated`'s hard timeout so the result comes back as JSON rather than as a dead job.
7. **GPU.** cuQuantum's image is x86_64. Roihu's GH200 nodes are aarch64, and the only x86 GPUs (L40) are in `vizinteractive` (12 h, interactive). Either build an aarch64 image (qiskit-aer-gpu aarch64 wheel availability not checked) or leave cuQuantum unavailable on Roihu, as it is on Rahti without a GPU.
8. **S3.** The `--s3-job-id` path works only with S3 credentials in the job environment. On a shared system that means a credentials file under `/projappl` or `/users`. CSC also advises against new Allas quota. FirecREST file transfer or a project scratch directory avoids both.

## 4. Proposed execution design

**Where the API runs.** Off Roihu. Login nodes allow only light one-core work. CSC forbids "a reverse tunnel or a similar service", and SSH tunnelling is not enabled. The web interface is limited to 16 h interactive apps. Keep the API on Rahti (or locally) and add a third dispatcher, `EXECUTION_MODE=slurm`, beside `dispatcher_http` and `dispatcher_k8s`.

**How runs become Slurm jobs.** Use FirecREST (`https://api.roihu.csc.fi/v1/`) with a project robot account. The project manager has to request it. The robot account may run only "applications, scripts, binaries and API calls explicitly defined by project members", so the job script is fixed, versioned in the repo, and takes only a payload file.

Pack one request into one Slurm job, following CSC's rule for short tasks:

- A `/compare` with 14 backends becomes one job on `small` with `--ntasks=14 --cpus-per-task=1 --mem-per-cpu=1G`.
- Each backend is an `srun --exact -n1 -c1 apptainer exec ... <backend>.sif python main.py --payload-file ...` step, so each gets its own core and cgroup.
- For "exclusive" mode, use one full node on `medium` with the steps run one after another.
- A playlist or experiment becomes one job running HyperQueue (CSC's recommended tool), with one task per (circuit, backend) and one core per task.

The SIFs live in `/projappl/<project>/qrosetta/sif/<image>-<sha>.sif`, built from the same commit as the Rahti images.

**How results come back.**

- The API uploads `payload-<id>.json` to `/scratch/<project>/qrosetta/jobs/<job>/` through FirecREST.
- Each step writes `result-<key>.json` with `--result-file`.
- The API polls the job state through FirecREST at a few-second interval, which also respects CSC's "no tight polling" rule. It then downloads the result files and deletes the directory.
- This replaces the S3 exchange, so no storage credentials reach Roihu.
- The aggregator, exporter and report code stay unchanged, because a result file is the same JSON the K8s path stores in S3.

**What could run tomorrow without code changes.** Small circuits only (payload under 128 KiB). From a `sinteractive` or `small` batch job on roihu-cpu:

1. Copy a SIF there, or rebuild it with `apptainer build x.sif docker://...` from a registry that Roihu can reach.
2. Run `apptainer exec --containall --cleanenv --pwd /home/appuser/app --env ... x.sif python main.py --self-test`.
3. Run the CLI with `--payload` and take the last stdout line.

That checks that the backends start and agree, provided §2.3 does not stop them. The timing fields would still carry the §2.2 cgroup errors, and the results do not go back into the API, because I did not find a route that accepts externally produced runner results.

## 5. Open questions for the owner

1. Is Roihu's Apptainer setuid? If so, item 3.2 is required before any image runs. Run `apptainer exec qulacs.sif ls /home/appuser/app` and `apptainer --version` on roihu-cpu.
2. Will the project manager request a FirecREST robot account? Does CSC accept a public web front end that turns user-submitted QASM into Slurm jobs under it? The usage policy asks for input validation and authorization; QASM is data, but CSC may want to review this.
3. Which CPU limit should a Roihu run record: a cpuset core on a shared `small` node (cheap, has neighbour effects) or a full `medium` node (288 BU per hour)? Do Roihu and Rahti results need to be comparable?
4. Is SMT on, and does Slurm allocate whole cores? Check with `lscpu`, `scontrol show node <node>` and `sacctmgr show assoc user=$USER format=Account,Partition,MaxJobs,MaxSubmit -p`.
5. Does Roihu use cgroup v2 with ConstrainCores and ConstrainRAMSpace? `cat /proc/self/cgroup` and `cat /sys/fs/cgroup/<that path>/../../memory.max` inside a job would show it.
6. Is cuQuantum in scope for Roihu (aarch64 GH200 or x86 L40 in `vizinteractive` only)?
7. Is LUMI-O wanted for anything, given that CSC advises against new Allas quota and §4 needs no object store?

## 6. Reproduction

Everything ran under `~/.tmp/apptainer-test` (outputs in `out/`, SIFs in `work/`), with `TMPDIR`, `APPTAINER_TMPDIR`, `APPTAINER_CACHEDIR` and `PROOT_TMP_DIR` pointing there and every heavy command run through `~/.tmp/playtest/bin/capped`. The two SIFs are kept, 390 MB in total; the OCI archives and the Apptainer layer cache were deleted.
