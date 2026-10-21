"""Time `python -c "import main"` and read its peak RSS, N runs in fresh processes.

Usage: python import_bench.py [runs]   (prints one JSON object)
Each child runs in a new directory of symlinks to rosetta-api/'s entries other than data/, since
main.py mounts ./static, db/database.py creates ./data on import, and the working tree is mounted
read-only. Peak RSS is the child's ru_maxrss from wait4.
"""
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

API = Path(__file__).resolve().parents[2] / "rosetta-api"


def api_directory():
    cwd = Path(tempfile.mkdtemp())
    for entry in API.iterdir():
        if entry.name != "data":
            (cwd / entry.name).symlink_to(entry)
    return cwd


def one_run():
    cwd = api_directory()
    started = time.perf_counter()
    child = subprocess.Popen([sys.executable, "-c", "import main"], cwd=cwd)
    _, status, usage = os.wait4(child.pid, 0)
    elapsed = time.perf_counter() - started
    if status != 0:
        raise SystemExit(f"import main exited with status {status}")
    return elapsed, usage.ru_maxrss / 1024


def main():
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    samples = [one_run() for _ in range(runs)]
    seconds = [round(s, 3) for s, _ in samples]
    rss = [round(r, 1) for _, r in samples]
    print(json.dumps({"python": sys.version.split()[0], "seconds": seconds, "median_seconds": statistics.median(seconds),
                      "peak_rss_mib": rss, "median_peak_rss_mib": statistics.median(rss)}))


if __name__ == "__main__":
    main()
