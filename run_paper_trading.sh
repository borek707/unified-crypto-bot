#!/bin/bash
# PassivBot Pro - PAPER TRADING (bez prawdziwych pieniędzy!)

echo "=================================================="
echo "📝 PAPER TRADING MODE (symulacja)"
echo "=================================================="
echo ""
echo "⚠️  To jest SYMULACJA - nie używasz prawdziwych pieniędzy!"
echo "   Bot śledzi "paper trades" w bazie danych."
echo ""
echo "Konfiguracja: $12, grid trading, BTC/USDC"
echo ""

export EXCHANGE_API_KEY="0xb64995df52ea75ca8497d61e9e7e3ff185bf6787"
export EXCHANGE_API_SECRET="0x839358e35f7155dfc8468a1d9d7d8c305b944b39db94ab9014cc11281ba65c7d"
export EXCHANGE_TYPE="hyperliquid"

cd ~/.openclaw/workspace/skills/passivbot-pro

# Run simulation (paper trading)
python3 -m scripts.main --config ~/.openclaw/workspace/config_paper.json --mode simulate --symbol BTC/USDC:USDC --days 7 "$@"

echo ""
echo "=================================================="
python3 ~/.openclaw/workspace/paper_trading_tracker.py
echo "=================================================="
