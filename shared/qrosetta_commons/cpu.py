"""CPU scheduling context of a runner process: cgroup CPU quota and throttling, the CPUs a
timed window ran on, and the host CPU model."""

import os
import resource

_CGROUP = "/sys/fs/cgroup"
_PROC_CGROUP = "/proc/self/cgroup"
_CPUFREQ_MAX = "/sys/devices/system/cpu/cpu{}/cpufreq/cpuinfo_max_freq"


def _read(path):
    try:
        with open(path) as fh:
            return fh.read()
    except OSError:
        return None


def _v2_dirs():
    """This process's cgroup v2 directory and its ancestors up to the mount, innermost first.

    Inside a cgroup namespace (podman, Kubernetes) the process's cgroup is the mount itself.
    Without one (Apptainer, a Slurm step) ``/proc/self/cgroup`` names a path below the
    host's mount, and that directory holds this process's counters and limits.
    """
    text = _read(_PROC_CGROUP) or ""
    relative = next((line[3:].strip() for line in text.splitlines() if line.startswith("0::")), "/")
    own = os.path.normpath(_CGROUP + "/" + relative.lstrip("/"))
    if relative in ("", "/") or not os.path.isfile(os.path.join(own, "cpu.stat")):
        return [_CGROUP]
    dirs = [own]
    while dirs[-1] != _CGROUP and dirs[-1].startswith(_CGROUP + "/"):
        dirs.append(os.path.dirname(dirs[-1]))
    return dirs


def _v2_cpu_limits():
    """``(cores, directory)`` for each finite cgroup v2 ``cpu.max`` from this process's cgroup
    up to the mount, innermost first; None when no directory has a ``cpu.max`` file."""
    limits, seen = [], False
    for directory in _v2_dirs():
        text = _read(f"{directory}/cpu.max")
        if text is None:
            continue
        seen = True
        quota, period = text.split()[:2]
        if quota != "max":
            limits.append((int(quota) / int(period), directory))
    return limits if seen else None


def _v2_limiting_dir():
    """The directory whose ``cpu.max`` is the smallest in force, else this process's own."""
    try:
        limits = _v2_cpu_limits()
    except (ValueError, ZeroDivisionError, IndexError):
        limits = None
    if limits:
        return min(limits, key=lambda limit: limit[0])[1]
    return _v2_dirs()[0]


def cgroup_cpu_quota_cores():
    """CPU quota in force for this process in cores: the smallest cgroup v2 ``cpu.max`` from
    its cgroup up to the mount, else v1 ``cfs_quota_us / cfs_period_us``; None when
    unlimited or unreadable."""
    try:
        limits = _v2_cpu_limits()
        if limits is not None:
            return min(limit[0] for limit in limits) if limits else None
        quota = _read(f"{_CGROUP}/cpu/cpu.cfs_quota_us")
        period = _read(f"{_CGROUP}/cpu/cpu.cfs_period_us")
        if quota is None or period is None or int(quota) < 0:
            return None
        return int(quota) / int(period)
    except (ValueError, ZeroDivisionError, IndexError):
        return None


def _cpu_stat_usec(v2_dir, v2_key, v1_path, v1_key, v1_scale):
    for path, key, scale in ((f"{v2_dir}/cpu.stat", v2_key, 1), (v1_path, v1_key, v1_scale)):
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
    """Cumulative time the cgroup holding this process's CPU quota was throttled, in
    microseconds (v2 ``throttled_usec`` of ``_v2_limiting_dir``, v1 ``throttled_time`` in ns);
    None when unreadable."""
    return _cpu_stat_usec(_v2_limiting_dir(), "throttled_usec", f"{_CGROUP}/cpu/cpu.stat",
                          "throttled_time", 1000)


def cgroup_cpu_usage_usec():
    """Cumulative CPU time of every process in this process's cgroup, in microseconds (v2
    ``usage_usec``, v1 ``cpuacct.usage`` in ns); None when unreadable."""
    return _cpu_stat_usec(_v2_dirs()[0], "usage_usec", f"{_CGROUP}/cpuacct/cpuacct.usage", None, 1000)


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


AFFINITY_ENV = "QROSETTA_CPU_AFFINITY"


def parse_cpu_list(text):
    """CPU ids from a list such as ``"0-7,16"``; ValueError on malformed input."""
    cpus = set()
    for part in str(text).split(","):
        part = part.strip()
        if not part:
            continue
        lo, _, hi = part.partition("-")
        start, end = int(lo), int(hi or lo)
        if start < 0 or end < start:
            raise ValueError(f"bad CPU range {part!r}")
        cpus.update(range(start, end + 1))
    if not cpus:
        raise ValueError("empty CPU list")
    return cpus


def apply_cpu_affinity():
    """Restrict this process to the CPUs in ``QROSETTA_CPU_AFFINITY`` when it is set."""
    text = os.getenv(AFFINITY_ENV)
    if text:
        os.sched_setaffinity(0, parse_cpu_list(text))


def cgroup_memory_limit_mib():
    """Memory limit in force for this process in MiB: the smallest cgroup v2 ``memory.max``
    from its cgroup up to the mount, else v1 ``memory.limit_in_bytes``; None when unlimited
    or unreadable."""
    values = [_read(f"{d}/memory.max") for d in _v2_dirs()]
    values = [v.strip() for v in values if v is not None]
    if values:
        try:
            finite = [int(v) for v in values if v != "max"]
        except ValueError:
            return None
        finite = [v for v in finite if v < 2 ** 60]
        return min(finite) / 2 ** 20 if finite else None
    for path in (f"{_CGROUP}/memory/memory.limit_in_bytes",):
        text = _read(path)
        if text is None:
            continue
        text = text.strip()
        if text == "max":
            return None
        try:
            value = int(text)
        except ValueError:
            return None
        return None if value >= 2 ** 60 else value / 2 ** 20
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
        "memory_limit_mib": cgroup_memory_limit_mib(),
        "cpu_affinity": affinity,
        "cpu_affinity_setting": os.getenv(AFFINITY_ENV) or None,
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
