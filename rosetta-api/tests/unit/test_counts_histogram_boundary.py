"""Building a counts histogram must stay outside the timed simulation window.

The shared instrument documents the split: drawing shots is simulation work, shaping the
drawn indices into a counts histogram is bookkeeping and belongs in postprocess_fn. On the
circuit sizes this project publishes, the histogram costs more than the draw, and five
runners used to charge it to simulation_time while nine did not. That put the reported
gap between the fastest backends below the size of the inconsistency itself.

These tests pin both halves: the split preserves the sampled counts exactly, and the
runners that sample from a statevector keep the histogram in postprocess_fn.
"""
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pytest

from qrosetta_commons.helpers import _counts_from_samples, _draw_statevector_samples

_RUNNERS = Path(__file__).resolve().parents[3] / "runners"

pytestmark = pytest.mark.skipif(
    not _RUNNERS.exists(), reason="runner sources not present in this checkout")


def _random_statevector(n_qubits, seed=7):
    rng = np.random.default_rng(seed)
    sv = rng.normal(size=2 ** n_qubits) + 1j * rng.normal(size=2 ** n_qubits)
    return sv / np.linalg.norm(sv)


@pytest.mark.parametrize("n_qubits", [2, 3, 5, 8])
@pytest.mark.parametrize("seed", [0, 42, 12345])
def test_split_draw_and_histogram_match_the_combined_form(n_qubits, seed):
    """Moving the histogram out must not perturb the RNG stream or the counts."""
    sv = _random_statevector(n_qubits)
    n_shots = 2048

    # The combined form this replaced: one generator, drawn then counted.
    rng = np.random.default_rng(seed)
    expected = {
        format(k, f"0{n_qubits}b"): v
        for k, v in Counter(
            rng.choice(len(sv), size=n_shots, p=np.abs(sv) ** 2)).items()
    }

    actual = _counts_from_samples(
        _draw_statevector_samples(sv, n_shots, seed), n_qubits)

    assert actual == expected


def test_draw_is_reproducible_under_a_seed():
    sv = _random_statevector(4)
    a = _draw_statevector_samples(sv, 512, 99)
    b = _draw_statevector_samples(sv, 512, 99)
    assert np.array_equal(a, b)


def _runner_sources():
    return sorted(_RUNNERS.glob("*/main.py"))


# A runner draws its own shots if any of these appear; the shared helper is preferred but
# a hand-rolled draw is equally subject to the boundary rule (pyquil renormalises its
# probabilities first, so it keeps its own draw deliberately).
_DRAW_MARKERS = ("_draw_statevector_samples", "rng.choice(", "multinomial(")

# Tokens that only appear when a counts histogram is being assembled.
_HISTOGRAM_MARKERS = ("_counts_from_samples", "Counter(", "bitstring")


def _measured_execute_body(source):
    """The body of the measured execute_fn, up to the next nested def or the job call."""
    match = re.search(
        r"def process_run_measured\(.*?def execute\(compiled, payload\):(.*?)"
        r"(?=\n    def |\n    return run_measured_job)",
        source, re.S)
    return match.group(1) if match else None


def test_statevector_samplers_shape_counts_outside_the_timed_window():
    """A runner that draws its own shots must build the histogram in postprocess_fn.

    Building it in execute_fn puts it inside t2..t3 and makes that backend's
    simulation_time incomparable with the natively-sampling runners. On the circuit sizes
    published here the histogram outweighs the draw, so this is not a rounding error.
    """
    offenders = []
    for path in _runner_sources():
        source = path.read_text()
        body = _measured_execute_body(source)
        if body is None or not any(m in body for m in _DRAW_MARKERS):
            continue
        if "postprocess_fn=" not in source:
            offenders.append(f"{path.parent.name} (no postprocess_fn passed)")
            continue
        built_inside = [m for m in _HISTOGRAM_MARKERS if m in body]
        if built_inside:
            offenders.append(
                f"{path.parent.name} (histogram in execute_fn: {', '.join(built_inside)})")

    assert not offenders, (
        "these runners charge counts-histogram construction to simulation_time: "
        + ", ".join(offenders))


def test_the_boundary_check_actually_inspects_the_sampling_runners():
    """Guard the guard: if the regex stops matching, the test above passes vacuously."""
    sampling = [
        path.parent.name for path in _runner_sources()
        if (body := _measured_execute_body(path.read_text())) is not None
        and any(m in body for m in _DRAW_MARKERS)
    ]
    # quest, projectq, both pennylane runners, torchquantum and pyquil all sample.
    assert len(sampling) >= 6, f"expected the statevector samplers, matched only {sampling}"
