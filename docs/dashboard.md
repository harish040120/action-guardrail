# Dashboard

## Overview

The HTML dashboard is an **operations console for the Guardrail API**. It provides monitoring, policy inspection, HITL approval, audit review, and action testing.

---

## Pages

### Overview

Shows live gateway status:

- **Health** — Online / Offline
- **Rules loaded** — number of deployed policy rules
- **Default action** — what happens to unmatched actions
- **Pending HITL** — count of awaiting approvals
- **Blocked** — recent blocked actions
- **HITL Required** — recent HITL-routed actions
- **Allowed / Executed** — recent allowed actions
- **Dry run mode** — ON / off
- **Recent actions** — table with time, agent, tool, action type, verdict, executed

### Approvals (HITL)

The most important page. Shows every pending HITL request with:

- Tool name and REQUIRE_HITL badge
- Action type and agent ID
- Arguments summary and full JSON
- Reason for HITL
- Created / expires timestamps
- Remaining time
- **Approve & Execute** button — calls `POST /v1/hitl/{id}/approve`
- **Reject** button — calls `POST /v1/hitl/{id}/reject`

Auto-refreshes every 8 seconds.

### Audit Log

Full audit trail with filters:

- Agent (dropdown, derived from data)
- Tool (dropdown, derived from data)
- Action type (dropdown, derived from data)
- Verdict (BLOCK / REQUIRE_HITL / LOG_AND_ALLOW)
- Time range (15min / 1h / 24h / 7d / all)
- Limit

Click any row to open a detail modal showing all fields.

### Policies

Read-only view of deployed policy rules from `GET /v1/policies`.

Shows: default action, rule ID, description, action type, tool names, conditions, action, severity.

### Test Console

Send synthetic actions through the gateway.

- Quick scenario buttons: Block bulk delete, Allow small delete, External email → HITL, Internal email → Allow, Unknown tool → Block
- Endpoint selector: `/v1/actions/evaluate` (safe) or `/v1/actions/execute` (real execution)
- Warning banner when execute mode is selected

### Agents

Derived from audit data. Shows per-agent statistics:

- Total actions
- Blocked / HITL / Allowed counts
- Tools used
- Last seen

Click an agent to filter the Audit Log by that agent.

### Settings

Security information:

- Credentials are memory-only, never persisted
- Auth header: `x-api-key`

---

## Connection

The dashboard always opens on the connection screen. The user enters:

1. Guardrail API URL
2. API key

The connect sequence:

```
1. GET /health (no auth)
   → fails: "Unable to reach the Guardrail API."
2. GET /v1/policies (with x-api-key)
   → fails: "API reachable, but API key is invalid."
3. Both succeed: "Connected to Action Guardrail." → show dashboard
```

Credentials are held in JavaScript memory only. On page refresh, they must be re-entered.

---

## Multi-Agent Support

Every action contains an `agent_id`. The audit database records it.

The dashboard can show:

```text
Agent filter:
[ All Agents ▼ ]

openrouter-agent
claude-agent
sim-agent-1
manual-test
production-demo
```

Any agent that routes through `/v1/actions/execute` appears in the same dashboard.
