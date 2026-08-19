from fastapi import FastAPI, HTTPException, Depends
from mangum import Mangum
from app.core.auth import require_api_key
from app.core.engine import PolicyEngine
from app.core.models import ActionRequest, Decision
from app.core.normalizer import normalize
from app.core.audit import write_audit, query_by_agent, query_recent, AuditWriteError
from app.core.hitl import create_hitl_request, list_pending, resolve, get_hitl_request
from app.adapters.tools import dispatch, ToolExecutionError
from app.core.logger import get_logger
import os, traceback

log = get_logger()
app = FastAPI(title="Action Guardrail", version="3.0.0")
engine = PolicyEngine(os.getenv("POLICY_PATH", "policies/policy.yaml"))
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

FAIL_CLOSED_VERDICTS = {"block", "require_hitl"}   # audit MUST persist for these or the action does not proceed

@app.get("/health")
def health():
    return {"status": "ok", "dry_run": DRY_RUN, "rules_loaded": len(engine.rules),
            "default_action": engine.default_action}

@app.get("/v1/policies", dependencies=[Depends(require_api_key)])
def get_policies():
    return {"default_action": engine.default_action, "rules": engine.rules}
    # Note: intentionally no /reload endpoint. Policy changes ship via git → CI → sam deploy,
    # i.e. policy-as-code with a version history, not a live-mutable runtime endpoint.

@app.post("/v1/actions/evaluate", response_model=Decision, dependencies=[Depends(require_api_key)])
def evaluate_only(action: ActionRequest):
    """Evaluate policy WITHOUT executing anything — useful for agent self-checks / dry runs."""
    action = normalize(action)
    return engine.evaluate(action)

@app.post("/v1/actions/execute", dependencies=[Depends(require_api_key)])
def execute_action(action: ActionRequest):
    """The real enforcement boundary. The agent NEVER calls tool adapters directly —
    only this endpoint does, and only after a policy check passes."""
    action = normalize(action)
    try:
        decision = engine.evaluate(action)
    except Exception as e:
        log.error("evaluation_error", extra={"error": str(e), "trace": traceback.format_exc()})
        raise HTTPException(status_code=500, detail="Policy evaluation failed") from e

    if DRY_RUN:
        log.info("dry_run_decision", extra=decision.model_dump())
        return {"dry_run": True, "would_be_verdict": decision.verdict,
                "matched_rule_ids": decision.matched_rule_ids, "reason": decision.reason}

    if decision.verdict in FAIL_CLOSED_VERDICTS:
        try:
            write_audit(decision, executed=False)
        except AuditWriteError as e:
            log.error("audit_write_failed_fail_closed", extra={"error": str(e), "request_id": decision.request_id})
            raise HTTPException(status_code=503,
                                 detail="Audit system unavailable — action blocked (fail-closed policy)") from e
    else:
        try:
            write_audit(decision, executed=False)   # updated to executed=True below once it actually runs
        except AuditWriteError as e:
            log.error("audit_write_failed_logged_only", extra={"error": str(e), "request_id": decision.request_id})
            # log_and_allow proceeds even if audit write fails, but this is loud in CloudWatch
            # and should trigger a CloudWatch alarm in a real deployment.

    log.info("action_evaluated", extra={"request_id": decision.request_id, "verdict": decision.verdict,
                                         "matched_rule_ids": decision.matched_rule_ids})

    if decision.verdict == "block":
        raise HTTPException(status_code=403, detail={"verdict": "block", "reason": decision.reason,
                                                       "matched_rule_ids": decision.matched_rule_ids})

    if decision.verdict == "require_hitl":
        hitl = create_hitl_request(decision)
        return {"verdict": "require_hitl", "hitl_id": hitl["hitl_id"], "status": "PENDING",
                "expires_at": hitl["expires_at"], "reason": decision.reason}

    # log_and_allow → actually execute via the adapter, then update the audit record
    try:
        result = dispatch(decision.action_type, decision.arguments)
    except ToolExecutionError as e:
        log.error("tool_execution_failed", extra={"error": str(e), "request_id": decision.request_id})
        raise HTTPException(status_code=502, detail=f"Tool execution failed: {e}") from e

    try:
        write_audit(decision, executed=True, execution_result=result)
    except AuditWriteError as e:
        log.error("post_execution_audit_failed", extra={"error": str(e), "request_id": decision.request_id})

    return {"verdict": "log_and_allow", "executed": True, "result": result, "reason": decision.reason}

@app.get("/v1/hitl", dependencies=[Depends(require_api_key)])
def hitl_pending():
    return {"pending": list_pending()}

@app.post("/v1/hitl/{hitl_id}/approve", dependencies=[Depends(require_api_key)])
def hitl_approve(hitl_id: str, approved_by: str = "reviewer"):
    try:
        item = resolve(hitl_id, "APPROVED", approved_by)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    try:
        result = dispatch(item["action_type"], eval(item["arguments"]) if isinstance(item["arguments"], str) else item["arguments"])
    except ToolExecutionError as e:
        raise HTTPException(status_code=502, detail=f"Tool execution failed after approval: {e}")
    return {"status": "APPROVED", "executed": True, "result": result}

@app.post("/v1/hitl/{hitl_id}/reject", dependencies=[Depends(require_api_key)])
def hitl_reject(hitl_id: str, rejected_by: str = "reviewer"):
    try:
        resolve(hitl_id, "REJECTED", rejected_by)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"status": "REJECTED", "executed": False}

@app.get("/v1/audit", dependencies=[Depends(require_api_key)])
def audit(agent_id: str | None = None, limit: int = 50):
    return {"items": query_by_agent(agent_id, limit) if agent_id else query_recent(limit)}

handler = Mangum(app)
