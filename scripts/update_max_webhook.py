#!/usr/bin/env python3
from __future__ import annotations

import logging
import os
import sys
from typing import Any

import requests


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("max_webhook_sync")


def _get_env_first(*keys: str) -> str:
    for key in keys:
        value = (os.getenv(key) or "").strip()
        if value:
            return value
    return ""


def resolve_webhook_url() -> str:
    explicit_webhook_url = _get_env_first("MAX_WEBHOOK_URL", "WEBHOOK_URL")
    if explicit_webhook_url:
        return explicit_webhook_url.rstrip("/")

    base_url = _get_env_first("MAX_TUNNEL_URL", "TUNNEL_URL", "WEBHOOK_BASE_URL", "PUBLIC_BASE_URL")
    if not base_url:
        return ""

    return f"{base_url.rstrip('/')}/max/webhook"


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _extract_subscriptions(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("subscriptions", "items", "result", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def fetch_current_subscriptions(api_base: str, token: str, timeout: int) -> list[dict[str, Any]]:
    url = f"{api_base}/subscriptions"
    response = requests.get(url, headers=_headers(token), timeout=timeout)
    response.raise_for_status()
    items = _extract_subscriptions(response.json())
    logger.info("Fetched %s existing subscription(s)", len(items))
    return items


def delete_subscription(api_base: str, token: str, sub_url: str, timeout: int) -> bool:
    url = f"{api_base}/subscriptions"
    try:
        response = requests.delete(url, headers=_headers(token), params={"url": sub_url}, timeout=timeout)
        if response.status_code >= 400:
            logger.warning(
                "Failed to delete subscription url=%s status=%s body=%s",
                sub_url,
                response.status_code,
                response.text[:300],
            )
            return False
        logger.info("Deleted subscription url=%s", sub_url)
        return True
    except requests.RequestException as exc:
        logger.warning("Delete subscription request failed url=%s error=%s", sub_url, exc)
        return False


def create_subscription(api_base: str, token: str, webhook_url: str, secret: str, timeout: int) -> None:
    url = f"{api_base}/subscriptions"
    payload: dict[str, Any] = {"url": webhook_url}
    if secret:
        payload["secret"] = secret

    response = requests.post(url, headers=_headers(token), json=payload, timeout=timeout)
    response.raise_for_status()
    logger.info("Created new subscription url=%s", webhook_url)


def main() -> int:
    token = (os.getenv("MAX_BOT_TOKEN") or "").strip()
    api_base = (os.getenv("MAX_API_BASE", "https://platform-api.max.ru") or "").rstrip("/")
    secret = (os.getenv("MAX_WEBHOOK_SECRET") or "").strip()
    webhook_url = resolve_webhook_url()
    timeout = int(os.getenv("MAX_API_TIMEOUT", "20"))

    if not token:
        logger.error("MAX_BOT_TOKEN is empty")
        return 2
    if not webhook_url:
        logger.error(
            "Webhook URL is not configured. Set MAX_WEBHOOK_URL/WEBHOOK_URL "
            "or MAX_TUNNEL_URL/TUNNEL_URL/WEBHOOK_BASE_URL/PUBLIC_BASE_URL."
        )
        return 2

    logger.info("Syncing MAX webhook subscriptions for url=%s", webhook_url)

    try:
        current = fetch_current_subscriptions(api_base, token, timeout)
    except requests.RequestException as exc:
        logger.error("Cannot fetch current subscriptions: %s", exc)
        return 1

    deleted = 0
    failed = 0
    for item in current:
        existing_url = str(item.get("url") or "").strip()
        if not existing_url:
            continue
        if delete_subscription(api_base, token, existing_url, timeout):
            deleted += 1
        else:
            failed += 1

    logger.info("Cleanup finished: deleted=%s failed=%s", deleted, failed)

    try:
        create_subscription(api_base, token, webhook_url, secret, timeout)
    except requests.RequestException as exc:
        logger.error("Cannot create new subscription: %s", exc)
        return 1

    logger.info("Webhook sync completed. Active webhook should now be only: %s", webhook_url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
