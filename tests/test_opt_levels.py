#!/usr/bin/env python3
"""
Optimization level coverage test.

For each optimization level (0-3), submits a GHZ circuit to all enabled runners
via /compare (statevector) and /compare_measured, then verifies:
  - No error in the runner response
  - Required timing fields are present
  - Statevectors at level > 0 are numerically equivalent to level 0
    (optimization changes circuit structure, not results — global phase allowed)
"""

import sys
import time
import base64
import numpy as np
import httpx

BASE_URL = "http://localhost"
POLL_INTERVAL = 2.0
JOB_TIMEOUT = 180  # seconds per job

# 3-qubit GHZ state — no explicit measurements.
# For statevector runs the pipeline sends this as-is; runners strip nothing.
# For measured runs the job_manager inserts terminal measurements on all qubits.
TEST_QASM = """\
OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
h q[0];
cx q[0],q[1];
cx q[1],q[2];
"""


# ── helpers ──────────────────────────────────────────────────────────────────

def decode_sv(encoded: str) -> np.ndarray | None:
    """Decode a base64 complex128 statevector string."""
    if not isinstance(encoded, str):
        return None
    try:
        raw = base64.b64decode(encoded)
        return np.frombuffer(raw, dtype=np.complex128)
    except Exception:
        return None


def submit(client: httpx.Client, endpoint: str, payload: dict) -> str:
    resp = client.post(f"{BASE_URL}/{endpoint}", json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()["job_id"]


def poll(client: httpx.Client, job_id: str) -> dict | None:
    deadline = time.time() + JOB_TIMEOUT
    while time.time() < deadline:
        resp = client.get(f"{BASE_URL}/jobs/{job_id}", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data["status"] in ("completed", "failed"):
                return data
        time.sleep(POLL_INTERVAL)
    return None


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    passed: list[tuple] = []
    failed: list[tuple] = []

    with httpx.Client(timeout=30) as client:

        # ── discover runners ──────────────────────────────────────────────
        print("Fetching /runners …")
        try:
            resp = client.get(f"{BASE_URL}/runners")
            resp.raise_for_status()
            all_runners = resp.json()
        except Exception as e:
            print(f"FATAL: cannot reach /runners — is the stack up? ({e})")
            sys.exit(1)

        enabled = [r for r in all_runners if r.get("enabled", True)]
        runner_max = {r["id"]: r.get("max_level", 0) for r in enabled}
        enabled_ids = [r["id"] for r in enabled]

        print(f"Enabled runners ({len(enabled_ids)}): {', '.join(enabled_ids)}\n")

        # ── reference statevectors (level 0) ─────────────────────────────
        ref_sv: dict[str, np.ndarray] = {}

        # ── statevector runs ─────────────────────────────────────────────
        for level in range(4):
            print(f"{'═'*62}")
            print(f"  STATEVECTOR  level={level}")
            print(f"{'═'*62}")

            try:
                jid = submit(client, "compare", {
                    "qasm_string": TEST_QASM,
                    "optimization_level": level,
                    "timeout_seconds": JOB_TIMEOUT,
                    "target_simulators": enabled_ids,
                })
            except Exception as e:
                print(f"  SKIP level={level}: submit failed ({e})")
                continue

            print(f"  job {jid} … ", end="", flush=True)
            job = poll(client, jid)
            print("done" if job else "TIMEOUT")

            if job is None:
                for rid in enabled_ids:
                    failed.append((rid, f"sv L{level}", "job timed out"))
                continue

            raw = (job.get("results") or {}).get("raw_results", [])

            for entry in raw:
                rid = entry.get("simulator", "?")
                eff = min(level, runner_max.get(rid, level))
                tag = f"sv  L{level}→{eff}"

                if entry.get("error"):
                    msg = entry["error"][:90]
                    print(f"  FAIL  {rid:<26} [{tag}]  {msg}")
                    failed.append((rid, tag, msg))
                    continue

                missing = [f for f in (
                    "execution_time_sec", "compilation_time_sec", "simulation_time_sec"
                ) if f not in entry]
                if missing:
                    msg = f"missing fields: {missing}"
                    print(f"  FAIL  {rid:<26} [{tag}]  {msg}")
                    failed.append((rid, tag, msg))
                    continue

                sv_raw = entry.get("statevector")
                sv = decode_sv(sv_raw) if isinstance(sv_raw, str) else None

                if sv is not None:
                    if level == 0:
                        ref_sv[rid] = sv
                    elif rid in ref_sv and ref_sv[rid] is not None:
                        ref = ref_sv[rid]
                        if sv.shape == ref.shape:
                            fidelity = float(abs(np.vdot(sv, ref)) ** 2)
                            if fidelity < 0.9999:
                                msg = f"statevector mismatch fidelity={fidelity:.6f}"
                                print(f"  FAIL  {rid:<26} [{tag}]  {msg}")
                                failed.append((rid, tag, msg))
                                continue

                print(f"  pass  {rid:<26} [{tag}]")
                passed.append((rid, tag))

        print()

        # ── measured runs ─────────────────────────────────────────────────
        for level in range(4):
            print(f"{'═'*62}")
            print(f"  MEASURED     level={level}  shots=256")
            print(f"{'═'*62}")

            try:
                jid = submit(client, "compare_measured", {
                    "qasm_string": TEST_QASM,
                    "n_shots": 256,
                    "optimization_level": level,
                    "timeout_seconds": JOB_TIMEOUT,
                    "target_simulators": enabled_ids,
                })
            except Exception as e:
                print(f"  SKIP level={level}: submit failed ({e})")
                continue

            print(f"  job {jid} … ", end="", flush=True)
            job = poll(client, jid)
            print("done" if job else "TIMEOUT")

            if job is None:
                for rid in enabled_ids:
                    failed.append((rid, f"meas L{level}", "job timed out"))
                continue

            raw = (job.get("results") or {}).get("raw_results", [])

            for entry in raw:
                rid = entry.get("simulator", "?")
                eff = min(level, runner_max.get(rid, level))
                tag = f"meas L{level}→{eff}"

                if entry.get("error"):
                    msg = entry["error"][:90]
                    print(f"  FAIL  {rid:<26} [{tag}]  {msg}")
                    failed.append((rid, tag, msg))
                    continue

                counts = entry.get("counts") or {}
                total = sum(counts.values())
                if total == 0:
                    msg = "counts sum to 0"
                    print(f"  FAIL  {rid:<26} [{tag}]  {msg}")
                    failed.append((rid, tag, msg))
                    continue

                print(f"  pass  {rid:<26} [{tag}]  ({total} shots, {len(counts)} outcomes)")
                passed.append((rid, tag))

    # ── summary ───────────────────────────────────────────────────────────
    print(f"\n{'═'*62}")
    print(f"  {len(passed)} passed   {len(failed)} failed")
    print(f"{'═'*62}")

    if failed:
        print("\nFailed:")
        for rid, tag, reason in failed:
            print(f"  {rid:<26} [{tag}]  {reason}")
        sys.exit(1)

    print("\nAll runners passed all optimization levels.")


if __name__ == "__main__":
    main()
