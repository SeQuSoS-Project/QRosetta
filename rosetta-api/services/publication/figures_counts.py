"""Figures of the measured-distribution views; each returns a matplotlib Figure."""

import math

import numpy as np
import matplotlib.pyplot as plt

from .theme import _CATEGORICAL, _INK, _MUTED, _figsize, _log_axis, _prob_cmap
from .formats import _fmt_num
from .distributions import count_selection, disagrees, hamming, marginals, spread
from .selectors import _circuit_name

_GREY = "#c9c8c1"
_BAND = "#000000"


def _colours(results: dict, sims, p: dict):
    """Colour per backend: categorical, or the reference black, disagreeing backends
    categorical and the rest grey ("highlight")."""
    out = {}
    for i, s in enumerate(sims):
        base = _CATEGORICAL[i % len(_CATEGORICAL)]
        if p.get("colour") == "highlight":
            out[s] = _INK if s == p["ref"] else (base if disagrees(results, s, p["ref"]) else _GREY)
        else:
            out[s] = base
    return out


def _legend(ax, n):
    ax.legend(fontsize="small", frameon=False, loc="center left", bbox_to_anchor=(1.0, 0.5),
              ncol=1 if n <= 16 else 2)


def _need_ref(sims, p):
    if p["ref"] not in sims:
        raise ValueError(f"the reference backend {p['ref']} has no counts")


def _band_halfwidth(prob, shots):
    return 2 * math.sqrt(2 * prob * (1 - prob) / shots) if shots else 0.0


def fig_counts(results: dict, p: dict):
    """Count comparison in the chosen layout."""
    sel = count_selection(results, p)
    sims = sel["cp"]["sims"]
    rows = sel["rows"]
    labels = [r["label"] for r in rows]
    colours = _colours(results, sims, p)
    title = f"Measured outcome probabilities: {_circuit_name(results)}"
    K, M = len(rows), len(sims)
    if p["layout"] == "heatmap":
        P = np.array([r["vals"] for r in rows], dtype=float) if rows else np.zeros((1, max(1, M)))
        fig, ax = plt.subplots(figsize=_figsize((min(11.0, max(4.2, 0.85 * M + 2.4)),
                                                 min(10.0, max(2.6, 0.4 * K + 1.3)))))
        im = ax.imshow(P, cmap=_prob_cmap(), aspect="auto", vmin=0.0, vmax=max(P.max(), 1e-9))
        ax.set_xticks(range(M)); ax.set_xticklabels(sims, rotation=45, ha="right", fontsize="small")
        ax.set_yticks(range(K)); ax.set_yticklabels(labels, fontsize="small", fontfamily="monospace")
        ax.set_xlabel("backend"); ax.set_ylabel("measured outcome")
        if K * M <= 160:
            thr = P.max() * 0.6
            for i in range(K):
                for j in range(M):
                    if P[i, j] >= 0.005:
                        ax.text(j, i, _fmt_num(P[i, j], 2), ha="center", va="center",
                                fontsize="xx-small", color="white" if P[i, j] >= thr else _INK)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="probability")
        ax.set_title(title)
        return fig
    width = min(13.0, max(5.5, 0.55 * K + 2.5))
    if p["layout"] == "panels":
        _need_ref(sims, p)
        cols = min(4, max(1, M))
        nrows = math.ceil(M / cols)
        fig, axes = plt.subplots(nrows, cols, squeeze=False, sharex=True, sharey=True,
                                 figsize=_figsize((min(13.0, 3.2 * cols), 1.9 * nrows + 0.8)),
                                 layout="constrained")
        ref = sims.index(p["ref"])
        x = np.arange(K)
        for k, ax in enumerate(axes.flat):
            if k >= M:
                ax.axis("off")
                continue
            s = sims[k]
            ax.bar(x, [r["vals"][k] for r in rows], color=colours[s], width=0.8)
            ax.hlines([r["vals"][ref] for r in rows], x - 0.4, x + 0.4, colors=_INK, linewidth=1)
            ax.set_title(s, fontsize="small", loc="left")
            if p["yscale"] == "log":
                _log_axis(ax)
            ax.set_xticks(x)
            ax.set_xticklabels(labels, rotation=90, fontsize="xx-small", fontfamily="monospace")
        fig.supylabel("probability", fontsize="small")
        fig.suptitle(title)
        return fig
    fig, ax = plt.subplots(figsize=_figsize((width, 4.2)))
    x = np.arange(K)
    if p["layout"] == "diff":
        _need_ref(sims, p)
        ref = sims.index(p["ref"])
        others = [s for s in sims if s != p["ref"]]
        bw = 0.8 / max(len(others), 1)
        if p["band"]:
            shots = sel["cp"]["totals"][p["ref"]]
            hw = [_band_halfwidth(r["vals"][ref], shots) for r in rows]
            ax.bar(x, [2 * h for h in hw], bottom=[-h for h in hw], width=0.92, color=_BAND,
                   alpha=0.08, label="±2σ shot noise")
        for i, s in enumerate(others):
            k = sims.index(s)
            ax.bar(x - 0.4 + bw * (i + 0.5), [r["vals"][k] - r["vals"][ref] for r in rows],
                   width=bw * 0.95, color=colours[s], label=s)
        ax.axhline(0, color=_MUTED, linewidth=0.8)
        ax.set_ylabel(f"probability − {p['ref']}")
        _legend(ax, len(others) + 1)
    else:
        bw = 0.8 / max(M, 1)
        for i, s in enumerate(sims):
            ax.bar(x - 0.4 + bw * (i + 0.5), [r["vals"][i] for r in rows], width=bw * 0.95,
                   color=colours[s], label=s)
        ax.set_ylabel("probability")
        if p["yscale"] == "log":
            _log_axis(ax)
        _legend(ax, M)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45 if K > 6 else 0, ha="right" if K > 6 else "center",
                       fontsize="small", fontfamily="monospace")
    ax.set_title(title)
    return fig


