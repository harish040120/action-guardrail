# Action Guardrail

**A real-time enforcement gateway that sits between AI agents and the tools they call — deployed on AWS.**

Live endpoint: `https://ql3rxw4r7a.execute-api.us-east-1.amazonaws.com`

---

## 1. Problem Statement

AI agents are increasingly given tools — database access, email, file systems, payment APIs — and asked to decide for themselves when to use them. Most existing "guardrails" only inspect the model's **text output**: they check what the LLM *says*, not what it *does*.

That leaves a gap. An agent can be told not to do something dangerous, refuse in words, and still call the tool anyway — because nothing actually stands between the model's decision and the tool's execution. A single prompt injection, hallucinated plan, or renamed tool call can trigger a bulk delete, an email to the wrong domain, or a file read outside its sandbox, with no checkpoint in between.

**The core problem:** once an agent has a tool, it is trusted with the tool's full blast radius — with no independent, non-bypassable checkpoint between "the model decided to act" and "the action happened."

---

## 2. Solution

Action Guardrail moves enforcement from the *prompt layer* to the *execution layer*.

The agent never touches a database, inbox, or filesystem directly. Every tool call is sent as a structured action request to a policy-as-code enforcement gateway, which normalizes it, evaluates it against explicit rules, and returns exactly one of three verdicts:

| Verdict | Meaning |
|---|---|
| **BLOCK** | Action is denied outright. Nothing executes. |
| **REQUIRE_HITL** | Action is paused and persisted as a pending approval. A human must approve or reject it before it can run. |
| **LOG_AND_ALLOW** | Action is safe by policy — it is logged and executed. |

The agent **cannot bypass this**, because it never has direct credentials to the underlying systems — only the Guardrail's execution gateway does.

```text
                 ┌───────────────────────┐
                 │ Claude / OpenRouter /  │
                 │ any tool-calling agent │
                 └───────────┬────────────┘
                              │ proposes a tool call
                              ▼
                 ┌────────────────────────┐
                 │      API Gateway        │  ← public HTTPS entry point
                 └───────────┬─────────────┘
                              ▼
                 ┌────────────────────────────┐
                 │   AWS Lambda (FastAPI)      │
                 │  ─────────────────────────  │
                 │  1. Normalize tool → action  │
                 │  2. Evaluate policy-as-code  │
                 │  3. Write audit record       │
                 └───┬───────────┬──────────┬───┘
                     ▼           ▼          ▼
                  BLOCK    REQUIRE_HITL   LOG_AND_ALLOW
                     │           │             │
                    403     Human review    Execute via
                          (dashboard Approve/  sandboxed
                           Reject) → execute    adapter
                     │           │             │
                     └─────┬─────┴──────┬──────┘
                           ▼             ▼
                       DynamoDB      Tool adapters
                    (audit + HITL)  (DB / email / file)
```

---

## 3. Core Security Logic

### Action normalization
Raw tool names are mapped to canonical **action types**, so an agent can't dodge policy by renaming a tool:

```text
db_delete, execute_sql, bulk_delete   →  database.delete
send_email                            →  email.send
read_file                             →  file.read
```

### Default deny
```yaml
default_action: block
```
Any action with no matching policy rule is blocked automatically. Nothing is implicitly trusted.

### Most-restrictive-rule-wins
If multiple policy rules match the same action, the engine doesn't rely on rule order in the YAML — it evaluates **all** matches and returns the most restrictive verdict:

```text
BLOCK  >  REQUIRE_HITL  >  LOG_AND_ALLOW
```

### Fail-closed auditing
For `block` and `require_hitl` verdicts, a failure to write the audit record blocks the action rather than allowing it to slip through. Auditability is treated as a security control, not a nice-to-have.

---

## 4. Policy Rules (deployed, policy-as-code)

Policies live in `policies/policy.yaml`, shipped through Git → CI/CD → `sam deploy`. They are **not** editable from the dashboard — the dashboard only displays what Lambda currently has loaded, via `GET /v1/policies`.

