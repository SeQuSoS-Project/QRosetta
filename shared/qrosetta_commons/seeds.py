"""Deterministic per-runner seed derivation from one master seed."""

import hashlib


def derive_runner_seed(master_seed: int, runner_key: str) -> int:
    """Return a seed in ``[0, 2**31 - 1]`` for ``runner_key`` derived from ``master_seed``.

    The first four bytes of ``sha256(f"{master_seed}:{runner_key}")``, read big-endian,
    with the top bit cleared so the value fits a signed 32-bit integer. The same inputs
    give the same seed on every platform and Python version; different runner keys give
    independent streams.
    """
    if isinstance(master_seed, bool) or not isinstance(master_seed, int):
        raise TypeError(f"master_seed must be an int, got {type(master_seed).__name__}")
    if not isinstance(runner_key, str) or not runner_key:
        raise ValueError("runner_key must be a non-empty string")
    digest = hashlib.sha256(f"{master_seed}:{runner_key}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF
