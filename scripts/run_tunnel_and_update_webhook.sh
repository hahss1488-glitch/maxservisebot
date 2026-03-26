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
CURRENT_TUNNEL_URL_FILE="${CURRENT_TUNNEL_URL_FILE:-current_tunnel_url.txt}"

[ -n "$MAX_BOT_TOKEN" ] || fail "MAX_BOT_TOKEN is required"

if [ -n "${TUNNEL_START_CMD:-}" ]; then
  log "Starting tunnel with TUNNEL_START_CMD"
  bash -lc "$TUNNEL_START_CMD"
fi

resolve_webhook_url() {
  if [ -n "${MAX_WEBHOOK_URL:-}" ]; then
    printf '%s\n' "${MAX_WEBHOOK_URL%/}"
    return
  fi

  local base_url="${MAX_TUNNEL_URL:-${TUNNEL_URL:-${WEBHOOK_BASE_URL:-${PUBLIC_BASE_URL:-}}}}"
  if [ -z "$base_url" ] && [ -f "$CURRENT_TUNNEL_URL_FILE" ]; then
    base_url="$(tr -d '\r\n' < "$CURRENT_TUNNEL_URL_FILE")"
  fi

  [ -n "$base_url" ] || fail "Cannot resolve webhook URL. Set MAX_WEBHOOK_URL or MAX_TUNNEL_URL (or CURRENT_TUNNEL_URL_FILE)."
  printf '%s/max/webhook\n' "${base_url%/}"
}

extract_urls() {
  python - "$1" <<'PY'
import json,sys
payload = json.loads(sys.argv[1])

def extract_subscriptions(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("subscriptions", "items", "result", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return value
    return []

def iter_urls(items):
    for item in items:
        candidate = item
        if isinstance(candidate, dict) and isinstance(candidate.get("subscription"), dict):
            candidate = candidate["subscription"]
        if isinstance(candidate, dict):
            for key in ("url", "webhook_url", "callback_url", "endpoint"):
                value = candidate.get(key)
                if isinstance(value, str) and value:
                    yield value
                    break

for u in iter_urls(extract_subscriptions(payload)):
    print(u)
PY
}

api_call() {
  local method="$1"
  local url="$2"
  local data="${3:-}"
  local response status body

  if [ -n "$data" ]; then
    response="$(curl -sS -X "$method" \
      -H "Authorization: Bearer $MAX_BOT_TOKEN" \
      -H 'Content-Type: application/json' \
      --data "$data" \
      -w $'\n%{http_code}' \
      "$url")"
  else
    response="$(curl -sS -X "$method" \
      -H "Authorization: Bearer $MAX_BOT_TOKEN" \
      -w $'\n%{http_code}' \
      "$url")"
  fi

  status="${response##*$'\n'}"
  body="${response%$'\n'*}"

  log "MAX API $method $url -> HTTP $status"
  if [ -n "$body" ]; then
    log "MAX API response body: $body"
  fi

  printf '%s\n%s' "$status" "$body"
}

WEBHOOK_URL="$(resolve_webhook_url)"
log "Resolved new webhook URL: $WEBHOOK_URL"

get_result="$(api_call GET "$MAX_API_BASE/subscriptions")"
get_status="$(printf '%s' "$get_result" | head -n1)"
get_body="$(printf '%s' "$get_result" | tail -n +2)"

[[ "$get_status" =~ ^2 ]] || fail "GET /subscriptions failed with HTTP $get_status"

mapfile -t existing_urls < <(extract_urls "$get_body")
if [ "${#existing_urls[@]}" -eq 0 ]; then
  log "No old subscriptions found"
else
  log "Found old subscriptions (${#existing_urls[@]}):"
  for old_url in "${existing_urls[@]}"; do
    log " - $old_url"
  done
fi

for old_url in "${existing_urls[@]}"; do
  log "Deleting old subscription: $old_url"
  delete_response="$(curl -sS -G -X DELETE \
    -H "Authorization: Bearer $MAX_BOT_TOKEN" \
    --data-urlencode "url=$old_url" \
    -w $'\n%{http_code}' \
    "$MAX_API_BASE/subscriptions")"

  delete_status="${delete_response##*$'\n'}"
  delete_body="${delete_response%$'\n'*}"

  log "MAX API DELETE $MAX_API_BASE/subscriptions?url=<encoded> -> HTTP $delete_status"
  if [ -n "$delete_body" ]; then
    log "MAX API DELETE response body: $delete_body"
  fi

  [[ "$delete_status" =~ ^2|^404$ ]] || fail "DELETE failed for $old_url (HTTP $delete_status)"
done

create_payload="$(python - <<PY
import json
payload = {"url": "$WEBHOOK_URL"}
secret = "$MAX_WEBHOOK_SECRET"
if secret:
    payload["secret"] = secret
print(json.dumps(payload, ensure_ascii=False))
PY
)"

create_result="$(api_call POST "$MAX_API_BASE/subscriptions" "$create_payload")"
create_status="$(printf '%s' "$create_result" | head -n1)"
[[ "$create_status" =~ ^2 ]] || fail "POST /subscriptions failed with HTTP $create_status"

log "New webhook registered: $WEBHOOK_URL"

final_result="$(api_call GET "$MAX_API_BASE/subscriptions")"
final_status="$(printf '%s' "$final_result" | head -n1)"
final_body="$(printf '%s' "$final_result" | tail -n +2)"
[[ "$final_status" =~ ^2 ]] || fail "Final GET /subscriptions failed with HTTP $final_status"

mapfile -t final_urls < <(extract_urls "$final_body")
log "Final subscriptions count: ${#final_urls[@]}"
for url in "${final_urls[@]}"; do
  log "Final subscription: $url"
done

if [ "${#final_urls[@]}" -ne 1 ] || [ "${final_urls[0]:-}" != "$WEBHOOK_URL" ]; then
  fail "Expected exactly one active webhook ($WEBHOOK_URL), got: ${final_urls[*]:-<empty>}"
fi

log "Webhook sync completed successfully. Active webhook: $WEBHOOK_URL"
