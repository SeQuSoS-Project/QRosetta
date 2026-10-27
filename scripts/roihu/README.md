# Roihu preparation

`docs/audits/2026-10-21-overnight/2026-10-21-roihu-apptainer.md` (gitignored) describes how the runner images behave under Apptainer and how a run could reach Roihu's Slurm.

## Measured readings (`cgroup_check.py`)

The CPU probe in `shared/qrosetta_commons/cpu.py` used to read `/sys/fs/cgroup` directly.

Inside a cgroup namespace (podman, Kubernetes), that directory is the container's own cgroup. Apptainer and Slurm steps run without one, so the same directory is the host's root, and the probe reported:
- no quota;
- no memory limit;
- 0.0 s of throttling;
- the whole host's CPU as container CPU.

The probe now finds its own cgroup from `/proc/self/cgroup` and takes limits from the strictest ancestor. The table below shows both versions in the qulacs runner image on 2026-10-21, each measuring a 0.5 s busy loop.

| Environment | Version | Quota (cores) | Memory limit (MiB) | Container CPU (s) | Throttled (s) |
|---|---|---|---|---|---|
| podman `--cpus=1 --memory=1g` | old | 1.0 | 1024 | 0.501 | 0.0 |
| podman `--cpus=1 --memory=1g` | new | 1.0 | 1024 | 0.500 | 0.0 |
| podman `--cpus=0.5` | old | 0.5 | 1024 | 0.500 | 0.487 |
| podman `--cpus=0.5` | new | 0.5 | 1024 | 0.500 | 0.497 |
| Apptainer 1.5.4 in a `CPUQuota=100% MemoryMax=1G` scope | old | null | null | 1.175 | 0.0 |
| Apptainer 1.5.4 in a `CPUQuota=100% MemoryMax=1G` scope | new | 1.0 | 1024 | 0.500 | 0.0 |
| Apptainer 1.5.4 in a `CPUQuota=50%` scope | old | null | null | 0.742 | 0.0 |
| Apptainer 1.5.4 in a `CPUQuota=50%` scope | new | 0.5 | 1024 | 0.500 | 0.498 |

The two podman runs at half a CPU throttle for slightly different times, because each run waits on the quota at different moments. Under podman, the new version reads the same directory as the old one.

```bash
podman run --rm --cpus=1 --memory=1g -v $PWD:/c:ro,z --entrypoint python \
  localhost/qsimulators-pytket_qulacs_runner:latest /c/scripts/roihu/cgroup_check.py \
  /c/<old>/cpu.py /c/shared/qrosetta_commons/cpu.py
systemd-run --user --scope -p CPUQuota=100% -p MemoryMax=1G \
  apptainer exec --containall --cleanenv -B $PWD:/c qulacs.sif python /c/scripts/roihu/cgroup_check.py ...
```

On Roihu (2026-10-22, Apptainer 1.4.5 with the setuid starter, `srun -n1 -c1 --mem-per-cpu=1G` on the `test` partition), the container's `/sys` has no cgroup filesystem: `/sys/fs/cgroup` is empty and both versions report null for every cgroup value. With the host's `/sys/fs/cgroup` bound in (`-B /sys/fs/cgroup`):

| Environment | Version | Quota (cores) | Memory limit (MiB) | Container CPU (s) | Throttled (s) |
|---|---|---|---|---|---|
| Roihu Slurm step, `-B /sys/fs/cgroup` | old | null | null | 0.937 | 0.0 |
| Roihu Slurm step, `-B /sys/fs/cgroup` | new | null | 1024 | 0.500 | 0.0 |

Slurm limits the step to one core by cpuset (`cpu.max` is `max` at every level), so there is no quota and `cpu_environment.cpu_affinity` holds the allowed core. The 1 GiB limit is on the step's `user` directory, one level above the task. Compute nodes (AMD EPYC 9965, 2 × 192 cores) have SMT off.

## Running one job (`run_runner.sh`)

`run_runner.sh <image.sif> <run|run_measured|compile> <payload.json> <result.json>` runs one job of a runner or compiler SIF the way compose runs its container:
- the working directory is `/home/appuser/app`;
- it passes the compose environment (the five thread pins, `RUNNER_MAX_CONCURRENT=1`, and the qubit caps);
- it uses `--containall --cleanenv`;
- it binds the host's `/sys/fs/cgroup` read-only, without which the CPU probe reads no cgroup values under setuid Apptainer;
- the payload directory is mounted read-only and the result directory writable.

`run_runner.sh <image.sif> --self-test` runs the image's probes. Never use `apptainer run`, because it starts the HTTP server.

I tested it on 2026-10-21 on the local qulacs SIF, inside a `CPUQuota=100% MemoryMax=1G` systemd scope. `QR_EXTRA_BINDS` mounted this branch's `qrosetta_commons` over the image's copy, because the SIF predates `--payload-file`.

Both a Bell statevector job and a 1000-shot measured job, seed 7, wrote their results to files. Each result recorded the thread pins, `cpu_quota_cores: 1.0`, `memory_limit_mib: 1024`, `memory_method: vmhwm` and the image commit.

Inside the job's cgroup, container CPU (`simulation_cgroup_cpu_time_sec`) was about 1 ms higher than process CPU. Apptainer's own helper processes share the job's cgroup, and their CPU time is counted there.

## One request as one Slurm job (`compare_job.sh`)

On 2026-10-22, on Roihu's `test` partition (`sbatch --ntasks=4`), a Bell circuit ran as four steps: qulacs and qiskit, each statevector and 1000 shots with seed 7, opt level 0, preprocessing on, 3 timing repeats. The SIFs were built from 0a8f9bd. All four steps ran on node rc4284, an AMD EPYC 9965, each on its own core (80–83). Every result had the same statevector or counts as the same payload run locally through `run_runner.sh`. Each recorded `memory_limit_mib: 1024`, `cpu_quota_cores: null`, the Slurm job and node, and the SIF sha256. Container CPU was 0.4–1.0 ms above process CPU, the Apptainer helpers' share described above.
