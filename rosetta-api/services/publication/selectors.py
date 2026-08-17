# Pulling the pieces a figure or table needs out of a report.

from typing import Any, List


def _pairwise_records(divergence_report: dict) -> List[dict]:
    recs = divergence_report.get("pairwise_agreement")
    return recs if isinstance(recs, list) else []


def _pair_key(rec: dict) -> str:
    s = rec.get("simulators", ["?", "?"])
    return f"{s[0]} × {s[1]}"


def _key_metric(rec: dict) -> Any:
    m = rec.get("metrics", {})
    return m.get("direct_fidelity") if rec.get("mode") == "statevector" else m.get("js_divergence")


def _heatmap_specs(mode: str):
    if mode == "statevector":
        return [("fidelity_matrix", "Raw statevector fidelity (no transform)", "fidelity_heatmap")]
    return [
        ("statistical_distance_matrix (js_divergence)", "Raw Jensen–Shannon divergence", "js_divergence_heatmap"),
        ("hellinger_distance_matrix", "Raw Hellinger distance", "hellinger_heatmap"),
    ]
