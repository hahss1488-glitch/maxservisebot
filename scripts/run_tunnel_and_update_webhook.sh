#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

fail() {
  log "ERROR: $*"
  exit 1
}

MAX_API_BASE="${MAX_API_BASE:-https://platform-api.max.ru}"
MAX_BOT_TOKEN="${MAX_BOT_TOKEN:-}"
MAX_WEBHOOK_SECRET="${MAX_WEBHOOK_SECRET:-}"
MAXSERVISEBOT_HOME="${MAXSERVISEBOT_HOME:-/root/maxservisebot}"
CURRENT_TUNNEL_URL_FILE="${CURRENT_TUNNEL_URL_FILE:-$MAXSERVISEBOT_HOME/current_tunnel_url.txt}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEBHOOK_SYNC_LOCK_FILE="${WEBHOOK_SYNC_LOCK_FILE:-/tmp/maxservisebot-webhook-sync.lock}"

[ -n "$MAX_BOT_TOKEN" ] || fail "MAX_BOT_TOKEN is required"
exec 9>"$WEBHOOK_SYNC_LOCK_FILE"
if ! flock -n 9; then
  fail "Another tunnel/webhook sync is already running (lock=$WEBHOOK_SYNC_LOCK_FILE)"
fi
log "Webhook orchestrator entrypoint started: $0"
log "Working directory: $(pwd)"
log "Using CURRENT_TUNNEL_URL_FILE=$CURRENT_TUNNEL_URL_FILE"
log "Using WEBHOOK_SYNC_LOCK_FILE=$WEBHOOK_SYNC_LOCK_FILE"

if [ -n "${TUNNEL_START_CMD:-}" ]; then
  log "Starting tunnel with TUNNEL_START_CMD"
  bash -lc "$TUNNEL_START_CMD"
fi

resolve_tunnel_url() {
  local base_url="${MAX_TUNNEL_URL:-${TUNNEL_URL:-${WEBHOOK_BASE_URL:-${PUBLIC_BASE_URL:-}}}}"
  if [ -n "$base_url" ]; then
    printf '%s\n' "${base_url%/}"
    return
  fi

  if [ -n "${TUNNEL_STATUS_URL:-}" ]; then
    local status_payload
    status_payload="$(curl -fsS "$TUNNEL_STATUS_URL")" || fail "Cannot fetch TUNNEL_STATUS_URL=$TUNNEL_STATUS_URL"
    base_url="$(python - "$status_payload" <<'PY'
import json, sys
payload = json.loads(sys.argv[1])

def extract(data):
    if isinstance(data, str):
        value = data.strip()
        if value.startswith("http://") or value.startswith("https://"):
            return value
        return ""
    if isinstance(data, dict):
        for key in ("url", "public_url", "publicUrl", "tunnel_url", "tunnelUrl", "https", "https_url"):
            value = extract(data.get(key))
            if value:
                return value
        for key in ("data", "result", "tunnel"):
            value = extract(data.get(key))
            if value:
                return value
    if isinstance(data, list):
        for item in data:
            value = extract(item)
            if value:
                return value
    return ""

print(extract(payload))
PY
)"
    [ -n "$base_url" ] || fail "Cannot parse tunnel URL from TUNNEL_STATUS_URL response"
    printf '%s\n' "${base_url%/}"
    return
  fi

  if [ -f "$CURRENT_TUNNEL_URL_FILE" ]; then
    base_url="$(tr -d '\r\n' < "$CURRENT_TUNNEL_URL_FILE")"
    if [ -n "$base_url" ]; then
      printf '%s\n' "${base_url%/}"
      return
    fi
  fi

  fail "Cannot resolve tunnel URL. Set MAX_TUNNEL_URL/TUNNEL_URL/... or TUNNEL_STATUS_URL."
}

TUNNEL_BASE_URL="$(resolve_tunnel_url)"
mkdir -p "$(dirname "$CURRENT_TUNNEL_URL_FILE")"
printf '%s\n' "$TUNNEL_BASE_URL" > "$CURRENT_TUNNEL_URL_FILE"
log "Saved current tunnel URL to $CURRENT_TUNNEL_URL_FILE: $TUNNEL_BASE_URL"

export MAX_TUNNEL_URL="$TUNNEL_BASE_URL"
log "Delegating webhook sync to $SCRIPT_DIR/update_max_webhook.py"
python "$SCRIPT_DIR/update_max_webhook.py"
