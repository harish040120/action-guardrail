# Policies

## Policy-as-Code

Policies are defined in `policies/policy.yaml` and deployed via Git → CI/CD → SAM. They are **not** editable at runtime.

The dashboard reads policies from:

```
GET /v1/policies
```

---

## Current Rules

### 1. Block Bulk Delete

```yaml
id: block-bulk-delete
description: "Block any DB delete where record count exceeds 100"
action_type: database.delete
tool_names: [db_delete, execute_sql, bulk_delete]
conditions:
  - field: arguments.record_count
    operator: greater_than
    value: 100
action: block
severity: high
```

Result:

```text
db_delete(users, 500)  →  BLOCK
```

### 2. Allow Small Delete

```yaml
id: allow-small-delete
description: "Allow DB deletes of 100 records or fewer"
action_type: database.delete
tool_names: [db_delete, execute_sql, bulk_delete]
conditions:
  - field: arguments.record_count
    operator: less_than
    value: 101
action: log_and_allow
severity: low
```

Result:

```text
db_delete(sessions, 5)  →  ALLOW + EXECUTE
```

### 3. External Email → HITL

```yaml
id: hitl-external-email
description: "Require human approval for email to an external domain"
action_type: email.send
tool_names: [send_email]
conditions:
  - field: arguments.recipient_domain
    operator: not_in
    value: ["mycompany.com"]
action: require_hitl
severity: medium
```

Result:

```text
send_email(gmail.com)  →  HITL
```

### 4. Internal Email → Allow

```yaml
id: allow-internal-email
description: "Allow email to internal domain"
action_type: email.send
tool_names: [send_email]
conditions:
  - field: arguments.recipient_domain
    operator: in
    value: ["mycompany.com"]
action: log_and_allow
severity: none
```

Result:

```text
send_email(mycompany.com)  →  ALLOW
```

### 5. Confidential File Read

```yaml
id: log-confidential-read
description: "Log and allow reads of paths containing 'confidential'"
action_type: file.read
tool_names: [read_file]
conditions:
  - field: arguments.path
    operator: contains
    value: "confidential"
action: log_and_allow
severity: low
```

### 6. Normal File Read

```yaml
id: allow-normal-read
description: "Allow ordinary file reads"
action_type: file.read
tool_names: [read_file]
conditions: []
action: log_and_allow
severity: none
```

---

## Changing Policies

Edit `policies/policy.yaml`, then:

```text
git commit → git push → GitHub Actions → sam build → sam deploy
```

The Lambda gets the updated policy. The dashboard reflects the change on next refresh.
