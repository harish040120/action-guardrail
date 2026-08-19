#!/usr/bin/env bash
# Deploys the Action Guardrail console (index.html + config.js) to S3 as a public static website.
# Run this from your own machine (the one with `aws` configured) — not from this sandbox.
#
# Usage:
#   ./deploy.sh <globally-unique-bucket-name> [aws-region]
#
# Example:
#   ./deploy.sh action-guardrail-console-alucard us-east-1

set -euo pipefail

BUCKET="${1:?Usage: ./deploy.sh <bucket-name> [region]}"
REGION="${2:-us-east-1}"

echo "==> Validating configuration"
if [ ! -f index.html ]; then
  echo "ERROR: index.html not found in current directory." >&2
  exit 1
fi
if [ ! -f config.js ]; then
  echo "ERROR: config.js not found. Copy config.example.js to config.js and set your API key." >&2
  exit 1
fi
if grep -q "REPLACE_ME" config.js; then
  echo "WARNING: config.js still contains REPLACE_ME. Ensure the API key is set before deploying." >&2
fi

echo "==> Creating bucket s3://$BUCKET in $REGION"
if [ "$REGION" = "us-east-1" ]; then
  aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" 2>/dev/null || echo "   (bucket may already exist)"
else
  aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" \
    --create-bucket-configuration LocationConstraint="$REGION" 2>/dev/null || echo "   (bucket may already exist)"
fi

echo "==> Disabling Block Public Access on this bucket (required for a public static site)"
aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration \
  BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false

echo "==> Enabling static website hosting"
aws s3 website "s3://$BUCKET" --index-document index.html

echo "==> Applying public-read bucket policy"
cat > /tmp/bucket-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "PublicReadGetObject",
    "Effect": "Allow",
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::$BUCKET/*"
  }]
}
EOF
aws s3api put-bucket-policy --bucket "$BUCKET" --policy file:///tmp/bucket-policy.json

echo "==> Uploading index.html"
aws s3 cp index.html "s3://$BUCKET/index.html" --content-type "text/html" --cache-control "no-cache"

echo "==> Uploading config.js"
aws s3 cp config.js "s3://$BUCKET/config.js" --content-type "application/javascript" --cache-control "no-cache"

ENDPOINT="http://$BUCKET.s3-website-$REGION.amazonaws.com"
if [ "$REGION" != "us-east-1" ]; then
  ENDPOINT="http://$BUCKET.s3-website.$REGION.amazonaws.com"
fi

echo ""
echo "==> Done. Your console is live at:"
echo "    $ENDPOINT"
echo ""
echo "Optional polish (skip if you're tight on time): put a CloudFront distribution"
echo "in front of this bucket for HTTPS + a nicer domain. Not required for a working demo."
