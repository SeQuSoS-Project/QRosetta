"""OpenAPI media types: routes that send a page or a file declare that media type for 200,
and not application/json."""
import pytest

pytest.importorskip("pytket")

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402
from services.publication.theme import MIME_TYPES  # noqa: E402

ZIP_ROUTES = [("/export", "post"), ("/jobs/{job_id}/export", "post"),
              ("/history/runs/{run_id}/export", "post"), ("/experiments/{job_id}/bundle", "get")]
RENDER_ROUTES = [("/publication/render", "post"), ("/jobs/{job_id}/publication/render", "post")]


@pytest.fixture(scope="module")
def spec():
    app.openapi_schema = None
    return TestClient(app).get("/openapi.json").json()


def _ok_media_types(spec, path, method):
    return set(spec["paths"][path][method]["responses"]["200"].get("content", {}))


@pytest.mark.parametrize("path, method", ZIP_ROUTES)
def test_zip_routes_declare_application_zip_only(spec, path, method):
    assert _ok_media_types(spec, path, method) == {"application/zip"}


@pytest.mark.parametrize("path, method", RENDER_ROUTES)
def test_render_routes_declare_every_format_media_type_and_no_json(spec, path, method):
    declared = _ok_media_types(spec, path, method)
    assert set(MIME_TYPES.values()) <= declared
    assert "application/json" not in declared


def test_index_page_is_declared_and_sent_as_html(spec):
    assert _ok_media_types(spec, "/", "get") == {"text/html"}
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].split(";")[0] == "text/html"


def test_no_route_declares_json_beside_a_file_type(spec):
    binary = {"application/zip", "image/png", "application/pdf", "text/html"}
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            declared = set(op["responses"].get("200", {}).get("content", {}))
            assert not (declared & binary and "application/json" in declared), (method, path, declared)
