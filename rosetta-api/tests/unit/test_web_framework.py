"""Framework settings of the API app: a JSON body sent without Content-Type is read as JSON,
response models go through JSONResponse (json.dumps, no NaN), and the login form parser
refuses more than 1,000 fields."""
import pytest

pytest.importorskip("pytket")

from fastapi.responses import JSONResponse  # noqa: E402
from fastapi.routing import APIRoute  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402


def test_a_json_body_without_content_type_is_read_as_json():
    response = TestClient(app).post("/plan", content=b'{"unknown_field": 1}')
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert {"loc": ["body", "unknown_field"], "msg": "Extra inputs are not permitted",
            "type": "extra_forbidden"} in errors


def test_response_models_are_serialised_by_json_response():
    routes = [r for r in app.routes if isinstance(r, APIRoute) and r.response_field is not None]
    assert routes
    assert [r.path for r in routes if r.response_class is not JSONResponse] == []


def test_a_non_finite_float_in_a_response_model_is_refused():
    with pytest.raises(ValueError, match="not JSON compliant"):
        JSONResponse({"value": float("nan")})


def test_a_login_form_of_more_than_1000_fields_is_a_400():
    body = "&".join(f"f{i}=1" for i in range(1001)).encode()
    response = TestClient(app).post("/auth/token", content=body,
                                    headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert response.status_code == 400
    assert response.json() == {"detail": "Too many fields. Maximum number of fields is 1000."}