| Rule | Condition | Verdict |
|---|---|---|
| `block-bulk-delete` | `database.delete`, `record_count > 100` | BLOCK |
| `allow-small-delete` | `database.delete`, `record_count <= 100` | LOG_AND_ALLOW |
| `hitl-external-email` | `email.send`, `recipient_domain` not in `mycompany.com` | REQUIRE_HITL |
| `allow-internal-email` | `email.send`, `recipient_domain` in `mycompany.com` | LOG_AND_ALLOW |
| `log-confidential-read` | `file.read`, confidential path | LOG_AND_ALLOW (flagged) |
| `allow-normal-read` | `file.read`, normal path | LOG_AND_ALLOW |
| *(no match)* | any unrecognized action | **BLOCK** (default deny) |

---

## 5. Features

- **Execution gateway** (`POST /v1/actions/execute`) — the real enforcement boundary. Evaluates, audits, and only then executes.
- **Dry-run evaluation** (`POST /v1/actions/evaluate`) — see the verdict without executing, for safe testing.
- **Human-in-the-loop approvals** — pending actions persist in DynamoDB (`PENDING` → `APPROVED`/`REJECTED`/`EXPIRED`), with `approved_by`/`rejected_by` recorded. Double-resolving an already-resolved request correctly returns `409`.
- **Sandboxed tool adapters** — an in-memory demo DB (1,000 fake users, 50 sessions), a captured (non-sending) email outbox, and a jailed file-read directory with path-traversal protection via basename stripping. These prove the enforcement boundary actually executes/blocks real actions, without touching production systems.
- **Full audit trail** — every evaluated action is recorded with `agent_id`, `tool_name`, `action_type`, `verdict`, `matched_rule_ids`, `reason`, `timestamp`, `arguments`, and `executed`. DynamoDB is keyed as `agent_id` (partition) + `timestamp#request_id` (sort), so history is queryable per agent, in order.
- **Multi-agent observability** — every action carries an `agent_id`, so multiple independent agents (e.g. `openrouter-agent`, `claude-agent`, `console-test`) all show up filterable in the same audit trail — as long as they route through the Guardrail's API.
- **Real LLM integration** — a Dockerized OpenRouter agent (`gpt-oss-20b:free`) proposes real tool calls that are intercepted and evaluated by the live AWS endpoint, not a simulator.
- **Management console** (S3-hosted static dashboard) — Overview, Policies (live from the API), Approvals (HITL queue with Approve/Reject), Audit Log (filterable by agent), and a Test Console for `/evaluate` and `/execute`.
- **CI/CD** — GitHub Actions runs tests, assumes an AWS IAM role via **OIDC** (no long-lived AWS keys stored in GitHub), then runs `sam build && sam deploy`, followed by a health check and automatic S3 dashboard upload.

---

## 6. AWS Services Used — and why

| Service | Role | Why it was chosen |
|---|---|---|
| **API Gateway (HTTP API)** | Public HTTPS entry point for agents and the dashboard | Decouples the public interface from Lambda; handles routing without managing a server |
| **AWS Lambda** | Runs the FastAPI app — normalizer, policy engine, HITL logic, audit logic, tool adapters | Serverless: no infrastructure to manage, scales automatically, and integrates natively with API Gateway. A fit for short, stateless policy-evaluation requests |
| **DynamoDB — `guardrail_audit_log`** | Permanent audit trail | Serverless, low-latency key-value store; partition/sort key design (`agent_id` + `timestamp#request_id`) directly supports per-agent, time-ordered queries |
| **DynamoDB — `guardrail_hitl_requests`** | Pending/resolved human approvals | Makes HITL *stateful* — approvals persist and survive restarts, instead of `require_hitl` being a verdict the system immediately forgets |
| **IAM (execution role + GitHub OIDC role)** | Lambda's DynamoDB access; GitHub Actions' deploy permissions | Least-privilege execution for Lambda; OIDC lets GitHub Actions assume an AWS role for deployment **without** storing static AWS access keys in the repo/CI secrets |
| **CloudFormation / AWS SAM** | Infrastructure as code (`template.yaml` defines Lambda, API Gateway, both DynamoDB tables, IAM) | Infrastructure is reproducible and version-controlled, not manually clicked together in the console — a prerequisite for real CI/CD |
| **Amazon S3** | Hosts the static management dashboard (`index.html`) | Cheapest, simplest way to serve a static SPA; integrated into the CI/CD pipeline so the dashboard redeploys automatically after each backend deploy |
| **CloudWatch** | Lambda/API Gateway logs, application logging via Python's logger | Operational visibility into requests and errors. *(Note: this is logging/observability — no CloudWatch alarms are configured yet; see Limitations.)* |

