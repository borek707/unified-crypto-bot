#!/bin/bash
# PassivBot Pro - $12 config runner

export EXCHANGE_API_KEY="0xb64995df52ea75ca8497d61e9e7e3ff185bf6787"
export EXCHANGE_API_SECRET="0x839358e35f7155dfc8468a1d9d7d8c305b944b39db94ab9014cc11281ba65c7d"
export EXCHANGE_TYPE="hyperliquid"

cd ~/.openclaw/workspace/skills/passivbot-pro

echo "=== PassivBot Pro - $12 Account ==="
echo "Config: ~/.openclaw/workspace/config_12usd.json"
echo ""

python3 -m scripts.main --config ~/.openclaw/workspace/config_12usd.json "$@"
