import asyncio
import pytest
from fastapi import HTTPException

import api


def test_max_webhook_secret_guard(monkeypatch):
    monkeypatch.setattr(api, "MAX_WEBHOOK_SECRET", "s3cr3t")

    called = {"ok": 0}

    async def _proc(payload):
        called["ok"] += 1

    monkeypatch.setattr(api, "process_max_update", _proc)

    with pytest.raises(HTTPException):
        asyncio.run(api.max_webhook({"update_type": "message_created"}, x_max_bot_api_secret=None))

    good = asyncio.run(
        api.max_webhook(
            {"update_type": "message_created", "message": {"sender": {"user_id": 1}, "recipient": {"chat_id": 1}, "body": {"text": "x"}}},
            x_max_bot_api_secret="s3cr3t",
        )
    )
    assert getattr(good, "status_code", 0) == 200
    assert called["ok"] == 1
