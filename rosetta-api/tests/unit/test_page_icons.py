"""Every page names its icon (an empty data: URL), so the browser does not request /favicon.ico,
which the server does not have: a 404 there is a console error on every page load."""
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[2] / "static"


@pytest.mark.parametrize("page", sorted(p.name for p in STATIC.glob("*.html")))
def test_page_declares_its_icon(page):
    head = (STATIC / page).read_text().split("</head>")[0]
    assert '<link rel="icon" href="data:,">' in head
