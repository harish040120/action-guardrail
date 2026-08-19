from app.adapters.tools import execute_db_delete, execute_send_email, execute_read_file, _DEMO_DB

def test_db_delete_actually_removes_rows():
    before = len(_DEMO_DB["sessions"])
    result = execute_db_delete({"table": "sessions", "record_count": 5})
    assert result["deleted"] == 5
    assert len(_DEMO_DB["sessions"]) == before - 5

def test_email_actually_queued():
    result = execute_send_email({"recipient_domain": "mycompany.com", "subject": "hi"})
    assert result["outbox_size"] >= 1

def test_confidential_file_actually_read():
    result = execute_read_file({"path": "confidential_report.txt"})
    assert "confidential" in result["content_preview"].lower()
