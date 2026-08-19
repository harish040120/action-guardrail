import pytest
from app.core.engine import PolicyEngine
from app.core.models import ActionRequest

engine = PolicyEngine("policies/policy.yaml")

def act(tool, args, action_type):
    return ActionRequest(tool_name=tool, arguments=args, context={"action_type": action_type}, agent_id="a1")

def test_bulk_delete_blocked():
    d = engine.evaluate(act("db_delete", {"record_count": 500}, "database.delete"))
    assert d.verdict == "block" and "block-bulk-delete" in d.matched_rule_ids

def test_alternate_tool_name_still_blocked():
    # "execute_sql" is a different raw tool name mapped to the same action_type
    d = engine.evaluate(act("execute_sql", {"record_count": 500}, "database.delete"))
    assert d.verdict == "block"

def test_small_delete_allowed():
    d = engine.evaluate(act("db_delete", {"record_count": 5}, "database.delete"))
    assert d.verdict == "log_and_allow"

def test_external_email_requires_hitl():
    d = engine.evaluate(act("send_email", {"recipient_domain": "gmail.com"}, "email.send"))
    assert d.verdict == "require_hitl"

def test_internal_email_allowed():
    d = engine.evaluate(act("send_email", {"recipient_domain": "mycompany.com"}, "email.send"))
    assert d.verdict == "log_and_allow"

def test_confidential_read_logged():
    d = engine.evaluate(act("read_file", {"path": "/data/confidential/x.csv"}, "file.read"))
    assert d.verdict == "log_and_allow" and "log-confidential-read" in d.matched_rule_ids

def test_unknown_tool_defaults_to_block():
    d = engine.evaluate(act("transfer_money", {"amount": 1}, "finance.transfer"))
    assert d.verdict == "block"
    assert d.matched_rule_ids == []

def test_most_restrictive_wins_when_multiple_rules_match(tmp_path):
    p = tmp_path / "p.yaml"
    p.write_text("""
version: 2
default_action: block
rules:
  - id: allow-all-delete
    description: allow
    action_type: database.delete
    tool_names: [db_delete]
    conditions: []
    action: log_and_allow
  - id: block-big-delete
    description: block big
    action_type: database.delete
    tool_names: [db_delete]
    conditions:
      - field: arguments.record_count
        operator: greater_than
        value: 100
    action: block
""")
    eng = PolicyEngine(str(p))
    d = eng.evaluate(act("db_delete", {"record_count": 500}, "database.delete"))
    assert d.verdict == "block"   # even though a log_and_allow rule also matched

def test_empty_policy_refuses_to_load(tmp_path):
    p = tmp_path / "empty.yaml"
    p.write_text("version: 2\nrules: []\n")
    with pytest.raises(ValueError):
        PolicyEngine(str(p))

def test_duplicate_rule_ids_rejected(tmp_path):
    p = tmp_path / "dup.yaml"
    p.write_text("""
version: 2
default_action: block
rules:
  - {id: x, description: d, tool_names: [t], conditions: [], action: block}
  - {id: x, description: d2, tool_names: [t2], conditions: [], action: block}
""")
    with pytest.raises(ValueError):
        PolicyEngine(str(p))
