"""GET /config request_defaults covers every field of every run request body with the model's
default, explains every default that stands for a server decision, and is what the page starts
its controls from (state.js mirror, index.html values, SET_CONFIG_LIMITS)."""
import asyncio
import json
import re
from pathlib import Path

import pydantic
import pytest

import schemas.benchmark as benchmark
from config import settings
from routers.frontend import get_config
from schemas import AgreementThresholds
from services.request_defaults import ITEM_FIELDS, ITEM_WHEN_OMITTED, REQUEST_KINDS, WHEN_OMITTED, request_defaults
from tests.unit.frontend_harness import call_js, requires_node

_STATIC = Path(__file__).resolve().parents[2] / "static"
_ROUTERS = Path(__file__).resolve().parents[2] / "routers"


def _published():
    return json.loads(asyncio.run(get_config()).body)["request_defaults"]


def _placeholder(value) -> bool:
    return value is None or value == {} or value == []


def _check_fields(entries, model, notes):
    assert set(entries) == set(model.model_fields), model.__name__
    for name, field in model.model_fields.items():
        entry = entries[name]
        if field.is_required():
            assert entry == {"server_fills": False, **({"when_omitted": notes[name]} if name in notes else {})}
            continue
        assert entry["server_fills"] is True
        assert entry["default"] == field.get_default(call_default_factory=True), (model.__name__, name)
        if _placeholder(entry["default"]):
            assert entry.get("when_omitted"), f"{model.__name__}.{name}: say what an omitted value means"


def test_get_config_publishes_request_defaults():
    assert _published() == json.loads(json.dumps(request_defaults()))


def test_every_request_field_is_published_with_its_model_default():
    published = _published()["requests"]
    assert set(published) == set(REQUEST_KINDS)
    for kind, (endpoint, model) in REQUEST_KINDS.items():
        assert published[kind]["endpoint"] == endpoint
        _check_fields(published[kind]["fields"], model, WHEN_OMITTED)
        if kind in ITEM_FIELDS:
            field, item_model = ITEM_FIELDS[kind]
            assert published[kind]["items"]["field"] == field
            assert field in model.model_fields
            _check_fields(published[kind]["items"]["fields"], item_model, ITEM_WHEN_OMITTED[item_model.__name__])
        else:
            assert "items" not in published[kind]


def test_notes_name_existing_fields_only():
    fields = set().union(*(m.model_fields for _, m in REQUEST_KINDS.values()))
    assert set(WHEN_OMITTED) <= fields
    for _, item_model in ITEM_FIELDS.values():
        assert set(ITEM_WHEN_OMITTED[item_model.__name__]) <= set(item_model.model_fields)


def test_every_run_request_model_is_listed():
    """A request body with a timeout is a run request; each one is a request_defaults kind."""
    run_models = {obj for obj in vars(benchmark).values()
                  if isinstance(obj, type) and issubclass(obj, pydantic.BaseModel)
                  and "timeout_seconds" in obj.model_fields}
    assert run_models == {model for _, model in REQUEST_KINDS.values()}
    routes = "".join(p.read_text() for p in _ROUTERS.glob("*.py"))
    for endpoint, model in REQUEST_KINDS.values():
        assert re.search(rf'@router\.post\("{re.escape(endpoint)}"', routes), endpoint
        assert f"payload: {model.__name__}" in routes, model.__name__


def test_shared_fields_have_one_default():
    """The page has one control per setting, so a field shared by several kinds must have one
    default. ``mode`` is the exception: required for playlists, 'measured' for experiments."""
    published = _published()["requests"]
    seen = {}
    for kind, spec in published.items():
        for name, entry in spec["fields"].items():
            if name == "mode":
                continue
            seen.setdefault(name, entry)
            assert seen[name] == entry, (kind, name)
    assert published["run_batch_suite"]["fields"]["mode"] == {"server_fills": False}
    assert published["experiments"]["fields"]["mode"] == {"server_fills": True, "default": "measured"}


def test_thresholds_and_compile_only():
    published = _published()
    assert published["agreement_thresholds"] == AgreementThresholds().model_dump()
    compile_only = published["compile_only"]
    assert compile_only["must_be_empty"] == list(benchmark.COMPILE_ONLY_EMPTY_FIELDS)
    assert compile_only["max_qubits"] == settings.MAX_QUBITS_COMPILE
    assert compile_only["set"] == {"simulate": False}
    for endpoint in compile_only["endpoints"]:
        model = next(m for e, m in REQUEST_KINDS.values() if e == endpoint)
        assert "simulate" in model.model_fields and "compilers" in model.model_fields


