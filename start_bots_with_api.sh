#!/bin/bash
# Start 3 paper trading bots WITH API KEYS

if [ -z "$HYPERLIQUID_API_KEY" ] || [ -z "$HYPERLIQUID_SECRET" ]; then
  echo "ERROR: Set HYPERLIQUID_API_KEY and HYPERLIQUID_SECRET in your .env or environment."
  exit 1
fi

echo "======================================================================"
echo "🚀 STARTING 3 LIVE PAPER TRADING BOTS"
echo "======================================================================"
echo ""
echo "API Key: ${HYPERLIQUID_API_KEY:0:10}...${HYPERLIQUID_API_KEY: -6}"
echo ""

mkdir -p ~/.openclaw/workspace/memory/passivbot_logs/{low,medium,high}

cd ~/.openclaw/workspace/skills/passivbot-micro/scripts

# LOW RISK Bot
echo "[1/3] Starting LOW RISK bot..."
python3 unified_bot.py \
  --config ~/.openclaw/workspace/config_low_risk.json \
  --testnet \
  > ~/.openclaw/workspace/memory/passivbot_logs/low/live.log 2>&1 &
echo $! > ~/.openclaw/workspace/bot_low.pid
echo "   PID: $(cat ~/.openclaw/workspace/bot_low.pid)"

# MEDIUM RISK Bot  
echo "[2/3] Starting MEDIUM RISK bot..."
python3 unified_bot.py \
  --config ~/.openclaw/workspace/config_medium_risk.json \
  --testnet \
  > ~/.openclaw/workspace/memory/passivbot_logs/medium/live.log 2>&1 &
echo $! > ~/.openclaw/workspace/bot_medium.pid
echo "   PID: $(cat ~/.openclaw/workspace/bot_medium.pid)"

# HIGH RISK Bot
echo "[3/3] Starting HIGH RISK bot..."
python3 unified_bot.py \
  --config ~/.openclaw/workspace/config_high_risk.json \
  --testnet \
  > ~/.openclaw/workspace/memory/passivbot_logs/high/live.log 2>&1 &
echo $! > ~/.openclaw/workspace/bot_high.pid
echo "   PID: $(cat ~/.openclaw/workspace/bot_high.pid)"

echo ""
echo "======================================================================"
echo "✅ ALL 3 BOTS STARTED WITH API KEYS!"
echo "======================================================================"
echo ""
echo "Check status: ~/.openclaw/workspace/check_bots.sh"
echo ""
