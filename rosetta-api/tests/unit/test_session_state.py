"""Browser-side session state: the recorded jobs a page offers to reopen, per-tab editor circuit
and run modes, form controls the browser must not restore, the name rule shared with the
server, Load's qubit limit, API error wording and the RO-Crate download name."""
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from schemas.benchmark import Label, first_control_character, is_blank_name
from tests.unit.frontend_harness import call_js, requires_node

STATIC = Path(__file__).resolve().parents[2] / "static"
MIN = 60 * 1000
T0 = 1_800_000_000_000


def _job(job_id, t=T0, **extra):
    return {"job_id": job_id, "kind": "single", "title": job_id, "submitted_at": t, **extra}


@requires_node
def test_a_new_run_keeps_earlier_unfinished_jobs():
    r = call_js(["session_store.js"], [
        ("recordJob", [_job("a"), T0]),
        ("markJobStopped", ["a", T0 + MIN]),
        ("recordJob", [_job("b", T0 + 2 * MIN), T0 + 2 * MIN]),
        ("markJobFinished", ["b", T0 + 3 * MIN]),
        ("listJobs", [T0 + 4 * MIN]),
    ])
    jobs = {j["job_id"]: j["state"] for j in r[-1]}
    assert jobs == {"a": "stopped", "b": "finished"}


@requires_node
def test_finished_jobs_expire_with_the_server_copy_and_unfinished_after_six_hours():
    r = call_js(["session_store.js"], [
        ("recordJob", [_job("done"), T0]),
        ("markJobFinished", ["done", T0 + MIN]),
        ("recordJob", [_job("open"), T0]),
        ("listJobs", [T0 + 30 * MIN]),
        ("listJobs", [T0 + 32 * MIN]),
        ("listJobs", [T0 + 6 * 60 * MIN + 1]),
    ])
    assert {j["job_id"] for j in r[3]} == {"done", "open"}
    assert [j["job_id"] for j in r[4]] == ["open"]
    assert r[5] == []


@requires_node
def test_forget_and_sign_out_drop_jobs():
    r = call_js(["session_store.js"], [
        ("recordJob", [_job("anon"), T0]),
        ("recordJob", [_job("mine", account="x@y.z"), T0]),
        ("recordJob", [_job("gone"), T0]),
        ("forgetJob", ["gone"]),
        ("forgetSignedInJobs", []),
        ("listJobs", [T0 + MIN]),
    ])
    assert [j["job_id"] for j in r[-1]] == ["anon"]


@requires_node
def test_editor_circuit_and_modes_are_kept_per_tab():
    qa, qb = "OPENQASM 2.0;\nqreg q[1];\n// A\n", "OPENQASM 2.0;\nqreg q[1];\n// B\n"
    r = call_js(["session_store.js"], [
        ("saveEditorCircuit", [qa, "A"]),
        ("saveRunModes", [{"statevector": False, "measured": True}]),
        ("__newTab__", []),
        ("loadEditorCircuit", []),
        ("loadRunModes", []),
        ("saveEditorCircuit", [qb, "B"]),
        ("loadEditorCircuit", []),
    ])
    assert r[3]["name"] == "A"
    assert r[4] == {"statevector": False, "measured": True}
    assert r[6]["name"] == "B"


def test_static_form_controls_are_not_restored_by_the_browser():
    html = (STATIC / "index.html").read_text()
    tags = re.findall(r"<(?:input|select|textarea)\b[^>]*>", html)
    missing = [t for t in tags if "autocomplete=" not in t]
    assert not missing, missing
    restorable = [t for t in tags if 'autocomplete="off"' not in t]
    assert all('type="email"' in t or 'type="password"' in t for t in restorable), restorable
    assert "pagehide" in (STATIC / "js" / "app.js").read_text()


def test_narrow_screens_stack_into_one_scrolling_column():
    """Phones and tablets up to 1023 px (lg) get one scrolling column; the results-reveal
    media query in workspace.js uses the same breakpoint."""
    html = (STATIC / "index.html").read_text()
    scroll = re.search(r'id="workspace-scroll" class="([^"]+)"', html).group(1).split()
    assert "overflow-y-auto" not in scroll and "lg:overflow-y-auto" in scroll
    outer = re.search(r'<div class="(flex flex-col [^"]*)">\s*<header', html).group(1).split()
    assert "h-screen" not in outer and "lg:h-screen" in outer
    assert not re.search(r'\bmd:(h-screen|flex-row|w-1/2|overflow-y-auto|min-h-0)', html)
    assert "(max-width: 1023px)" in (STATIC / "js" / "workspace.js").read_text()


