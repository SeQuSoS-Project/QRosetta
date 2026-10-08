"""The page's limits before GET /config answers (state.js defaults, index.html attributes) are
the server's, and GET /algorithms never offers more qubits than a circuit may be generated with."""
import re
from pathlib import Path

from config import settings

_STATIC = Path(__file__).resolve().parents[2] / "static"


def _state_default(name):
    match = re.search(rf"^\s*{name}: (\d+),$", (_STATIC / "js" / "state.js").read_text(), re.M)
    assert match, name
    return int(match.group(1))


def test_state_defaults_match_the_server_limits():
    assert _state_default("maxQubitsStatevector") == settings.MAX_QUBITS_STATEVECTOR
    assert _state_default("maxQubitsMeasured") == settings.MAX_QUBITS_MEASURED
    assert _state_default("maxQubitsCompile") == settings.MAX_QUBITS_COMPILE
    assert _state_default("maxRequestBytes") == settings.MAX_UPLOAD_BYTES
    assert _state_default("maxQasmSize") == settings.MAX_QASM_SIZE
    assert _state_default("maxExperimentCells") == settings.MAX_EXPERIMENT_CELLS
    assert _state_default("maxExportItems") == settings.MAX_EXPORT_ITEMS
    assert _state_default("maxLabelLength") == settings.MAX_LABEL_LENGTH


def test_html_inputs_do_not_exceed_the_server_limits():
    html = (_STATIC / "index.html").read_text()
    for input_id in ("algo-qubits", "gen-min", "gen-max"):
        tag = re.search(rf'<input[^>]*id="{input_id}"[^>]*>', html, re.S).group(0)
        assert f'max="{settings.MAX_QUBITS_STATEVECTOR}"' in tag, input_id
    for input_id in ("ctx-algo-name", "single-run-name"):
        tag = re.search(rf'<input[^>]*id="{input_id}"[^>]*>', html, re.S).group(0)
        assert f'maxlength="{2 * settings.MAX_LABEL_LENGTH}"' in tag, input_id


def test_algorithm_qubit_ranges_fit_the_generator_limit():
    import asyncio
    from routers.generation import get_algorithms
    for algo in asyncio.run(get_algorithms()):
        assert algo["min_qubits"] <= algo["max_qubits"] <= settings.MAX_QUBITS_MEASURED, algo["id"]
