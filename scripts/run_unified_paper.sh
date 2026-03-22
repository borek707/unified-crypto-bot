#!/bin/bash
# Unified Bot - PAPER TRADING (symulacja)

echo "=================================================="
echo "🤖 UNIFIED BOT - PAPER TRADING"
echo "=================================================="
echo ""
echo "Strategia: Auto LONG/SHORT/GRID"
echo "Kapitał: $12 (paper)"
echo ""

cd ~/.openclaw/workspace/skills/passivbot-micro/scripts

# Run in simulation mode
python3 unified_bot.py --testnet --capital 12.0
