"""Workspace, account and run-view behaviour from the second play-test round: sign-in expiry on a
skewed clock, the Run Name kept across reloads, saved-run headings and source, multi-run count
checks, run-key order, the experiment's compile-only note, the large measured-run warning, the
analysing phase, and the page structure (Quirk overlay, account menu, help texts)."""
import base64
import json
import re
from pathlib import Path

from tests.unit.frontend_harness import call_js, requires_node

STATIC = Path(__file__).resolve().parents[2] / "static"
JS = STATIC / "js"


def _token(claims):
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"h.{body}.s"


@requires_node
def test_sign_in_expiry_follows_the_server_clock():
    token = _token({"sub": "a@b.c", "iat": 1_000_000, "exp": 1_000_000 + 3600})
    fast_local_ms = (1_000_000 + 35 * 60) * 1000
    skew, expiry, no_skew = call_js(["auth.js"], [
        ("clockSkewMs", [token, fast_local_ms]),
        ("localExpiry", [token, -35 * 60 * 1000]),
        ("localExpiry", [token, 0]),
    ])
    assert skew == -35 * 60 * 1000
    assert expiry == fast_local_ms + 3600 * 1000
    assert no_skew == (1_000_000 + 3600) * 1000
    assert call_js(["auth.js"], [("clockSkewMs", [_token({"sub": "x"}), 5])]) == [0]


@requires_node
def test_run_name_survives_a_reload_and_reaches_a_new_tab():
    first, new_tab, empty = call_js(["session_store.js"], [
        ("saveRunName", ["GHZ final"]), ("loadRunName", []), ("__newTab__", []), ("loadRunName", []),
        ("saveRunName", [""]), ("loadRunName", []),
    ])[1::2]
    assert first == "GHZ final" and new_tab == "GHZ final" and empty == ""


@requires_node
def test_storage_events_for_recorded_jobs_are_recognised():
    assert call_js(["session_store.js"], [
        ("isJobsStorageKey", ["rosetta_jobs"]), ("isJobsStorageKey", [None]), ("isJobsStorageKey", ["rosetta_token"]),
    ]) == [True, True, False]


@requires_node
def test_saved_run_heading_keeps_mode_and_shots():
    measured = {"n_shots": 8200, "divergence_report": {"pairwise_agreement": [{"mode": "measured"}]}}
    out = call_js(["history.js"], [
        ("savedRunHeading", [measured, "Bell"]),
        ("savedRunHeading", [measured, "Bell (Measured)"]),
        ("savedRunHeading", [{"raw_results": []}, "QFT"]),
        ("savedRunHeading", [{"simulated": False}, "QFT"]),
        ("savedRunHeading", [{"mode": "measured", "benchmark_summary": []}, "Suite"]),
    ])
    assert out == ["Bell (Measured, 8200 shots)", "Bell (Measured, 8200 shots)", "QFT (Statevector)",
                   "QFT (compile only)", "Suite (Measured)"]


@requires_node
def test_saved_run_source_is_shown_for_uploads_and_unrecorded_runs():
    job, upload, old = call_js(["history.js"], [
        ("savedRunSourceNote", [{"saved_from": "server_job"}]),
        ("savedRunSourceNote", [{"saved_from": "upload"}]),
        ("savedRunSourceNote", [{}]),
    ])
    assert job is None
    assert upload["tag"] == "Uploaded" and "uploaded" in upload["text"]
    assert old["tag"] == "Source not recorded"


@requires_node
def test_multi_run_counts_are_whole_numbers_within_the_limits():
    parsed = call_js(["config.js"], [("parseRunCount", [v]) for v in ["3", " 2 ", "", "1e1", "2.5", "-1"]])
    assert parsed[:3] == [3, 2, 0] and all(v is None for v in parsed[3:])
    cells = [{"runner": "qiskit", "level": 0, "raw": "10"}, {"runner": "qiskit", "level": 1, "raw": "7"},
             {"runner": "cirq", "level": 0, "raw": "1e1"}]
    problems = call_js(["config.js"], [("runCountProblemsFor", [cells, 16, 48, {"qiskit": "Qiskit (IBM)"}])])[0]
    assert any("Qiskit (IBM) has 17 runs; the limit is 16" in p for p in problems)
    assert any('"1e1" is not a whole number' in p for p in problems)
    total = call_js(["config.js"], [("runCountProblemsFor", [[{"runner": f"r{i}", "level": 0, "raw": "16"} for i in range(4)], 16, 48])])[0]
    assert total == ["64 runs in all; the limit is 48."]


