"""The Recent runs button: signed-out users open and close this browser's list of runs the server
still keeps (the same list the page offers on load), with a note when it is empty."""
import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / "static"
JS = STATIC / "js"


def _tag(html, element_id):
    found = re.search(rf'<button id="{element_id}"[^>]*>', html, re.S)
    assert found, element_id
    return found.group(0)


def test_the_button_controls_the_recent_runs_banner_and_waits_for_a_run_to_end():
    html = (STATIC / "index.html").read_text()
    tag = _tag(html, "btn-recent-runs")
    assert 'type="button"' in tag and "data-busy-disable" in tag
    assert 'aria-controls="resume-job-banner"' in tag and 'aria-expanded="false"' in tag
    assert 'id="resume-job-empty" class="hidden"' in html


def test_the_button_is_wired_once_and_opens_the_existing_list():
    main = (JS / "main.js").read_text()
    assert main.count("'#btn-recent-runs'") == 1 and "toggleRecentJobs()" in main
    workspace = (JS / "workspace.js").read_text()
    body = workspace[workspace.index("export function toggleRecentJobs"):]
    assert "offerRecentJobs({ onRequest: true })" in body.split("\n}\n")[0]


def test_only_signed_out_users_see_it():
    auth = (JS / "auth.js").read_text()
    body = auth[auth.index("export function updateAuthUI"):]
    assert "getElementById('btn-recent-runs')?.classList.toggle('hidden', !!getState().authToken)" in body.split("\n}\n")[0]


def test_the_manual_names_it():
    assert "<strong>Recent runs</strong>" in (STATIC / "docs.html").read_text()


def test_every_close_of_the_list_resets_aria_expanded():
    workspace = (JS / "workspace.js").read_text()
    hides = [m.start() for m in re.finditer(r"getElementById\('resume-job-banner'\)\?\.classList\.add\('hidden'\)", workspace)]
    helper = workspace[workspace.index("function _hideRecentJobs"):]
    helper = helper.split("\n}\n")[0]
    assert len(hides) == 1 and workspace.index("function _hideRecentJobs") < hides[0] < workspace.index("function _hideRecentJobs") + len(helper)
    assert "setAttribute('aria-expanded', 'false')" in helper
    for caller in ("export async function runWorkspace", "export async function resumeJob", "export function toggleRecentJobs"):
        body = workspace[workspace.index(caller):].split("\n}\n")[0]
        assert "_hideRecentJobs()" in body, caller
