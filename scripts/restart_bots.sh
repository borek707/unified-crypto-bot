#!/bin/bash
# restart_bots.sh - Restart all trading bots

echo "🔄 Restarting bots..."
./scripts/stop_bots.sh
sleep 3
./scripts/start_bots.sh