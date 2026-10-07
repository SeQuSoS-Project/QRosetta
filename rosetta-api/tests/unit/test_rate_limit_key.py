"""Rate-limit key: the address the nearest proxy appended, or the address the Cloud Run
frontend saw when the request carries its token; never a caller-supplied header."""

from types import SimpleNamespace

import pytest

from services import security
from services.security import client_address


def _req(headers, host="10.0.0.5"):
    return SimpleNamespace(headers=headers, client=SimpleNamespace(host=host))


@pytest.fixture
def token(monkeypatch):
    monkeypatch.setattr(security.settings, "PROXY_TOKEN", "s3cret")
    return "s3cret"


def test_ignores_x_real_ip():
    assert client_address(_req({"x-real-ip": "6.6.6.6", "x-forwarded-for": "198.51.100.2"})) == "198.51.100.2"


def test_uses_last_forwarded_hop_not_client_supplied_first():
    assert client_address(_req({"x-forwarded-for": "6.6.6.6, 198.51.100.2"})) == "198.51.100.2"


def test_falls_back_to_socket_peer():
    assert client_address(_req({})) == "10.0.0.5"
    assert client_address(_req({"x-forwarded-for": " "})) == "10.0.0.5"


def test_frontend_client_header_with_token(token):
    headers = {"x-forwarded-for": "203.0.113.9, 34.1.2.3", "x-qrosetta-client-ip": "203.0.113.9",
               "x-qrosetta-proxy-token": token}
    assert client_address(_req(headers)) == "203.0.113.9"


@pytest.mark.parametrize("sent", [None, "", "wrong"])
def test_frontend_client_header_without_the_token_is_ignored(token, sent):
    headers = {"x-forwarded-for": "6.6.6.6, 198.51.100.2", "x-qrosetta-client-ip": "6.6.6.6"}
    if sent is not None:
        headers["x-qrosetta-proxy-token"] = sent
    assert client_address(_req(headers)) == "198.51.100.2"


def test_frontend_proxy_sends_the_client_header_and_token():
    from pathlib import Path
    infra = Path(__file__).resolve().parents[3] / "infra"
    conf = (infra / "nginx-frontend.conf").read_text()
    assert "real_ip_header X-Forwarded-For;" in conf and "real_ip_recursive on;" in conf
    assert "set_real_ip_from 0.0.0.0/0" not in conf
    assert "proxy_set_header X-Qrosetta-Client-Ip $remote_addr;" in conf
    assert 'proxy_set_header X-Qrosetta-Proxy-Token "${QROSETTA_PROXY_TOKEN}";' in conf
    dockerfile = (infra / "Dockerfile.frontend").read_text()
    assert "/etc/nginx/templates/default.conf.template" in dockerfile
    assert "NGINX_ENVSUBST_FILTER=^QROSETTA_" in dockerfile


def test_client_header_ignored_when_no_token_is_configured(monkeypatch):
    monkeypatch.setattr(security.settings, "PROXY_TOKEN", "")
    headers = {"x-forwarded-for": "198.51.100.2", "x-qrosetta-client-ip": "6.6.6.6",
               "x-qrosetta-proxy-token": ""}
    assert client_address(_req(headers)) == "198.51.100.2"
