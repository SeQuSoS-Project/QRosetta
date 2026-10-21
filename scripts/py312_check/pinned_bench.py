"""Run scripts/harness_bench/bench.py with the process pinned to one CPU (4: a P-core on the i9-13950HX).

Usage through harness_bench/run.sh: run.sh <ref> ../py312_check/pinned_bench.py [repeats] [cases]
Rootless podman has no cpuset controller, so the pin is set inside the container.
"""
import os
import runpy
import sys
from pathlib import Path

os.sched_setaffinity(0, {4})
bench = Path(__file__).resolve().parents[1] / "harness_bench" / "bench.py"
sys.argv[0] = str(bench)
sys.path.insert(0, str(bench.parent))
runpy.run_path(str(bench), run_name="__main__")
