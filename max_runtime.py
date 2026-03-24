from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from max_api import MaxClient, MaxApiError


class BadRequest(Exception):
    pass


@dataclass
class InlineKeyboardButton:
    text: str
    callback_data: str | None = None
    url: str | None = None


@dataclass
class KeyboardButton:
    text: str


class InlineKeyboardMarkup:
    def __init__(self, inline_keyboard: list[list[InlineKeyboardButton]]):
        self.inline_keyboard = inline_keyboard


class ReplyKeyboardMarkup:
    def __init__(self, keyboard: list[list[str | KeyboardButton]], resize_keyboard: bool = True):
        self.keyboard = keyboard
        self.resize_keyboard = resize_keyboard


@dataclass
class InputMediaPhoto:
    media: Any
    caption: str | None = None


def _serialize_markup(reply_markup: Any) -> list[dict[str, Any]]:
    if reply_markup is None:
        return []
    if isinstance(reply_markup, InlineKeyboardMarkup):
        rows = []
        for row in reply_markup.inline_keyboard:
            buttons = []
            for btn in row:
                if btn.url:
                    buttons.append({"type": "link", "text": btn.text, "url": btn.url})
                else:
                    buttons.append({"type": "callback", "text": btn.text, "payload": btn.callback_data or ""})
            rows.append(buttons)
        return [{"type": "inline_keyboard", "payload": {"buttons": rows}}]
    if isinstance(reply_markup, ReplyKeyboardMarkup):
        rows = []
        for row in reply_markup.keyboard:
            buttons = []
            for cell in row:
                text = cell.text if isinstance(cell, KeyboardButton) else str(cell)
                buttons.append({"type": "message", "text": text})
            rows.append(buttons)
        return [{"type": "inline_keyboard", "payload": {"buttons": rows}}]
    return []


class MaxUser:
    def __init__(self, user_id: int, first_name: str = "", last_name: str = "", username: str = ""):
        self.id = int(user_id)
        self.first_name = first_name
        self.last_name = last_name
        self.username = username


class MaxChat:
    def __init__(self, chat_id: int):
        self.id = int(chat_id)


class MaxBot:
    def __init__(self, client: MaxClient):
        self.client = client
        self._incoming_files: dict[str, str] = {}

    async def send_message(self, *, chat_id: int, text: str, reply_markup=None):
        resp = self.client.send_message(chat_id=chat_id, text=text, attachments=_serialize_markup(reply_markup))
        return MaxSentMessage(self, chat_id, int(resp.get("message_id", 0)), text)

    async def send_photo(self, *, chat_id: int, photo: Any, filename: str = "image.jpg", caption: str = "", reply_markup=None):
        content = _read_bytes(photo)
        token = self.client.upload_bytes(content, filename=filename, mime="image/jpeg")
        attachments = [{"type": "image", "payload": {"token": token}}] + _serialize_markup(reply_markup)
        resp = self.client.send_message(chat_id=chat_id, text=caption or "", attachments=attachments)
        return MaxSentMessage(self, chat_id, int(resp.get("message_id", 0)), caption)

    async def send_video(self, *, chat_id: int, video: Any, caption: str = ""):
        content = _read_bytes(video)
        token = self.client.upload_bytes(content, filename="video.mp4", mime="video/mp4")
        attachments = [{"type": "video", "payload": {"token": token}}]
        resp = self.client.send_message(chat_id=chat_id, text=caption or "", attachments=attachments)
        return MaxSentMessage(self, chat_id, int(resp.get("message_id", 0)), caption)

    async def send_document(self, *, chat_id: int, document: Any, filename: str = "file.bin", caption: str = ""):
        content = _read_bytes(document)
        token = self.client.upload_bytes(content, filename=filename)
        attachments = [{"type": "file", "payload": {"token": token, "name": filename}}]
        resp = self.client.send_message(chat_id=chat_id, text=caption or "", attachments=attachments)
        return MaxSentMessage(self, chat_id, int(resp.get("message_id", 0)), caption)

    async def edit_message_text(self, *, chat_id: int, message_id: int, text: str, reply_markup=None):
        try:
            self.client.edit_message(chat_id=chat_id, message_id=message_id, text=text, attachments=_serialize_markup(reply_markup))
        except MaxApiError as exc:
            raise BadRequest(str(exc)) from exc

    async def delete_message(self, *, chat_id: int, message_id: int):
        try:
            self.client.delete_message(chat_id=chat_id, message_id=message_id)
        except MaxApiError as exc:
            raise BadRequest(str(exc)) from exc

    async def pin_chat_message(self, *, chat_id: int, message_id: int, disable_notification: bool = True):
        # MAX API pin endpoint differs; fallback no-op for compatibility.
        return None

    async def unpin_chat_message(self, *, chat_id: int, message_id: int):
        return None

    async def copy_message(self, *, chat_id: int, from_chat_id: int, message_id: int, caption: str = ""):
        return await self.send_message(chat_id=chat_id, text=caption or "📎 Вложение")

    async def get_user_profile_photos(self, user_id: int, limit: int = 1):
        return type("_P", (), {"photos": []})()

    async def get_file(self, file_id: str):
        url = self._incoming_files.get(str(file_id))
        if not url:
            raise BadRequest("Unknown incoming file")
        return _RemoteFile(url)

    def remember_incoming_file(self, file_id: str, url: str) -> None:
        if file_id and url:
            self._incoming_files[str(file_id)] = str(url)


