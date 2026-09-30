"""The agreement-threshold defaults the browser sends (static/js/utils.js) and shows
(static/index.html) equal the AgreementThresholds defaults in schemas/benchmark.py, and the
shots fields start at the schema's n_shots default."""
import re
from pathlib import Path

import pytest

from schemas import AgreementThresholds, MeasuredQasmPayload

_STATIC = Path(__file__).resolve().parents[2] / "static"
_UTILS = _STATIC / "js" / "utils.js"
_INDEX = _STATIC / "index.html"

_INPUT_IDS = {
    "fidelity_tolerance": "th-fidelity",
    "phase_tolerance": "th-phase",
    "js_threshold": "th-js",
    "hellinger_threshold": "th-hellinger",
}

pytestmark = pytest.mark.skipif(not _UTILS.exists(), reason="frontend not present in this checkout")


def _js_defaults() -> dict:
    block = re.search(r"AGREEMENT_THRESHOLD_DEFAULTS\s*=\s*\{(.*?)\}", _UTILS.read_text(), re.S)
    assert block, "utils.js no longer defines AGREEMENT_THRESHOLD_DEFAULTS"
    return {k: float(v) for k, v in re.findall(r"(\w+)\s*:\s*([0-9.eE+-]+)", block.group(1))}


def test_js_defaults_match_schema():
    schema = AgreementThresholds()
    js = _js_defaults()
    for key in _INPUT_IDS:
        assert js[key] == getattr(schema, key), f"utils.js {key}={js[key]}, schema {getattr(schema, key)}"


def test_index_input_values_match_schema():
    html = _INDEX.read_text()
    schema = AgreementThresholds()
    for key, element_id in _INPUT_IDS.items():
        m = re.search(rf'id="{element_id}"\s+value="([^"]+)"', html)
        assert m, f"index.html has no value for #{element_id}"
        assert float(m.group(1)) == getattr(schema, key), f"#{element_id}={m.group(1)}, schema {getattr(schema, key)}"


def test_index_shots_values_match_schema_default():
    html = _INDEX.read_text()
    default = MeasuredQasmPayload.model_fields["n_shots"].default
    for element_id in ("shots-single", "shots-batch"):
        m = re.search(rf'id="{element_id}"\s+value="([^"]+)"', html)
        assert m, f"index.html has no value for #{element_id}"
        assert int(m.group(1)) == default, f"#{element_id}={m.group(1)}, schema n_shots default {default}"
