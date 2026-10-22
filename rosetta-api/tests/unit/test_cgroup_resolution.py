"""The CPU probe reads its own cgroup v2 directory: the mount inside a cgroup namespace
(podman, Kubernetes), the path in /proc/self/cgroup without one (Apptainer, Slurm), with
CPU and memory limits taken from the strictest ancestor."""
from qrosetta_commons import cpu


def _tree(tmp_path, monkeypatch, proc_line, files):
    root = tmp_path / "cgroup"
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    root.mkdir(exist_ok=True)
    proc = tmp_path / "proc_cgroup"
    proc.write_text(proc_line + "\n")
    monkeypatch.setattr(cpu, "_CGROUP", str(root))
    monkeypatch.setattr(cpu, "_PROC_CGROUP", str(proc))
    return root


def test_inside_a_cgroup_namespace_the_mount_is_read_as_before(tmp_path, monkeypatch):
    root = _tree(tmp_path, monkeypatch, "0::/", {
        "cpu.max": "100000 100000\n",
        "cpu.stat": "usage_usec 900\nthrottled_usec 40\n",
        "memory.max": str(2 ** 30) + "\n",
    })
    assert cpu._v2_dirs() == [str(root)]
    assert cpu.cgroup_cpu_quota_cores() == 1.0
    assert cpu.cgroup_memory_limit_mib() == 1024
    assert cpu.cgroup_cpu_usage_usec() == 900
    assert cpu.cgroup_throttled_usec() == 40


def test_without_a_namespace_the_process_cgroup_and_its_limiting_ancestor_are_read(tmp_path, monkeypatch):
    _tree(tmp_path, monkeypatch, "0::/system.slice/slurmstepd.scope/job_7/step_0", {
        "cpu.stat": "usage_usec 123456789\n",
        "system.slice/slurmstepd.scope/job_7/cpu.max": "200000 100000\n",
        "system.slice/slurmstepd.scope/job_7/memory.max": str(4 * 2 ** 30) + "\n",
        "system.slice/slurmstepd.scope/job_7/cpu.stat": "usage_usec 5000\nthrottled_usec 777\n",
        "system.slice/slurmstepd.scope/job_7/step_0/cpu.max": "max 100000\n",
        "system.slice/slurmstepd.scope/job_7/step_0/memory.max": str(2 ** 30) + "\n",
        "system.slice/slurmstepd.scope/job_7/step_0/cpu.stat": "usage_usec 500\nthrottled_usec 0\n",
    })
    assert cpu.cgroup_cpu_quota_cores() == 2.0
    assert cpu.cgroup_memory_limit_mib() == 1024
    assert cpu.cgroup_cpu_usage_usec() == 500
    assert cpu.cgroup_throttled_usec() == 777


def test_no_quota_anywhere_reads_the_process_cgroup_and_reports_no_quota(tmp_path, monkeypatch):
    _tree(tmp_path, monkeypatch, "0::/user.slice/run.scope", {
        "cpu.stat": "usage_usec 99999999\n",
        "user.slice/cpu.max": "max 100000\n",
        "user.slice/run.scope/cpu.max": "max 100000\n",
        "user.slice/run.scope/cpu.stat": "usage_usec 321\nthrottled_usec 0\n",
    })
    assert cpu.cgroup_cpu_quota_cores() is None
    assert cpu.cgroup_memory_limit_mib() is None
    assert cpu.cgroup_cpu_usage_usec() == 321
    assert cpu.cgroup_throttled_usec() == 0


def test_a_path_not_below_the_mount_falls_back_to_the_mount(tmp_path, monkeypatch):
    root = _tree(tmp_path, monkeypatch, "0::/docker/abc123", {
        "cpu.max": "50000 100000\n",
        "cpu.stat": "usage_usec 10\nthrottled_usec 2\n",
    })
    assert cpu._v2_dirs() == [str(root)]
    assert cpu.cgroup_cpu_quota_cores() == 0.5
    assert cpu.cgroup_throttled_usec() == 2


def test_unreadable_proc_cgroup_falls_back_to_the_mount(tmp_path, monkeypatch):
    root = _tree(tmp_path, monkeypatch, "0::/", {"cpu.stat": "usage_usec 1\n"})
    monkeypatch.setattr(cpu, "_PROC_CGROUP", str(tmp_path / "missing"))
    assert cpu._v2_dirs() == [str(root)]
    assert cpu.cgroup_cpu_usage_usec() == 1