class MaxSentMessage:
    def __init__(self, bot: MaxBot, chat_id: int, message_id: int, text: str = ""):
        self.bot = bot
        self.chat_id = chat_id
        self.message_id = message_id
        self.text = text

    async def reply_text(self, text: str, reply_markup=None):
        return await self.bot.send_message(chat_id=self.chat_id, text=text, reply_markup=reply_markup)

    async def reply_photo(self, photo: Any, filename: str = "image.jpg", caption: str = "", reply_markup=None):
        return await self.bot.send_photo(chat_id=self.chat_id, photo=photo, filename=filename, caption=caption, reply_markup=reply_markup)

    async def reply_document(self, document: Any, filename: str = "file.bin", caption: str = ""):
        return await self.bot.send_document(chat_id=self.chat_id, document=document, filename=filename, caption=caption)

    async def edit_text(self, text: str, reply_markup=None):
        await self.bot.edit_message_text(chat_id=self.chat_id, message_id=self.message_id, text=text, reply_markup=reply_markup)

    async def delete(self):
        if self.message_id:
            await self.bot.delete_message(chat_id=self.chat_id, message_id=self.message_id)


class MaxCallbackQuery:
    def __init__(self, *, bot: MaxBot, from_user: MaxUser, message: MaxSentMessage, data: str, callback_id: str):
        self.bot = bot
        self.from_user = from_user
        self.message = message
        self.data = data
        self.callback_id = callback_id

    async def answer(self, text: str = "", show_alert: bool = False):
        notification = text if show_alert else ""
        self.bot.client.answer_callback(self.callback_id, message=text if not show_alert else "", notification=notification)

    async def edit_message_text(self, text: str, reply_markup=None):
        await self.message.edit_text(text=text, reply_markup=reply_markup)


class MaxIncomingMessage(MaxSentMessage):
    def __init__(self, *, bot: MaxBot, message_id: int, chat_id: int, from_user: MaxUser, text: str = "", attachments: list[dict[str, Any]] | None = None):
        super().__init__(bot, chat_id, message_id, text)
        self.from_user = from_user
        self.text = text
        self.attachments = attachments or []
        self.photo = []
        self.video = None
        self.document = None
        self._parse_attachments()

    def _parse_attachments(self):
        for att in self.attachments:
            atype = att.get("type")
            payload = att.get("payload") or {}
            token = payload.get("token") or payload.get("id") or ""
            url = payload.get("url") or att.get("url") or ""
            if token and url:
                self.bot.remember_incoming_file(str(token), str(url))
            if atype == "image":
                self.photo.append(type("_Photo", (), {"file_id": str(token)})())
            elif atype == "video":
                self.video = type("_Video", (), {"file_id": str(token), "mime_type": "video/mp4"})()
            elif atype in {"file", "document"}:
                self.document = type("_Doc", (), {"file_id": str(token), "mime_type": payload.get("mime", "application/octet-stream")})()


class Update:
    ALL_TYPES = ["message_created", "message_callback"]

    def __init__(self, *, effective_user: MaxUser | None, effective_chat: MaxChat | None, message: MaxIncomingMessage | None = None, callback_query: MaxCallbackQuery | None = None):
        self.effective_user = effective_user
        self.effective_chat = effective_chat
        self.message = message
        self.callback_query = callback_query
        self.effective_message = message or (callback_query.message if callback_query else None)


class CallbackContext:
    def __init__(self, *, bot: MaxBot, application: Any, user_data: dict[str, Any]):
        self.bot = bot
        self.application = application
        self.user_data = user_data


def _read_bytes(value: Any) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, BytesIO):
        return value.getvalue()
    if hasattr(value, "read"):
        pos = value.tell() if hasattr(value, "tell") else None
        data = value.read()
        if pos is not None and hasattr(value, "seek"):
            value.seek(pos)
        return data
    if isinstance(value, (str, Path)):
        return Path(value).read_bytes()
    raise ValueError("Unsupported media source")


class _RemoteFile:
    def __init__(self, url: str):
        self.url = url

    async def download_as_bytearray(self):
        from urllib.request import urlopen

        with urlopen(self.url, timeout=10) as resp:
            return bytearray(resp.read())
