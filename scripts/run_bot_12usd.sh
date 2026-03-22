#!/bin/bash
# PassivBot Pro - $12 config runner

if [ -z "$EXCHANGE_API_KEY" ] || [ -z "$EXCHANGE_API_SECRET" ]; then
  echo "ERROR: Set EXCHANGE_API_KEY and EXCHANGE_API_SECRET in your .env or environment."
  exit 1
fi
export EXCHANGE_TYPE="hyperliquid"

cd ~/.openclaw/workspace/skills/passivbot-pro

echo "=== PassivBot Pro - $12 Account ==="
echo "Config: ~/.openclaw/workspace/config_12usd.json"
echo ""

python3 -m scripts.main --config ~/.openclaw/workspace/config_12usd.json "$@"
