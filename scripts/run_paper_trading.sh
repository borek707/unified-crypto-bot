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

if [ -z "$EXCHANGE_API_KEY" ] || [ -z "$EXCHANGE_API_SECRET" ]; then
  echo "ERROR: Set EXCHANGE_API_KEY and EXCHANGE_API_SECRET in your .env or environment."
  exit 1
fi
export EXCHANGE_TYPE="hyperliquid"

cd ~/.openclaw/workspace/skills/passivbot-pro

# Run simulation (paper trading)
python3 -m scripts.main --config ~/.openclaw/workspace/config_paper.json --mode simulate --symbol BTC/USDC:USDC --days 7 "$@"

echo ""
echo "=================================================="
python3 ~/.openclaw/workspace/paper_trading_tracker.py
echo "=================================================="
