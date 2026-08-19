import boto3, os, json
from app.core.models import Decision

AUDIT_TABLE = os.getenv("AUDIT_TABLE_NAME", "guardrail_audit_log")
REGION = os.getenv("AWS_REGION") or os.getenv("AWS_REGION_OVERRIDE", "us-east-1")

SENSITIVE_KEYS = {"password", "api_key", "secret", "token", "credit_card", "ssn", "authorization"}

def redact(obj):
    if isinstance(obj, dict):
        return {k: ("***REDACTED***" if k.lower() in SENSITIVE_KEYS else redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    return obj

def _table():
    return boto3.resource("dynamodb", region_name=REGION).Table(AUDIT_TABLE)

class AuditWriteError(Exception):
    pass

def write_audit(decision: Decision, executed: bool, execution_result: dict | None = None):
    item = {
        "agent_id": decision.agent_id,                                  # partition key
        "sort_key": f"{decision.timestamp}#{decision.request_id}",       # sort key
        "request_id": decision.request_id,
        "tool_name": decision.tool_name,
        "action_type": decision.action_type or "unknown",
        "verdict": decision.verdict,
        "matched_rule_ids": decision.matched_rule_ids,
        "reason": decision.reason,
        "timestamp": decision.timestamp,
        "arguments": json.dumps(redact(decision.arguments)),
        "executed": executed,
        "execution_result": json.dumps(redact(execution_result)) if execution_result else None,
    }
    try:
        _table().put_item(Item=item)
    except Exception as e:
        raise AuditWriteError(str(e)) from e

def query_by_agent(agent_id: str, limit: int = 50):
    resp = _table().query(
        KeyConditionExpression="agent_id = :a",
        ExpressionAttributeValues={":a": agent_id},
        ScanIndexForward=False, Limit=limit,
    )
    return resp.get("Items", [])

def query_recent(limit: int = 50):
    # Fallback for "show me everything" demo use — a scan is fine at this data volume;
    # documented as a known scaling limitation, not claimed as production-grade analytics.
    return _table().scan(Limit=limit).get("Items", [])
