"""Wall-clock bounds of the speed tests, multiplied by QROSETTA_TEST_TIME_SCALE (default 1; CI sets it)."""

import os

SCALE = float(os.environ.get("QROSETTA_TEST_TIME_SCALE", "1"))


def seconds(value: float) -> float:
    """``value`` seconds on this host."""
    return value * SCALE
