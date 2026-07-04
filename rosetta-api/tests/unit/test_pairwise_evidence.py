# Tests for deterministic pairwise evidence records in divergence reports.

import math

from services.analysis.divergence import create_counts_report, create_divergence_report


def _record(report, sim_a, sim_b):
    pair = [sim_a, sim_b]
    return next(item for item in report["pairwise_agreement"] if item["simulators"] == pair)


def test_statevector_pairwise_evidence_preserves_matrices_and_labels_direct_agreement():
    report = create_divergence_report([
        {
            "simulator": "a",
            "statevector": ["1", "0"],
            "qubit_ordering": "lsb",
            "sdk_versions": {"sdk-a": "1.0"},
        },
        {
            "simulator": "b",
            "statevector": ["1", "0"],
            "qubit_ordering": "lsb",
            "sdk_versions": {"sdk-b": "2.0"},
        },
    ])

    assert report["fidelity_matrix"] == [[-1.0, 1.0], [1.0, -1.0]]
    assert "pairwise_agreement" in report

    evidence = _record(report, "a", "b")
    assert evidence["agreement"] == "agree_directly"
    assert evidence["registered_transform"] == "identity"
    assert evidence["metrics"]["direct_fidelity"] == 1.0
    assert evidence["metrics"]["direct_relative_phase_rad"] == 0.0
    assert evidence["provenance"]["qubit_ordering"] == {"a": "lsb", "b": "lsb"}
    assert evidence["provenance"]["sdk_versions"] == {
        "a": {"sdk-a": "1.0"},
        "b": {"sdk-b": "2.0"},
    }


def test_statevector_pairwise_evidence_labels_global_phase_only_when_phase_nonzero():
    report = create_divergence_report([
        {"simulator": "a", "statevector": ["1", "0"], "qubit_ordering": "msb"},
        {"simulator": "b", "statevector": ["1j", "0"], "qubit_ordering": "msb"},
    ])

    evidence = _record(report, "a", "b")
    assert evidence["agreement"] == "agree_up_to_global_phase"
    assert evidence["registered_transform"] == "global_phase_alignment"
    assert evidence["metrics"]["direct_fidelity"] == 1.0
    assert math.isclose(evidence["metrics"]["direct_relative_phase_rad"], math.pi / 2)
    assert math.isclose(evidence["transform_effect"]["relative_phase_delta_rad"], -math.pi / 2)
    assert evidence["transform_effect"]["relative_phase_after_alignment_rad"] == 0.0


def test_statevector_pairwise_evidence_labels_bit_reversal_for_one_hot_ordering_probe():
    lsb_one_hot = ["0", "1", "0", "0", "0", "0", "0", "0"]
    msb_one_hot = ["0", "0", "0", "0", "1", "0", "0", "0"]

    report = create_divergence_report([
        {"simulator": "lsb_backend", "statevector": lsb_one_hot, "qubit_ordering": "lsb"},
        {"simulator": "msb_backend", "statevector": msb_one_hot, "qubit_ordering": "msb"},
    ])

    assert report["fidelity_matrix"][0][1] == 0.0
    assert report["fidelity_matrix"][1][0] == 0.0

    evidence = _record(report, "lsb_backend", "msb_backend")
    assert evidence["agreement"] == "agree_after_bit_reversal"
    assert evidence["registered_transform"] == "bit_reversal"
    assert evidence["metrics"]["direct_fidelity"] == 0.0
    assert evidence["metrics"]["bit_reversed_fidelity"] == 1.0
    assert evidence["metrics"]["is_cross_group"] is True
    assert evidence["transform_effect"]["fidelity_delta"] == 1.0
    assert evidence["transform_effect"]["fidelity_after_transform"] == 1.0
    assert evidence["transform_effect"]["relative_phase_after_transform_rad"] == 0.0


def test_statevector_pairwise_evidence_labels_residual_when_current_registered_modes_do_not_explain():
    report = create_divergence_report([
        {"simulator": "a", "statevector": ["1", "0"], "qubit_ordering": "msb"},
        {"simulator": "b", "statevector": ["0", "1"], "qubit_ordering": "msb"},
    ])

    evidence = _record(report, "a", "b")
    assert evidence["agreement"] == "residual_disagreement"
    assert evidence["registered_transform"] is None
    assert evidence["transform_effect"] is None
    assert evidence["metrics"]["direct_fidelity"] == 0.0


def test_statevector_pairwise_evidence_records_not_comparable_pairs():
    report = create_divergence_report([
        {"simulator": "a", "statevector": ["1", "0"], "qubit_ordering": "msb"},
        {"simulator": "b", "error": "runner failed"},
    ])

    evidence = _record(report, "a", "b")
    assert evidence["agreement"] == "not_comparable"
    assert evidence["metrics"]["reason"] == "missing_statevector"
    assert evidence["run_status"] == {"a": "completed", "b": "error"}


def test_counts_pairwise_evidence_labels_current_threshold_decision_and_keeps_matrices():
    report = create_counts_report([
        {
            "simulator": "a",
            "counts": {"0": 10, "1": 0},
            "qubit_ordering": "lsb",
            "sampling_method": "native",
            "seed": 7,
        },
        {
            "simulator": "b",
            "counts": {"0": 0, "1": 10},
            "qubit_ordering": "msb",
            "sampling_method": "sv_sample",
            "seed": 7,
        },
    ], n_shots=10)

    assert "statistical_distance_matrix (js_divergence)" in report
    assert "hellinger_distance_matrix" in report
    evidence = _record(report, "a", "b")
    assert evidence["agreement"] == "distance_exceeds_threshold"
    assert evidence["registered_transform"] == "identity_threshold_check"
    assert evidence["metrics"]["n_shots"] == 10
    assert evidence["metrics"]["is_cross_group"] is True
    assert evidence["provenance"]["sampling_method"] == {"a": "native", "b": "sv_sample"}
    assert evidence["provenance"]["seed"] == {"a": 7, "b": 7}


def test_counts_pairwise_evidence_records_not_comparable_pairs():
    report = create_counts_report([
        {"simulator": "a", "counts": {"0": 10}, "qubit_ordering": "lsb"},
        {"simulator": "b", "error": "runner failed"},
    ], n_shots=10)

    evidence = _record(report, "a", "b")
    assert evidence["agreement"] == "not_comparable"
    assert evidence["metrics"]["reason"] == "missing_counts"
    assert evidence["run_status"] == {"a": "completed", "b": "error"}
