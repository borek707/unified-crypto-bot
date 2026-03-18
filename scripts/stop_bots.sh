#!/bin/bash
# stop_bots.sh - Stop all trading bots

echo "🛑 Stopping all trading bots..."

# Kill all unified_bot processes
pkill -f "unified_bot.py" 2>/dev/null || true

# Wait for processes to stop
sleep 2

# Force kill if still running
if pgrep -f "unified_bot.py" > /dev/null; then
    echo "Force killing remaining processes..."
    pkill -9 -f "unified_bot.py" 2>/dev/null || true
fi

# Clean up PID files
rm -f memory/bot_*.pid

echo "✅ All bots stopped."