**Non-AWS but part of the deployment story:** GitHub Actions orchestrates the pipeline: `git push → pytest → AWS OIDC → assume IAM role → sam build → sam deploy → health check → S3 dashboard upload`.

---

## 7. How Changes Get Deployed

Editing `template.yaml` or the application code **does not** change the live AWS stack by itself — it's just a file on disk until a deploy is run:

```bash
sam build
sam deploy
```

This packages the code, diffs it against the current CloudFormation stack, and updates only what changed. Nothing in production changes until this completes (or until the CI/CD pipeline runs it automatically on push).

---

## 8. Verified Test Cases

The system has been exercised end-to-end against the **live AWS endpoint**, both via direct API calls and via a real OpenRouter LLM agent:

| # | Scenario | Result |
|---|---|---|
| 1 | Delete 500 users | `403 BLOCK` (`block-bulk-delete`) |
| 2 | Delete 5 sessions | `200 log_and_allow`, executed |
| 3 | Email to `gmail.com` | `require_hitl`, `PENDING` → resolved via dashboard |
| 4 | Email to `mycompany.com` | `200 log_and_allow`, executed |
| 5 | Read `confidential_report.txt` | `log_and_allow`, logged (multiple-rule match) |
| 6 | Unknown tool (`transfer_money`) | `403 BLOCK` — default deny |
| 7 | Renamed tool (`execute_sql`, `bulk_delete`) | Still normalizes to `database.delete` → same policy applies |
| 8 | HITL double-approve | Second approval returns `409` |
| 9 | HITL rejection | `REJECTED`, `executed: false` |
| 10 | Path traversal (`../../etc/passwd`) | Blocked by basename stripping in the file adapter |

**Explicitly out of scope / future work** (not claimed as done): oversized-payload protection, multi-tenant audit isolation, per-agent rate limiting.

---

## 9. Production Readiness

**Overall assessment: strong prototype / production-track MVP — not yet enterprise-production-final.**

**What's genuinely production-oriented:**
- Real cloud deployment (not localhost) across API Gateway, Lambda, DynamoDB, S3
- Infrastructure as code (SAM/CloudFormation) — reproducible, not console-clicked
- CI/CD via GitHub Actions with OIDC (no long-lived AWS credentials)
- Default-deny policy engine with most-restrictive-wins semantics
- Fail-closed audit logging for dangerous verdicts
- Persistent, stateful HITL approvals
- A genuine execution boundary — the agent cannot reach the tool adapters directly

**What's intentionally not production-final yet:**
- **Authentication** — the dashboard currently uses a shared API key entered client-side, visible to anyone with browser devtools on that page. Production hardening would move to Cognito + JWT with an API Gateway JWT authorizer.
- **Dashboard hosting** — currently a public S3 static website (Block Public Access disabled). A hardened version would use a private S3 bucket behind CloudFront.
- **HITL audit continuity** — approving/rejecting a HITL request should also write its own audit event (`HITL_APPROVED`/`HITL_REJECTED`), preserving the original `require_hitl` record rather than only updating status.
- **RBAC / multi-tenancy** — agents are identified by `agent_id`, but there's no organization/tenant/role/scope model yet.
- **Rate limiting** — no per-agent throttling yet.
- **Payload-size limits** — no protection against oversized requests yet.
- **IAM least privilege** — the GitHub deployment role was broadened to get CI/CD working; it should be tightened.
- **Tool adapters are sandboxed demo targets** (in-memory DB, captured email outbox, jailed file directory) by design — not connected to real production systems.

---

## 10. Repository Structure (as built)

```text
action-guardrail/
├── app/
│   └── main.py              # FastAPI app: normalizer, policy engine, HITL, audit, adapters
├── policies/
│   └── policy.yaml          # policy-as-code rules + default_action
├── agent/
│   └── openrouter_agent.py  # real LLM tool-calling agent, targets the live Guardrail URL
├── template.yaml            # SAM/CloudFormation: Lambda, API Gateway, DynamoDB x2, IAM
├── requirements.txt
├── Dockerfile                # containerized agent for reproducible demo runs
└── .github/workflows/        # CI/CD: tests → OIDC → sam build/deploy → health check → S3 upload
```
