"""Counts construction stays outside the timed simulation window.

Drawing shots is simulation work; turning a backend's raw result into a counts dict is
bookkeeping and belongs in postprocess_fn. These tests check that the split preserves the
sampled counts exactly and that no runner's measured execute_fn builds counts.
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
    """Splitting draw and histogram must not perturb the RNG stream or the counts."""
    sv = _random_statevector(n_qubits)
    n_shots = 2048

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


# A runner draws its own shots if any of these appear (pyquil renormalises its
# probabilities before drawing, so it has its own draw).
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
    simulation_time incomparable with the natively-sampling runners.
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


# Calls that turn a backend's raw result into a counts dict. They belong in postprocess_fn
# for every runner, native samplers included.
_COUNTS_BUILDER_MARKERS = ("get_counts(", "Counter(", "readout_counts")


def test_no_runner_builds_counts_inside_execute_fn():
    """execute_fn returns the backend's raw result; postprocess_fn builds the counts dict."""
    offenders = []
    for path in _runner_sources():
        body = _measured_execute_body(path.read_text())
        if body is None:
            continue
        found = [m for m in _COUNTS_BUILDER_MARKERS if m in body]
        if found:
            offenders.append(f"{path.parent.name} ({', '.join(found)})")

    assert not offenders, (
        "these runners build counts inside the timed simulation window: "
        + ", ".join(offenders))


def test_the_counts_builder_check_inspects_every_runner():
    """Guard the guard: every runner's measured execute_fn must be found by the regex."""
    sources = _runner_sources()
    unmatched = [p.parent.name for p in sources
                 if _measured_execute_body(p.read_text()) is None]
    assert sources and not unmatched, f"measured execute_fn not located in: {unmatched}"


def test_the_boundary_check_actually_inspects_the_sampling_runners():
    """Guard the guard: if the regex stops matching, the test above passes vacuously."""
    sampling = [
        path.parent.name for path in _runner_sources()
        if (body := _measured_execute_body(path.read_text())) is not None
        and any(m in body for m in _DRAW_MARKERS)
    ]
    # quest, projectq, both pennylane runners, torchquantum and pyquil all sample.
    assert len(sampling) >= 6, f"expected the statevector samplers, matched only {sampling}"
