"""An SVG figure whose names carry markup stays well-formed XML with no script, and the render
routes send figures as attachments under a policy that runs nothing."""
import copy
import xml.etree.ElementTree as ET

import pytest
from fastapi.testclient import TestClient

from routers.security_headers import NON_HTML_CSP
from services.publication import render_artifact
from tests.unit.test_publication import MEASURED

NAMES = ["</text><script>window.x=1</script>", "a ]]> b <![CDATA[ c", '<img src=x onerror="window.x=1">',
         "‮gnp.exe‬"]
VIEWS = [("performance_time", {}), ("resource_memory", {}), ("counts_overview", {}),
         ("counts_overview", {"layout": "heatmap"}), ("qubit_marginals", {}), ("hamming_weight", {}),
         ("rank_probability", {})]


def _assert_inert(svg: bytes, where):
    root = ET.fromstring(svg)
    for el in root.iter():
        tag = el.tag.rsplit("}", 1)[-1].lower()
        assert tag not in ("script", "foreignobject", "iframe"), where
        for attr in el.attrib:
            name = attr.rsplit("}", 1)[-1].lower()
            assert not name.startswith("on"), where
            if name == "href":
                href = el.attrib[attr].lstrip().lower()
                assert href.startswith(("#", "data:image/png;")), (where, href[:40])


@pytest.mark.parametrize("name", NAMES)
def test_svg_with_markup_in_names_is_inert(name):
    pytest.importorskip("matplotlib")
    rep = copy.deepcopy(MEASURED)
    rep["run_name"] = name
    for result in rep["raw_results"]:
        result["device"] = name
    for aid, params in VIEWS:
        svg = render_artifact(rep, "measured", aid, "svg", params=params)[0]
        _assert_inert(svg, aid)
        assert name in "".join(ET.fromstring(svg).itertext()), aid


def test_render_route_sends_figures_as_attachments():
    pytest.importorskip("matplotlib")
    from main import app
    rep = copy.deepcopy(MEASURED)
    rep["run_name"] = NAMES[0]
    r = TestClient(app).post("/publication/render", json={"results": rep, "artifact_id": "counts_overview", "format": "svg"})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert r.headers["content-disposition"].startswith("attachment;")
    assert r.headers["content-security-policy"] == NON_HTML_CSP
    assert r.headers["x-content-type-options"] == "nosniff"
    _assert_inert(r.content, "route")
