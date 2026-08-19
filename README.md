# Action Guardrail — Console

A production-style management console for the Action Guardrail enforcement gateway. Monitor agents, review HITL approvals, inspect audit trails, and test policy decisions.

## Quick Start

### 1. Local Setup

```bash
cp config.example.js config.js
# Edit config.js — set your real API key
```

Open `index.html` in a browser. The console auto-connects using `config.js`.

### 2. Deploy to S3

```bash
chmod +x deploy.sh
./deploy.sh <your-unique-bucket-name> us-east-1
```

The script uploads `index.html` and `config.js` to S3 and enables static website hosting.

## Files

| File | Purpose |
|---|---|
| `index.html` | Single-page console (HTML + CSS + JS, no build step) |
| `config.js` | Runtime config with API URL and key (gitignored) |
| `config.example.js` | Template — copy to `config.js` and fill in your key |
| `deploy.sh` | S3 deployment script |

## Configuration

`config.js`:

```js
window.GUARDRAIL_CONFIG = {
  apiUrl: "https://your-api-id.execute-api.us-east-1.amazonaws.com",
  apiKey: "your-api-key-here"
};
```

If `config.js` is missing or contains `REPLACE_ME`, the console shows the connection gate for manual entry.

## Security Limitation

This is a static client-side dashboard. The API key is held in browser `sessionStorage` and can be inspected by the browser owner. **This is a demo/evaluation security model.**

For production, use:
- Cognito / OIDC authentication
- A backend-for-frontend (BFF) pattern
- CloudFront + WAF in front of S3

## Console Features

- **Overview** — Health, rules loaded, default action, pending HITL count, verdict distribution, recent actions
- **Approvals** — Review pending HITL requests with full arguments, approve (with execution), or reject
- **Audit Log** — Filter by agent, tool, action type, verdict; click rows for detail view
- **Policies** — View deployed policy rules (read-only, deployed via Git → CI/CD → SAM)
- **Test Console** — Quick scenario buttons or custom action testing against `/v1/actions/evaluate` or `/v1/actions/execute`

## Backend

The backend is an AWS Lambda (FastAPI + Mangum) with:
- DynamoDB for audit log and HITL requests
- API Gateway with API key authentication
- Policy engine evaluating YAML rules

**Do not bypass the guardrail.** The agent calls `/v1/actions/execute`, not tool adapters directly.
