# In-memory demo "database": preloaded with 1000 fake rows.
_DEMO_DB = {"users": list(range(1, 1001)), "sessions": list(range(1, 51))}
_EMAIL_OUTBOX = []          # captured "sent" emails, inspectable via /v1/audit
_FILE_ROOT = "/tmp/guardrail_demo_files"   # jailed local dir, not the real filesystem

import os
os.makedirs(_FILE_ROOT, exist_ok=True)
with open(f"{_FILE_ROOT}/confidential_report.txt", "w") as f:
    f.write("Q3 salaries — demo confidential file for read testing.\n")

class ToolExecutionError(Exception):
    pass

def execute_db_delete(arguments: dict) -> dict:
    table = arguments.get("table")
    count = int(arguments.get("record_count", 0))
    if table not in _DEMO_DB:
        raise ToolExecutionError(f"Unknown demo table: {table}")
    before = len(_DEMO_DB[table])
    _DEMO_DB[table] = _DEMO_DB[table][count:]
    return {"table": table, "deleted": before - len(_DEMO_DB[table]), "remaining": len(_DEMO_DB[table])}

def execute_send_email(arguments: dict) -> dict:
    record = {"recipient_domain": arguments.get("recipient_domain"), "subject": arguments.get("subject")}
    _EMAIL_OUTBOX.append(record)
    return {"status": "queued_in_demo_outbox", "outbox_size": len(_EMAIL_OUTBOX)}

def execute_read_file(arguments: dict) -> dict:
    requested = arguments.get("path", "")
    safe_name = os.path.basename(requested)          # prevents path traversal out of the jail
    full_path = os.path.join(_FILE_ROOT, safe_name)
    if not os.path.exists(full_path):
        raise ToolExecutionError(f"No such demo file: {safe_name}")
    with open(full_path) as f:
        return {"path": safe_name, "content_preview": f.read()[:200]}

ADAPTERS = {
    "database.delete": execute_db_delete,
    "email.send": execute_send_email,
    "file.read": execute_read_file,
}

def dispatch(action_type: str, arguments: dict) -> dict:
    fn = ADAPTERS.get(action_type)
    if not fn:
        raise ToolExecutionError(f"No adapter registered for action_type: {action_type}")
    return fn(arguments)
