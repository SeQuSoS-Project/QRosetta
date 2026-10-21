# Roihu preparation

`docs-audit/2026-10-21-roihu-apptainer.md` describes how the runner images behave under Apptainer and how a run could reach Roihu's Slurm.

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

On Roihu, run the same check inside an `srun` step. Slurm may limit a step to a set of CPUs (a cpuset) rather than a quota. Such a run would show no quota, and its affinity list (`cpu_environment.cpu_affinity`) would show the allowed CPUs.
