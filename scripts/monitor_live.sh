#!/bin/bash
# Live Bot Monitor - uruchamiaj w osobnym terminalu

echo "=================================================="
echo "🤖 LIVE BOT MONITOR"
echo "=================================================="
echo ""
echo "Odświeżanie co 30 sekund..."
echo "Naciśnij Ctrl+C aby wyjść"
echo ""

while true; do
    clear
    python3 ~/.openclaw/workspace/bot_monitor.py
    echo ""
    echo "Odświeżanie za 30s... (Ctrl+C aby wyjść)"
    sleep 30
done
