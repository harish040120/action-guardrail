# Architecture

## System Overview

```text
                  ┌───────────────────┐
                  │   Claude /        │
                  │   OpenRouter /    │
                  │   Any AI Agent    │
                  └─────────┬─────────┘
                            │
                      tool/action request
                            │
                            ▼
                ┌──────────────────────────┐
                │       API Gateway        │
                └────────────┬─────────────┘
                             │
                             ▼
                ┌──────────────────────────┐
                │   Action Guardrail Lambda │
                │        FastAPI            │
                │                          │
                │  1. Normalize            │
                │  2. Policy Evaluation    │
                │  3. Audit                │
                │  4. HITL if required     │
                │  5. Execute if allowed   │
                └───────┬────────┬─────────┘
                        │        │
             ┌──────────┘        └────────────┐
             ▼                                ▼
       DynamoDB Audit                    Tool Adapter
       + HITL State                      DB / Email / File
```

The critical architectural change is that **the agent does not have direct access to the tool adapters**. The Guardrail owns the execution boundary.

---

## Action Flow

Every action goes through:

```text
Agent
  ↓
/v1/actions/execute
  ↓
Normalize tool → action_type
  ↓
Policy Engine
  ↓
Audit
  ↓
Decision
```

Three possible outcomes:

| Verdict | Behavior |
|---|---|
| **BLOCK** | 403 returned. Tool is NOT executed. |
| **REQUIRE_HITL** | Pending approval. Human approves/rejects. Tool executes only after approval. |
| **LOG_AND_ALLOW** | Tool executes. Result is audited. |

---

## Default-Deny

```yaml
default_action: block
```

If someone invents an unknown action like `transfer_money`, `send_bank_payment`, or `delete_everything` and there is no matching rule:

```text
No policy match
      ↓
default_action = block
      ↓
403
```

Unknown actions are blocked by default rather than silently allowed.

---

## Alternate-Tool-Name Protection

Suppose your policy protects `db_delete` but the agent tries `execute_sql`.

The normalizer maps:

| Tool Name | Normalized Action Type |
|---|---|
| `db_delete` | `database.delete` |
| `execute_sql` | `database.delete` |
| `bulk_delete` | `database.delete` |

All of them reach the same policy category. An agent cannot simply rename a dangerous tool to bypass the rule.

---

## Most-Restrictive-Wins

If multiple policies match an action, the most restrictive verdict wins:

```text
BLOCK > REQUIRE_HITL > LOG_AND_ALLOW
```

Example:

```text
Rule A → log_and_allow
Rule B → block

Final: BLOCK
```

This is explicitly implemented in the policy engine.

---

## AWS Services

### Lambda

Runs the FastAPI Action Guardrail. The SAM template uses Python 3.11.

### API Gateway

Public API entry point. Routes requests to Lambda.

### DynamoDB — Audit

Table: `guardrail_audit_log`

Stores: `agent_id`, `request_id`, `tool_name`, `action_type`, `verdict`, `matched_rule_ids`, `reason`, `timestamp`, `arguments`, `executed`, `execution_result`

### DynamoDB — HITL

Table: `guardrail_hitl_requests`

Stores pending approval state: `PENDING`, `APPROVED`, `REJECTED`, `EXPIRED`

### IAM

Lambda execution role, DynamoDB permissions, GitHub OIDC deployment role.

### CloudFormation / SAM

`template.yaml` defines: Lambda, API Gateway, DynamoDB (Audit + HITL), IAM permissions.

### S3

Hosts the static dashboard frontend: `index.html`.

### GitHub Actions

CI/CD pipeline: `git push` → pytest → AWS OIDC → SAM build → SAM deploy → health check.
