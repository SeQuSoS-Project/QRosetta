"""GET /publication/views: every export view of views.VIEWS with its parameters, defaults and
allowed values, and formats the render routes and crate items accept."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import publication
from routers.errors import register_error_handlers
from services.publication import list_artifacts
from services.publication.items import _prepare
from services.publication.views import VIEWS, normalize_params, view_defaults, view_param_specs
from tests.unit.test_artifacts_parity import _counts_rich
from tests.unit.test_publication import MEASURED, STATEVECTOR


@pytest.fixture(scope="module")
def listing():
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(publication.router)
    response = TestClient(app).get("/publication/views")
    assert response.status_code == 200
    return response.json()


def test_every_view_in_order_with_its_parameters(listing):
    assert [v["id"] for v in listing["views"]] == [v["id"] for v in VIEWS]
    for entry in listing["views"]:
        specs = view_param_specs(entry["id"])
        assert [p["name"] for p in entry["params"]] == list(specs)
        assert {p["name"]: p["default"] for p in entry["params"]} == view_defaults(entry["id"])
        for p in entry["params"]:
            assert (p["default"] is None) == ("default_when_null" in p)
            if p["type"] == "choice":
                assert p["choices"] == list(specs[p["name"]][1])
    assert listing["scale"] == {"min": 1, "max": 4}


@pytest.mark.parametrize("report", [_counts_rich(), MEASURED])
def test_listed_values_are_accepted(listing, report):
    for entry in listing["views"]:
        for p in entry["params"]:
            values = (p.get("choices") or []) + [p["default"]] + [p[k] for k in ("min", "max") if k in p]
            for value in values:
                if value is not None:
                    normalize_params(entry["id"], {p["name"]: value}, report)


@pytest.mark.parametrize("mode,report", [("measured", _counts_rich()), ("statevector", STATEVECTOR)])
def test_formats_match_the_catalog_and_the_items(listing, mode, report):
    catalog = {a["id"]: a for a in list_artifacts(report, mode)}
    for entry in listing["views"]:
        for artifact in entry["artifacts"]:
            if artifact["artifact_id"] in catalog:
                assert artifact["formats"] == catalog[artifact["artifact_id"]]["formats"]
        _prepare(report, [{"view": entry["id"], "params": {}, "formats": entry["item_formats"]}])
