"""Publication artifacts: deterministic figures (SVG/PNG/PDF) and tables built from a report.

theme.py holds constants, matplotlib setup, palette and glossary text; formats.py number
formatting and output renderers; selectors.py report accessors; figures.py and tables.py
the builders; registry.py the artifact catalog and public API. static/js/artifact_formats.js
mirrors the text builders and catalog.
"""

from .theme import (
    AGREEMENT_COLORS,
    BASE_DPI,
    MAX_HISTOGRAM_OUTCOMES,
    MAX_HISTOGRAM_PAIRS,
    MAX_OVERVIEW_BARS,
    MAX_OVERVIEW_OUTCOMES,
    MIME_TYPES,
    MIN_OUTCOME_PROB,
    PUBLICATION_CATEGORIES,
    SUPPORTED_FIGURE_FORMATS,
    SUPPORTED_TABLE_FORMATS,
    TAB_TABLE_FORMATS,
    VERDICT_COLORS,
    _rank_outcomes,
)
from .figures import (
    _fig_agreement_distribution,
    _fig_count_histogram,
    _fig_counts_overview_bars,
    _fig_counts_overview_heatmap,
    _fig_heatmap,
    _fig_ranking_bar,
)
from .formats import (
    _fmt_int,
    _fmt_num,
    _fmt_text,
    _latex_escape,
    _render_csv,
    _render_figure,
    _render_html,
    _render_latex,
    _render_markdown,
    _render_xlsx,
    _table_bytes,
    basename_slug,
)
from .registry import build_publication_artifacts, list_artifacts, render_artifact
from .selectors import _heatmap_specs, _key_metric, _pair_key, _pairwise_records
from .tables import (
    _tbl_agreement,
    _tbl_matrix,
    _tbl_metadata,
    _tbl_performance,
    _tbl_resources,
    _tbl_statistical,
    _txt_executed_qasm,
    _txt_glossary,
)

__all__ = [
    "build_publication_artifacts",
    "list_artifacts",
    "render_artifact",
    "basename_slug",
    "AGREEMENT_COLORS",
    "BASE_DPI",
    "MAX_HISTOGRAM_OUTCOMES",
    "MAX_HISTOGRAM_PAIRS",
    "MAX_OVERVIEW_BARS",
    "MAX_OVERVIEW_OUTCOMES",
    "MIME_TYPES",
    "MIN_OUTCOME_PROB",
    "PUBLICATION_CATEGORIES",
    "SUPPORTED_FIGURE_FORMATS",
    "SUPPORTED_TABLE_FORMATS",
    "TAB_TABLE_FORMATS",
    "VERDICT_COLORS",
    "_fig_agreement_distribution",
    "_fig_count_histogram",
    "_fig_counts_overview_bars",
    "_fig_counts_overview_heatmap",
    "_fig_heatmap",
    "_fig_ranking_bar",
    "_fmt_int",
    "_fmt_num",
    "_fmt_text",
    "_heatmap_specs",
    "_key_metric",
    "_latex_escape",
    "_pair_key",
    "_pairwise_records",
    "_rank_outcomes",
    "_render_csv",
    "_render_figure",
    "_render_html",
    "_render_latex",
    "_render_markdown",
    "_render_xlsx",
    "_table_bytes",
    "_tbl_agreement",
    "_tbl_matrix",
    "_tbl_metadata",
    "_tbl_performance",
    "_tbl_resources",
    "_tbl_statistical",
    "_txt_executed_qasm",
    "_txt_glossary",
]
