from __future__ import annotations

import json
import logging
import os
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

logger = logging.getLogger(__name__)


class MaxApiError(RuntimeError):
    pass


class MaxClient:
    def __init__(self, token: str | None = None, base_url: str | None = None, timeout: float = 10.0):
        self.token = token or os.getenv("MAX_BOT_TOKEN", "")
        self.base_url = (base_url or os.getenv("MAX_API_BASE", "https://platform-api.max.ru")).rstrip("/")
        self.timeout = timeout

    @property
    def _headers(self) -> dict[str, str]:
        if not self.token:
            raise MaxApiError("MAX_BOT_TOKEN is empty")
        return {"Authorization": self.token}

    def _request(self, method: str, path: str, *, params: dict[str, Any] | None = None, json_body: dict[str, Any] | None = None, files=None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        if params:
            url = f"{url}?{urlencode({k: v for k, v in params.items() if v is not None})}"
        headers = self._headers.copy()
        data = None
        if files:
            try:
                import requests  # type: ignore
            except Exception as exc:  # noqa: BLE001
                raise MaxApiError("requests package required for upload flow") from exc
            try:
                resp = requests.request(method, url, json=json_body, files=files, headers=headers, timeout=self.timeout)
            except Exception as exc:  # noqa: BLE001
                raise MaxApiError(str(exc)) from exc
            if resp.status_code >= 400:
                raise MaxApiError(f"MAX API {resp.status_code}: {resp.text[:300]}")
            if not resp.text:
                return {}
            try:
                return resp.json()
            except ValueError:
                return {"raw": resp.text}

        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = Request(url=url, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")[:300]
            raise MaxApiError(f"MAX API {exc.code}: {body}") from exc
        except URLError as exc:
            raise MaxApiError(str(exc)) from exc
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except ValueError:
            return {"raw": raw}

    def answer_callback(self, callback_id: str, *, message: str = "", notification: str = "") -> None:
        body: dict[str, str] = {}
        if message:
            body["message"] = message
        if notification:
            body["notification"] = notification
        self._request("POST", "/answers", params={"callback_id": callback_id}, json_body=body if body else None)

    def upload_bytes(self, content: bytes, filename: str = "file.bin", mime: str = "application/octet-stream") -> str:
        files = {"file": (filename, content, mime)}
        data = self._request("POST", "/uploads", files=files)
        token = data.get("token") or data.get("id") or ""
        if not token:
            raise MaxApiError(f"Upload response missing token/id: {data}")
        return str(token)

    def send_message(self, *, user_id: int | None = None, chat_id: int | None = None, text: str = "", attachments: list[dict[str, Any]] | None = None, format_mode: str = "markdown", notify: bool = True, link: str = "") -> dict[str, Any]:
        params: dict[str, Any] = {}
        if user_id is not None:
            params["user_id"] = int(user_id)
        if chat_id is not None:
            params["chat_id"] = int(chat_id)
        body: dict[str, Any] = {
            "text": text,
            "attachments": attachments or [],
            "notify": bool(notify),
            "format": format_mode,
        }
        if link:
            body["link"] = link
        return self._request("POST", "/messages", params=params, json_body=body)

    def edit_message(self, *, chat_id: int, message_id: int, text: str, attachments: list[dict[str, Any]] | None = None, format_mode: str = "markdown") -> dict[str, Any]:
        params = {"chat_id": int(chat_id), "message_id": int(message_id)}
        body = {"text": text, "attachments": attachments or [], "format": format_mode}
        return self._request("PUT", "/messages", params=params, json_body=body)

    def delete_message(self, *, chat_id: int, message_id: int) -> None:
        self._request("DELETE", "/messages", params={"chat_id": int(chat_id), "message_id": int(message_id)})
