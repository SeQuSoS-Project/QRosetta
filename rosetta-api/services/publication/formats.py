# Rendering a figure or a table into a concrete output format.
#
# _fmt_num, _latex_escape, basename_slug and the table renderers are mirrored by
# static/js/artifacts_renderer.js and compared byte-for-byte by
# tests/unit/test_artifacts_parity.py. Change one, change both.

import csv
import io
from datetime import datetime
from html import escape as _html_escape
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from openpyxl import Workbook

from .theme import BASE_DPI, _MPL_LOCK


def _savefig_bytes(fig, fmt: str, scale: int = 1) -> bytes:
    buf = io.BytesIO()
    metadata = {"svg": {"Date": None}, "pdf": {"CreationDate": None},
                "png": {"Software": None}}[fmt]
    fig.savefig(buf, format=fmt, bbox_inches="tight", dpi=BASE_DPI * max(1, scale),
                metadata=metadata)
    return buf.getvalue()


def _render_figure(build_fig, fmt: str, scale: int = 1) -> bytes:
    """Build a fresh figure, render one format, and always close it (no figure leak).

    Serialized on _MPL_LOCK because pyplot's global state is not thread-safe and callers
    run this in a worker thread."""
    with _MPL_LOCK:
        fig = build_fig()
        try:
            return _savefig_bytes(fig, fmt, scale)
        finally:
            plt.close(fig)


def _fmt_num(v: Any, digits: int = 4) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return "—" if np.isnan(v) else f"{v:.{digits}f}"
    return str(v)


_LATEX_ESCAPE = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def _latex_escape(text: Any) -> str:
    return "".join(_LATEX_ESCAPE.get(ch, ch) for ch in str(text))


def basename_slug(text: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in text.lower()).strip("-")


def _render_latex(headers, rows, title, caption) -> str:
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
    sio = io.StringIO()
    w = csv.writer(sio)
    w.writerow(headers)
    w.writerows(rows)
    return sio.getvalue()


def _render_html(headers, rows, title, caption) -> str:
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
