# Publication-ready artifact engine — deterministic figures + tables.
#
# Split along the section boundaries the single module already used:
#
#   theme.py      constants, matplotlib configuration, palette, glossary wording
#   formats.py    rendering a figure or table into a concrete output format
#   selectors.py  pulling the pieces a builder needs out of a report
#   figures.py    figure builders (each returns a matplotlib Figure)
#   tables.py     table and text-blob builders
#   registry.py   which artifacts exist for a report, and the public API
#
# Every name importable from services.publication before the split still is, so callers
# and tests are unaffected.
#
# formats.py carries the parity contract: _fmt_num, _latex_escape, basename_slug and the
# table renderers are mirrored by static/js/artifacts_renderer.js and compared byte-for-byte
# by tests/unit/test_artifacts_parity.py.

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
    _fmt_num,
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
    # Public surface.
    "build_publication_artifacts",
    "list_artifacts",
    "render_artifact",
    "basename_slug",
    # Configuration.
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
    # Internals re-exported so the pre-split import path keeps working.
    "_fig_agreement_distribution",
    "_fig_count_histogram",
    "_fig_counts_overview_bars",
    "_fig_counts_overview_heatmap",
    "_fig_heatmap",
    "_fig_ranking_bar",
    "_fmt_num",
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
