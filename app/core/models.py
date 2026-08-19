from pydantic import BaseModel
from typing import Any, Literal, Optional
from datetime import datetime, timezone
import uuid

class ActionRequest(BaseModel):
    tool_name: str                       # raw tool name the agent asked for, e.g. "db_delete"
    arguments: dict[str, Any] = {}        # tool arguments
    context: dict[str, Any] = {}          # e.g. {"environment": "production"}
    agent_id: str = "unknown"
    request_id: Optional[str] = None

    def model_post_init(self, __context):
        if not self.request_id:
            self.request_id = str(uuid.uuid4())

    def as_policy_doc(self) -> dict:
        """Flattened document the policy engine evaluates dotted-path fields against."""
        return {
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "context": self.context,
            "agent": {"id": self.agent_id},
        }

class Decision(BaseModel):
    request_id: str
    tool_name: str
    action_type: Optional[str]
    verdict: Literal["block", "require_hitl", "log_and_allow"]
    matched_rule_ids: list[str]
    reason: str
    timestamp: str
    agent_id: str
    arguments: dict[str, Any]

    @staticmethod
    def now():
        return datetime.now(timezone.utc).isoformat()
