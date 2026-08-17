# Figure builders. Each returns a matplotlib Figure; rendering to bytes is formats.py's job.

import numpy as np
from typing import Dict, List

import matplotlib.pyplot as plt

from .theme import (
    AGREEMENT_COLORS, MAX_HISTOGRAM_OUTCOMES, MAX_OVERVIEW_BARS, MAX_OVERVIEW_OUTCOMES,
    VERDICT_COLORS, _AGREEMENT_ORDER, _CATEGORICAL, _INK, _MUTED,
    MIN_OUTCOME_PROB, _VERDICT_ORDER, _blue_cmap, _prob_cmap, _rank_outcomes,
)
from .selectors import _pairwise_records


def _fig_agreement_distribution(divergence_report: dict, mode: str):
    records = _pairwise_records(divergence_report)
    counts = {}
    for r in records:
        counts[r.get("agreement", "unknown")] = counts.get(r.get("agreement", "unknown"), 0) + 1
    labels = [c for c in _AGREEMENT_ORDER if c in counts] + [c for c in counts if c not in _AGREEMENT_ORDER]
    values = [counts[c] for c in labels]
    colors = [AGREEMENT_COLORS.get(c, _MUTED) for c in labels]
    summary = divergence_report.get("statistical_test_summary")
    has_v = bool(summary and summary.get("verdict_counts"))
    ncols = 2 if has_v else 1
    fig, axes = plt.subplots(1, ncols, figsize=(6.5 * ncols, 4.2))
    axes = axes if has_v else [axes]
    ax = axes[0]
    bars = ax.bar(range(len(labels)), values, color=colors, width=0.72)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels([l.replace("_", "\n") for l in labels], fontsize=8)
    ax.set_ylabel("pair count"); ax.set_title("Explained-cause agreement classes")
    for b, v in zip(bars, values):
        ax.text(b.get_x() + b.get_width() / 2, v, str(v), ha="center", va="bottom", fontsize=9)
    ax.margins(y=0.15)
    if has_v:
        vc = summary["verdict_counts"]
        vlab = [v for v in _VERDICT_ORDER if v in vc] + [v for v in vc if v not in _VERDICT_ORDER]
        vval = [vc[v] for v in vlab]
        ax2 = axes[1]
        vb = ax2.bar(range(len(vlab)), vval, color=[VERDICT_COLORS.get(v, _MUTED) for v in vlab], width=0.72)
        ax2.set_xticks(range(len(vlab)))
        ax2.set_xticklabels([v.replace("_", "\n") for v in vlab], fontsize=8)
        ax2.set_ylabel("pair count"); ax2.set_title("Shot-noise statistical verdicts")
        for b, v in zip(vb, vval):
            ax2.text(b.get_x() + b.get_width() / 2, v, str(v), ha="center", va="bottom", fontsize=9)
        ax2.margins(y=0.15)
    fig.suptitle("Cross-simulator agreement (analysis over registered transforms)", fontsize=11)
    return fig


def _fig_heatmap(divergence_report: dict, key: str, title: str):
    labels = divergence_report.get("simulators", [])
    arr = np.array(divergence_report[key], dtype=float)
    mask = (arr == -1.0)
    np.fill_diagonal(mask, True)
    masked = np.ma.masked_array(arr, mask=mask)
    n = len(labels)
    fig, ax = plt.subplots(figsize=(max(4.5, 0.6 * n + 2), max(4.0, 0.6 * n + 1.5)))
    im = ax.imshow(masked, cmap=_blue_cmap(), aspect="equal", vmin=0.0)
    ax.set_xticks(range(n)); ax.set_yticks(range(n))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_title(title)
    if n <= 12:
        for i in range(n):
            for j in range(n):
                if not masked.mask[i, j]:
                    ax.text(j, i, f"{arr[i, j]:.2f}", ha="center", va="center", fontsize=7, color=_INK)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    return fig


