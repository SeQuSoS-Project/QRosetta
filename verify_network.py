import urllib.request
import urllib.error
import sys

def test_url(url, description, expect_success=True):
    print(f"Testing {description} ({url})...", end=" ")
    try:
        urllib.request.urlopen(url, timeout=3)
        if expect_success:
            print("✅ Success")
            return True
        else:
            print("❌ Failed (Connection succeeded but should have failed)")
            return False
    except urllib.error.URLError as e:
        if not expect_success:
            print(f"✅ Success (Connection blocked as expected: {e})")
            return True
        else:
            print(f"❌ Failed ({e})")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

print("--- Network Verification ---")

# 1. Test Internal Connectivity (should work)
# The API container attempting to talk to a runner (e.g., qiskit_runner on port 8000)
internal_success = test_url("http://pytket-qiskit-runner:8000", "Internal Service (Qiskit Runner)", expect_success=True)

# 2. Test External Connectivity (should fail)
# Attempting to reach google.com
external_success = test_url("https://www.google.com", "External Internet (Google)", expect_success=False)

if internal_success and external_success:
    print("\n🎉 Verification PASSED: Network isolation is working correctly.")
    sys.exit(0)
else:
    print("\n⚠️ Verification FAILED.")
    sys.exit(1)
