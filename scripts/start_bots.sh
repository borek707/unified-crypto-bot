#!/bin/bash
# start_bots.sh - Start all trading bots

set -e

echo "🚀 Starting Unified Crypto Trading Bots..."

# Check if already running
if pgrep -f "unified_bot.py" > /dev/null; then
    echo "⚠️  Bots already running! Use restart_bots.sh to restart."
    exit 1
fi

# Create log directories
mkdir -p memory/passivbot_logs/{low,medium,high}
mkdir -p memory/logs

# Start Low Risk Bot
echo "Starting Low Risk Bot..."
nohup python3 skills/passivbot-micro/scripts/unified_bot.py \
    --config config/config_low_risk.json \
    --testnet \
    > memory/passivbot_logs/low/live.log 2>&1 &
echo $! > memory/bot_low.pid
sleep 2

# Start Medium Risk Bot
echo "Starting Medium Risk Bot..."
nohup python3 skills/passivbot-micro/scripts/unified_bot.py \
    --config config/config_medium_risk.json \
    --testnet \
    > memory/passivbot_logs/medium/live.log 2>&1 &
echo $! > memory/bot_medium.pid
sleep 2

# Start High Risk Bot
echo "Starting High Risk Bot..."
nohup python3 skills/passivbot-micro/scripts/unified_bot.py \
    --config config/config_high_risk.json \
    --testnet \
    > memory/passivbot_logs/high/live.log 2>&1 &
echo $! > memory/bot_high.pid

echo ""
echo "✅ All bots started!"
echo ""
echo "Check status: ./scripts/status.sh"
echo "View logs: tail -f memory/passivbot_logs/*/live.log"
echo ""