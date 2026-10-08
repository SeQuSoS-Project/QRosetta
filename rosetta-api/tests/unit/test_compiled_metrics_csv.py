"""tables/compiled_circuits.csv tells refusals apart from other compile errors."""

import csv
import io

from services.export_compiled import compiled_metrics_csv


def test_refusal_columns_distinguish_refusals_from_crashes():
    report = {"compiled_circuits": [
        {"compiler": "cirq-transformers~opt0~run1", "compiler_id": "cirq-transformers",
         "optimization_level": 0, "dispatch_status": "error", "error": "CompileRefused: cu3",
         "refusal": "cu3 with theta in [2pi, 4pi)", "refusal_kind": "input"},
        {"compiler": "staq~opt1~run1", "compiler_id": "staq", "optimization_level": 1,
         "dispatch_status": "error", "error": "ValueError: staq exited with status 1"},
        {"compiler": "pyzx~opt1~run1", "compiler_id": "pyzx", "optimization_level": 1,
         "dispatch_status": "ok", "gate_count": 4, "gate_counts": {"cx": 1, "h": 3}},
    ]}
    rows = list(csv.DictReader(io.StringIO(compiled_metrics_csv([(None, report)], {}))))
    assert rows[0]["refusal_kind"] == "input" and rows[0]["refusal"].startswith("cu3")
    assert rows[1]["dispatch_status"] == "error" and rows[1]["refusal_kind"] == ""
    assert rows[1]["refusal"] == ""
    assert rows[2]["gate_count"] == "4" and rows[2]["gate_counts"] == '{"cx": 1, "h": 3}'
    assert list(rows[0])[:7] == ["task", "compiler", "compiler_id", "optimization_level",
                                 "dispatch_status", "refusal_kind", "refusal"]
