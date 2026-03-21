#!/bin/bash
# PassivBot Pro wrapper - uruchamia z API keys

export EXCHANGE_API_KEY="0xb64995df52ea75ca8497d61e9e7e3ff185bf6787"
export EXCHANGE_API_SECRET="0x839358e35f7155dfc8468a1d9d7d8c305b944b39db94ab9014cc11281ba65c7d"
export EXCHANGE_TYPE="hyperliquid"
export USE_TESTNET="true"

cd ~/.openclaw/workspace/skills/passivbot-pro/scripts

python3 main.py "$@"
