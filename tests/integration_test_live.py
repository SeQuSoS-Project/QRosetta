import httpx
import json

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
        response = httpx.post("http://localhost/run_batch_suite", json=test_payload, timeout=120)
        
        # 1. Assert that the response status code is 200
        assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"
        
        print("✅ Status code is 200.")
        
        # 2. Parse the JSON and assert that "benchmark_summary" exists and has 1 item
        data = response.json()
        assert "benchmark_summary" in data, "Response JSON is missing 'benchmark_summary' key."
        assert len(data["benchmark_summary"]) == 1, f"Expected 1 item in 'benchmark_summary', but found {len(data['benchmark_summary'])}."
        
        print("✅ 'benchmark_summary' is valid.")
        
        # 3. Check for errors in the first task
        first_task = data["benchmark_summary"][0]
        assert "error" not in first_task, f"Task failed with an error: {first_task.get('error')}"

        print("Task completed successfully.")

        print("\nIntegration Test Passed!")

    except Exception as e:
        print(f"\nIntegration Test Failed: {e}")
        raise

if __name__ == "__main__":
    run_integration_test()
