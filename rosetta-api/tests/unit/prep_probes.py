"""Module-level functions that the preparation-worker tests run in the worker process."""
import os
import signal
import time

from services.circuit_resolver import prepare_statevector_dispatch
from services.quirk_converter import quirk_url


def pid() -> int:
    return os.getpid()


def allocate(mib: int, hold_sec: float = 30.0) -> int:
    block = bytearray(mib * 1024 * 1024)
    time.sleep(hold_sec)
    return len(block)


def sleep(seconds: float) -> float:
    time.sleep(seconds)
    return seconds


def exit_with(code: int) -> None:
    os._exit(code)


def kill_self() -> None:
    os.kill(os.getpid(), signal.SIGKILL)


def oversized_statevector_preparation(qasm: str, apply_preprocessing: bool) -> dict:
    """prepare_statevector_dispatch after holding 400 MiB for 30 s."""
    allocate(400)
    return prepare_statevector_dispatch(qasm, apply_preprocessing)


def oversized_quirk_drawing(qasm: str):
    """quirk_url after holding 400 MiB for 30 s."""
    allocate(400)
    return quirk_url(qasm)
