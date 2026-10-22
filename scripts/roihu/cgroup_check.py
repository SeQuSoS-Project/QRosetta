"""Read the CPU probe's cgroup values with two versions of qrosetta_commons/cpu.py side by side.

Usage: python cgroup_check.py <old cpu.py> <new cpu.py>
Prints, for each version, the CPU quota and memory limit it finds and a WindowProbe around
0.5 s of busy CPU. Run it inside a runner container (podman) and under Apptainer inside a
limited scope or Slurm step; see README.md.
"""
import importlib.util
import json
import sys
import time


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def busy(seconds):
    end = time.process_time() + seconds
    while time.process_time() < end:
        pass


def main():
    out = {"proc_cgroup": open("/proc/self/cgroup").read().strip()}
    for name, path in (("old", sys.argv[1]), ("new", sys.argv[2])):
        module = load(f"cpu_{name}", path)
        probe = module.WindowProbe().start()
        start = time.process_time()
        busy(0.5)
        process_cpu = time.process_time() - start
        probe.stop()
        out[name] = {
            "quota_cores": module.cgroup_cpu_quota_cores(),
            "memory_limit_mib": module.cgroup_memory_limit_mib(),
            "window_process_cpu_sec": round(process_cpu, 3),
            "window_cgroup_cpu_sec": None if probe.cgroup_cpu_sec is None else round(probe.cgroup_cpu_sec, 3),
            "window_throttled_sec": probe.throttled_sec,
        }
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
