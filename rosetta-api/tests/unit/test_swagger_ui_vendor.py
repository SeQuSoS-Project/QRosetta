"""The /docs page loads Swagger UI from the vendored copy in static/vendor: every file matches its
recorded sha256, the page references only same-origin files that exist where nginx and the API
serve them, and it carries no inline script."""
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path

from fastapi.openapi.docs import swagger_ui_default_parameters
from fastapi.testclient import TestClient
from starlette.requests import Request

from routers.frontend import SWAGGER_UI_VERSION, swagger_ui_page

_API = Path(__file__).resolve().parents[2]
_STATIC = _API / "static"
_VENDOR = _STATIC / "vendor" / "swagger-ui"
_MANIFEST = json.loads((_VENDOR / "manifest.json").read_text())


class _Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls, self.scripts, self.handlers, self._in_script = [], [], [], False
        self.inline_script = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.handlers += [name for name in attrs if name.startswith("on")]
        if tag == "script":
            self.scripts.append(attrs)
            self._in_script = True
        for name in ("src", "href"):
            if attrs.get(name):
                self.urls.append(attrs[name])

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_script = False

    def handle_data(self, data):
        if self._in_script:
            self.inline_script += data.strip()


def _parse(html: str) -> _Page:
    page = _Page()
    page.feed(html)
    return page


def test_vendored_files_match_the_manifest():
    assert _MANIFEST["package"] == "swagger-ui-dist"
    assert _MANIFEST["version"] == SWAGGER_UI_VERSION
    assert sorted(p.name for p in _VENDOR.iterdir() if p.is_dir()) == [SWAGGER_UI_VERSION]
    files = _VENDOR / SWAGGER_UI_VERSION
    assert sorted(p.name for p in files.iterdir()) == sorted(_MANIFEST["sha256"])
    for name, digest in _MANIFEST["sha256"].items():
        assert hashlib.sha256((files / name).read_bytes()).hexdigest() == digest, name
    assert {"LICENSE", "NOTICE"} <= set(_MANIFEST["sha256"])


def test_docs_page_loads_only_vendored_same_origin_files():
    from main import app
    client = TestClient(app)
    response = client.get("/docs")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "http://" not in response.text and "https://" not in response.text
    page = _parse(response.text)
    assert not page.inline_script and not page.handlers
    assert all(script.get("src") for script in page.scripts)
    assert len(page.urls) == 5, page.urls
    for url in page.urls:
        assert url.startswith("/") and not url.startswith("//"), url
        on_disk = _STATIC / url.lstrip("/")
        assert on_disk.is_file(), url
        served = client.get(url)
        assert served.status_code == 200, url
        assert served.content == on_disk.read_bytes(), url
    vendored = {url.rsplit("/", 1)[1] for url in page.urls if url.startswith("/vendor/")}
    assert vendored == {"swagger-ui-bundle.js", "swagger-ui.css", "favicon-16x16.png",
                        "favicon-32x32.png"}


def test_docs_page_prefixes_assets_and_spec_with_the_root_path():
    from main import app
    request = Request({"type": "http", "method": "GET", "path": "/docs", "headers": [],
                       "query_string": b"", "root_path": "/proxied/", "app": app})
    page = _parse(swagger_ui_page(request))
    assert page.urls and all(url.startswith("/proxied/") for url in page.urls), page.urls
    assert 'data-openapi-url="/proxied/openapi.json"' in swagger_ui_page(request)


def test_initialiser_sets_fastapis_default_options():
    script = (_STATIC / "js" / "api_docs_main.js").read_text()
    for name in swagger_ui_default_parameters:
        assert f"{name}:" in script, name
    assert "validatorUrl: null" in script


def test_third_party_notices_list_the_vendored_copy():
    notices = (_API.parent / "THIRD_PARTY_NOTICES.md").read_text()
    assert f"rosetta-api/static/vendor/swagger-ui/{SWAGGER_UI_VERSION}/" in notices
