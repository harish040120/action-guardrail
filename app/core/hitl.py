import boto3, os, json, uuid
from datetime import datetime, timezone, timedelta
from app.core.models import Decision

HITL_TABLE = os.getenv("HITL_TABLE_NAME", "guardrail_hitl_requests")
REGION = os.getenv("AWS_REGION") or os.getenv("AWS_REGION_OVERRIDE", "us-east-1")
DEFAULT_TTL_MINUTES = 60

def _table():
    return boto3.resource("dynamodb", region_name=REGION).Table(HITL_TABLE)

def create_hitl_request(decision: Decision) -> dict:
    now = datetime.now(timezone.utc)
    item = {
        "hitl_id": str(uuid.uuid4()),
        "request_id": decision.request_id,
        "status": "PENDING",                 # PENDING | APPROVED | REJECTED | EXPIRED
        "tool_name": decision.tool_name,
        "action_type": decision.action_type,
        "arguments": json.dumps(decision.arguments),
        "agent_id": decision.agent_id,
        "reason": decision.reason,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=DEFAULT_TTL_MINUTES)).isoformat(),
        "resolved_by": None,
        "resolved_at": None,
    }
    _table().put_item(Item=item)
    return item

def get_hitl_request(hitl_id: str) -> dict | None:
    resp = _table().get_item(Key={"hitl_id": hitl_id})
    return resp.get("Item")

def list_pending() -> list:
    resp = _table().scan(FilterExpression="#s = :p",
                          ExpressionAttributeNames={"#s": "status"},
                          ExpressionAttributeValues={":p": "PENDING"})
    items = resp.get("Items", [])
    now = datetime.now(timezone.utc).isoformat()
    return [i for i in items if i["expires_at"] > now]

def list_hitl_history() -> list:
    resp = _table().scan(FilterExpression="#s <> :p",
                          ExpressionAttributeNames={"#s": "status"},
                          ExpressionAttributeValues={":p": "PENDING"})
    items = resp.get("Items", [])
    items.sort(key=lambda x: x.get("resolved_at") or x.get("created_at") or "", reverse=True)
    return items

def resolve(hitl_id: str, status: str, resolved_by: str) -> dict:
    assert status in ("APPROVED", "REJECTED")
    item = get_hitl_request(hitl_id)
    if not item:
        raise ValueError("HITL request not found")
    if item["status"] != "PENDING":
        raise ValueError(f"HITL request already {item['status']}")
    if item["expires_at"] < datetime.now(timezone.utc).isoformat():
        _table().update_item(Key={"hitl_id": hitl_id},
                              UpdateExpression="SET #s = :e",
                              ExpressionAttributeNames={"#s": "status"},
                              ExpressionAttributeValues={":e": "EXPIRED"})
        raise ValueError("HITL request expired")
    now = datetime.now(timezone.utc).isoformat()
    _table().update_item(
        Key={"hitl_id": hitl_id},
        UpdateExpression="SET #s = :st, resolved_by = :rb, resolved_at = :ra",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":st": status, ":rb": resolved_by, ":ra": now},
    )
    item.update(status=status, resolved_by=resolved_by, resolved_at=now)
    return item
