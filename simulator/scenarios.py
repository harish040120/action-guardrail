import httpx
import os
import sys

BASE = os.environ.get("GUARDRAIL_URL", "http://localhost:8000")
HEADERS = {
    "x-api-key": os.environ.get("GUARDRAIL_API_KEY", "dev-local-key")
}


def call(tool_name, arguments):
    return httpx.post(
        f"{BASE}/v1/actions/execute",
        json={
            "tool_name": tool_name,
            "arguments": arguments,
            "agent_id": "sim-agent-1"
        },
        headers=HEADERS,
        timeout=10
    )


def run():
    results = []

    # 1. Bulk delete -> BLOCK
    r = call(
        "db_delete",
        {
            "table": "users",
            "record_count": 500
        }
    )

    results.append(
        (
            "Bulk delete (BLOCK expected)",
            r.status_code == 403
        )
    )

    # 2. Small delete -> EXECUTE
    r = call(
        "db_delete",
        {
            "table": "sessions",
            "record_count": 5
        }
    )

    results.append(
        (
            "Small delete (executed expected)",
            r.status_code == 200
            and r.json().get("executed") is True
        )
    )

    # 3. External email -> HITL
    r = call(
        "send_email",
        {
            "recipient_domain": "gmail.com",
            "subject": "Q3"
        }
    )

    ok = (
        r.status_code == 200
        and r.json().get("verdict") == "require_hitl"
    )

    results.append(
        (
            "External email (HITL expected)",
            ok
        )
    )

    hitl_id = r.json().get("hitl_id") if ok else None

    # 4. Internal email -> EXECUTE
    r = call(
        "send_email",
        {
            "recipient_domain": "mycompany.com",
            "subject": "standup"
        }
    )

    results.append(
        (
            "Internal email (executed expected)",
            r.status_code == 200
            and r.json().get("executed") is True
        )
    )

    # 5. Confidential file -> EXECUTE
    r = call(
        "read_file",
        {
            "path": "confidential_report.txt"
        }
    )

    results.append(
        (
            "Confidential read (executed expected)",
            r.status_code == 200
            and r.json().get("executed") is True
        )
    )

    # 6. Unknown tool -> BLOCK
    r = call(
        "transfer_money",
        {
            "amount": 100
        }
    )

    results.append(
        (
            "Unknown tool (BLOCK expected - default-deny)",
            r.status_code == 403
        )
    )

    # 7. Approve HITL -> EXECUTE deferred action
    if hitl_id:
        approve = httpx.post(
            f"{BASE}/v1/hitl/{hitl_id}/approve",
            headers=HEADERS,
            params={
                "approved_by": "demo-reviewer"
            }
        )

        results.append(
            (
                "HITL approve executes the deferred email",
                approve.status_code == 200
                and approve.json().get("executed") is True
            )
        )

    passed = sum(
        1 for _, ok in results
        if ok
    )

    for name, ok in results:
        print(
            f"[{'PASS' if ok else 'FAIL'}] {name}"
        )

    print(
        f"\n{passed}/{len(results)} passed"
    )

    sys.exit(
        0 if passed == len(results) else 1
    )


if __name__ == "__main__":
    run()
