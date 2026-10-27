"""The OpenAPI contract older qrosetta CLIs rely on (CLI spec S16): the app serves the committed
baseline, the comparison refuses breaking changes and allows additive ones, every route the
CLI client names is covered, and the documentation-only response models match what the
routes return without changing it."""

import ast
import json
import re
from pathlib import Path
from typing import List, Literal, Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from tests import openapi_cli_contract as contract

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def now():
    return contract.current()


def test_the_app_serves_every_route_of_the_baseline(now):
    baseline = contract.load_baseline()
    refused, notes = contract.verdict(baseline, now)
    assert not refused, "\n".join(refused + ["refresh: PYTHONPATH=.:../shared python -m tests.openapi_cli_contract --write"])
    assert set(baseline["routes"]) == set(contract.CLI_ROUTES), "refresh the baseline after changing CLI_ROUTES"
    assert set(now["routes"]) == set(contract.CLI_ROUTES)


def test_the_baseline_is_deterministic(now):
    assert contract.dumps(contract.current()) == contract.dumps(now)
    text = Path(contract.BASELINE).read_text(encoding="utf-8")
    assert text == contract.dumps(json.loads(text))


class Row(BaseModel):
    id: str
    available: bool
    device: Optional[str]


class RowMore(Row):
    profiles: List[str]


class RowRenamed(BaseModel):
    key: str
    available: bool
    device: Optional[str]


class RowNullable(BaseModel):
    id: Optional[str]
    available: bool
    device: Optional[str]


class RowNarrowed(BaseModel):
    id: str
    available: bool
    device: str


class RowOptionalId(BaseModel):
    id: Optional[str] = None
    available: bool
    device: Optional[str]


class Req(BaseModel):
    qasm: str
    mode: Literal["statevector", "measured"] = "statevector"


class ReqOptional(Req):
    seed: Optional[int] = None


class ReqRequired(Req):
    seed: int


class ReqWideMode(BaseModel):
    qasm: str
    mode: Literal["statevector", "measured", "compile"] = "statevector"


class ReqNarrowMode(BaseModel):
    qasm: str
    mode: Literal["statevector"] = "statevector"


class ReqIntQasm(BaseModel):
    qasm: int
    mode: Literal["statevector", "measured"] = "statevector"


def _routes(row=Row, req=Req, extra_param=False, drop_post=False, status=200):
    app = FastAPI()

    if extra_param:
        @app.get("/rows", responses={200: {"model": List[row]}})
        def rows(limit: int, fresh: bool = False):
            return []
    else:
        @app.get("/rows", responses={200: {"model": List[row]}})
        def rows(fresh: bool = False):
            return []

    if not drop_post:
        @app.post("/run", response_model=Row, status_code=status)
        def run(payload: req):
            return {}

    return contract.extract(app.openapi(), ("GET /rows", "POST /run"))


def _found(**changes):
    return contract.compare(_routes(), _routes(**changes))


def _breaking(**changes):
    return [f"{where}: {msg}" for breaking, where, msg in _found(**changes) if breaking]


@pytest.mark.parametrize("changes", [
    {"row": RowMore},
    {"req": ReqOptional},
    {"req": ReqWideMode},
    {"row": RowNarrowed},
])
def test_additive_changes_are_allowed(changes):
    assert _found(**changes) and not _breaking(**changes)


@pytest.mark.parametrize("changes, expected", [
    ({"row": RowRenamed}, "GET /rows response[].id: removed"),
    ({"row": RowNullable}, "GET /rows response[].id: may return"),
    ({"row": RowOptionalId}, "GET /rows response[].id: no longer always present"),
    ({"req": ReqRequired}, "POST /run body.seed: added, required"),
    ({"req": ReqNarrowMode}, "POST /run body.mode: accepts only ['statevector']"),
    ({"req": ReqIntQasm}, "POST /run body.qasm: accepts ['integer']"),
    ({"extra_param": True}, "GET /rows parameter query:limit: added, required"),
    ({"drop_post": True}, "POST /run: removed"),
    ({"status": 201}, "POST /run response: status 201 (was 200)"),
])
def test_breaking_changes_are_refused(changes, expected):
    breaking = _breaking(**changes)
    assert any(line.startswith(expected) for line in breaking), breaking


