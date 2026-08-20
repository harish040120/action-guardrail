# API Reference

## Base URL

```
https://<your-api-id>.execute-api.us-east-1.amazonaws.com
```

## Authentication

All endpoints except `/health` require the `x-api-key` header.

```
x-api-key: <your-api-key>
```

---

## Endpoints

### GET /health

Health check. No authentication required.

**Response:**

```json
{
  "status": "ok",
  "dry_run": false,
  "rules_loaded": 6,
  "default_action": "block"
}
```

---

### GET /v1/policies

Returns the currently deployed policy rules.

**Headers:** `x-api-key`

**Response:**

```json
{
  "default_action": "block",
  "rules": [
    {
      "id": "block-bulk-delete",
      "description": "Block any DB delete where record count exceeds 100",
      "action_type": "database.delete",
      "tool_names": ["db_delete", "execute_sql", "bulk_delete"],
      "conditions": [
        {"field": "arguments.record_count", "operator": "greater_than", "value": 100}
      ],
      "action": "block",
      "severity": "high"
    }
  ]
}
```

---

### POST /v1/actions/evaluate

Evaluate an action against policies **without executing it**. Useful for agent self-checks and dry runs.

**Headers:** `x-api-key`, `Content-Type: application/json`

**Request:**

```json
{
  "tool_name": "db_delete",
  "arguments": {"table": "users", "record_count": 500},
  "agent_id": "my-agent",
  "context": {"action_type": "database.delete"}
}
```

**Response:**

```json
{
  "request_id": "...",
  "tool_name": "db_delete",
  "action_type": "database.delete",
  "verdict": "block",
  "matched_rule_ids": ["block-bulk-delete"],
  "reason": "Block any DB delete where record count exceeds 100",
  "timestamp": "...",
  "agent_id": "my-agent",
  "arguments": {"table": "users", "record_count": 500}
}
```

---

### POST /v1/actions/execute

The real enforcement boundary. The agent NEVER calls tool adapters directly — only this endpoint does, and only after a policy check passes.

**Headers:** `x-api-key`, `Content-Type: application/json`

**Request:** Same as `/v1/actions/evaluate`.

**Responses:**

**BLOCK (403):**

```json
{
  "detail": {
    "verdict": "block",
    "reason": "Block any DB delete where record count exceeds 100",
    "matched_rule_ids": ["block-bulk-delete"]
  }
}
```

**REQUIRE_HITL:**

```json
{
  "verdict": "require_hitl",
  "hitl_id": "...",
  "status": "PENDING",
  "expires_at": "...",
  "reason": "External email requires human approval"
}
```

**LOG_AND_ALLOW:**

```json
{
  "verdict": "log_and_allow",
  "executed": true,
  "result": {"status": "deleted", "rows": 5},
  "reason": "..."
}
```

---

### GET /v1/hitl

List all pending HITL requests.

**Headers:** `x-api-key`

**Response:**

```json
{
  "pending": [
    {
      "hitl_id": "...",
      "status": "PENDING",
      "tool_name": "send_email",
      "action_type": "email.send",
      "arguments": "{\"recipient_domain\": \"gmail.com\"}",
      "agent_id": "openrouter-agent",
      "reason": "External email requires human approval",
      "created_at": "...",
      "expires_at": "..."
    }
  ]
}
```

---

### POST /v1/hitl/{hitl_id}/approve

Approve and execute a pending HITL request.

**Headers:** `x-api-key`

**Query:** `approved_by=<reviewer_name>`

**Response:**

```json
{
  "status": "APPROVED",
  "executed": true,
  "result": {"status": "sent", "message_id": "..."}
}
```

---

### POST /v1/hitl/{hitl_id}/reject

Reject a pending HITL request. The action is permanently blocked.

**Headers:** `x-api-key`

**Query:** `rejected_by=<reviewer_name>`

**Response:**

```json
{
  "status": "REJECTED",
  "executed": false
}
```

---

### GET /v1/audit

Query audit records.

**Headers:** `x-api-key`

**Query Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `agent_id` | string | — | Filter by agent |
| `limit` | int | 50 | Max records to return |

**Response:**

```json
{
  "items": [
    {
      "agent_id": "openrouter-agent",
      "request_id": "...",
      "tool_name": "db_delete",
      "action_type": "database.delete",
      "verdict": "block",
      "matched_rule_ids": ["block-bulk-delete"],
      "reason": "...",
      "timestamp": "...",
      "arguments": "...",
      "executed": false,
      "execution_result": null
    }
  ]
}
```
