"""The server's verdict rule (services/analysis/divergence/verdicts.py) gives every pair and
backend of the corpus (verdict_corpus.py) the answers the page's own copy of the rule gave
(verdict_reference/, run in Node)."""
import json
import re

import pytest

from services.analysis.divergence import verdicts
from tests.unit.frontend_harness import call_js, requires_node
from tests.unit.verdict_corpus import AGREEMENTS, corpus

pytestmark = requires_node

REFERENCE = ["../../tests/unit/verdict_reference/backend_verdicts.js",
             "../../tests/unit/verdict_reference/run_status.js"]

PAIR_FUNCTIONS = {
    "differs": "isDisagreement",
    "differs_by_only": "isByOnlyDisagreement",
    "assessment": "measuredAssessment",
    "statevector_group": "statevectorGroup",
    "effective_agreement": "effectiveAgreement",
    "unaligned_basis": "unalignedBasis",
    "agrees": "agreesForTest",
}


def _canon(v):
    """A form in which true and 1, or 1 and 1.0 as text, stay apart, and 1 and 1.0 as numbers do not."""
    if isinstance(v, bool) or v is None:
        return ["const", v]
    if isinstance(v, (int, float)):
        return ["num", float(v)]
    if isinstance(v, str):
        return ["str", v]
    if isinstance(v, list):
        return ["list", [_canon(x) for x in v]]
    return ["obj", sorted([k, _canon(x)] for k, x in v.items())]


def _snake(key: str) -> str:
    return re.sub(r"([A-Z])", r"_\1", key).lower()


def _reference_counts(js: dict) -> dict:
    out = {_snake(k): v for k, v in js.items() if k != "backends"}
    out["backends"] = [{_snake(k): v for k, v in b.items()} for b in js["backends"]]
    return out


def _through_json(v):
    return json.loads(json.dumps(v))


@pytest.fixture(scope="module")
def reports():
    return corpus()


@pytest.fixture(scope="module")
def pairs(reports):
    return [(name, i, p) for name, report in reports
            for i, p in enumerate(report["divergence_report"].get("pairwise_agreement") or [])]


def test_corpus_covers_every_class(reports, pairs):
    found = {verdicts.pair_verdict(p)["verdict"] for _, _, p in pairs}
    assert found == {"not_comparable", "differs_by_only", "differs", "inconclusive", "agrees",
                     "bit_order", "unassessed"}
    assert len(reports) > 600 and len(pairs) > 5000
    recorded = [name for name, _ in reports if name.startswith(("experiments/", "examples/"))]
    assert len(recorded) >= 13


def test_every_pair_gets_the_reference_answer(pairs):
    calls = [(fn, [p]) for _, _, p in pairs for fn in PAIR_FUNCTIONS.values()]
    out = call_js(REFERENCE, calls)
    width = len(PAIR_FUNCTIONS)
    differences = []
    for n, (name, i, p) in enumerate(pairs):
        expected = dict(zip(PAIR_FUNCTIONS, out[n * width:(n + 1) * width]))
        got = {k: v for k, v in _through_json(verdicts.pair_verdict(p)).items() if k in PAIR_FUNCTIONS}
        if _canon(got) != _canon(expected):
            differences.append((name, i, p, expected, got))
    assert not differences, differences[:3]


@pytest.fixture(scope="module")
def reference_counts(reports):
    return call_js(REFERENCE, [("backendVerdicts", [report]) for _, report in reports])


def test_every_report_gets_the_reference_counts(reports, reference_counts):
    differences = []
    for (name, report), js in zip(reports, reference_counts):
        got = _through_json(verdicts.backend_verdicts(report))
        del got["headline_model"]
        expected = _reference_counts(js)
        if _canon(got) != _canon(expected):
            differences.append((name, expected, got))
    assert not differences, differences[:2]


def _reference_model(js: dict) -> dict:
    group = lambda g: {"members": g["members"], "differs_from": g["differsFrom"],  # noqa: E731
                       "compared_outside": g["comparedOutside"], "differs_from_all": g["differsFromAll"]}
    out = {_snake(k): v for k, v in js.items()}
    out["differing"] = [b["key"] for b in js["differing"]]
    out["named"] = [group(g) for g in js["named"]]
    out["camps"] = [group(g) for g in js["camps"]]
    return out


def test_every_report_gets_the_reference_headline_model(reports, reference_counts):
    models = call_js(REFERENCE, [("headlineModel", [v]) for v in reference_counts])
    differences = []
    kinds = set()
    for (name, report), js in zip(reports, models):
        got = _through_json(verdicts.backend_verdicts(report)["headline_model"])
        kinds.add(got["kind"])
        if _canon(got) != _canon(_reference_model(js)):
            differences.append((name, _reference_model(js), got))
    assert not differences, differences[:2]
    assert kinds == {"none", "named", "camps", "pairs", "spread"}


def test_experiment_label_groups_follow_the_reference():
    from services.experiment import statevector_label_groups
    labels = [a for a in AGREEMENTS if isinstance(a, str)] + ["unknown"]
    expected = call_js(REFERENCE, [("statevectorGroup", [{"agreement": k, "mode": "statevector"}]) for k in labels])
    groups = statevector_label_groups([{"agreement_class": k, "count_basis": "agreement_label"} for k in labels])
    assert [groups[k] for k in labels] == expected


def test_runner_status_follows_the_reference(reports):
    raws = [r for _, report in reports for r in report.get("raw_results") or []]
    out = call_js(REFERENCE, [("runnerStatus", [r]) for r in raws])
    assert [verdicts.runner_status(r) for r in raws] == out
