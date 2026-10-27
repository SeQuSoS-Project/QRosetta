"""Top-level functions for test_run_isolated to run in a spawned child process."""
import os
import signal
import time


def fast(payload):
    return {"result": payload.get("x", 0) * 2}


def slow(payload):
    time.sleep(payload.get("sleep", 60))
    return {"result": "should have been killed"}


def boom(payload):
    os.kill(os.getpid(), signal.SIGKILL)


def raiser(payload):
    raise ValueError("bad gate")


def with_qasm(payload):
    return {
        "result": "ok",
        "execution_time_sec": 0.01,
        "transpiled_qasm": "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n",
    }


def returns_error(payload):
    return {"simulator": "t", "error": "bad gate", "execution_time_sec": None}


def starts_subprocess(payload):
    """Starts a long-running subprocess, records its pid, then outlives the budget."""
    import subprocess
    child = subprocess.Popen(["sleep", "120"])
    with open(payload["pid_file"], "w") as fh:
        fh.write(str(child.pid))
    if payload.get("return_early"):
        return {"result": "ok"}
    time.sleep(60)


def process_alive(pid):
    """True when ``pid`` exists and is not a zombie."""
    try:
        with open(f"/proc/{pid}/stat") as fh:
            return not fh.read().split(") ", 1)[1].startswith("Z")
    except FileNotFoundError:
        return False


def slow_records_pid(payload):
    """Writes its own pid, then sleeps."""
    with open(payload["pid_file"], "w") as fh:
        fh.write(str(os.getpid()))
    time.sleep(payload.get("sleep", 60))
    return {"result": "should have been killed"}


def reports_environment(payload):
    """Returns this process's environment and whether it read the image identity."""
    from qrosetta_commons import image_identity
    return {"environ": dict(os.environ),
            "identity_read": image_identity._identity.cache_info().currsize,
            "build_files_read": image_identity.build_file_hashes.cache_info().currsize,
            "execution_time_sec": 0.01}


def reports_watched_pid(payload):
    """Reports whether the process ``payload['watch_pid']`` is alive when this run starts."""
    return {"watched_alive": process_alive(payload["watch_pid"])}


def serve_one_slow_run(pid_file, measured):
    """Acts as a runner worker: awaits one slow run through ExecutionSlots until killed."""
    import asyncio
    from qrosetta_commons.helpers import ExecutionSlots
    asyncio.run(ExecutionSlots(1).run(
        slow_records_pid, {"pid_file": pid_file, "sleep": 30, "hard_timeout_seconds": 60},
        measured=measured))
