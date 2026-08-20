# Demo Guide

## Demo A — BLOCK

1. Open the dashboard → **Test Console**
2. Select endpoint: `/v1/actions/execute`
3. Enter:

```json
{
  "tool_name": "db_delete",
  "arguments": {"table": "users", "record_count": 500},
  "agent_id": "console-test",
  "context": {"action_type": "database.delete"}
}
```

4. Click **Send**

**Expected result:**

```text
HTTP 403

verdict: block
reason: Block any DB delete where record count exceeds 100
matched_rule_ids: ["block-bulk-delete"]
```

**Dashboard verification:**

```text
Audit Log → db_delete → BLOCK → executed: no
```

---

## Demo B — ALLOW

1. Change arguments:

```json
{
  "tool_name": "db_delete",
  "arguments": {"table": "sessions", "record_count": 5},
  "agent_id": "console-test",
  "context": {"action_type": "database.delete"}
}
```

2. Click **Send**

**Expected result:**

```json
{
  "verdict": "log_and_allow",
  "executed": true
}
```

**Dashboard verification:**

```text
Audit Log → db_delete → LOG_AND_ALLOW → executed: yes
```

---

## Demo C — HITL

1. Enter:

```json
{
  "tool_name": "send_email",
  "arguments": {"recipient_domain": "gmail.com", "subject": "Q3 report"},
  "agent_id": "console-test",
  "context": {"action_type": "email.send"}
}
```

2. Click **Send**

**Expected result:**

```json
{
  "verdict": "require_hitl",
  "hitl_id": "...",
  "status": "PENDING"
}
```

3. Go to **Approvals** page
4. See the pending request with tool, agent, arguments, reason
5. Click **Approve & Execute**
6. Enter reviewer name → Confirm

**Expected result:**

```text
Approved — action executed and logged
```

The card is removed from pending. The audit log shows the approval.

---

## Demo D — Real OpenRouter Agent

Run the agent with a dangerous request:

```bash
python agent/openrouter_agent.py "Delete 500 users from the database"
```

**Expected flow:**

```text
LLM proposes db_delete(500 records)
        ↓
Guardrail
        ↓
403 BLOCK
        ↓
block-bulk-delete
```

Run with an email request:

```bash
python agent/openrouter_agent.py "Send an email to someone at gmail.com about the Q3 report"
```

**Expected flow:**

```text
LLM proposes send_email(gmail.com)
        ↓
Guardrail
        ↓
REQUIRE_HITL
        ↓
Dashboard shows approval request
```

This is the **best live demo** because it shows a real LLM → tool call → guardrail → policy decision.

---

## Demo E — Multi-Agent

1. Run the OpenRouter agent with `agent_id: "openrouter-agent"`
2. Use the Test Console with `agent_id: "console-test"`
3. Go to **Agents** page

Both agents appear with their respective statistics. The Audit Log can filter by agent.

---

## One-Minute Explanation

> "We built an enforcement gateway for AI agents. Instead of allowing an LLM to directly execute tools, every tool action is routed through our Guardrail API. The system normalizes the action, evaluates it against policy-as-code using default-deny and most-restrictive-wins logic, records the decision in DynamoDB, and either blocks it, requires human approval, or executes it through a controlled tool adapter. We deployed the gateway using API Gateway, Lambda, DynamoDB, and AWS SAM, and built a dashboard where we can inspect policies, audit actions, filter activity by agent, and approve HITL requests. Because every agent sends an agent_id, the same dashboard can monitor Claude, OpenRouter, or any other agent that uses the gateway."
