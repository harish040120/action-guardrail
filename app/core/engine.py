import yaml
from app.core.models import ActionRequest, Decision

OPERATORS = {
    "equals": lambda a, b: a == b,
    "not_equals": lambda a, b: a != b,
    "greater_than": lambda a, b: a is not None and a > b,
    "less_than": lambda a, b: a is not None and a < b,
    "contains": lambda a, b: b in a if a is not None else False,
    "not_contains": lambda a, b: b not in a if a is not None else True,
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
}

VERDICT_RANK = {"block": 3, "require_hitl": 2, "log_and_allow": 1}

def resolve_path(doc: dict, path: str):
    node = doc
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node

class PolicyEngine:
    def __init__(self, policy_path: str = "policies/policy.yaml"):
        self.policy_path = policy_path
        self.rules = []
        self.default_action = "block"
        self.load()

    def load(self):
        with open(self.policy_path) as f:
            data = yaml.safe_load(f)
        if not data or not data.get("rules"):
            raise ValueError(f"Policy file {self.policy_path} has no rules — refusing to start")
        self.default_action = data.get("default_action", "block")
        if self.default_action not in VERDICT_RANK:
            raise ValueError(f"Invalid default_action: {self.default_action}")
        seen_ids = set()
        for rule in data["rules"]:
            if rule["id"] in seen_ids:
                raise ValueError(f"Duplicate rule id: {rule['id']}")
            seen_ids.add(rule["id"])
        self.rules = data["rules"]

    def _rule_matches(self, rule: dict, action: ActionRequest, doc: dict) -> bool:
        tool_ok = action.tool_name in rule.get("tool_names", [])
        type_ok = rule.get("action_type") and rule["action_type"] == action.context.get("action_type")
        if not (tool_ok or type_ok):
            return False
        for cond in rule.get("conditions", []):
            field_val = resolve_path(doc, cond["field"])
            op = OPERATORS.get(cond["operator"])
            if op is None:
                raise ValueError(f"Unknown operator: {cond['operator']}")
            if not op(field_val, cond["value"]):
                return False
        return True

    def evaluate(self, action: ActionRequest) -> Decision:
        doc = action.as_policy_doc()
        matches = [r for r in self.rules if self._rule_matches(r, action, doc)]

        if not matches:
            return Decision(
                request_id=action.request_id, tool_name=action.tool_name,
                action_type=action.context.get("action_type"),
                verdict=self.default_action, matched_rule_ids=[],
                reason=f"No policy rule matched — default_action '{self.default_action}' applied",
                timestamp=Decision.now(), agent_id=action.agent_id, arguments=action.arguments,
            )

        # Most-restrictive-wins across ALL matching rules, not first-match.
        winning = max(matches, key=lambda r: VERDICT_RANK[r["action"]])
        top_rank = VERDICT_RANK[winning["action"]]
        winners = [r for r in matches if VERDICT_RANK[r["action"]] == top_rank]

        return Decision(
            request_id=action.request_id, tool_name=action.tool_name,
            action_type=action.context.get("action_type"),
            verdict=winning["action"],
            matched_rule_ids=[r["id"] for r in winners],
            reason="; ".join(r["description"] for r in winners),
            timestamp=Decision.now(), agent_id=action.agent_id, arguments=action.arguments,
        )