def _default(kind, field):
    return _published()["requests"][kind]["fields"][field]["default"]


def _state_value(name):
    match = re.search(rf"^\s*{name}: ([^,]+),$", (_STATIC / "js" / "state.js").read_text(), re.M)
    assert match, name
    return json.loads(match.group(1).replace("'", '"'))


def test_state_mirror_equals_published_defaults():
    assert _state_value("defaultOptimizationLevel") == _default("compare", "optimization_level")
    assert _state_value("defaultTimingRepeats") == _default("compare", "timing_repeats")
    assert _state_value("defaultExclusive") == _default("compare", "exclusive")
    assert _state_value("defaultPreprocessing") == ("on" if _default("compare", "apply_preprocessing") else "off")
    assert _state_value("defaultBypassLimits") == _default("compare", "bypass_limits")
    assert _state_value("defaultShots") == _default("compare_measured", "n_shots")
    assert _state_value("timeoutDefault") == _default("compare", "timeout_seconds")


def _tag(html, element_id):
    return re.search(rf'<input[^>]*id="{element_id}"[^>]*>', html, re.S).group(0)


def test_index_html_starts_at_the_published_defaults():
    html = (_STATIC / "index.html").read_text()
    assert f'value="{_default("compare", "timeout_seconds")}"' in _tag(html, "timeout-input")
    assert f'value="{_default("compare", "timing_repeats")}"' in _tag(html, "timing-repeats-input")
    assert f'value="{_default("compare_measured", "n_shots")}"' in _tag(html, "shots-single")
    assert (" checked" in _tag(html, "exclusive-checkbox")) == _default("compare", "exclusive")
    assert (" checked" in _tag(html, "bypass-limits-checkbox")) == _default("compare", "bypass_limits")
    on = re.search(r'<input[^>]*name="preprocessing" value="on"[^>]*>', html).group(0)
    off = re.search(r'<input[^>]*name="preprocessing" value="off"[^>]*>', html).group(0)
    assert (" checked" in on) == _default("compare", "apply_preprocessing")
    assert (" checked" in off) == (not _default("compare", "apply_preprocessing"))
    assert 'placeholder="empty: a random seed' in _tag(html, "seed-input") and 'value=' not in _tag(html, "seed-input")
    assert _default("compare_measured", "seed") is None


@requires_node
def test_page_state_reads_request_defaults():
    config = json.loads(asyncio.run(get_config()).body)
    keys = ["defaultOptimizationLevel", "defaultTimingRepeats", "defaultExclusive", "defaultPreprocessing",
            "defaultBypassLimits", "defaultShots", "timeoutDefault", "thresholdDefaults"]
    changed = json.loads(json.dumps(config))
    fields = changed["request_defaults"]["requests"]
    fields["compare"]["fields"]["optimization_level"]["default"] = 2
    fields["compare"]["fields"]["timing_repeats"]["default"] = 3
    fields["compare"]["fields"]["exclusive"]["default"] = True
    fields["compare"]["fields"]["apply_preprocessing"]["default"] = False
    fields["compare"]["fields"]["timeout_seconds"]["default"] = 90
    fields["compare_measured"]["fields"]["n_shots"]["default"] = 1000
    changed["request_defaults"]["agreement_thresholds"]["js_threshold"] = 0.5
    before, _, after, _, changed_state = call_js(["state.js"], [
        ("getState", []), ("dispatch", ["SET_CONFIG_LIMITS", config]), ("getState", []),
        ("dispatch", ["SET_CONFIG_LIMITS", changed]), ("getState", [])])
    assert {k: before[k] for k in keys if k != "thresholdDefaults"} == {k: after[k] for k in keys if k != "thresholdDefaults"}
    assert after["thresholdDefaults"] == AgreementThresholds().model_dump()
    assert changed_state["defaultOptimizationLevel"] == 2
    assert changed_state["defaultTimingRepeats"] == 3
    assert changed_state["defaultExclusive"] is True
    assert changed_state["defaultPreprocessing"] == "off"
    assert changed_state["timeoutDefault"] == 90
    assert changed_state["defaultShots"] == 1000
    assert changed_state["thresholdDefaults"]["js_threshold"] == 0.5


@pytest.mark.parametrize("path", ["workspace.js", "settings_bar.js", "config.js", "run_plan.js"])
def test_page_has_no_literal_fallback_for_published_defaults(path):
    text = (_STATIC / "js" / path).read_text()
    assert "?.value || '0'" not in text.replace("data-level') || '0'", "")
    assert "|| '1'" not in text and "timingRepeats ?? 1" not in text
    assert "|| 'on'" not in text
    assert "optimization_level ?? 0" not in text
