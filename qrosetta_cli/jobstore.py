"""The local server's finished-job settings that `start` gives compose: how many finished jobs the
API keeps, its job storage budget, the memory its finished jobs may hold, and how long it keeps a
finished job. Each comes from its
environment variable, else the config file's [lifecycle] key, else the compose default. None of
them is a measurement setting."""

import re

from qrosetta_cli.errors import usage

MIB = 1024 * 1024
MIN_RETENTION_SEC = 60
API_MEMORY_LIMIT_MIB = 2048
CHANGE_HINT = "change: qrosetta config path → [lifecycle] jobs_kept, job_storage, job_memory, job_retention"

_SIZE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(MiB|GiB)?\s*$", re.IGNORECASE)
_DURATION = re.compile(r"^\s*(\d+)\s*([smh])?\s*$", re.IGNORECASE)


def parse_jobs_kept(value):
    """A whole number of finished jobs, at least 1."""
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f"must be a whole number of jobs, at least 1, not {value!r}")
    text = str(value).strip()
    if not text.isdigit() or int(text) < 1:
        raise ValueError(f"must be a whole number of jobs, at least 1, not {value!r}")
    return int(text)


def parse_job_storage(value):
    """MiB from an integer (MiB), '4096', '4096MiB' or '4GiB' (fractions allowed); at least 1 MiB."""
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f'must be a size such as "4GiB", "4096MiB" or 4096 (MiB), not {value!r}')
    match = _SIZE.match(str(value))
    if not match:
        raise ValueError(f'must be a size such as "4GiB", "4096MiB" or 4096 (MiB), not {value!r}')
    number, unit = float(match.group(1)), (match.group(2) or "MiB").lower()
    mib = round(number * (1024 if unit == "gib" else 1))
    if mib < 1:
        raise ValueError(f"must be at least 1 MiB, not {value!r}")
    return mib


def parse_job_retention(value):
    """Seconds from an integer (seconds), '86400', '90s', '30m' or '24h'; at least 60, the API's
    minimum."""
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f'must be a time such as "24h", "90m", "3600s" or 3600 (seconds), not {value!r}')
    match = _DURATION.match(str(value))
    if not match:
        raise ValueError(f'must be a time such as "24h", "90m", "3600s" or 3600 (seconds), not {value!r}')
    seconds = int(match.group(1)) * {"s": 1, "m": 60, "h": 3600}[(match.group(2) or "s").lower()]
    if seconds < MIN_RETENTION_SEC:
        raise ValueError(f"must be at least 1 minute (the API's minimum), not {value!r}")
    return seconds


# key: (environment variable, compose default, parser)
SETTINGS = {
    "jobs_kept": ("QROSETTA_JOB_MAX_KEPT", 200, parse_jobs_kept),
    "job_storage": ("QROSETTA_JOB_SPILL_MAX_MIB", 4096, parse_job_storage),
    "job_memory": ("QROSETTA_JOB_MEMORY_MAX_MIB", 512, parse_job_storage),
    "job_retention": ("QROSETTA_JOB_TTL_SEC", 86400, parse_job_retention),
}
ENV_VARS = tuple(var for var, _, _ in SETTINGS.values())


def resolve(env, cfg):
    """{key: (value, source)}: the environment variable, else config lifecycle.<key>, else the
    compose default. A value that does not parse is refused with the place it came from."""
    out = {}
    for key, (var, default, parse) in SETTINGS.items():
        raw, source = env.get(var), f"env {var}"
        if raw in (None, ""):
            raw = cfg.get("lifecycle", key) if cfg is not None else None
            source = f"config lifecycle.{key}"
        if raw is None:
            out[key] = (default, "default")
            continue
        try:
            out[key] = (parse(raw), source)
        except ValueError as exc:
            where = f"edit {cfg.path}" if source.startswith("config") and cfg is not None else f"unset {var}"
            raise usage(f"{source}: {key} {exc}.", hint=where, reason="job_setting_invalid") from None
    return out


def compose_env(settings):
    """The variables docker-compose.yml interpolates for the API."""
    return {SETTINGS[key][0]: str(value) for key, (value, _) in settings.items()}


def _hours(seconds):
    if seconds % 3600 == 0:
        return f"{seconds // 3600} h"
    if seconds % 60 == 0:
        return f"{seconds // 60} min"
    return f"{seconds} s"


def describe(settings):
    """'Finished jobs: kept up to 24 h, at most 200, in up to 4.0 GiB of job storage and 512 MiB of
    memory'."""
    return (
        f"Finished jobs: kept up to {_hours(settings['job_retention'][0])}, at most "
        f"{settings['jobs_kept'][0]}, in up to {settings['job_storage'][0] / 1024:.1f} GiB of job storage"
        f" and {settings['job_memory'][0]} MiB of memory"
    )


def line(settings):
    return f"{describe(settings)} ({CHANGE_HINT})"


def block(settings):
    """The JSON form: values and where each came from."""
    return {
        "jobs_kept": settings["jobs_kept"][0],
        "job_storage_mib": settings["job_storage"][0],
        "job_memory_mib": settings["job_memory"][0],
        "job_retention_sec": settings["job_retention"][0],
        "sources": {key: source for key, (_, source) in settings.items()},
    }
