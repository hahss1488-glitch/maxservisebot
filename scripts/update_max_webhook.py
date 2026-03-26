#!/usr/bin/env python3
from __future__ import annotations

import logging
import os
import subprocess
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


def _current_tunnel_file_path() -> str:
    return (_get_env_first("CURRENT_TUNNEL_URL_FILE") or "current_tunnel_url.txt").strip()


def _extract_possible_url(payload: Any) -> str:
    if isinstance(payload, str) and payload.strip():
        value = payload.strip()
        return value if value.startswith("http://") or value.startswith("https://") else ""
    if isinstance(payload, dict):
        for key in ("url", "public_url", "publicUrl", "tunnel_url", "tunnelUrl", "https", "https_url"):
            candidate = payload.get(key)
            url = _extract_possible_url(candidate)
            if url:
                return url
        for key in ("data", "result", "tunnel"):
            nested = payload.get(key)
            url = _extract_possible_url(nested)
            if url:
                return url
    if isinstance(payload, list):
        for item in payload:
            url = _extract_possible_url(item)
            if url:
                return url
    return ""


def _discover_tunnel_url(timeout: int) -> str:
    status_url = _get_env_first("TUNNEL_STATUS_URL")
    if not status_url:
        return ""
    try:
        response = requests.get(status_url, timeout=timeout)
        response.raise_for_status()
        tunnel_url = _extract_possible_url(response.json())
        if tunnel_url:
            logger.info("Discovered tunnel url from TUNNEL_STATUS_URL: %s", tunnel_url)
        else:
            logger.warning("Cannot extract tunnel url from TUNNEL_STATUS_URL payload")
        return tunnel_url.rstrip("/")
    except requests.RequestException as exc:
        logger.warning("Failed to discover tunnel url from TUNNEL_STATUS_URL: %s", exc)
        return ""
    except ValueError as exc:
        logger.warning("TUNNEL_STATUS_URL did not return valid JSON: %s", exc)
        return ""


def resolve_tunnel_base_url(timeout: int) -> str:
    base_url = _get_env_first("MAX_TUNNEL_URL", "TUNNEL_URL", "WEBHOOK_BASE_URL", "PUBLIC_BASE_URL")
    if not base_url:
        base_url = _discover_tunnel_url(timeout)
    if not base_url:
        tunnel_file = _current_tunnel_file_path()
        try:
            if os.path.exists(tunnel_file):
                base_url = (open(tunnel_file, "r", encoding="utf-8").read() or "").strip()
        except OSError as exc:
            logger.warning("Failed to read tunnel URL file=%s error=%s", tunnel_file, exc)
    return base_url.rstrip("/")


def persist_tunnel_url(base_url: str) -> None:
    if not base_url:
        return
    tunnel_file = _current_tunnel_file_path()
    parent = os.path.dirname(os.path.abspath(tunnel_file))
    os.makedirs(parent, exist_ok=True)
    with open(tunnel_file, "w", encoding="utf-8") as handle:
        handle.write(f"{base_url.rstrip('/')}\n")
    logger.info("Saved current tunnel url to file=%s", tunnel_file)


def resolve_webhook_url(base_url: str) -> str:
    explicit_webhook_url = _get_env_first("MAX_WEBHOOK_URL", "WEBHOOK_URL")
    if explicit_webhook_url:
        return explicit_webhook_url.rstrip("/")
    if not base_url:
        return ""
    return f"{base_url.rstrip('/')}/max/webhook"


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": token,
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


def _extract_subscription_urls(subscriptions: list[dict[str, Any]]) -> list[str]:
    urls: list[str] = []
    for item in subscriptions:
        candidate_keys = ("url", "webhook_url", "callback_url", "endpoint")
        sub_url = ""
        for key in candidate_keys:
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                sub_url = value.strip()
                break

        if not sub_url:
            nested = item.get("subscription")
            if isinstance(nested, dict):
                for key in candidate_keys:
                    value = nested.get(key)
                    if isinstance(value, str) and value.strip():
                        sub_url = value.strip()
                        break

        if sub_url:
            urls.append(sub_url)

    # сохраняем порядок и убираем дубли
    deduped: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        deduped.append(url)
    return deduped


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
        if response.status_code == 404:
            logger.info("Subscription url=%s already absent (404)", sub_url)
            return True
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
    timeout = int(os.getenv("MAX_API_TIMEOUT", "20"))
    tunnel_start_cmd = (os.getenv("TUNNEL_START_CMD") or "").strip()

    if not token:
        logger.error("MAX_BOT_TOKEN is empty")
        return 2
    if tunnel_start_cmd:
        logger.info("Starting tunnel with TUNNEL_START_CMD")
        try:
            subprocess.run(["bash", "-lc", tunnel_start_cmd], check=True)
        except subprocess.CalledProcessError as exc:
            logger.error("Tunnel start command failed exit=%s", exc.returncode)
            return 1

    base_url = resolve_tunnel_base_url(timeout)
    webhook_url = resolve_webhook_url(base_url)
    if not webhook_url:
        logger.error(
            "Webhook URL is not configured. Set MAX_WEBHOOK_URL/WEBHOOK_URL "
            "or MAX_TUNNEL_URL/TUNNEL_URL/WEBHOOK_BASE_URL/PUBLIC_BASE_URL."
        )
        return 2
    if base_url:
        persist_tunnel_url(base_url)

    logger.info("Syncing MAX webhook subscriptions for url=%s", webhook_url)

    try:
        current = fetch_current_subscriptions(api_base, token, timeout)
    except requests.RequestException as exc:
        logger.error("Cannot fetch current subscriptions: %s", exc)
        return 1

    deleted = 0
    failed = 0
    existing_urls = _extract_subscription_urls(current)
    if existing_urls:
        logger.info("Found old subscriptions: %s", ", ".join(existing_urls))
    else:
        logger.info("No old subscriptions found")

    for existing_url in existing_urls:
        if delete_subscription(api_base, token, existing_url, timeout):
            deleted += 1
        else:
            failed += 1

    logger.info("Cleanup finished: deleted=%s failed=%s", deleted, failed)
    if failed:
        logger.error("Aborting create because some old subscriptions were not deleted")
        return 1

    try:
        create_subscription(api_base, token, webhook_url, secret, timeout)
    except requests.RequestException as exc:
        logger.error("Cannot create new subscription: %s", exc)
        return 1

    try:
        final_subscriptions = fetch_current_subscriptions(api_base, token, timeout)
    except requests.RequestException as exc:
        logger.error("Cannot verify final subscriptions: %s", exc)
        return 1

    final_urls = _extract_subscription_urls(final_subscriptions)
    if len(final_urls) != 1 or final_urls[0] != webhook_url:
        logger.error("Expected exactly one final subscription=%s, got=%s", webhook_url, final_urls)
        return 1

    logger.info("Webhook sync completed. Active webhook: %s", webhook_url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
