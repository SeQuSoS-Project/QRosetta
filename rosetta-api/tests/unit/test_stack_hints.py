"""What the Backends and Compile-only services popovers say about services a local stack lists
but does not run (stack_hints.js), and where the page uses it."""
from pathlib import Path

from tests.unit.frontend_harness import call_js, requires_node

_STATIC = Path(__file__).resolve().parents[2] / "static"
_JS = _STATIC / "js"


def _row(rid, available=True, reason=None, enabled=True, source=None):
    return {"id": rid, "enabled": enabled, "available": available, "unavailable_reason": reason,
            "versions": {"image_identity": {"source": source}} if source else None}


def _runners(running=3, total=14):
    rows = [_row(f"r{i}", source="release") for i in range(running)]
    rows += [_row(f"r{i}", available=False, reason="unreachable") for i in range(running, total)]
    return rows + [_row("braket", available=False, reason="disabled", enabled=False)]


@requires_node
def test_a_local_service_that_does_not_answer_is_not_running():
    calls = [
        ("notRunningLocally", [_row("qibo", False, "unreachable"), "local"]),
        ("notRunningLocally", [_row("qibo", False, "unreachable"), "kubernetes"]),
        ("notRunningLocally", [_row("qibo", False, "not deployed on this server"), "local"]),
        ("notRunningLocally", [_row("cuquantum", False, "requires a GPU; this deployment has none"), "local"]),
        ("notRunningLocally", [_row("braket", False, "disabled", enabled=False), "local"]),
        ("notRunningLocally", [_row("qiskit"), "local"]),
        ("notRunningLocally", [_row("qibo", False, "unreachable"), None]),
    ]
    assert call_js(["stack_hints.js"], calls) == [True, False, False, False, False, False, False]


@requires_node
def test_the_tooltip_names_the_commands_for_the_service():
    pull, build = call_js(["stack_hints.js"], [
        ("partsText", [[{"text": "Not running in this stack. To add it: "}, {"code": "qrosetta pull qibo"},
                        {"text": ", then "}, {"code": "qrosetta start -d qibo"}]]),
        ("serviceHintParts", ["pyzx", "build"]),
    ])
    assert pull == "Not running in this stack. To add it: qrosetta pull qibo, then qrosetta start -d qibo"
    assert [p.get("code") for p in build if "code" in p] == ["qrosetta build pyzx", "qrosetta start -d pyzx"]
    text = call_js(["stack_hints.js"], [("serviceHintParts", ["qibo", "pull"])])[0]
    assert "".join(p.get("code", p.get("text", "")) for p in text) == pull


@requires_node
def test_the_command_is_build_only_for_a_stack_of_locally_built_images():
    verbs = call_js(["stack_hints.js"], [
        ("imageVerb", [[_row("qiskit", source="built_locally"), _row("qibo", False, "unreachable")]]),
        ("imageVerb", [[_row("qiskit", source="release")]]),
        ("imageVerb", [[_row("qiskit", source="built_locally"), _row("cirq", source="release")]]),
        ("imageVerb", [[_row("qibo", False, "unreachable")]]),
        ("imageVerb", [[]]),
    ])
    assert verbs == ["build", "pull", "pull", "pull", "pull"]


@requires_node
def test_the_popover_line_counts_running_services_and_hides_when_all_run():
    line, compilers, none_missing, k8s = call_js(["stack_hints.js"], [
        ("stackSummaryParts", [_runners(3, 14), "local", "backends", "pull"]),
        ("stackSummaryParts", [[_row(f"c{i}", available=i < 2, reason=None if i < 2 else "unreachable")
                                for i in range(8)], "local", "compile-only services", "build"]),
        ("stackSummaryParts", [_runners(14, 14), "local", "backends", "pull"]),
        ("stackSummaryParts", [_runners(3, 14), "kubernetes", "backends", "pull"]),
    ])
    text = lambda parts: "".join(p.get("code", p.get("text", "")) for p in parts)
    assert text(line) == ("3 of 14 backends run in this stack. To add all: qrosetta pull --profile full, "
                          "then qrosetta start -d --profile full.")
    assert [p["code"] for p in line if "code" in p] == ["qrosetta pull --profile full", "qrosetta start -d --profile full"]
    assert text(compilers).startswith("2 of 8 compile-only services run in this stack. To add all: qrosetta build --profile full")
    assert none_missing is None and k8s is None


@requires_node
def test_a_gpu_backend_without_a_gpu_is_counted_but_not_offered_commands():
    rows = [_row(f"r{i}") for i in range(13)]
    rows.append(_row("cuquantum", False, "requires a GPU; this deployment has none (QROSETTA_GPU_AVAILABLE is not set to true)"))
    hidden, with_one_missing = call_js(["stack_hints.js"], [
        ("stackSummaryParts", [rows, "local", "backends", "pull"]),
        ("stackSummaryParts", [rows[1:] + [_row("qibo", False, "unreachable")], "local", "backends", "pull"]),
    ])
    assert hidden is None
    assert with_one_missing[0]["text"].startswith("12 of 14 backends run in this stack.")


@requires_node
def test_the_empty_state_says_no_selected_backend_runs():
    base = {"source": "editor", "circuitName": "QFT (3q)", "playlist": [], "modes": {"statevector": True, "measured": False},
            "preprocessing": "on", "compilerCount": 0, "backends": [], "backendsLoaded": True, "examples": []}
    running, ticked = call_js(["empty_state.js"], [
        ("emptyStateModel", [{**base, "noBackendRunning": True}]),
        ("emptyStateModel", [base]),
    ])
    assert running["title"] == "No selected backend is running in this stack"
    assert ticked["title"] == "No backend is ticked"


def test_the_popovers_use_the_hints_and_keep_other_reasons():
    config = (_JS / "config.js").read_text()
    assert "notRunningLocally(r, mode) ? partsText(serviceHintParts(r.id, verb))" in config
    assert "stackSummaryParts(runners, mode, 'backends', verb)" in config
    assert "'No selected backend is running in this stack.'" in config
    compilers = (_JS / "compilers_config.js").read_text()
    assert "stackSummaryParts(compilers, mode, 'compile-only services', verb)" in compilers
    assert "`Unavailable: ${compiler.unavailable_reason || 'unknown'}`" in compilers
    html = (_STATIC / "index.html").read_text()
    body = html.split('id="pop-compilers"', 1)[1].split('class="qr-popover-body">', 1)[1]
    assert body.lstrip().startswith('<div id="compiler-stack-note" class="qr-section hidden"></div>')


def test_the_reason_code_matches_the_server():
    from services.availability import UNREACHABLE
    assert f"const NOT_RUNNING = '{UNREACHABLE}';" in (_JS / "stack_hints.js").read_text()


def test_an_unavailable_compiler_name_keeps_aa_contrast():
    # text-gray-400 on white is 2.5:1; text-gray-500 is 4.8:1 (axe color-contrast, 2026-11-06).
    src = (_JS / "compilers_config.js").read_text()
    assert "'text-gray-500 line-through'" in src and "text-gray-400" not in src
