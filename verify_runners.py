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

def test_api(level):
    payload = {
        "qasm_string": QASM,
        "optimization_level": level
    }
    try:
        response = requests.post(API_URL, json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            results = data.get("raw_results", [])
            print(f"\n--- Optimization Level {level} ---")
            for res in results:
                simulator = res.get("simulator")
                if "error" in res:
                    print(f"[{simulator}] FAILED: {res['error']}")
                else:
                    print(f"[{simulator}] OK")
            return True
        else:
            print(f"Level {level}: FAILED ({response.status_code}) - {response.text}")
            return False
    except Exception as e:
        print(f"Level {level}: ERROR - {str(e)}")
        return False

print("Broad Verifying Optimization Level Support via Rosetta API...")
time.sleep(2) # Give services a moment
test_api(0)
test_api(3)
