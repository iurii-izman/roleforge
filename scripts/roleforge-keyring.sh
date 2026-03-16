#!/usr/bin/env bash
set -euo pipefail

SERVICE="roleforge"

usage() {
  cat <<'EOF'
Usage:
  scripts/roleforge-keyring.sh set <domain> <key>
  scripts/roleforge-keyring.sh get <domain> <key>
  scripts/roleforge-keyring.sh exists <domain> <key>

Examples:
  scripts/roleforge-keyring.sh set google client_id
  scripts/roleforge-keyring.sh set linear api_key
  scripts/roleforge-keyring.sh get telegram bot_token
  scripts/roleforge-keyring.sh get linear api_key
EOF
}

if [[ $# -lt 3 ]]; then
  usage
  exit 1
fi

COMMAND="$1"
DOMAIN="$2"
KEY="$3"

case "$COMMAND" in
  set)
    secret-tool store \
      --label="RoleForge ${DOMAIN} ${KEY}" \
      service "$SERVICE" \
      domain "$DOMAIN" \
      key "$KEY"
    ;;
  get)
    secret-tool lookup \
      service "$SERVICE" \
      domain "$DOMAIN" \
      key "$KEY"
    ;;
  exists)
    if secret-tool lookup service "$SERVICE" domain "$DOMAIN" key "$KEY" >/dev/null; then
      echo "yes"
    else
      echo "no"
    fi
    ;;
  *)
    usage
    exit 1
    ;;
esac