def _lines(ax, xs, series, colours, err=None):
    for s, ys in series.items():
        ax.plot(xs, ys, marker="o", markersize=3, linewidth=1.2, color=colours[s], label=s)
        if err is not None:
            ax.errorbar(xs, ys, yerr=err[s], fmt="none", ecolor=colours[s], elinewidth=0.8,
                        capsize=0)


def fig_marginals(results: dict, p: dict):
    d = marginals(results)
    sims, n = d["cp"]["sims"], d["n"]
    colours = _colours(results, sims, p)
    xs = np.arange(n)
    fig, ax = plt.subplots(figsize=_figsize((max(5.5, 0.45 * n + 3), 3.8)))
    if p["layout"] == "diff":
        _need_ref(sims, p)
        ref = d["m"][p["ref"]]
        if p["errorbars"]:
            shots = d["cp"]["totals"][p["ref"]]
            hw = np.array([_band_halfwidth(v, shots) for v in ref])
            ax.fill_between(xs, -hw, hw, color=_BAND, alpha=0.08, linewidth=0, label="±2σ shot noise")
        _lines(ax, xs, {s: [a - b for a, b in zip(d["m"][s], ref)] for s in sims if s != p["ref"]},
               colours)
        ax.axhline(0, color=_MUTED, linewidth=0.8)
        ax.set_ylabel(f"P(c[j] = 1) − {p['ref']}")
    else:
        err = None
        if p["errorbars"]:
            err = {s: [2 * math.sqrt(v * (1 - v) / d["cp"]["totals"][s]) if d["cp"]["totals"][s]
                       else 0.0 for v in d["m"][s]] for s in sims}
        _lines(ax, xs, {s: d["m"][s] for s in sims}, colours, err)
        ax.set_ylim(-0.02, 1.02)
        ax.set_ylabel("P(c[j] = 1)")
    ax.set_xticks(xs); ax.set_xticklabels([str(j) for j in xs], fontsize="small")
    ax.set_xlabel("classical bit j")
    ax.set_title(f"Single-bit marginals: {_circuit_name(results)}")
    _legend(ax, len(sims))
    return fig


def fig_hamming(results: dict, p: dict):
    d = hamming(results)
    sims, n = d["cp"]["sims"], d["n"]
    colours = _colours(results, sims, p)
    xs = np.arange(n + 1)
    fig, ax = plt.subplots(figsize=_figsize((max(5.5, 0.5 * n + 3), 3.8)))
    if p["layout"] == "lines":
        _lines(ax, xs, {s: d["h"][s] for s in sims}, colours)
        ax.set_ylabel("probability")
    else:
        if p["layout"] == "diff":
            _need_ref(sims, p)
            ref = d["h"][p["ref"]]
            shots = d["cp"]["totals"][p["ref"]]
            hw = [_band_halfwidth(v, shots) for v in ref]
            ax.bar(xs, [2 * h for h in hw], bottom=[-h for h in hw], width=0.92, color=_BAND,
                   alpha=0.08, label="±2σ shot noise")
            series = {s: [a - b for a, b in zip(d["h"][s], ref)] for s in sims if s != p["ref"]}
            ax.axhline(0, color=_MUTED, linewidth=0.8)
            ax.set_ylabel(f"probability − {p['ref']}")
        else:
            series = {s: d["h"][s] for s in sims}
            ax.set_ylabel("probability")
        bw = 0.8 / max(len(series), 1)
        for i, (s, ys) in enumerate(series.items()):
            ax.bar(xs - 0.4 + bw * (i + 0.5), ys, width=bw * 0.95, color=colours[s], label=s)
    ax.set_xticks(xs); ax.set_xticklabels([str(w) for w in xs], fontsize="small")
    ax.set_xlabel("number of ones w")
    ax.set_title(f"Hamming-weight distribution: {_circuit_name(results)}")
    _legend(ax, len(sims))
    return fig


def fig_rank(results: dict, p: dict):
    d = spread(results)
    sims = d["cp"]["sims"]
    colours = _colours(results, sims, p)
    fig, ax = plt.subplots(figsize=_figsize((6.5, 4.0)))
    for s in sims:
        ys = d["rows"][s]["sorted"]
        ax.plot(np.arange(1, len(ys) + 1), ys, linewidth=1.1, color=colours[s], label=s,
                drawstyle="steps-post")
    _log_axis(ax)
    if p["xscale"] == "log":
        _log_axis(ax, "x")
    ax.set_xlabel("rank"); ax.set_ylabel("probability")
    ax.set_title(f"Outcome probabilities by rank: {_circuit_name(results)}")
    _legend(ax, len(sims))
    return fig
