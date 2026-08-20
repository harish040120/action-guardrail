# Deployment

## Backend (AWS)

### Prerequisites

- AWS CLI configured
- AWS SAM CLI installed
- Python 3.11

### Deploy

```bash
sam build --use-container
sam deploy --guided
```

SAM will prompt for:

- Stack name
- Region
- Capabilities

After deployment, note the API Gateway URL from the output.

### Verify

```bash
curl https://<your-api-id>.execute-api.us-east-1.amazonaws.com/health
```

---

## Dashboard (S3 Static Website)

### Prerequisites

- AWS CLI configured
- A globally unique S3 bucket name

### Deploy

```bash
chmod +x deploy.sh
./deploy.sh <your-unique-bucket-name> us-east-1
```

The script:

1. Creates the S3 bucket
2. Disables Block Public Access
3. Enables static website hosting
4. Applies public-read bucket policy
5. Uploads `index.html`

### Access

```
http://<bucket-name>.s3-website-us-east-1.amazonaws.com
```

### Optional: CloudFront

Put a CloudFront distribution in front of the S3 bucket for HTTPS and a custom domain.

---

## CI/CD (GitHub Actions)

The pipeline runs on `git push` to `main`:

```text
git push
   ↓
GitHub Actions
   ↓
pytest
   ↓
AWS OIDC (no long-lived keys)
   ↓
sam build --use-container
   ↓
sam deploy
   ↓
curl /health (verify)
```

### Setup

1. Create IAM role `guardrail-github-actions-role` with OIDC trust (see `aws/github-oidc-trust.json`)
2. Add the role ARN to `samconfig.toml`
3. Configure GitHub repository secrets if needed

---

## Policy Changes

Edit `policies/policy.yaml`, then:

```bash
git add policies/policy.yaml
git commit -m "Update policy: ..."
git push
```

GitHub Actions deploys the new policy to Lambda.

---

## Files

| File | Purpose |
|---|---|
| `template.yaml` | SAM/CloudFormation template |
| `samconfig.toml` | SAM deploy config |
| `app/` | FastAPI application |
| `policies/policy.yaml` | Policy rules |
| `agent/openrouter_agent.py` | OpenRouter agent |
| `index.html` | Dashboard |
| `deploy.sh` | S3 deployment script |
| `.github/workflows/ci-cd.yml` | CI/CD pipeline |
