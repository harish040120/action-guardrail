from fastapi import Header, HTTPException
import os, hmac

API_KEY = os.environ["GUARDRAIL_API_KEY"]     # set via SAM parameter / Secrets Manager, never hardcoded

def require_api_key(x_api_key: str = Header(...)):
    if not hmac.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
