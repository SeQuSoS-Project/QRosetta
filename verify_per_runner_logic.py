import requests
import json
import time

API_URL = "http://localhost/compare"

QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
h q[0];
cx q[0],q[1];
"""

def test_per_runner():
    payload = {
        "qasm_string": QASM,
        "optimization_level": 1,
        "runner_config": {
            "qiskit": 3,
            "cirq": 0
        }
    }
    print(f"Sending request with global opt=1, qiskit=3, cirq=0...")
    try:
        response = requests.post(API_URL, json=payload, timeout=30)
        if response.status_code == 200:
            print("Request successful. check docker logs for Level verification.")
            return True
        else:
            print(f"FAILED ({response.status_code}) - {response.text}")
            return False
    except Exception as e:
        print(f"ERROR - {str(e)}")
        return False

if __name__ == "__main__":
    test_per_runner()
