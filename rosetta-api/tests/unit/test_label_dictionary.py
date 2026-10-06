"""Every code the backend can put in a pair record, run status or compile record has plain
wording and a docs anchor in static/js/labels.js."""
import re
from pathlib import Path

from tests.unit.frontend_harness import call_js, requires_node
from tests.unit.test_artifacts_parity import _COUNT_REASONS, _SV_REASONS

pytestmark = requires_node

_ROOT = Path(__file__).resolve().parents[2]
_LABEL = re.compile(r'"(agree_[a-z_]+|residual_disagreement|not_comparable|distance_(?:within|exceeds)_threshold'
                    r'|consistent_within_shot_noise|inconclusive_low_shots|ambiguous|distinguishable'
                    r'|marginal_distinguishable|no_marginal_difference_detected)"')
_REASON = re.compile(r'inconclusive_reason"\]\s*=\s*"([a-z_]+)"')


def _emitted_codes():
    codes = set()
    for path in (_ROOT / "services").rglob("*.py"):
        text = path.read_text()
        codes |= set(_LABEL.findall(text))
        codes |= set(_REASON.findall(text))
    codes |= {"ok", "error", "timeout", "offline", "input", "output_check"}
    codes |= set(_SV_REASONS) | set(_COUNT_REASONS) | {"inconsistent_bitstring_lengths"}
    return sorted(codes)


def test_every_emitted_code_has_wording_and_anchor():
    codes = _emitted_codes()
    assert "low_power" in codes and "marginal_distinguishable" in codes
    labels = call_js(["labels.js"], [("LABELS", [])])[0]
    missing = [c for c in codes if c not in labels]
    assert not missing, f"codes without wording in labels.js: {missing}"
    docs = (_ROOT / "static" / "docs.html").read_text()
    anchors = {entry["anchor"] for entry in labels.values()}
    absent = [a for a in anchors if f'id="{a}"' not in docs]
    assert not absent, f"labels.js anchors missing from docs.html: {absent}"


def test_unknown_codes_fall_back_to_the_code():
    assert call_js(["labels.js"], [("labelText", ["something_new"]), ("labelText", [None])]) == ["something_new", ""]
