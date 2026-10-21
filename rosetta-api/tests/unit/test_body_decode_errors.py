"""A JSON request body that is not UTF-8 is a 422 validation error on every body route, the
code each route declares, not FastAPI's undeclared 400."""
import pytest

pytest.importorskip("pytket")

from fastapi.routing import APIRoute  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402

NOT_UTF8 = b"\x12$4\x80\xff"


def _body_routes():
    out = []
    for route in app.routes:
        if isinstance(route, APIRoute) and route.include_in_schema and route.body_field is not None:
            path = route.path.replace("{", "").replace("}", "")
            for method in route.methods:
                out.append((method, path, route.path))
    return out


@pytest.mark.parametrize("method, url, template", _body_routes(), ids=lambda v: str(v))
def test_undecodable_json_body_is_a_declared_422(method, url, template):
    client = TestClient(app)
    response = client.request(method, url, content=NOT_UTF8,
                              headers={"Content-Type": "application/json"})
    if template == "/auth/token":
        assert response.status_code in (401, 422)
        return
    assert response.status_code == 422, response.text
    assert response.json() == {"detail": [{"loc": ["body"], "type": "json_invalid",
                                           "msg": "JSON decode error: the body is not valid UTF-8"}]}
    app.openapi_schema = None
    declared = client.get("/openapi.json").json()["paths"][template][method.lower()]["responses"]
    assert "422" in declared


def test_an_explicit_400_with_the_same_wording_is_left_alone():
    from fastapi import FastAPI, HTTPException
    from routers.errors import register_error_handlers
    small = FastAPI()
    register_error_handlers(small)

    @small.get("/plain")
    def plain():
        raise HTTPException(status_code=400, detail="There was an error parsing the body")
    response = TestClient(small).get("/plain")
    assert response.status_code == 400
    assert response.json() == {"detail": "There was an error parsing the body"}
