#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8000}"
ENV_MAIN="${ENV_MAIN:-frontend/savery/.env}"

echo "SAVERY_TUNNEL_STARTING"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared not found; install Cloudflare Tunnel (cloudflared) from Cloudflare docs." >&2
  exit 1
fi

pkill -f "cloudflared tunnel --url http://localhost:${PORT}" >/dev/null 2>&1 || true

URL_RE='https://[a-zA-Z0-9.-]+trycloudflare\.com'
FOUND_URL=""

cloudflared tunnel --url "http://localhost:${PORT}" 2>&1 | while IFS= read -r line; do
  echo "$line"

  if [[ -z "$FOUND_URL" && "$line" =~ $URL_RE ]]; then
    FOUND_URL="${BASH_REMATCH[0]}"

    mkdir -p "$(dirname "$ENV_MAIN")"
    tmp_env_file="$(mktemp "${ENV_MAIN}.XXXXXX")"
    printf 'EXPO_PUBLIC_API_BASE_URL=%s/api\n' "$FOUND_URL" >"$tmp_env_file"
    mv "$tmp_env_file" "$ENV_MAIN"
    echo "SAVERY_TUNNEL_READY ${FOUND_URL}"
  fi
done
