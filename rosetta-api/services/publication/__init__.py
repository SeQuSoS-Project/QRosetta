"""Publication artifacts: deterministic figures (SVG/PNG/PDF) and tables built from a report.

theme.py holds constants, matplotlib setup, palette and glossary text; formats.py number
formatting and output renderers; selectors.py report accessors; figures.py and tables.py
the builders; distributions.py and figures_counts.py the measured-distribution views; views.py
the export views and their parameters; subset.py the backend subset; registry.py the artifact
catalog and rendering; items.py the crate files of export items. static/js/artifact_formats.js,
artifact_distributions.js, artifact_views.js and artifact_catalog.js mirror them.
"""

from .theme import SUPPORTED_FIGURE_FORMATS, SUPPORTED_TABLE_FORMATS
from .figures import _fig_heatmap, _fig_ranking_bar
from .formats import _fmt_int, _fmt_num, _fmt_p, _table_bytes
from .registry import list_artifacts, render_artifact
from .items import build_publication_items, categories_to_items, item_paths
from .views import ParameterError, normalize_params, view_defaults, view_slug
from .tables import _tbl_performance

__all__ = [
    "ParameterError",
    "SUPPORTED_FIGURE_FORMATS",
    "SUPPORTED_TABLE_FORMATS",
    "build_publication_items",
    "categories_to_items",
    "item_paths",
    "list_artifacts",
    "normalize_params",
    "render_artifact",
    "view_defaults",
    "view_slug",
    "_fig_heatmap",
    "_fig_ranking_bar",
    "_fmt_int",
    "_fmt_num",
    "_fmt_p",
    "_table_bytes",
    "_tbl_performance",
]
