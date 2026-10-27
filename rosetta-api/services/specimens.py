"""Which images the backends of a report ran from: each result's ``specimen`` (published
release, built locally, or not recorded) from the image identity the runner or compiler
process reported, and the report's ``specimens`` roll-up."""

NOT_RECORDED = "not recorded"
PUBLISHED = "published_release"
BUILT_LOCALLY = "built_locally"

STATEMENTS = {
    "all_published": "Every backend that ran reports an image built by the release pipeline, of one release.",
    "all_built_locally": "Every backend that ran reports an image built locally (not a published release image).",
    "mixed": ("The backends that ran report images of different kinds or releases (see backends); "
              "their environments may differ beyond their SDKs."),
    "unknown": ("No backend that ran reports how its image was built (images built before they "
                "recorded it); the images cannot be identified from the report."),
    "none_ran": "No backend returned a result, so no image is identified.",
}

_SPECIMEN_KINDS = {"release": PUBLISHED, "built_locally": BUILT_LOCALLY}
_PROCESS_FIELDS = ("image_identity", "build_files", "image_git_sha", "sdk_versions",
                   "runner_code_sha256")


def _identity(result: dict) -> dict:
    value = result.get("image_identity")
    return value if isinstance(value, dict) else {}


def runner_image_record(api_image, result: dict) -> tuple:
    """``(runner_image, runner_image_basis)``: the image the API created a Kubernetes Job
    with when it has one, else the image the container runtime showed the runner process
    (Apptainer path and sha256, a privileged podman container's image and id), else the
    API's "not recorded" text."""
    if api_image and not str(api_image).startswith(NOT_RECORDED):
        return api_image, "dispatch"
    container = _identity(result).get("container")
    container = container if isinstance(container, dict) else {}
    image = container.get("image")
    digest = container.get("image_sha256") or container.get("image_id")
    if image or digest:
        ref = f"{image}@{digest}" if image and digest else str(image or digest)
        return ref, "runner_self_report"
    return api_image or NOT_RECORDED, NOT_RECORDED


def ran(result: dict) -> bool:
    """True when the runner or compiler process returned this result after starting the
    run (not an API-side timeout, offline or never-started record)."""
    return (isinstance(result, dict) and not result.get("never_started")
            and any(field in result for field in _PROCESS_FIELDS))


def result_specimen(result: dict) -> dict:
    """``{kind, release, image_git_sha, runner_image}``; ``kind`` is published_release,
    built_locally or "not recorded"."""
    identity = _identity(result)
    kind = _SPECIMEN_KINDS.get(identity.get("source"), NOT_RECORDED)
    git_sha = result.get("image_git_sha") or identity.get("git_sha") or NOT_RECORDED
    return {"kind": kind, "release": identity.get("release") if kind == PUBLISHED else None,
            "image_git_sha": git_sha, "runner_image": result.get("runner_image", NOT_RECORDED)}


def _statement(specimens: list) -> str:
    if not specimens:
        return "none_ran"
    kinds = {s["kind"] for s in specimens}
    releases = {s["release"] for s in specimens if s["kind"] == PUBLISHED}
    if kinds == {PUBLISHED} and len(releases) == 1:
        return "all_published"
    if kinds == {BUILT_LOCALLY}:
        return "all_built_locally"
    if kinds == {NOT_RECORDED}:
        return "unknown"
    return "mixed"


def _roll_up(pairs, no_result) -> dict:
    """The ``specimens`` record of ``(key, specimen)`` pairs and the keys with no result."""
    seen = {}
    for key, spec in pairs:
        if spec not in seen.setdefault(key, []):
            seen[key].append(spec)
    no_result = [k for k in dict.fromkeys(no_result) if k not in seen]
    everything = [spec for specs in seen.values() for spec in specs]
    backends = {k: specs[0] if len(specs) == 1 else {"varies": specs} for k, specs in seen.items()}
    statement = _statement(everything)
    commits = sorted({str(s["image_git_sha"]) for s in everything})
    notes = []
    if len(commits) > 1:
        notes.append(f"The images were built from {len(commits)} different commits "
                     f"({', '.join(commits)}), so the measurement code (qrosetta_commons) may "
                     "differ between backends.")
    dirty = sorted(k for k, specs in seen.items()
                   if any(str(s["image_git_sha"]).endswith("-dirty") for s in specs))
    if dirty:
        notes.append("Source not identifiable for " + ", ".join(dirty) + ": built from a "
                     "checkout with uncommitted changes.")
    return {"statement": statement, "meaning": STATEMENTS[statement],
            "backends": backends, "image_git_shas": commits, "no_result": no_result,
            "notes": notes}


def summarize(entries) -> dict:
    """The ``specimens`` record of ``entries`` (``(key, result)`` pairs). A key seen more
    than once (a playlist) keeps one specimen when all agree, else ``{"varies": [...]}``;
    keys whose results did not run are listed under ``no_result``."""
    pairs, no_result = [], []
    for key, result in entries:
        if ran(result):
            spec = result.get("specimen")
            pairs.append((key, spec if isinstance(spec, dict) else result_specimen(result)))
        else:
            no_result.append(key)
    return _roll_up(pairs, no_result)


def combine(records) -> dict:
    """One ``specimens`` record from several (the tasks of a playlist)."""
    pairs, no_result = [], []
    for record in records:
        if not isinstance(record, dict):
            continue
        for key, spec in (record.get("backends") or {}).items():
            if isinstance(spec, dict):
                pairs += [(key, s) for s in spec["varies"]] if "varies" in spec else [(key, spec)]
        no_result += list(record.get("no_result") or [])
    return _roll_up(pairs, no_result)


def report_entries(report: dict):
    """``(key, result)`` for every runner result and compile record of a single report."""
    for r in report.get("raw_results") or []:
        if isinstance(r, dict):
            yield str(r.get("simulator")), r
    for r in report.get("compiled_circuits") or []:
        if isinstance(r, dict):
            yield str(r.get("compiler")), r


def annotate(report: dict) -> None:
    """Set ``specimen`` on every result that ran and ``specimens`` on the report."""
    for _key, result in report_entries(report):
        if ran(result):
            result["specimen"] = result_specimen(result)
    report["specimens"] = summarize(report_entries(report))
