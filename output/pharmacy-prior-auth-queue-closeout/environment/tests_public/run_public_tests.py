#!/usr/bin/env python3
"""Public tests for the prior authorization queue processor.

Tests two easy-path cases: ST met via queue + Q within limit,
and ST not required + Q within limit.
"""

import json
import subprocess
import sys
import time
import urllib.request
import urllib.error
import os


def check_services():
    """Check if all services are running."""
    for port in [5001, 5002, 5003, 5004]:
        try:
            urllib.request.urlopen(f"http://localhost:{port}/", timeout=2)
        except Exception:
            return False
    return True


def run_public_tests():
    # Check services
    if not check_services():
        print("FAIL: Services are not running.")
        print("Start them with: bash /app/services/start_services.sh")
        return False

    # Back up original queue
    with open("/app/queue.json") as f:
        original_queue = f.read()

    # Clear audit log if it exists
    audit_path = "/app/audit.log"
    if os.path.exists(audit_path):
        os.remove(audit_path)

    # Clear submissions
    with open("/app/data/submissions.jsonl", "w") as f:
        pass

    try:
        # Create test queue with 2 easy-path cases
        test_queue = [
            {
                "case_id": "PUB001",
                "drug_id": "DRUG003",
                "patient_id": "PAT001",
                "requested_quantity": 25,
                "diagnosis_code": "E10.9",
                "prior_drugs": [{"drug_id": "DRUG001", "outcome": "failed"}],
                "notes": ""
            },
            {
                "case_id": "PUB002",
                "drug_id": "DRUG001",
                "patient_id": "PAT002",
                "requested_quantity": 45,
                "diagnosis_code": "E11.0",
                "prior_drugs": [],
                "notes": ""
            }
        ]

        with open("/app/queue.json", "w") as f:
            json.dump(test_queue, f, indent=2)

        # Run the processor
        result = subprocess.run(
            ["python3", "/app/process_queue.py"],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            print(f"FAIL: Processor exited with code {result.returncode}")
            if result.stderr:
                print(f"stderr: {result.stderr}")
            return False

        # Check audit log exists and has 2 entries
        if not os.path.exists(audit_path):
            print("FAIL: Audit log not created")
            return False

        entries = []
        with open(audit_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))

        if len(entries) != 2:
            print(f"FAIL: Expected 2 audit entries, got {len(entries)}")
            return False

        # Check PUB001: DRUG003 requires ST, PAT001 has prior DRUG001 failed in queue, Q=25 <= 30
        # Expected: APPROVED, MEETS_CRITERIA
        pub001 = None
        for e in entries:
            if e.get("case_id") == "PUB001":
                pub001 = e
                break

        if pub001 is None:
            print("FAIL: PUB001 not found in audit log")
            return False

        if pub001.get("decision_code") != "APPROVED":
            print(f"FAIL: PUB001 expected APPROVED, got {pub001.get('decision_code')}")
            return False

        if pub001.get("reason_code") != "MEETS_CRITERIA":
            print(f"FAIL: PUB001 expected MEETS_CRITERIA, got {pub001.get('reason_code')}")
            return False

        # Check PUB002: DRUG001 does not require ST, Q=45 < 60
        # Expected: APPROVED, MEETS_CRITERIA
        pub002 = None
        for e in entries:
            if e.get("case_id") == "PUB002":
                pub002 = e
                break

        if pub002 is None:
            print("FAIL: PUB002 not found in audit log")
            return False

        if pub002.get("decision_code") != "APPROVED":
            print(f"FAIL: PUB002 expected APPROVED, got {pub002.get('decision_code')}")
            return False

        if pub002.get("reason_code") != "MEETS_CRITERIA":
            print(f"FAIL: PUB002 expected MEETS_CRITERIA, got {pub002.get('reason_code')}")
            return False

        # Check submissions
        submissions = []
        with open("/app/data/submissions.jsonl") as f:
            for line in f:
                line = line.strip()
                if line:
                    submissions.append(json.loads(line))

        if len(submissions) != 2:
            print(f"FAIL: Expected 2 submissions, got {len(submissions)}")
            return False

        print("PASS: All public tests passed")
        return True

    except Exception as e:
        print(f"FAIL: Unexpected error: {e}")
        return False

    finally:
        # Restore original queue
        with open("/app/queue.json", "w") as f:
            f.write(original_queue)

        # Clean up audit log
        if os.path.exists(audit_path):
            os.remove(audit_path)

        # Clean up submissions
        with open("/app/data/submissions.jsonl", "w") as f:
            pass


if __name__ == "__main__":
    success = run_public_tests()
    sys.exit(0 if success else 1)
