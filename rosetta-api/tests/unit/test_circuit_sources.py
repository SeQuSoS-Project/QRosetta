"""circuit_sources.js: menu values name their source, QASMBench sizes come from the file name,
and an MQT Bench size moves to the nearest one the suite has."""
from tests.unit.frontend_harness import call_js, requires_node

pytestmark = requires_node


def test_values_name_their_source_and_sizes():
    algo, qb, mqt, near, mid, edge = call_js(["circuit_sources.js"], [
        ("selectionFor", ["ghz"]),
        ("selectionFor", ["qasmbench:adder_n10"]),
        ("selectionFor", ["mqt:qft"]),
        ("nearestSize", [[2, 4, 8], 5]),
        ("nearestSize", [[2, 4, 8], 6]),
        ("nearestSize", [[], 7]),
    ])
    assert algo == {"kind": "algorithm", "name": "ghz"}
    assert qb == {"kind": "qasmbench", "name": "adder_n10", "qubits": 10}
    assert mqt["kind"] == "mqt" and mqt["name"] == "qft"
    assert near == 4 and mid == 4 and edge == 7


def test_qasmbench_name_without_size_has_none():
    assert call_js(["circuit_sources.js"], [("qasmbenchQubits", ["teleportation"])]) == [0]
