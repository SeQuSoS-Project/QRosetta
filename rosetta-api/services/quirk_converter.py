# Converts Quirk URLs to QASM formats.

import json
import re
import urllib.parse

class QuirkCompiler:
    def __init__(self, qasm_string: str):
        self.qasm_string = qasm_string
        self.num_qubits = 0
        self.columns = []
        self.depth_trackers = []

    def _parse_qreg(self):
        match = re.search(r"qreg\s+[a-zA-Z0-9_]+\[(\d+)\]", self.qasm_string)
        if match:
            self.num_qubits = int(match.group(1))
            self.depth_trackers = [0] * self.num_qubits
        else:
            raise ValueError("Could not find a valid qreg statement to determine qubit count.")

    def _add_gate(self, gate_type: str, targets: list[int], controls: list[int] = None):
        if controls is None:
            controls = []

        all_involved = targets + controls

        max_depth = 0
        for q in all_involved:
            max_depth = max(max_depth, self.depth_trackers[q])

        while len(self.columns) <= max_depth:
            self.columns.append([1] * self.num_qubits)

        for t in targets:
            self.columns[max_depth][t] = gate_type
        for c in controls:
            self.columns[max_depth][c] = "•"

        new_depth = max_depth + 1
        for q in all_involved:
            self.depth_trackers[q] = new_depth

    def compile(self):
        self._parse_qreg()

        lines = self.qasm_string.split(';')
        for line in lines:
            line = line.strip()
            if not line or line.startswith('//') or line.startswith('OPENQASM') or line.startswith('include') or line.startswith('qreg') or line.startswith('creg') or line.startswith('measure'):
                continue

            match_1q = re.match(r"(h|x|y|z)\s+[a-zA-Z0-9_]+\[(\d+)\]", line)
            if match_1q:
                gate = match_1q.group(1).upper()
                target = int(match_1q.group(2))
                self._add_gate(gate, [target])
                continue

            match_cx = re.match(r"cx\s+[a-zA-Z0-9_]+\[(\d+)\],\s*[a-zA-Z0-9_]+\[(\d+)\]", line)
            if match_cx:
                control = int(match_cx.group(1))
                target = int(match_cx.group(2))
                self._add_gate("X", [target], [control])
                continue

    def generate_url(self) -> str:
        self.compile()
        quirk_dict = {"cols": self.columns}
        json_str = json.dumps(quirk_dict)
        encoded_json = urllib.parse.quote(json_str)
        return f"https://quirk-e.dev/#circuit={encoded_json}"
