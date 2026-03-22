#!/bin/bash
# Check live bot status

echo "======================================================================"
echo "🤖 LIVE BOT STATUS CHECK"
echo "======================================================================"
echo ""

# Check PIDs
for risk in low medium high; do
    pid_file="$HOME/.openclaw/workspace/bot_${risk}.pid"
    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo "✅ ${risk^^} RISK bot: RUNNING (PID: $pid)"
        else
            echo "❌ ${risk^^} RISK bot: STOPPED"
        fi
    else
        echo "❌ ${risk^^} RISK bot: NO PID FILE"
    fi
done

echo ""
echo "======================================================================"
echo "📊 Recent Log Activity (last 5 lines):"
echo "======================================================================"
echo ""

for risk in low medium high; do
    log_file="$HOME/.openclaw/workspace/memory/passivbot_logs/${risk}/live.log"
    echo "🟢 ${risk^^} RISK:"
    if [ -f "$log_file" ]; then
        tail -5 "$log_file" 2>/dev/null | sed 's/^/  /'
    else
        echo "  No log file"
    fi
    echo ""
done

echo "======================================================================"
echo "💡 Commands:"
echo "  • Full logs: tail -f ~/.openclaw/workspace/memory/passivbot_logs/*/live.log"
echo "  • Stop all:  kill \$(cat ~/.openclaw/workspace/bot_*.pid)"
echo "======================================================================"
