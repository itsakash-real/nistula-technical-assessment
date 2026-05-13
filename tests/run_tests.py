"""
Manual test runner for the webhook pipeline.

Sends each payload from sample_payloads.json to the running
server and prints a structured result for each test case.

Usage:
    Make sure the server is running first:
        uvicorn app.main:app --reload

    Then in a separate terminal:
        python tests/run_tests.py

This is intentionally simple — no test framework dependency.
A reviewer can run this in under 30 seconds and see every
scenario play out with clear pass/fail output.
"""

import json
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8000/webhook/message"
PAYLOADS_FILE = "tests/sample_payloads.json"

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"


def run_tests():
    with open(PAYLOADS_FILE) as f:
        test_cases = json.load(f)["test_cases"]

    print(f"\n{BOLD}Nistula Webhook — Test Runner{RESET}")
    print("=" * 60)

    passed = 0
    failed = 0

    for tc in test_cases:
        tc_id = tc["id"]
        description = tc["description"]
        payload = tc["payload"]
        expected_status = tc.get("expected_status", 200)

        print(f"\n{BOLD}[{tc_id}]{RESET} {description}")

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                BASE_URL,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                status = response.getcode()
                body = json.loads(response.read())

            if expected_status == 200:
                query_type = body.get("query_type")
                action = body.get("action")
                score = body.get("confidence_score")
                reply_preview = body.get("drafted_reply", "")[:80]

                print(f"  Status       : {GREEN}{status}{RESET}")
                print(f"  Query Type   : {query_type}")
                print(f"  Confidence   : {score}")
                print(f"  Action       : {YELLOW}{action}{RESET}")
                print(f"  Reply Preview: {reply_preview}...")
                passed += 1
            else:
                print(f"  {RED}FAIL — Expected status {expected_status}, got {status}{RESET}")
                failed += 1

        except urllib.error.HTTPError as e:
            status = e.code
            body = json.loads(e.read())

            if status == expected_status:
                print(f"  Status       : {GREEN}{status} (expected){RESET}")
                if "details" in body:
                    for detail in body["details"]:
                        print(f"  Validation   : {detail['field']} — {detail['issue']}")
                passed += 1
            else:
                print(f"  {RED}FAIL — Expected {expected_status}, got {status}{RESET}")
                print(f"  Body: {body}")
                failed += 1

        except Exception as e:
            print(f"  {RED}ERROR — {str(e)}{RESET}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"{BOLD}Results: {GREEN}{passed} passed{RESET} | {RED}{failed} failed{RESET}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    run_tests()