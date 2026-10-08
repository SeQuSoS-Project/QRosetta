"""Both nginx configs answer an oversized body with the API's JSON error shape and compress
responses."""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("conf", ["nginx/nginx.conf", "infra/nginx-frontend.conf"])
def test_oversized_body_gets_json_detail(conf):
    text = (ROOT / conf).read_text()
    assert re.search(r"error_page\s+413\s+=\s+@too_large;", text)
    block = re.search(r"location @too_large \{(.*?';)\s*\}", text, re.S).group(1)
    assert "default_type application/json;" in block
    body = re.search(r"return 413 '(.*)';", block).group(1)
    assert isinstance(json.loads(body)["detail"], str)


@pytest.mark.parametrize("conf", ["nginx/nginx.conf", "infra/nginx-frontend.conf"])
def test_responses_are_compressed_by_nginx(conf):
    text = (ROOT / conf).read_text()
    assert re.search(r"^\s*gzip on;", text, re.M)
    assert re.search(r"^\s*gzip_proxied any;", text, re.M)
    assert re.search(r"^\s*gzip_types[^;]*application/json", text, re.M)
