#!/bin/bash
# Start Paper Trading with 3 Risk Profiles

echo "=================================================="
echo "🚀 PAPER TRADING - 3 RISK PROFILES"
echo "=================================================="
echo ""
echo "Starting with $100 paper capital each:"
echo "  🟢 LOW RISK:    Conservative (max 2x leverage)"
echo "  🟡 MEDIUM RISK: Balanced (max 3x leverage)"
echo "  🔴 HIGH RISK:   Aggressive (max 5x leverage)"
echo ""

cd ~/.openclaw/workspace/skills/passivbot-micro/scripts

# Create separate log directories
mkdir -p ~/.openclaw/workspace/memory/passivbot_logs/low
mkdir -p ~/.openclaw/workspace/memory/passivbot_logs/medium
mkdir -p ~/.openclaw/workspace/memory/passivbot_logs/high

# Start LOW RISK bot
echo "[1/3] Starting LOW RISK bot..."
python3 unified_bot.py \
  --config ~/.openclaw/workspace/config_low_risk.json \
  --testnet \
  > ~/.openclaw/workspace/memory/passivbot_logs/low/bot.log 2>&1 &
LOW_PID=$!
echo "   PID: $LOW_PID - Log: passivbot_logs/low/bot.log"

# Start MEDIUM RISK bot
echo "[2/3] Starting MEDIUM RISK bot..."
python3 unified_bot.py \
  --config ~/.openclaw/workspace/config_medium_risk.json \
  --testnet \
  > ~/.openclaw/workspace/memory/passivbot_logs/medium/bot.log 2>&1 &
MED_PID=$!
echo "   PID: $MED_PID - Log: passivbot_logs/medium/bot.log"

# Start HIGH RISK bot
echo "[3/3] Starting HIGH RISK bot..."
python3 unified_bot.py \
  --config ~/.openclaw/workspace/config_high_risk.json \
  --testnet \
  > ~/.openclaw/workspace/memory/passivbot_logs/high/bot.log 2>&1 &
HIGH_PID=$!
echo "   PID: $HIGH_PID - Log: passivbot_logs/high/bot.log"

echo ""
echo "=================================================="
echo "✅ ALL 3 BOTS STARTED!"
echo "=================================================="
echo ""
echo "Monitor with:"
echo "  • Logs LOW:    tail -f ~/.openclaw/workspace/memory/passivbot_logs/low/bot.log"
echo "  • Logs MEDIUM: tail -f ~/.openclaw/workspace/memory/passivbot_logs/medium/bot.log"
echo "  • Logs HIGH:   tail -f ~/.openclaw/workspace/memory/passivbot_logs/high/bot.log"
echo ""
echo "  • Dashboard:   python3 ~/.openclaw/workspace/bot_monitor.py"
echo "  • Live view:   ~/.openclaw/workspace/monitor_live.sh"
echo ""
echo "To stop all bots: kill $LOW_PID $MED_PID $HIGH_PID"
echo ""

# Save PIDs
echo "$LOW_PID $MED_PID $HIGH_PID" > ~/.openclaw/workspace/bot_pids.txt
echo "PIDs saved to: bot_pids.txt"
