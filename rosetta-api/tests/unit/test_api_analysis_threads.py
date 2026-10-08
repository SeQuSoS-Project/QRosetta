"""The API image runs its analysis with single-threaded BLAS, and the single-bit marginal sums
need no matrix product."""
import re
from pathlib import Path

import numpy as np

from services.analysis.divergence.marginals import marginal_counts

_DOCKERFILE = Path(__file__).resolve().parents[2] / "Dockerfile"


def test_api_image_pins_blas_threads():
    env = dict(re.findall(r"\b([A-Z_]+_NUM_THREADS)=(\S+)", _DOCKERFILE.read_text()))
    assert env.get("OMP_NUM_THREADS") == "1"
    assert env.get("OPENBLAS_NUM_THREADS") == "1"
    assert env.get("MKL_NUM_THREADS") == "1"


def test_marginal_counts_sums_ones_per_position():
    ones, total = marginal_counts({"011": 5, "110": 7, "000": 3})
    assert list(ones) == [7.0, 12.0, 5.0] and total == 15.0
    rng = np.random.default_rng(3)
    counts = {format(int(k), "014b"): int(v) for k, v in
              zip(rng.choice(2 ** 14, 900, replace=False), rng.integers(1, 40, 900))}
    keys = list(counts)
    bits = np.array([[int(c) for c in k] for k in keys])
    expected = np.array([counts[k] for k in keys]) @ bits
    assert list(marginal_counts(counts)[0]) == list(expected.astype(float))
