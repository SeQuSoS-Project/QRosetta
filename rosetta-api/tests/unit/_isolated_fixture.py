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


def reports_watched_pid(payload):
    """Reports whether the process ``payload['watch_pid']`` is alive when this run starts."""
    return {"watched_alive": process_alive(payload["watch_pid"])}
