#!/bin/bash
# status.sh - Check bot status

echo "=========================================="
echo "📊 BOT STATUS"
echo "=========================================="
echo ""

# Check processes
echo "🤖 Running Processes:"
ps aux | grep unified_bot | grep -v grep | grep python3 | while read line; do
    pid=$(echo $line | awk '{print $2}')
    cpu=$(echo $line | awk '{print $3}')
    mem=$(echo $line | awk '{print $4}')
    cmd=$(echo $line | awk '{for(i=11;i<=NF;i++)printf "%s ",$i}')
    
    # Extract risk level from config
    if echo $cmd | grep -q "low_risk"; then
        risk="LOW"
    elif echo $cmd | grep -q "medium_risk"; then
        risk="MEDIUM"
    elif echo $cmd | grep -q "high_risk"; then
        risk="HIGH"
    else
        risk="UNKNOWN"
    fi
    
    echo "  ✅ $risk Risk Bot (PID: $pid, CPU: $cpu%, MEM: $mem%)"
done

if ! pgrep -f "unified_bot.py" > /dev/null; then
    echo "  ❌ No bots running!"
fi

echo ""
echo "📝 Recent Activity:"
for risk in low medium high; do
    log_file="memory/passivbot_logs/$risk/live.log"
    if [ -f "$log_file" ]; then
        last_update=$(tail -1 "$log_file" 2>/dev/null | cut -d'|' -f1)
        echo "  $risk: $last_update"
    fi
done

echo ""
echo "💾 Database:"
if [ -f "memory/crypto_prices.db" ]; then
    size=$(du -h memory/crypto_prices.db | cut -f1)
    count=$(sqlite3 memory/crypto_prices.db "SELECT COUNT(*) FROM crypto_prices;" 2>/dev/null)
    echo "  Records: $count (Size: $size)"
else
    echo "  ❌ Database not found"
fi

echo ""
echo "=========================================="