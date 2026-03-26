import asyncio

import bot
from max_runtime import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    MaxBot,
    MaxCallbackQuery,
    MaxIncomingMessage,
    MaxUser,
    _serialize_markup,
)


class DummyClient:
    def __init__(self):
        self.sent = []
        self.answered = []

    def send_message(self, **kwargs):
        self.sent.append(kwargs)
        return {"message_id": 123}

    def answer_callback(self, callback_id: str, **kwargs):
        self.answered.append((callback_id, kwargs))

    def upload_bytes(self, content: bytes, filename: str = "file.bin", mime: str = "application/octet-stream"):
        return "token-1"

    def edit_message(self, **kwargs):
        return {}

    def delete_message(self, **kwargs):
        return {}


def test_resolve_response_target_prefers_chat_id():
    target_type, target_id = bot.resolve_response_target(
        {
            "sender": {"user_id": 1001},
            "recipient": {"chat_id": 9001, "user_id": 7777},
        }
    )
    assert target_type == "chat"
    assert target_id == 9001


def test_resolve_response_target_user_fallback_to_sender():
    target_type, target_id = bot.resolve_response_target(
        {
            "sender": {"user_id": 1002},
            "recipient": {"user_id": 5555},
        }
    )
    assert target_type == "user"
    assert target_id == 1002


def test_keyboard_serialization_inline_and_reply():
    inline = InlineKeyboardMarkup([[InlineKeyboardButton("A", callback_data="cb")]])
    data_inline = _serialize_markup(inline)
    assert data_inline[0]["type"] == "inline_keyboard"
    assert data_inline[0]["payload"]["buttons"][0][0]["payload"] == "cb"

    reply = ReplyKeyboardMarkup([["/start", "Меню"]])
    data_reply = _serialize_markup(reply)
    assert data_reply[0]["payload"]["buttons"][0][0]["type"] == "message"


def test_callback_answer_flow():
    client = DummyClient()
    runtime_bot = MaxBot(client)
    user = MaxUser(42)
    message = MaxIncomingMessage(bot=runtime_bot, message_id=1, chat_id=42, from_user=user, text="", attachments=[])
    query = MaxCallbackQuery(bot=runtime_bot, from_user=user, message=message, data="x", callback_id="cb-1")

    asyncio.run(query.answer("ok"))
    assert client.answered[0][0] == "cb-1"


def test_process_max_update_message_created(monkeypatch):
    called = {"safe": 0}

    async def _noop_startup():
        return None

    async def _safe(update, context):
        called["safe"] += 1

    monkeypatch.setattr(bot, "ensure_startup_once", _noop_startup)
    monkeypatch.setattr(bot, "safe_handle_message", _safe)

    payload = {
        "update_type": "message_created",
        "message": {
            "message_id": 10,
            "sender": {"user_id": 77, "first_name": "A"},
            "recipient": {"chat_id": 77},
            "body": {"text": "hello"},
        },
    }
    asyncio.run(bot.process_max_update(payload))
    assert called["safe"] == 1


def test_process_max_update_callback(monkeypatch):
    called = {"cb": 0}

    async def _noop_startup():
        return None

    async def _handle(update, context):
        called["cb"] += 1
        assert update.callback_query.data == "back"

    monkeypatch.setattr(bot, "ensure_startup_once", _noop_startup)
    monkeypatch.setattr(bot, "handle_callback", _handle)

    payload = {
        "update_type": "message_callback",
        "message": {
            "message_id": 11,
            "sender": {"user_id": 88},
            "recipient": {"chat_id": 88},
            "body": {"text": ""},
        },
        "callback": {"callback_id": "cb-x", "payload": "back"},
    }
    asyncio.run(bot.process_max_update(payload))
    assert called["cb"] == 1


def test_incoming_attachment_token_url_mapping():
    client = DummyClient()
    runtime_bot = MaxBot(client)
    user = MaxUser(9)
    msg = MaxIncomingMessage(
        bot=runtime_bot,
        message_id=3,
        chat_id=9,
        from_user=user,
        text="",
        attachments=[{"type": "image", "payload": {"id": "file-1", "url": "https://example.com/x.jpg"}}],
    )
    assert msg.photo
    assert runtime_bot._incoming_files["file-1"] == "https://example.com/x.jpg"
