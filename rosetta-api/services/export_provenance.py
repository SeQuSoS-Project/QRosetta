"""Crate records of the run itself: which images ran (specimens), the timing caveats and
whether the job covers every planned circuit, as provenance.json fields and as PropertyValue
entities on the crate root."""

from services import report_provenance
from services.timing_caveats import TIMING_CAVEATS_VERSION


def run_records(top: dict, reports: list, trusted: bool) -> dict:
    """``{specimens, timing_caveats, timing_caveats_version, timing_caveats_derived_at_export,
    run_completeness, run_completeness_meaning}`` for provenance.json."""
    caveats, version, derived = report_provenance.timing_caveats_of(reports)
    completeness, meaning = report_provenance.completeness_statement(top, trusted)
    return {
        "specimens": report_provenance.specimens_of(reports),
        "timing_caveats": caveats,
        "timing_caveats_version": version,
        "timing_caveats_derived_at_export": derived,
        "run_completeness": completeness,
        "run_completeness_meaning": meaning,
        "run_completeness_record": top.get("run_completeness", "not recorded"),
    }


def _specimen_detail(specimens: dict) -> str:
    parts = []
    for key, spec in sorted((specimens.get("backends") or {}).items()):
        specs = spec["varies"] if isinstance(spec, dict) and "varies" in spec else [spec]
        kinds = ", ".join(sorted({f"{s['kind']}" + (f" {s['release']}" if s.get("release") else "")
                                  + f" (commit {s['image_git_sha']})" for s in specs}))
        parts.append(f"{key}: {kinds}")
    return "; ".join(parts)


def root_properties(records: dict, trusted: bool) -> list:
    """PropertyValue entities ``#specimens``, ``#timing-caveats`` and ``#run-completeness``."""
    supplied = "" if trusted else " As supplied in the report; this server did not check it."
    specimens = records["specimens"]
    detail = _specimen_detail(specimens)
    notes = " ".join(specimens.get("notes") or [])
    caveats = records["timing_caveats"]
    codes = [c["code"] for c in caveats]
    derived = (" Derived at export from the recorded fields." if records["timing_caveats_derived_at_export"]
               else "")
    return [
        {"@id": "#specimens", "@type": "PropertyValue", "name": "specimens",
         "value": specimens["statement"],
         "description": (specimens["meaning"] + (f" Per backend: {detail}." if detail else "")
                         + (f" {notes}" if notes else "")
                         + " Full record in provenance.json (specimens)." + supplied)},
        {"@id": "#timing-caveats", "@type": "PropertyValue", "name": "timing_caveats",
         "value": ", ".join(codes) if codes else "none",
         "description": ((" ".join(c["text"] for c in caveats) if caveats else
                          "No recorded condition limits the comparison of these timings.")
                         + f" Rules {records['timing_caveats_version'] or TIMING_CAVEATS_VERSION}; "
                         "fields and backends per caveat in provenance.json (timing_caveats)."
                         + derived + supplied)},
        {"@id": "#run-completeness", "@type": "PropertyValue", "name": "run_completeness",
         "value": records["run_completeness"],
         "description": records["run_completeness_meaning"]},
    ]
