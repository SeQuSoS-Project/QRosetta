"""Export items (a view, its parameters and formats) written into an RO-Crate: figures with
a parameter spec, tables and text. Mirrored by itemPaths in static/js/artifact_views.js."""

import json
from typing import Dict, List, Tuple

from qrosetta_commons.helpers import get_logger

from .formats import _table_bytes
from .registry import _iter_artifacts, _legend
from .subset import subset_results
from .theme import SUPPORTED_FIGURE_FORMATS, TAB_TABLE_FORMATS
from .views import VIEW_BY_ID, ParameterError, dedupe_slugs, normalize_params, view_slug

logger = get_logger("rosetta-publication")

ITEM_EXTENSIONS = {"latex": "tex", "markdown": "md", "text": "txt"}
ITEM_FIGURE_FORMATS = SUPPORTED_FIGURE_FORMATS
ITEM_TABLE_FORMATS = TAB_TABLE_FORMATS
ITEM_TEXT_FORMATS = ("markdown", "text")

_CATEGORY_VIEWS = {
    "agreement": [("agreement_distribution", "figure"), ("agreement", "table")],
    "heatmaps": [("fidelity_heatmap", "figure"), ("js_divergence_heatmap", "figure"),
                 ("hellinger_heatmap", "figure")],
    "performance": [("execution_time", "both"), ("resource_usage", "both")],
    "statistical": [("statistical_test", "table"), ("counts", "figure")],
}


def categories_to_items(categories, figure_formats, table_formats) -> List[dict]:
    """The items an older ``publication_artifacts.categories`` request stands for: every view
    of each category at its defaults, in the figure and table formats asked for (others are
    ignored, as that request always ignored them)."""
    figure_formats = [f for f in figure_formats if f in ITEM_FIGURE_FORMATS]
    table_formats = [f for f in table_formats if f in ITEM_TABLE_FORMATS]
    items = []
    for cat in categories:
        for view, kind in _CATEGORY_VIEWS.get(cat, []):
            formats = ((list(figure_formats) if kind in ("figure", "both") else [])
                       + (list(table_formats) if kind in ("table", "both") else []))
            if formats:
                items.append({"view": view, "params": {}, "formats": formats})
    return items


def item_paths(view_id: str, slug: str, formats) -> List[str]:
    """Crate paths of one export item."""
    view = VIEW_BY_ID[view_id]
    paths = []
    figs = [f for f in formats if "figure" in view and f in ITEM_FIGURE_FORMATS]
    for f in figs:
        paths.append(f"figures/{slug}.{f}")
    if figs:
        paths.append(f"figures/{slug}.spec.json")
    for f in formats:
        if "table" in view and f in ITEM_TABLE_FORMATS:
            paths.append(f"tables/{slug}.{ITEM_EXTENSIONS.get(f, f)}")
        elif "text" in view and f in ITEM_TEXT_FORMATS:
            paths.append(f"reference/{slug}.{ITEM_EXTENSIONS.get(f, f)}")
    return paths


def _prepare(results: dict, items: List[dict]) -> List[Tuple[str, dict, List[str]]]:
    """(view, normalised params, formats) per item; ParameterError names the bad item."""
    prepared = []
    for item in items:
        vid = item.get("view")
        try:
            p = normalize_params(vid, item.get("params"), results)
        except ParameterError as exc:
            raise ParameterError(f"{vid}: {exc}") from None
        view = VIEW_BY_ID[vid]
        allowed = ((ITEM_FIGURE_FORMATS if "figure" in view else ())
                   + (ITEM_TABLE_FORMATS if "table" in view else ())
                   + (ITEM_TEXT_FORMATS if "text" in view else ()))
        formats = list(dict.fromkeys(item.get("formats") or []))
        bad = [f for f in formats if f not in allowed]
        if bad:
            raise ParameterError(f"format(s) {', '.join(bad)} not offered by view '{vid}'")
        prepared.append((vid, p, formats))
    return prepared


def build_publication_items(results: dict, mode: str, items: List[dict], task: str = None):
    """({path: bytes}, {path: description}) for export items [{view, params, formats}].

    Figures go to figures/<slug>.<fmt> with figures/<slug>.spec.json (view, parameters,
    caption, analysis version and, for a playlist circuit, ``task``), tables to
    tables/<slug>.<ext>, text views to reference/<slug>.<ext>. An item whose view this report
    does not offer is skipped. Raises ParameterError for an unknown view, a bad parameter or
    a format the view does not take.
    """
    files: Dict[str, bytes] = {}
    descriptions: Dict[str, str] = {}
    prepared = _prepare(results, items)
    slugs = dedupe_slugs([view_slug(vid, p, results) for vid, p, _ in prepared])
    analysis_version = (results.get("divergence_report") or {}).get("analysis_version")
    for (vid, p, formats), slug in zip(prepared, slugs):
        view = VIEW_BY_ID[vid]
        scoped = subset_results(results, p["backends"]) if p["backends"] else results
        by_id = {a["id"]: a for a in _iter_artifacts(scoped, mode, {vid: p})
                 if a["id"] in (view.get("figure"), view.get("table"), view.get("text"))}
        fig, tbl, txt = (by_id.get(view.get(k)) for k in ("figure", "table", "text"))
        if not (fig or tbl or txt):
            logger.info(f"Export item '{vid}' skipped: not available for this report")
            continue
        figs = [f for f in formats if f in ITEM_FIGURE_FORMATS]
        if fig and figs:
            caption = _legend(fig)
            for f in figs:
                files[f"figures/{slug}.{f}"] = fig["_render"](f, 1)
                descriptions[f"figures/{slug}.{f}"] = caption
            spec = {"view": vid, "figure": view.get("figure"), "table": view.get("table"),
                    "parameters": p, "caption": caption, "analysis_version": analysis_version}
            if task is not None:
                spec["task"] = task
            files[f"figures/{slug}.spec.json"] = (
                json.dumps(spec, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode()
            descriptions[f"figures/{slug}.spec.json"] = (
                "Parameters and caption the figure was drawn with; the same parameters "
                "reproduce it from results.json.")
        table_formats = [f for f in formats if f in ITEM_TABLE_FORMATS]
        if tbl and table_formats:
            headers, rows, title, caption = tbl["_data"]()
            legend = _legend(tbl)
            for f in table_formats:
                path = f"tables/{slug}.{ITEM_EXTENSIONS.get(f, f)}"
                files[path] = _table_bytes(headers, rows, title, caption, f)
                where = ("The file carries no caption; it is " if f == "csv"
                         else "The file carries the caption ")
                descriptions[path] = f"{legend} {where}\"{title}. {caption}\""
        if txt:
            for f in formats:
                if f in ITEM_TEXT_FORMATS:
                    path = f"reference/{slug}.{ITEM_EXTENSIONS.get(f, f)}"
                    files[path] = txt["_render"](f, 1)
                    descriptions[path] = _legend(txt)
    logger.info(f"Built {len(files)} export item file(s)")
    return files, descriptions
