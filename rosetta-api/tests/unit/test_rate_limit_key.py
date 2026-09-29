"""Rate-limit key: the client address recorded by the nearest proxy."""

from types import SimpleNamespace

from services.security import client_address


def _req(headers, host="10.0.0.5"):
    return SimpleNamespace(headers=headers, client=SimpleNamespace(host=host))


def test_prefers_x_real_ip():
    assert client_address(_req({"x-real-ip": "203.0.113.9", "x-forwarded-for": "1.1.1.1, 203.0.113.9"})) == "203.0.113.9"


def test_uses_last_forwarded_hop_not_client_supplied_first():
    assert client_address(_req({"x-forwarded-for": "6.6.6.6, 198.51.100.2"})) == "198.51.100.2"


def test_falls_back_to_socket_peer():
    assert client_address(_req({})) == "10.0.0.5"