def _fig_ranking_bar(ranking, value_keys, title, xlabel):
    rows = [r for r in ranking if r.get("simulator")]
    sims = [r["simulator"] for r in rows]
    fig, ax = plt.subplots(figsize=(max(5.0, 0.5 * len(sims) + 2), 4.2))
    y = np.arange(len(sims)); left = np.zeros(len(sims))
    for key, color, label in value_keys:
        vals = np.array([(r.get(key) or 0.0) if r.get("status") == "success" else 0.0 for r in rows])
        ax.barh(y, vals, left=left, color=color, label=label, height=0.7)
        left += vals
    ax.set_yticks(y); ax.set_yticklabels(sims, fontsize=8); ax.invert_yaxis()
    ax.set_xlabel(xlabel); ax.set_title(title)
    if len(value_keys) > 1:
        # Legend below the axes so it never overlaps the stacked bars.
        ax.legend(fontsize=8, frameon=False, loc="upper center",
                  bbox_to_anchor=(0.5, -0.12), ncol=len(value_keys))
    return fig


def _fig_count_histogram(counts_a, counts_b, a, b):
    na, nb = sum(counts_a.values()), sum(counts_b.values())

    def prob(counts, n, o):
        return counts.get(o, 0) / n if n else 0

    all_outcomes = sorted(set(counts_a) | set(counts_b))
    kept, rest = _rank_outcomes(
        all_outcomes, lambda o: max(prob(counts_a, na, o), prob(counts_b, nb, o)),
        MAX_HISTOGRAM_OUTCOMES)
    labels = list(kept)
    pa = [prob(counts_a, na, o) for o in kept]
    pb = [prob(counts_b, nb, o) for o in kept]
    if rest:
        # Fold sub-threshold / overflow outcomes into one aggregated "other" bar so the
        # figure stays a publishable width instead of scaling with the 2**n outcome space.
        labels.append(f"other (+{len(rest)})")
        pa.append(sum(prob(counts_a, na, o) for o in rest))
        pb.append(sum(prob(counts_b, nb, o) for o in rest))
    truncated = bool(rest)

    x = np.arange(len(labels))
    width = min(12.0, max(5.0, 0.42 * len(labels) + 1.6))
    fig, ax = plt.subplots(figsize=(width, 3.8))
    ax.bar(x - 0.2, pa, width=0.38, color="#2a78d6", label=str(a))
    ax.bar(x + 0.2, pb, width=0.38, color="#1baf7a", label=str(b))
    ax.set_xticks(x); ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
    ax.set_ylabel("probability")
    title = f"Measured distribution: {a} vs {b} (raw counts)"
    if truncated:
        title += (f"\n{len(kept)} of {len(all_outcomes)} outcomes shown "
                  f"(p≥{MIN_OUTCOME_PROB:g} on either side); {len(rest)} folded into 'other'")
    ax.set_title(title)
    # Legend outside the axes so it never sits on top of the bars.
    ax.legend(fontsize=8, frameon=False, loc="center left", bbox_to_anchor=(1.0, 0.5))
    return fig


def _counts_probabilities(counts_by_sim: Dict[str, dict], sims_order: List[str]):
    """Shared setup for the total count figures: ordered backends with counts, a per-sim
    probability accessor, and the sorted union of observed outcomes."""
    sims = [s for s in sims_order if counts_by_sim.get(s)]
    totals = {s: sum(counts_by_sim[s].values()) for s in sims}

    def prob(s, o):
        return counts_by_sim[s].get(o, 0) / totals[s] if totals[s] else 0.0

    all_outcomes = sorted(set().union(*[set(counts_by_sim[s]) for s in sims])) if sims else []
    return sims, prob, all_outcomes


