#!/bin/bash
# PassivBot Pro wrapper - uruchamia z API keys

if [ -z "$EXCHANGE_API_KEY" ] || [ -z "$EXCHANGE_API_SECRET" ]; then
  echo "ERROR: Set EXCHANGE_API_KEY and EXCHANGE_API_SECRET in your .env or environment."
  exit 1
fi
export EXCHANGE_TYPE="hyperliquid"
export USE_TESTNET="true"

cd ~/.openclaw/workspace/skills/passivbot-pro/scripts

python3 main.py "$@"
