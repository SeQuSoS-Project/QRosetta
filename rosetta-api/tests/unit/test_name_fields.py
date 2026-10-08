"""Every name field of every request schema refuses control and invisible formatting
characters, and the visible-name fields refuse blank names; names stored before the rule are
cleaned when a saved run is read."""
import inspect
import typing

import pytest
from pydantic import BaseModel, BeforeValidator, ValidationError

import schemas
import schemas.benchmark as benchmark
from schemas.benchmark import printable_name

_CHECKS = {benchmark._printable_text: "printable", benchmark._visible_text: "visible"}


def _validators(annotation) -> list:
    found = []
    for arg in typing.get_args(annotation):
        if isinstance(arg, BeforeValidator):
            found.append(arg.func)
        elif not isinstance(arg, (str, int, float)):
            found += _validators(arg)
    return found


def _name_fields():
    seen = []
    for module in (benchmark, __import__("schemas.history", fromlist=["x"]),
                   __import__("schemas.share", fromlist=["x"]), __import__("schemas.auth", fromlist=["x"])):
        for _, model in inspect.getmembers(module, inspect.isclass):
            if not issubclass(model, BaseModel) or model.__module__ != module.__name__:
                continue
            for name, field in model.model_fields.items():
                funcs = [f for f in _validators(field.annotation)
                         + [m.func for m in field.metadata if isinstance(m, BeforeValidator)]
                         if f in _CHECKS]
                if funcs:
                    seen.append((model, name, field, funcs))
    return seen


NAME_FIELDS = _name_fields()


def test_the_known_name_fields_are_found():
    found = {(m.__name__, n) for m, n, _f, _v in NAME_FIELDS}
    assert {("RunHistoryUpdate", "run_name"), ("RunHistoryFromJob", "run_name"),
            ("SavedCircuitCreate", "name"), ("ShareLinkCreate", "label"),
            ("BenchmarkTask", "name")} <= found


@pytest.mark.parametrize("model,name,field,funcs", NAME_FIELDS,
                         ids=[f"{m.__name__}.{n}" for m, n, _f, _v in NAME_FIELDS])
def test_name_field_has_one_validator_doing_every_check(model, name, field, funcs):
    assert len(funcs) == 1


@pytest.mark.parametrize("model,name,field,funcs", NAME_FIELDS,
                         ids=[f"{m.__name__}.{n}" for m, n, _f, _v in NAME_FIELDS])
@pytest.mark.parametrize("bad", ["a\x00b", "a‮b", "a b", "a⁠b"])
def test_name_field_refuses_control_and_invisible_characters(model, name, field, funcs, bad):
    key = field.validation_alias.choices[0] if field.validation_alias else (field.alias or name)
    with pytest.raises(ValidationError) as caught:
        model.model_validate({key: bad})
    assert any(e["loc"][:1] == (key,) and "control characters" in e["msg"] for e in caught.value.errors())


@pytest.mark.parametrize("model,name,field,funcs",
                         [x for x in NAME_FIELDS if x[3] == [benchmark._visible_text]],
                         ids=lambda x: getattr(x, "__name__", None) or str(x)[:20])
def test_visible_name_field_refuses_blank_names(model, name, field, funcs):
    key = field.validation_alias.choices[0] if field.validation_alias else (field.alias or name)
    with pytest.raises(ValidationError) as caught:
        model.model_validate({key: "⠀ ́"})
    assert any(e["loc"][:1] == (key,) and "visible character" in e["msg"] for e in caught.value.errors())


def test_history_names_are_visible_label_fields():
    visible = {(m.__name__, n) for m, n, _f, v in NAME_FIELDS if v == [benchmark._visible_text]}
    assert {("RunHistoryUpdate", "run_name"), ("RunHistoryFromJob", "run_name"),
            ("SavedCircuitCreate", "name")} <= visible


@pytest.mark.parametrize("stored,expected", [
    ("a\x00b", "ab"), ("x‮y", "xy"), ("‮", "fallback"), (" ok ", "ok"),
    (None, "fallback"), ("⠀", "fallback"), ("n" * 300, "n" * 200),
])
def test_stored_names_are_cleaned_on_read(stored, expected):
    assert printable_name(stored, "fallback") == expected


def test_saved_run_report_carries_a_clean_name(monkeypatch):
    import services.history as history

    class Run:
        id, run_name, s3_object_key, created_at = "abcdef123456", "bad\x00name‮", "k", None

    monkeypatch.setattr(history, "_owned_run", lambda db, user_id, run_id: Run)
    monkeypatch.setattr(history, "fetch_run_report", lambda key: {"raw_results": []})
    report = history.get_run_report_with_metadata(None, 1, Run.id)
    assert report["run_name"] == "badname"
    from services.report_validation import report_problems
    assert report_problems(report) == []
