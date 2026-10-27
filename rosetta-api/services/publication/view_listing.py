"""GET /publication/views: every export view with its artifacts, parameters (type, allowed
values, default) and formats, read from views.VIEWS and the format lists the renderer and the
crate items use."""

from typing import Any, Dict, List

from .items import ITEM_FIGURE_FORMATS, ITEM_TABLE_FORMATS, ITEM_TEXT_FORMATS
from .theme import SUPPORTED_FIGURE_FORMATS, TAB_TABLE_FORMATS
from .views import COMMON_PARAMS, FIGURE_PARAMS, MAX_MARGINAL_BITS, VIEWS, view_param_specs

RENDER_FORMATS = {"figure": SUPPORTED_FIGURE_FORMATS, "table": TAB_TABLE_FORMATS, "text": ITEM_TEXT_FORMATS}
ITEM_FORMATS = {"figure": ITEM_FIGURE_FORMATS, "table": ITEM_TABLE_FORMATS, "text": ITEM_TEXT_FORMATS}

NULL_DEFAULTS = {
    "backends": "every backend of the report",
    "backend": "the first selected backend with counts",
    "bits": "the first three classical bits (fewer when the report has fewer)",
}


def _param(name: str, spec: tuple) -> Dict[str, Any]:
    kind = spec[0]
    out: Dict[str, Any] = {"name": name, "type": kind, "default": spec[-1]}
    if kind == "choice":
        out["choices"] = list(spec[1])
    elif kind in ("int", "float"):
        out["min"], out["max"] = spec[1]
    elif kind == "bits":
        out["max_items"] = MAX_MARGINAL_BITS
    if isinstance(out["default"], tuple):
        out["default"] = list(out["default"])
    if out["default"] is None and kind in NULL_DEFAULTS:
        out["default_when_null"] = NULL_DEFAULTS[kind]
    out["scope"] = ("every view" if name in COMMON_PARAMS
                    else "views with a figure" if name in FIGURE_PARAMS else "this view")
    return out


def view_entry(view: dict) -> Dict[str, Any]:
    """One view: its id, the artifact ids it renders with their render formats, the formats an
    export item of the view takes, and its parameters in order."""
    artifacts = [{"artifact_id": view[kind], "kind": kind, "formats": list(RENDER_FORMATS[kind])}
                 for kind in ("figure", "table", "text") if kind in view]
    item_formats: List[str] = []
    for kind in ("figure", "table", "text"):
        if kind in view:
            item_formats += [f for f in ITEM_FORMATS[kind] if f not in item_formats]
    return {"id": view["id"], "artifacts": artifacts, "item_formats": item_formats,
            "params": [_param(name, spec) for name, spec in view_param_specs(view["id"]).items()]}


def views_listing(scale_range: tuple) -> Dict[str, Any]:
    """Every export view, in the Exports tab's order, and the render routes' scale range."""
    return {"views": [view_entry(v) for v in VIEWS],
            "scale": {"min": scale_range[0], "max": scale_range[1]}}
