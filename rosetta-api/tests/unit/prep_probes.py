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


def marked_slow_statevector_preparation(qasm: str, apply_preprocessing: bool) -> dict:
    """prepare_statevector_dispatch after writing this process's pid to the file named by
    QROSETTA_TEST_PREP_MARKER and sleeping 30 s."""
    with open(os.environ["QROSETTA_TEST_PREP_MARKER"], "w") as fh:
        fh.write(str(os.getpid()))
    time.sleep(30)
    return prepare_statevector_dispatch(qasm, apply_preprocessing)


def oversized_quirk_drawing(qasm: str):
    """quirk_url after holding 400 MiB for 30 s."""
    allocate(400)
    return quirk_url(qasm)


def reordered_set() -> set:
    """{3, 17}, listed 3 then 17; a pickled copy lists 17 then 3 (int hashes are not seeded)."""
    items = set(range(32))
    for item in range(32):
        if item not in (3, 17):
            items.discard(item)
    return items


class ListsASet(Exception):
    """Lists the set ``expected`` in its message, like Lark's UnexpectedToken."""

    def __init__(self, expected, parser=None):
        super().__init__()
        self.expected = expected
        self.parser = parser

    def __str__(self):
        return "Expected one of: " + ", ".join(str(item) for item in self.expected)


def raise_listing_a_set() -> None:
    raise ListsASet(reordered_set())


def raise_listing_a_set_beside_a_parser() -> None:
    raise ListsASet(reordered_set(), parser=lambda token: token)


def raise_a_set_argument() -> None:
    raise ValueError(reordered_set())


class NeedsItsParser(Exception):
    """Builds its message with ``parser``, which cannot be pickled."""

    def __init__(self, parser):
        super().__init__()
        self.parser = parser

    def __str__(self):
        return f"parsed {self.parser('x')}"


def raise_needing_its_parser() -> None:
    raise NeedsItsParser(lambda token: token.upper())
