# First hour on Roihu

These steps answer the open questions of `docs/audits/2026-10-21-overnight/2026-10-21-roihu-apptainer.md` (gitignored) §5 before any code depends on the answers. Run them on roihu-cpu, in `sinteractive` or a short job on the `test` partition, with small circuits only.

## 1. The machine and Slurm

```bash
apptainer --version; ls -l "$(command -v apptainer)"; ls -l /usr/libexec/apptainer/bin/starter-suid 2>/dev/null
lscpu | grep -E 'Model name|Thread|Core|Socket'
sacctmgr show assoc user=$USER format=Account,Partition,MaxJobs,MaxSubmit -p
srun --account=<project> --partition=test -n1 -c1 --mem-per-cpu=1G bash -c \
  'cat /proc/self/cgroup; d=/sys/fs/cgroup$(sed -n "s/^0:://p" /proc/self/cgroup); \
   for f in cpu.max memory.max cpuset.cpus.effective; do echo "$f: $(cat $d/$f 2>/dev/null)"; done; \
   for p in $d/.. $d/../..; do echo "$p cpu.max=$(cat $p/cpu.max 2>/dev/null) memory.max=$(cat $p/memory.max 2>/dev/null)"; done; \
   taskset -cp $$'
```

The output answers five questions:
- whether Apptainer is setuid;
- whether SMT is on;
- the job limits;
- whether cgroup v2 is in use;
- whether Slurm sets a CPU quota (`cpu.max`) or only a cpuset, and at which level.

## 2. Images

Copy two SIFs, for example qulacs and qiskit built from the `roihu-prep` commit, to `/projappl/<project>/qrosetta/sif/`. Building on Roihu from a registry that Roihu can reach also works.

```bash
apptainer exec qulacs.sif ls -l /home/appuser/app     # permission check (images before roihu-prep fail as a foreign uid)
scripts/roihu/run_runner.sh qulacs.sif --self-test
```

## 3. The CPU probe inside a Slurm step

```bash
srun -n1 -c1 --mem-per-cpu=1G apptainer exec --containall -B $PWD:/c qulacs.sif \
  python /c/scripts/roihu/cgroup_check.py /c/<old>/cpu.py /c/shared/qrosetta_commons/cpu.py
```

The new version should report the step's memory limit. It should report a CPU quota only if Slurm sets one. Otherwise `cpu_environment.cpu_affinity` holds the allowed cores.

## 4. One request as one job

Write `tasks.tsv` with two lines, for example a `bell-qulacs` line using qulacs and a `bell-qiskit` line using qiskit, both with `run`. Give each line a payload file, then submit:

```bash
sbatch --account=<project> --ntasks=2 scripts/roihu/compare_job.sh <job_dir> <sif_dir>
```

Check three things:
- Both `*.result.json` files exist.
- Each result's `batch_environment` names the job, the node and the SIF sha256.
- The statevectors agree with a local run of the same payload.

These results do not go back into the API. No route accepts runner results produced elsewhere yet, and the Slurm dispatcher (FirecREST) is a separate piece of work.