def test_multi_run_expansion_is_capped_before_the_loop():
    src = (JS / "config.js").read_text()
    assert "Math.min(count, cap)" in src and "parseRunCount(" in src
    assert "checkRunCountLimits" not in (JS / "workspace.js").read_text()
    assert 'id="run-blocked-msg"' in (STATIC / "index.html").read_text()


@requires_node
def test_run_keys_sort_by_run_number():
    keys = ["qiskit~opt0~run10", "qiskit~opt0~run2", "cirq", "qiskit~opt0~run1", "qiskit~opt1~run1"]
    pairs = [(a, b) for a in keys for b in keys]
    results = call_js(["runner_key.js"], [("compareRunnerKeys", [a, b]) for a, b in pairs])
    order = sorted(keys, key=lambda k: sum(1 for (a, b), r in zip(pairs, results) if a == k and r > 0))
    assert order == ["cirq", "qiskit~opt0~run1", "qiskit~opt0~run2", "qiskit~opt0~run10", "qiskit~opt1~run1"]


@requires_node
def test_experiment_panel_says_where_compile_outputs_are():
    with_levels, elsewhere, none = call_js(["experiment.js"], [
        ("experimentCompilerNote", [{"pyzx": [1, 2], "staq": [1]}, None]),
        ("experimentCompilerNote", [{}, "Bell (Statevector) · preprocessing on and off"]),
        ("experimentCompilerNote", [None, None]),
    ])
    assert "3 levels" in with_levels and "compiled_circuits.csv" in with_levels
    assert "Bell (Statevector) · preprocessing on and off" in elsewhere and "not this one" in elsewhere
    assert none is None


@requires_node
def test_large_measured_runs_are_warned_about():
    limit, text = call_js(["workspace.js"], [("SLOW_MEASURED_QUBITS", []), ("slowMeasuredWarning", [24, 60, 300])])
    assert limit == 22
    assert "24-qubit" in text and "60 s" in text and "300 s" in text


@requires_node
def test_analysing_phase_needs_every_run_finished():
    assert call_js(["status_cards.js"], [
        ("allRunsFinished", [{"qiskit": "done", "cirq": "timeout", "pyzx": "error"}]),
        ("allRunsFinished", [{"qiskit": "done", "cirq": "running"}]),
        ("allRunsFinished", [{}]),
    ]) == [True, False, False]


def test_queued_statuses_show_no_timer():
    src = (JS / "status_cards.js").read_text()
    assert re.search(r"queued:\s*\{[^}]*untimed: true", src)
    assert "if (cfg.untimed) return wrap;" in src


def test_quirk_opens_as_a_full_page_overlay_with_a_new_tab_link():
    html = (STATIC / "index.html").read_text()
    tab_content = html[html.index('id="tab-content"'):html.index('id="export-panel"')]
    assert 'id="visualizer-panel"' not in tab_content
    overlay = re.search(r'<div id="visualizer-panel"[^>]*class="([^"]+)"', html).group(1).split()
    assert {"fixed", "inset-0"} <= set(overlay)
    assert 'id="quirk-open-link"' in html and 'target="_blank"' in html
    assert "link.href = data.url" in (JS / "renderers.js").read_text()


def test_account_actions_sit_in_a_menu_with_their_labels():
    html = (STATIC / "index.html").read_text()
    menu = html[html.index('<details id="account-menu"'):html.index("</details>")]
    assert ">Logout</button>" in menu and "Delete\n" in menu and "text-red-600" in menu
    assert 'id="user-email-display"' in menu


def test_preprocessing_off_help_mentions_required_transforms():
    html = (STATIC / "index.html").read_text()
    assert "Raw SDK behaviour" not in html
    assert "applied regardless" in html


def test_playlist_clear_asks_first_and_auto_gen_names_its_cap():
    src = (JS / "batch.js").read_text()
    clear = src[src.index("export function clearBatch"):src.index("export function _normalizePlaylistItem")]
    assert "confirm(" in clear
    assert "qubitCapReason()" in src and 'id="gen-cap-note"' in (STATIC / "index.html").read_text()


def test_popover_closes_when_tabbing_out():
    src = (JS / "popover.js").read_text()
    assert "e.key !== 'Tab'" in src and "_nextAfter(" in src and "focusout" in src


def test_example_description_links_known_issues():
    src = (JS / "app.js").read_text()
    assert "setTextWithManualLinks(desc," in src and "knownIssuesLink()" in src
