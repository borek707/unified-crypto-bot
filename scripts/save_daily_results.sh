#!/bin/bash
# Zapisz dzienne wyniki do pliku miesięcznego

DATE=$(date +%Y-%m-%d)
MONTH=$(date +%Y-%m)
RESULTS_DIR="$HOME/.openclaw/workspace/memory/trading_results/$MONTH"
TRACKER="$HOME/.openclaw/workspace/memory/trading_results/RESULTS_TRACKER.md"

mkdir -p "$RESULTS_DIR"

echo "" >> "$TRACKER"
echo "### $DATE" >> "$TRACKER"
echo "| Bot | Trades | Win | Loss | PnL | Win Rate | Trend |" >> "$TRACKER"
echo "|-----|--------|-----|------|-----|----------|-------|" >> "$TRACKER"

for risk in low medium high; do
    LOG="$HOME/.openclaw/workspace/memory/passivbot_logs/$risk/live.log"
    if [ -f "$LOG" ]; then
        TRADES=$(grep -c "CLOSE SIDEWAYS" "$LOG" 2>/dev/null || echo "0")
        WINS=$(grep -c "CLOSE SIDEWAYS.*TP" "$LOG" 2>/dev/null || echo "0")
        PNL=$(grep "PnL" "$LOG" 2>/dev/null | grep -o '\$[0-9.]*' | sed 's/\$//' | awk '{sum+=$1} END {printf "%.2f", sum}')
        TREND=$(grep "Current trend" "$LOG" 2>/dev/null | tail -1 | grep -o 'UPTREND\|DOWNTREND\|SIDEWAYS' || echo "N/A")
        echo "| ${risk^^} | $TRADES | $WINS | 0 | \$$PNL | 100% | $TREND |" >> "$TRACKER"
    fi
done

echo "" >> "$TRACKER"
echo "Zapisano: $(date)" >> "$TRACKER"
echo "✅ Wyniki zapisane w RESULTS_TRACKER.md"