NAMES = [
    ("👩‍🔬 lab run", None),
    ("🏳️‍🌈", None),
    ("🧑\U0001F3FD‍💻", None),
    ("\U0001F3F4\U000E0067\U000E0062\U000E0073\U000E0063\U000E0074\U000E007F", None),
    ("\U0001FAF1\U0001F3FB‍\U0001FAF2\U0001F3FC", None),
    ("\U0001F642‍↔️", None),
    ("می‌خواهم", None),
    ("क्‍ष", None),
    ("a‍b", None),
    ("lab­run", (4, "U+00AD")),
    ("x‮y", (2, "U+202E")),
    ("x⁧y", (2, "U+2067")),
    ("a​b", (2, "U+200B")),
    ("﻿name", (1, "U+FEFF")),
    ("a⁠b", (2, "U+2060")),
    ("x\u0085", (2, "U+0085")),
    ("ㅤ", (1, "U+3164")),
    ("line\nbreak", (5, "U+000A")),
    ("para graph", (5, "U+2029")),
]


@requires_node
@pytest.mark.parametrize("name,bad", NAMES)
def test_name_rule_is_the_same_in_browser_and_server(name, bad):
    js_bad, js_problem, js_clean = call_js(["request_limits.js"], [
        ("firstUnprintable", [name]), ("labelProblem", [name, 200, "The run name"]), ("printableLabel", [name, 200])])
    py_bad = first_control_character(name)
    if bad is None:
        assert js_bad is None and py_bad is None and js_problem is None and js_clean == name.strip()
        TypeAdapter(Label).validate_python(name)
        return
    assert (js_bad["position"], js_bad["code"]) == bad
    assert (py_bad[0], f"U+{ord(py_bad[1]):04X}") == bad
    assert js_problem.endswith(f"character {bad[0]} is {bad[1]}.")
    with pytest.raises(ValidationError, match=re.escape(f"character {bad[0]} is {bad[1]}")):
        TypeAdapter(Label).validate_python(name)


@requires_node
def test_load_checks_the_ticked_modes_qubit_limit():
    limits = {"statevector": 18, "measured": 24, "compile": 24}
    r = call_js(["request_limits.js"], [
        ("loadQubitProblem", [18, {"statevector": True, "measured": False}, limits]),
        ("loadQubitProblem", [20, {"statevector": True, "measured": False}, limits]),
        ("loadQubitProblem", [30, {"statevector": True, "measured": True}, limits]),
        ("loadQubitProblem", [20, {"statevector": False, "measured": True}, limits]),
        ("loadQubitProblem", [25, {"statevector": False, "measured": True}, limits]),
        ("loadQubitProblem", [25, {"statevector": False, "measured": False}, limits]),
    ])
    assert r[0] is None
    assert "at most 18 qubits" in r[1] and "up to 24 qubits" in r[1]
    assert "at most 18 qubits" in r[2] and "24" not in r[2]
    assert r[3] is None
    assert "Measured runs allow at most 24" in r[4]
    assert "Compile-only runs allow at most 24" in r[5]


@requires_node
def test_api_errors_read_as_plain_messages():
    detail = [{"loc": ["body", "email"], "msg": "Value error, email must be a valid address such as name@example.org"},
              {"loc": ["body", "password"], "msg": "too short"}]
    r = call_js(["api.js"], [
        ("apiDetailText", [detail]),
        ("apiErrorText", [403, "This job was started by another signed-in account."]),
        ("apiErrorText", [422, "x"]),
        ("apiErrorText", [500, ""]),
    ])
    assert r[0] == "Email must be a valid address such as name@example.org\npassword: too short"
    assert r[1] == "This job was started by another signed-in account."
    assert r[2] == "The server rejected the request (HTTP 422): x"
    assert r[3].startswith("Request failed (HTTP 500)")


@requires_node
def test_crate_file_name_is_utc_and_names_the_run():
    when = int(datetime(2026, 10, 7, 21, 5, 53, tzinfo=timezone.utc).timestamp() * 1000)
    r = call_js(["utils.js"], [("crateFileName", ["Café GHZ (Statevector)", when]), ("crateFileName", [None, when])])
    assert r == ["rosetta-export-2026-10-07-2105UTC-cafe-ghz-statevector.zip", "rosetta-export-2026-10-07-2105UTC.zip"]


BLANK_NAMES = [("   ", True), ("", True), ("‍‌", True), ("️ \t", True),
               ("a", False), (" \U0001F642 ", False)]


@requires_node
@pytest.mark.parametrize("name,blank", BLANK_NAMES)
def test_blank_name_rule_is_the_same_in_browser_and_server(name, blank):
    js_blank, js_clean = call_js(["request_limits.js"], [("isBlankName", [name]), ("printableLabel", [name, 200])])
    assert js_blank is blank and is_blank_name(name) is blank
    if blank:
        assert js_clean == ""


@pytest.mark.parametrize("model,field", [("RunHistoryUpdate", "run_name"), ("RunHistoryFromJob", "run_name"),
                                         ("SavedCircuitCreate", "name")])
@pytest.mark.parametrize("name", ["   ", "　", "‍"])
def test_saved_names_need_a_visible_character(model, field, name):
    import schemas
    body = {field: name}
    if model == "SavedCircuitCreate":
        body["qasm_string"] = "OPENQASM 2.0;"
    with pytest.raises(ValidationError, match="at least one visible character"):
        getattr(schemas, model).model_validate(body)