def test_a_raised_api_level_covers_a_breaking_change():
    base = {"api_levels": [1, 1], "routes": _routes()}
    broken = _routes(row=RowRenamed)
    refused, _ = contract.verdict(base, {"api_levels": [1, 1], "routes": broken})
    assert refused
    refused, notes = contract.verdict(base, {"api_levels": [1, 2], "routes": broken})
    assert not refused and any(n.startswith("breaking, covered by API level 2") for n in notes)


def _client_route_literals():
    for path in sorted((REPO / "qrosetta_cli" / "client").glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                text = node.value
            elif isinstance(node, ast.JoinedStr):
                text = "".join(v.value if isinstance(v, ast.Constant) else "x" for v in node.values)
            else:
                continue
            m = re.fullmatch(r"(?:(?:GET|POST|PUT|PATCH|DELETE) )?(/[A-Za-z0-9_./{}-]+)", text)
            if m and len(m.group(1)) > 1:
                yield path.name, m.group(1)


def test_every_server_route_the_cli_client_names_is_in_the_contract():
    from main import app
    covered = set(contract.CLI_ROUTES) | set(contract.EXPERIMENTAL_ROUTES)
    matched = set()
    for module, sample in _client_route_literals():
        routes = [r for r in app.routes if getattr(r, "path_regex", None) and r.path_regex.match(sample)]
        for route in routes:
            names = {f"{m} {route.path}" for m in (route.methods or ())}
            assert names & covered, f"{module} reads {sample} ({sorted(names)}): add it to CLI_ROUTES or EXPERIMENTAL_ROUTES"
            matched |= names & covered
    assert {"GET /config", "POST /plan", "GET /jobs/{job_id}/summary"} <= matched


DOCUMENTED = {
    "/config": "ServerConfig", "/runners": "RunnerList", "/compilers": "CompilerList",
    "/algorithms": "AlgorithmList", "/examples": "ExampleList", "/examples/{name}": "ExampleText",
    "/generate_circuit": "QasmText", "/benchmarks/mqt/list": "MqtIndex",
    "/benchmarks/qasmbench/list": "QasmbenchIndex", "/benchmarks/mqt": "QasmText",
    "/benchmarks/qasmbench": "QasmText",
}


def test_documentation_models_never_filter_a_response():
    from main import app
    for route in app.routes:
        if getattr(route, "path", None) in DOCUMENTED:
            assert route.response_model is None, route.path
            assert route.responses[200]["model"].__name__ == DOCUMENTED[route.path]


@pytest.fixture
def client(monkeypatch):
    import services.service_listing as listing
    from main import app
    from services.security import limiter

    async def availability(names=None, services=None):
        from config import settings
        registry = services if services is not None else settings.get_runner_services()
        return {n: {"available": i % 2 == 0, "reason": None if i % 2 == 0 else "unreachable", "device": None,
                    **({"versions": {"sdk_versions": {"x": "1"}}} if services is not None else {})}
                for i, n in enumerate(names if names is not None else registry)}

    monkeypatch.setattr(listing, "runner_availability", availability)
    monkeypatch.setattr(limiter, "enabled", False)
    return TestClient(app)


def test_documentation_models_describe_the_real_responses(client):
    from schemas import listings as m
    first_example = client.get("/examples").json()[0]["name"]
    cases = [("GET", "/config", None, m.ServerConfig), ("GET", "/runners", None, m.RunnerList),
             ("GET", "/compilers", None, m.CompilerList), ("GET", "/algorithms", None, m.AlgorithmList),
             ("GET", "/examples", None, m.ExampleList), ("GET", f"/examples/{first_example}", None, m.ExampleText),
             ("GET", "/benchmarks/mqt/list", None, m.MqtIndex),
             ("GET", "/benchmarks/qasmbench/list", None, m.QasmbenchIndex),
             ("GET", "/benchmarks/mqt?algorithm=ghz&qubits=3", None, m.QasmText),
             ("GET", "/benchmarks/qasmbench?circuit=adder_n4", None, m.QasmText),
             ("POST", "/generate_circuit", {"algorithm": "ghz", "qubits": 3}, m.QasmText)]
    for method, path, body, model in cases:
        r = client.request(method, path, json=body)
        assert r.status_code == 200, path
        model.model_validate(r.json())
        schema = model.model_json_schema()
        listed = set(schema.get("properties") or {})
        data = r.json()
        if listed and isinstance(data, dict):
            assert set(schema.get("required", [])) <= set(data), path
