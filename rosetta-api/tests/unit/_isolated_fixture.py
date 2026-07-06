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
    # Simulate an OOM / hard crash: die without returning a result.
    os.kill(os.getpid(), signal.SIGKILL)


def raiser(payload):
    raise ValueError("bad gate")
