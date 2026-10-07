"""A report restricted to a subset of its backends. Mirrors _subsetResults in
static/js/artifact_formats.js."""

from typing import Iterable


def subset_results(results: dict, selected: Iterable[str]) -> dict:
    """Copy of ``results`` with N×N matrices sliced, pairwise records, raw results and the
    ranking/unranked lists filtered to ``selected``, and verdict counts recomputed. Does not
    mutate ``results``."""
    selected = set(selected)
    div = results.get("divergence_report") or {}
    all_sims = div.get("simulators") or []
    keep = [i for i, s in enumerate(all_sims) if s in selected]
    new_div = dict(div)
    new_div["simulators"] = [all_sims[i] for i in keep]
    for k, v in div.items():
        if (isinstance(v, list) and len(v) == len(all_sims)
                and all(isinstance(row, list) and len(row) == len(all_sims) for row in v)):
            new_div[k] = [[v[i][j] for j in keep] for i in keep]
    if isinstance(div.get("pairwise_agreement"), list):
        new_div["pairwise_agreement"] = [
            r for r in div["pairwise_agreement"]
            if len(r.get("simulators") or []) == 2
            and r["simulators"][0] in selected and r["simulators"][1] in selected]
    summary = div.get("statistical_test_summary")
    if isinstance(summary, dict) and summary.get("verdict_counts") is not None:
        vc = {}
        for r in new_div.get("pairwise_agreement") or []:
            v = ((r.get("metrics") or {}).get("statistical_test") or {}).get("verdict")
            if v:
                vc[v] = vc.get(v, 0) + 1
        new_div["statistical_test_summary"] = {**summary, "verdict_counts": vc}
    out = {**results, "divergence_report": new_div}
    if isinstance(results.get("raw_results"), list):
        out["raw_results"] = [r for r in results["raw_results"] if r.get("simulator") in selected]
    for rep in ("performance_report", "resource_report"):
        report = results.get(rep)
        if not report:
            continue
        patch = {k: [r for r in report[k] if r.get("simulator") in selected]
                 for k in ("ranking", "unranked") if isinstance(report.get(k), list)}
        out[rep] = {**report, **patch}
    return out
