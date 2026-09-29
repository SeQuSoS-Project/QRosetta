"""Number formatting and rendering of figures and tables into concrete output formats.

The formatters, escapers, basename_slug and the text table renderers are mirrored by
static/js/artifact_formats.js; tests/unit/test_artifacts_parity.py compares the two.
"""

import csv
import io
import math
import numbers
from datetime import datetime
from decimal import ROUND_HALF_UP, Context, Decimal
from html import escape as _html_escape
from typing import Any

import matplotlib.pyplot as plt
from openpyxl import Workbook

from .theme import BASE_DPI, _MPL_LOCK


def _savefig_bytes(fig, fmt: str, scale: int = 1) -> bytes:
    """Save ``fig`` as ``fmt`` with timestamp metadata removed."""
    buf = io.BytesIO()
    metadata = {"svg": {"Date": None}, "pdf": {"CreationDate": None},
                "png": {"Software": None}}[fmt]
    fig.savefig(buf, format=fmt, bbox_inches="tight", dpi=BASE_DPI * max(1, scale),
                metadata=metadata)
    return buf.getvalue()


def _render_figure(build_fig, fmt: str, scale: int = 1) -> bytes:
    """Build a figure, render it as ``fmt`` and close it, holding _MPL_LOCK throughout."""
    with _MPL_LOCK:
        fig = build_fig()
        try:
            return _savefig_bytes(fig, fmt, scale)
        finally:
            plt.close(fig)


_DEC = Context(prec=800)
_SCI_BELOW = 1e-3
_SCI_ABOVE = 1e15
_MAX_DIGITS = 17


def _fixed(x: float, digits: int) -> str:
    """Fixed-point ``x`` to ``digits`` places, ties away from zero (JS Number.toFixed)."""
    q = Decimal(x).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP, context=_DEC)
    return format(q, "f")


def _sci(x: float) -> str:
    """Scientific ``x`` with 3 significant digits and a signed 2+ digit exponent."""
    d = Decimal(abs(x))
    e = d.adjusted()
    m = d.scaleb(-e, context=_DEC).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP, context=_DEC)
    if m >= 10:
        m = Decimal("1.00")
        e += 1
    return f"{'-' if x < 0 else ''}{format(m, 'f')}e{'-' if e < 0 else '+'}{abs(e):02d}"


def _is_number(v: Any) -> bool:
    """True for real numbers other than booleans."""
    return isinstance(v, numbers.Real) and not isinstance(v, bool)


def _fmt_num(v: Any, digits: int = 4) -> str:
    """Format a real-valued metric.

    None/NaN -> "—"; 0 -> fixed zeros; 0 < |v| < 1e-3, |v| >= 1e15, or a value that would
    round to zero -> scientific (3 significant digits); a value other than 1 that would
    round to 1 gets extra decimals until it no longer does; otherwise ``digits`` places.
    Non-numbers are returned as text.
    """
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "true" if v else "false"
    if not _is_number(v):
        return str(v)
    x = float(v)
    if math.isnan(x):
        return "—"
    if math.isinf(x):
        return "inf" if x > 0 else "-inf"
    if x == 0:
        return _fixed(0.0, digits)
    if abs(x) < _SCI_BELOW or abs(x) >= _SCI_ABOVE:
        return _sci(x)
    s = _fixed(x, digits)
    if float(s) == 0:
        return _sci(x)
    d = digits
    while x != 1 and float(s) == 1 and d < _MAX_DIGITS:
        d += 1
        s = _fixed(x, d)
    return s


def _fmt_int(v: Any) -> str:
    """Format a count-like value: integral numbers without decimals, else as _fmt_num."""
    if _is_number(v) and math.isfinite(float(v)) and float(v).is_integer() \
            and abs(float(v)) < _SCI_ABOVE:
        return str(int(v))
    return _fmt_num(v)


def _fmt_text(v: Any) -> str:
    """Format a label: None or "" -> "—", booleans lower-case, else str(v)."""
    if v is None or v == "":
        return "—"
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


_LATEX_ESCAPE = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def _latex_escape(text: Any) -> str:
    """Escape LaTeX special characters in ``text``."""
    return "".join(_LATEX_ESCAPE.get(ch, ch) for ch in str(text))