def _fig_counts_overview_bars(counts_by_sim: Dict[str, dict], sims_order: List[str]):
    """Total measured-count figure (default): clustered bar histogram over the top-K outcomes.

    The field-standard cross-backend comparison (cf. Qiskit ``plot_histogram`` with a list of
    counts + ``number_to_keep``): one colour per backend, grouped by outcome, capped so it
    never stretches with the 2**n outcome space. Raw counts only; no transform is applied.
    """
    sims, prob, all_outcomes = _counts_probabilities(counts_by_sim, sims_order)
    kept, rest = _rank_outcomes(all_outcomes, lambda o: max((prob(s, o) for s in sims), default=0.0),
                                MAX_OVERVIEW_BARS)
    labels = list(kept)
    series = {s: [prob(s, o) for o in kept] for s in sims}
    if rest:
        labels.append(f"other (+{len(rest)})")
        for s in sims:
            series[s].append(sum(prob(s, o) for o in rest))

    K, M = len(labels), len(sims)
    x = np.arange(K)
    bar_w = 0.8 / max(M, 1)
    width = min(13.0, max(5.5, 0.85 * K + 2.0))
    fig, ax = plt.subplots(figsize=(width, 4.2))
    for i, s in enumerate(sims):
        offset = -0.4 + bar_w * (i + 0.5)
        ax.bar(x + offset, series[s], width=bar_w * 0.95,
               color=_CATEGORICAL[i % len(_CATEGORICAL)], label=str(s))
    ax.set_xticks(x); ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("probability")
    title = f"Measured outcome probabilities across {M} backend(s) (raw counts)"
    if rest:
        title += (f"\ntop {len(kept)} of {len(all_outcomes)} outcomes "
                  f"(p≥{MIN_OUTCOME_PROB:g} on any backend); rest folded into 'other'")
    ax.set_title(title)
    # Legend outside the axes so it never sits on top of the bars.
    ax.legend(fontsize=8, frameon=False, loc="center left", bbox_to_anchor=(1.0, 0.5),
              title="backend")
    return fig


def _fig_counts_overview_heatmap(counts_by_sim: Dict[str, dict], sims_order: List[str]):
    """Optional total measured-count figure: outcome × backend probability heatmap.

    Compact alternative to a wall of per-pair histograms — width scales with the number of
    backends (bounded), height with the number of shown outcomes (capped). A row of uniform
    colour = all backends agree on that outcome; a row that varies = disagreement. Raw
    counts only; no transform is applied (bit-reversal etc. remain separate labelled modes).
    """
    sims, prob, all_outcomes = _counts_probabilities(counts_by_sim, sims_order)
    kept, rest = _rank_outcomes(all_outcomes, lambda o: max((prob(s, o) for s in sims), default=0.0),
                                MAX_OVERVIEW_OUTCOMES)
    rows = list(kept)
    matrix = [[prob(s, o) for s in sims] for o in kept]
    if rest:
        rows.append(f"other (+{len(rest)})")
        matrix.append([sum(prob(s, o) for o in rest) for s in sims])

    P = np.array(matrix, dtype=float) if matrix else np.zeros((1, max(1, len(sims))))
    K, M = P.shape
    width = min(11.0, max(4.2, 0.85 * M + 2.4))
    height = min(10.0, max(2.6, 0.4 * K + 1.3))
    fig, ax = plt.subplots(figsize=(width, height))
    im = ax.imshow(P, cmap=_prob_cmap(), aspect="auto", vmin=0.0, vmax=max(P.max(), 1e-9))
    ax.set_xticks(range(M)); ax.set_xticklabels(sims, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(K)); ax.set_yticklabels(rows, fontsize=8, fontfamily="monospace")
    ax.set_xlabel("backend"); ax.set_ylabel("measured outcome")
    if K * M <= 160:  # annotate only when the grid is small enough to stay legible
        thr = P.max() * 0.6
        for i in range(K):
            for j in range(M):
                v = P[i, j]
                if v >= 0.005:
                    ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=6.5,
                            color="white" if v >= thr else _INK)
    title = f"Measured outcome probabilities across {M} backend(s) (raw counts)"
    if rest:
        title += (f"\noutcomes with p≥{MIN_OUTCOME_PROB:g} on any backend shown; "
                  f"{len(rest)} folded into 'other'")
    ax.set_title(title, fontsize=11)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="probability")
    return fig
