import httpx
import json
import time


def _poll_job(job_id: str, timeout: int = 120) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = httpx.get(f"http://localhost/jobs/{job_id}", timeout=10)
        assert resp.status_code == 200, f"Job poll HTTP {resp.status_code}: {resp.text}"
        data = resp.json()
        if data.get("status") == "completed":
            return data.get("results", {})
        time.sleep(1)
    raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")


def run_integration_test():
    """
    Runs an end-to-end integration test against the live Nginx/API stack.
    """
    test_payload = {
        "mode": "statevector",
        "n_shots": 1024,
        "tasks": [{"algorithm": "bell", "qubits": 2}]
    }

    try:
        print("Starting integration test...")

        # Make a POST request to the batch endpoint via the Nginx proxy
        response = httpx.post("http://localhost/run_batch_suite", json=test_payload, timeout=30)

        # 1. Assert that the response status code is 200
        assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

        print("Status code is 200.")

        # 2. Parse the job_id and poll for completion
        job_id = response.json()["job_id"]
        print(f"Job submitted: {job_id}. Polling for results...")

        data = _poll_job(job_id)

        # 3. Assert that "benchmark_summary" exists and has 1 item
        assert "benchmark_summary" in data, "Response JSON is missing 'benchmark_summary' key."
        assert len(data["benchmark_summary"]) == 1, \
            f"Expected 1 item in 'benchmark_summary', but found {len(data['benchmark_summary'])}."

        print("'benchmark_summary' is valid.")

        # 4. Check for errors in the first task
        first_task = data["benchmark_summary"][0]
        assert "error" not in first_task, f"Task failed with an error: {first_task.get('error')}"

        print("Task completed successfully.")
        print("\nIntegration Test Passed!")

    except Exception as e:
        print(f"\nIntegration Test Failed: {e}")
        raise


if __name__ == "__main__":
    run_integration_test()