def basename_slug(text: str) -> str:
    """Lower-case ``text`` with each non-alphanumeric character replaced by '-', trimmed."""
    return "".join(ch if ch.isalnum() else "-" for ch in text.lower()).strip("-")


def _render_latex(headers, rows, title, caption) -> str:
    """Render a booktabs LaTeX table."""
    col_spec = "l" * len(headers)
    lines = [
        "% Requires \\usepackage{booktabs}",
        "\\begin{table}[htbp]", "  \\centering",
        f"  \\caption{{{_latex_escape(title)}. {_latex_escape(caption)}}}",
        f"  \\label{{tab:{basename_slug(title)}}}",
        f"  \\begin{{tabular}}{{{col_spec}}}", "    \\toprule",
        "    " + " & ".join(_latex_escape(h) for h in headers) + " \\\\", "    \\midrule",
    ]
    for r in rows:
        lines.append("    " + " & ".join(_latex_escape(c) for c in r) + " \\\\")
    lines += ["    \\bottomrule", "  \\end{tabular}", "\\end{table}", ""]
    return "\n".join(lines)


def _render_csv(headers, rows) -> str:
    """Render a CSV (csv module defaults, CRLF rows)."""
    sio = io.StringIO()
    w = csv.writer(sio)
    w.writerow(headers)
    w.writerows(rows)
    return sio.getvalue()


def _render_html(headers, rows, title, caption) -> str:
    """Render a standalone HTML table."""
    head = "".join(f"<th>{_html_escape(str(h))}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{_html_escape(str(c))}</td>" for c in r) + "</tr>"
                   for r in rows)
    return (
        "<!doctype html><meta charset='utf-8'>"
        "<style>body{font-family:system-ui,sans-serif;color:#0b0b0b;margin:1rem}"
        "table{border-collapse:collapse;font-size:13px}"
        "caption{caption-side:top;text-align:left;font-weight:600;margin-bottom:.4rem}"
        "th,td{border-bottom:1px solid #e1e0d9;padding:4px 10px;text-align:left}"
        "thead th{border-bottom:2px solid #c3c2b7}"
        ".cap{color:#52514e;font-weight:400;font-size:12px}</style>"
        f"<table><caption>{_html_escape(title)}"
        f"<div class='cap'>{_html_escape(caption)}</div></caption>"
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
    )


def _render_markdown(headers, rows, title, caption) -> str:
    """Render a Markdown table preceded by a bold title line."""
    def esc(x):
        return str(x).replace("|", "\\|")
    lines = [f"**{title}** — {caption}", "",
             "| " + " | ".join(esc(h) for h in headers) + " |",
             "| " + " | ".join("---" for _ in headers) + " |"]
    for r in rows:
        lines.append("| " + " | ".join(esc(c) for c in r) + " |")
    lines.append("")
    return "\n".join(lines)


_FIXED_XLSX_EPOCH = datetime(2020, 1, 1, 0, 0, 0)


def _render_xlsx(headers, rows, title, caption) -> bytes:
    """Render a XLSX workbook with fixed timestamps."""
    wb = Workbook()
    wb.properties.created = _FIXED_XLSX_EPOCH
    wb.properties.modified = _FIXED_XLSX_EPOCH
    wb.properties.creator = "QRosetta"
    ws = wb.active
    ws.title = "Table"
    ws.append([title])
    ws.append([caption])
    ws.append(headers)
    for r in rows:
        ws.append([("" if c is None else c) for c in r])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _table_bytes(headers, rows, title, caption, fmt: str) -> bytes:
    """Render a table in ``fmt`` as bytes."""
    if fmt == "csv":
        return _render_csv(headers, rows).encode("utf-8")
    if fmt == "latex":
        return _render_latex(headers, rows, title, caption).encode("utf-8")
    if fmt == "html":
        return _render_html(headers, rows, title, caption).encode("utf-8")
    if fmt == "markdown":
        return _render_markdown(headers, rows, title, caption).encode("utf-8")
    if fmt == "xlsx":
        return _render_xlsx(headers, rows, title, caption)
    raise ValueError(f"unsupported table format: {fmt}")
