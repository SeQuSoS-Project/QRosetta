"""Every response carries a Content-Security-Policy and the other browser security headers,
from the API (routers/security_headers.py) and from both nginx configs for the files nginx
serves itself, with the same policies in both places."""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from routers.security_headers import (COMMON_HEADERS, NON_HTML_CSP, PAGE_CSP, REDOC_CSP, SHARE_CSP,
                                      SWAGGER_CSP, content_security_policy)

ROOT = Path(__file__).resolve().parents[3]
CONFS = ["nginx/nginx.conf", "infra/nginx-frontend.conf"]


@pytest.fixture(scope="module")
def client():
    from main import app
    return TestClient(app)


@pytest.mark.parametrize("path,policy", [
    ("/", PAGE_CSP), ("/static/index.html", PAGE_CSP), ("/static/docs.html", PAGE_CSP),
    ("/static/share.html", SHARE_CSP), ("/docs", SWAGGER_CSP), ("/redoc", REDOC_CSP),
    ("/config", NON_HTML_CSP), ("/js/main.js", NON_HTML_CSP), ("/css/tailwind.css", NON_HTML_CSP),
    ("/no-such-route", NON_HTML_CSP),
])
def test_api_responses_carry_the_policy_of_their_path(client, path, policy):
    r = client.get(path)
    assert r.headers["content-security-policy"] == policy, path
    for key, value in COMMON_HEADERS.items():
        assert r.headers[key] == value, (path, key)


def test_error_responses_carry_the_headers(client):
    r = client.post("/compare", content=b"x" * 2_000_000, headers={"Content-Type": "application/json"})
    assert r.status_code == 413
    assert r.headers["content-security-policy"] == NON_HTML_CSP
    assert r.headers["x-content-type-options"] == "nosniff"


def test_share_page_is_not_cached(client):
    assert client.get("/static/share.html").headers["cache-control"] == "no-store"


def test_policies_hold_the_required_directives():
    for policy in (PAGE_CSP, SHARE_CSP, SWAGGER_CSP, REDOC_CSP, NON_HTML_CSP):
        directives = dict(d.strip().split(" ", 1) for d in policy.split(";"))
        assert directives["frame-ancestors"] == "'none'" and directives["base-uri"] == "'none'"
        assert "'unsafe-eval'" not in policy
    for policy in (PAGE_CSP, SHARE_CSP, SWAGGER_CSP):
        directives = dict(d.strip().split(" ", 1) for d in policy.split(";"))
        assert directives["script-src"] == "'self'" and directives["style-src"] == "'self'"
        assert directives["object-src"] == "'none'" and directives["default-src"] == "'self'"
    assert "'unsafe-inline'" not in PAGE_CSP + SHARE_CSP + SWAGGER_CSP
    assert "frame-src https://quirk-e.dev;" in PAGE_CSP


def test_policy_choice():
    assert content_security_policy("/x/share.html", "text/html") == SHARE_CSP
    assert content_security_policy("/anything", "text/html; charset=utf-8") == PAGE_CSP
    assert content_security_policy("/publication/render", "image/svg+xml") == NON_HTML_CSP


def _maps(text):
    return {(m.group(1), m.group(2)): m.group(3)
            for m in re.finditer(r"map \$(\S+) \$(\S+) \{(.*?)\n\s*\}", text, re.S)}


@pytest.mark.parametrize("conf", CONFS)
def test_nginx_sends_the_api_policies_for_its_own_files(conf):
    text = (ROOT / conf).read_text()
    maps = _maps(text)
    own = maps[("uri", "qr_own_csp")]
    assert f'/share.html "{SHARE_CSP}";' in own
    assert f'default     "{PAGE_CSP}";' in own
    expected = {"content_security_policy": "qr_csp", "x_content_type_options": "qr_nosniff",
                "referrer_policy": "qr_referrer_policy", "cross_origin_opener_policy": "qr_coop",
                "x_frame_options": "qr_frame_options"}
    for header, var in expected.items():
        body = maps[(f"upstream_http_{header}", var)]
        assert re.search(r'^\s*default\s+"";', body, re.M), (conf, header)
    assert re.search(r'^\s*""\s+\$qr_own_csp;', maps[("upstream_http_content_security_policy", "qr_csp")], re.M)
    for name, value in COMMON_HEADERS.items():
        var = expected[name.lower().replace("-", "_")]
        assert re.search(rf'^\s*""\s+"{re.escape(value)}";', maps[(f"upstream_http_{name.lower().replace('-', '_')}", var)], re.M)
        assert re.search(rf"^\s*add_header {name} \${var} always;", text, re.M), (conf, name)
    assert re.search(r"^\s*add_header Content-Security-Policy \$qr_csp always;", text, re.M)
    assert re.search(r"^\s*add_header_inherit merge;", text, re.M)


@pytest.mark.parametrize("conf", CONFS)
def test_nginx_locations_add_no_security_header_of_their_own(conf):
    text = (ROOT / conf).read_text()
    for block in re.findall(r"location [^{]*\{(.*?)\n\s*\}", text, re.S):
        for name in ["Content-Security-Policy", *COMMON_HEADERS]:
            assert f"add_header {name}" not in block, (conf, name)
