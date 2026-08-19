from app.core.models import ActionRequest

# One place that maps every raw tool name an agent might invoke to a normalized
# governance category. Add new tool names here — policy rules key off action_type,
# so renamed/aliased tools are covered automatically without touching policy.yaml.
TOOL_TO_ACTION_TYPE = {
    "db_delete": "database.delete",
    "execute_sql": "database.delete",     # closes the "rename the tool" bypass
    "bulk_delete": "database.delete",
    "send_email": "email.send",
    "read_file": "file.read",
}

def normalize(action: ActionRequest) -> ActionRequest:
    action_type = TOOL_TO_ACTION_TYPE.get(action.tool_name, "unknown")
    action.context = {**action.context, "action_type": action_type}
    return action
