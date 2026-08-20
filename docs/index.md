# Action Guardrail

**An agent-action enforcement gateway deployed on AWS, with a dashboard for monitoring, policy inspection, HITL approval, audit, and testing.**

---

## The Problem

An LLM can produce a perfectly acceptable response but still ask a tool to perform a dangerous action.

```text
User: Delete all 500 users.

LLM: db_delete(table="users", record_count=500)
```

A normal LLM guardrail that only checks text may see nothing wrong. Your system instead checks the **action immediately before execution**.

---

## What You Have Built

An **enforcement gateway for AI agents**. Instead of allowing an LLM to directly execute tools, every tool action is routed through the Guardrail API.

```text
             ACTION GUARDRAIL
                    │
        ┌───────────┴───────────┐
        │                       │
   ENFORCEMENT              OBSERVABILITY
        │                       │
   Policy Engine             Dashboard
        │                       │
   ┌────┼────┐             ┌────┼────┐
 BLOCK  HITL ALLOW        Audit Agents Policies
   │     │    │
   └─────┴────┘
         │
    Tool Execution
```

**The agent can propose an action, but it cannot execute the action unless the Guardrail allows it.**

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML / JavaScript, S3 Static Website |
| API / Backend | FastAPI, Python 3.11, Uvicorn, Mangum |
| AI | OpenRouter, gpt-oss-20b:free, Tool Calling |
| Guardrail | Policy Engine, YAML Policy-as-Code, Action Normalizer, Default-Deny, Most-Restrictive-Wins, HITL, Audit, Tool Adapters |
| AWS | API Gateway, Lambda, DynamoDB, IAM, CloudFormation, SAM, S3 |
| DevOps | GitHub, GitHub Actions, GitHub OIDC |

---

## Quick Start

1. **Deploy the backend** — `sam deploy` (see [Deployment](deployment.md))
2. **Deploy the dashboard** — `./deploy.sh <bucket-name>` (see [Deployment](deployment.md))
3. **Open the dashboard** — enter your API URL and key
4. **Test an action** — use the Test Console or run the OpenRouter agent

---

## Key Features

- **Default-Deny** — unknown actions are blocked, not silently allowed
- **Most-Restrictive-Wins** — if multiple policies match, the strictest verdict applies
- **Human-in-the-Loop** — sensitive actions require human approval before execution
- **Multi-Agent** — any agent (Claude, OpenRouter, custom) can route through the same gateway
- **Full Audit** — every action is recorded in DynamoDB with agent, tool, verdict, and arguments
- **Policy-as-Code** — policies are YAML files deployed via Git → CI/CD → SAM
