"""CPU scheduling context of a runner process: cgroup CPU quota and throttling, the CPUs a
timed window ran on, and the host CPU model."""

import os
import resource

_CGROUP = "/sys/fs/cgroup"
_CPUFREQ_MAX = "/sys/devices/system/cpu/cpu{}/cpufreq/cpuinfo_max_freq"


def _read(path):
    try:
        with open(path) as fh:
            return fh.read()
    except OSError:
        return None


def cgroup_cpu_quota_cores():
    """CPU quota of this process's cgroup in cores (cgroup v2 ``cpu.max``, else v1
    ``cfs_quota_us / cfs_period_us``); None when unlimited or unreadable."""
    text = _read(f"{_CGROUP}/cpu.max")
    try:
        if text is not None:
            quota, period = text.split()[:2]
            return None if quota == "max" else int(quota) / int(period)
        quota = _read(f"{_CGROUP}/cpu/cpu.cfs_quota_us")
        period = _read(f"{_CGROUP}/cpu/cpu.cfs_period_us")
        if quota is None or period is None or int(quota) < 0:
            return None
        return int(quota) / int(period)
    except (ValueError, ZeroDivisionError):
        return None


def _cpu_stat_usec(v2_key, v1_path, v1_key, v1_scale):
    for path, key, scale in ((f"{_CGROUP}/cpu.stat", v2_key, 1), (v1_path, v1_key, v1_scale)):
        text = _read(path)
        if text is None:
            continue
        if key is None:
            try:
                return int(text.split()[0]) // scale
            except (IndexError, ValueError):
                return None
        for line in text.splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[0] == key:
                try:
                    return int(parts[1]) // scale
                except ValueError:
                    return None
    return None


def cgroup_throttled_usec():
    """Cumulative time this cgroup was throttled by its CPU quota, in microseconds
    (v2 ``throttled_usec``, v1 ``throttled_time`` in ns); None when unreadable."""
    return _cpu_stat_usec("throttled_usec", f"{_CGROUP}/cpu/cpu.stat", "throttled_time", 1000)


def cgroup_cpu_usage_usec():
    """Cumulative CPU time of every process in this cgroup, in microseconds (v2
    ``usage_usec``, v1 ``cpuacct.usage`` in ns); None when unreadable."""
    return _cpu_stat_usec("usage_usec", f"{_CGROUP}/cpuacct/cpuacct.usage", None, 1000)


def current_cpu():
    """The logical CPU this process last ran on (``/proc/self/stat`` field 39), or None."""
    text = _read("/proc/self/stat")
    if text is None:
        return None
    try:
        return int(text.rsplit(")", 1)[1].split()[36])
    except (IndexError, ValueError):
        return None


def cpu_max_mhz(cpu):
    """Maximum frequency of logical CPU ``cpu`` in MHz (cpufreq), or None."""
    text = _read(_CPUFREQ_MAX.format(cpu))
    try:
        return int(text) / 1000 if text is not None else None
    except ValueError:
        return None


def host_cpu_model():
    """The first ``model name`` in ``/proc/cpuinfo``, or None."""
    text = _read("/proc/cpuinfo") or ""
    for line in text.splitlines():
        if line.startswith("model name"):
            return line.split(":", 1)[1].strip()
    return None


def cpu_environment(cpus_used=()):
    """Process-level CPU context: host CPU model, cgroup quota, CPU affinity and the
    maximum frequency of each CPU in ``cpus_used``."""
    try:
        affinity = sorted(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        affinity = None
    return {
        "cpu_model": host_cpu_model(),
        "cpu_quota_cores": cgroup_cpu_quota_cores(),
        "cpu_affinity": affinity,
        "cpu_max_mhz": {str(c): cpu_max_mhz(c) for c in sorted(set(cpus_used))
                        if c is not None},
    }


class WindowProbe:
    """Snapshot of cgroup CPU usage and throttling, involuntary context switches and the
    current CPU, taken just outside a timed window on entry and exit."""

    __slots__ = ("_throttled", "_usage", "_nivcsw", "_cpu", "throttled_sec", "cgroup_cpu_sec",
                 "involuntary_switches", "cpus")

    def start(self):
        self._usage = cgroup_cpu_usage_usec()
        self._throttled = cgroup_throttled_usec()
        self._nivcsw = resource.getrusage(resource.RUSAGE_SELF).ru_nivcsw
        self._cpu = current_cpu()
        return self

    def stop(self):
        throttled = cgroup_throttled_usec()
        usage = cgroup_cpu_usage_usec()
        nivcsw = resource.getrusage(resource.RUSAGE_SELF).ru_nivcsw
        self.throttled_sec = (None if throttled is None or self._throttled is None
                              else (throttled - self._throttled) / 1e6)
        self.cgroup_cpu_sec = (None if usage is None or self._usage is None
                               else (usage - self._usage) / 1e6)
        self.involuntary_switches = nivcsw - self._nivcsw
        self.cpus = sorted({c for c in (self._cpu, current_cpu()) if c is not None})
        return self
