"""POST /plan plans what the page's own planner did: on a corpus of workspaces, the planned
requests (endpoint, kind, mode, title, payload) and the refusal texts equal those of
run_plan.js planRuns and runLimitProblems, and the request sizes equal jsonBytes."""
import json

import pytest

pytest.importorskip("pytket")

from schemas.plan import PlanRequest  # noqa: E402
from services.plan import limit_problems, plan_runs  # noqa: E402
from services.plan_text import js_json_bytes  # noqa: E402
from tests.unit.frontend_harness import call_js, requires_node  # noqa: E402
from tests.unit.plan_corpus import corpus, js_limits, plan_request  # noqa: E402

pytestmark = requires_node

_SHOWN = ("endpoint", "kind", "mode", "title", "payload")


def _js_plans(cases):
    names = call_js(["request_limits.js"], [("printableLabel", [ws["rawRunName"], 200]) for ws in cases])
    calls = []
    for ws, name in zip(cases, names):
        page_ws = {k: v for k, v in ws.items() if k != "rawRunName"}
        page_ws["runName"] = name
        page_ws["limits"] = {"maxLabelLength": 200}
        calls.append(("planRuns", [page_ws]))
    return call_js(["run_plan.js"], calls)


def _server_plans(cases):
    out = []
    for ws in cases:
        runs, problem = plan_runs(PlanRequest(**plan_request(ws)))
        out.append((runs, problem, [] if problem else limit_problems(runs)))
    return out


@pytest.fixture(scope="module")
def results():
    cases = corpus()
    js = _js_plans(cases)
    server = _server_plans(cases)
    limits = js_limits()
    texts = call_js(["run_plan.js"], [
        ("runLimitProblems", [plan["runs"], limits]) for plan in js] + [
        ("planProblemTexts", [problems if not problem else [problem], runs])
        for runs, problem, problems in server])
    n = len(cases)
    payloads = [run["payload"] for plan in js for run in plan["runs"]]
    sizes = call_js(["request_limits.js"], [("jsonBytes", [p]) for p in payloads])
    return {"cases": cases, "js": js, "server": server, "js_texts": texts[:n],
            "server_texts": texts[n:], "payloads": payloads, "sizes": sizes}


def test_planned_requests_are_identical(results):
    differences = []
    for i, (js, (runs, problem, _)) in enumerate(zip(results["js"], results["server"])):
        server_runs = [{k: r[k] for k in _SHOWN} for r in runs]
        page_runs = [{k: r.get(k) for k in _SHOWN} for r in js["runs"]]
        if json.loads(json.dumps(server_runs)) != page_runs:
            differences.append(i)
        if (problem is None) != (js["error"] is None):
            differences.append(i)
    assert differences == []


def test_refusal_texts_are_identical(results):
    differences = []
    for i, (js, (_runs, problem, _p), js_texts, server_texts) in enumerate(zip(
            results["js"], results["server"], results["js_texts"], results["server_texts"])):
        expected = [js["error"]] if js["error"] else js_texts
        if expected != server_texts:
            differences.append((i, expected[:1], server_texts[:1]))
    assert differences == []


def test_request_sizes_are_identical(results):
    assert [js_json_bytes(p) for p in results["payloads"]] == results["sizes"]


def test_the_corpus_reaches_every_limit(results):
    codes = {p["code"] for _runs, problem, problems in results["server"]
             for p in ([problem] if problem else problems)}
    assert {"playlist_empty", "editor_empty", "no_mode", "compile_only_needs_one_setting",
            "playlist_too_long", "bundled_over_prep_limit", "experiment_too_many_cells",
            "circuit_too_large", "request_too_large"} <= codes
