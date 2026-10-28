"""V6 report-fuzzing findings: a supplied report with an integer beyond the double range, or a
backend map that is an object instead of a list, is a 400 at once on every route that reads
one; crate CSVs keep formula-like cells as recorded and the READMEs say so."""
import copy
import csv
import io
import json
import re
import time
import zipfile
from pathlib import Path

import pytest

pytest.importorskip("pytket")

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402
from services.security import limiter  # noqa: E402
from tests.unit.test_publication import MEASURED  # noqa: E402

CORPUS = Path(__file__).resolve().parents[1] / "fuzz_corpus" / "reports"
ROUTES = [("/export", {}), ("/summary", {}), ("/publication/artifacts", {}),
          ("/publication/render", {"artifact_id": "fidelity_heatmap", "format": "svg"})]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(limiter, "enabled", False)
    return TestClient(app, raise_server_exceptions=False)


def _post(client, path, body):
    return client.post(path, content=json.dumps(body).encode(),
                       headers={"Content-Type": "application/json"})


@pytest.mark.parametrize("path,extra", ROUTES)
def test_v6_11_an_integer_beyond_the_double_range_is_a_400(client, path, extra):
    report = {**copy.deepcopy(MEASURED), "n_shots": 10 ** 400}
    r = _post(client, path, {"results": report, **extra})
    assert r.status_code == 400, r.text
    assert "n_shots is an integer beyond the double-precision range" in r.json()["detail"]


@pytest.mark.parametrize("name", sorted(p.name for p in CORPUS.glob("V6-11-*.json")))
def test_v6_11_saved_reports_are_a_400(client, name):
    body = json.loads((CORPUS / name).read_text())
    path = (CORPUS / name).with_suffix(".route").read_text().strip()
    assert _post(client, path, body).status_code == 400


@pytest.mark.parametrize("field,value", [
    ("simulators", {f"k{i}": i for i in range(1000)}),
    ("ordering_map", {f"k{i}": "lsb" for i in range(49)}),
])
@pytest.mark.parametrize("path,extra", ROUTES)
def test_v6_10_a_backend_map_over_the_cap_is_a_400_at_once(client, path, extra, field, value):
    report = copy.deepcopy(MEASURED)
    report["divergence_report"][field] = value
    start = time.perf_counter()
    r = _post(client, path, {"results": report, **extra})
    assert r.status_code == 400, r.text
    assert f"divergence_report.{field} holds more than 48 entries" in r.json()["detail"]
    assert time.perf_counter() - start < 2


def test_v6_10_saved_render_request_is_a_400_at_once(client):
    body = json.loads((CORPUS / "V6-10-render-simulators-object.json").read_text())
    start = time.perf_counter()
    assert _post(client, "/publication/render", body).status_code == 400
    assert time.perf_counter() - start < 2


def test_v6_10_a_ranking_over_the_cap_is_a_400(client):
    report = copy.deepcopy(MEASURED)
    row = report["performance_report"]["ranking"][0]
    report["performance_report"]["ranking"] = [dict(row) for _ in range(49)]
    r = _post(client, "/export", {"results": report})
    assert r.status_code == 400
    assert "performance_report.ranking holds 49 entries" in r.json()["detail"]


def test_v6_13_formula_like_cells_are_written_as_recorded_and_the_readme_says_so(client):
    report = copy.deepcopy(MEASURED)
    report["performance_report"]["ranking"][0]["status"] = "=HYPERLINK(\"http://example.invalid\")"
    items = [{"view": "execution_time", "formats": ["csv"]}]
    r = _post(client, "/export", {"results": report, "publication_artifacts": {"items": items}})
    assert r.status_code == 200, r.text
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        names = zf.namelist()
        readme = zf.read(next(n for n in names if n.endswith("/README.txt"))).decode()
        cells = [cell for n in names if n.endswith(".csv")
                 for row in csv.reader(io.StringIO(zf.read(n).decode())) for cell in row]
    assert any(cell.startswith("=HYPERLINK(") for cell in cells)
    assert not any(cell.startswith("'=") for cell in cells)
    assert "is a value (a negative number, an SDK's error text, a circuit name), not a formula" \
        in re.sub(r"\s+", " ", readme)


def test_v6_13_the_experiment_readme_says_so_too():
    from services.experiment_artifacts import TRIAGE_README
    assert "is a\n    value (a negative number" in TRIAGE_README


@pytest.mark.parametrize("name", ["V6-14-render-long-label.json", "V6-14-render-simulators-string.json"])
def test_v6_14_saved_render_requests_are_a_400_at_once(client, name):
    start = time.perf_counter()
    r = _post(client, "/publication/render", json.loads((CORPUS / name).read_text()))
    assert r.status_code == 400, r.text
    assert "backends are named by runner ids" in r.json()["detail"]
    assert time.perf_counter() - start < 2


def _set(report, where, value):
    report = copy.deepcopy(report)
    if where == "simulators":
        report["divergence_report"]["simulators"] = value
    elif where == "simulators[0]":
        report["divergence_report"]["simulators"][0] = value
    elif where == "pair":
        report["divergence_report"]["pairwise_agreement"][0]["simulators"][0] = value
    elif where == "ranking":
        report["performance_report"]["ranking"][0]["simulator"] = value
    else:
        report["raw_results"][0]["simulator"] = value
    return report


@pytest.mark.parametrize("where,value", [
    ("simulators", "q" * 10_000), ("simulators[0]", "y" * 200_000), ("simulators[0]", "a" * 65),
    ("pair", "Qiskit"), ("ranking", "=cmd|' /C calc'!A0"), ("raw", "q" * 65),
])
@pytest.mark.parametrize("path,extra", ROUTES)
def test_v6_14_backend_names_must_be_runner_keys(client, path, extra, where, value):
    r = _post(client, path, {"results": _set(MEASURED, where, value), **extra})
    assert r.status_code == 400, r.text
    assert "backends are named by runner ids or <id>~opt<L>~run<N> of at most 64" in r.json()["detail"]


@pytest.mark.parametrize("path,extra", [
    ("/publication/render", {"artifact_id": "agreement_distribution", "format": "svg"}),
    ("/export", {}), ("/summary", {})])
@pytest.mark.parametrize("field", ["agreement", "registered_transform", "verdict_counts"])
def test_v6_15_a_label_drawn_on_a_figure_is_at_most_64_characters(client, path, extra, field):
    report = copy.deepcopy(MEASURED)
    divergence = report["divergence_report"]
    if field == "verdict_counts":
        divergence["statistical_test_summary"] = {"verdict_counts": {"y" * 900_000: 1}}
    else:
        divergence["pairwise_agreement"][0][field] = "y" * 900_000
    start = time.perf_counter()
    r = _post(client, path, {"results": report, **extra})
    assert r.status_code == 400, r.text
    assert "holds a label of 900000 characters; labels and codes have at most 64" in r.json()["detail"]
    assert time.perf_counter() - start < 2


def test_v6_15_saved_render_request_is_a_400(client):
    body = json.loads((CORPUS / "V6-15-render-long-agreement-label.json").read_text())
    assert _post(client, "/publication/render", body).status_code == 400


def test_v6_14_runner_keys_up_to_the_length_pass(client):
    report = _set(MEASURED, "simulators[0]", "a" * 64)
    assert "runner ids" not in _post(client, "/summary", {"results": report}).text
