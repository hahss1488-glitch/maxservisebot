from fastapi.testclient import TestClient

import api


def test_max_webhook_secret_guard(monkeypatch):
    monkeypatch.setattr(api, "MAX_WEBHOOK_SECRET", "s3cr3t")

    called = {"ok": 0}

    async def _proc(payload):
        called["ok"] += 1

    monkeypatch.setattr(api, "process_max_update", _proc)

    client = TestClient(api.app)

    bad = client.post("/max/webhook", json={"update_type": "message_created"})
    assert bad.status_code == 401

    good = client.post(
        "/max/webhook",
        headers={"X-Max-Bot-Api-Secret": "s3cr3t"},
        json={"update_type": "message_created", "message": {"sender": {"user_id": 1}, "recipient": {"chat_id": 1}, "body": {"text": "x"}}},
    )
    assert good.status_code == 200
    assert called["ok"] == 1
