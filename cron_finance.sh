#!/usr/bin/env bash
# Cron wrapper dla finance-tracker z rate limiting
# Uruchamiać co 15 minut: */15 * * * *

set -e

SCRIPT_DIR="$HOME/.openclaw/workspace/skills/finance-tracker/scripts"
LOG_DIR="$HOME/.openclaw/workspace/memory/logs"
mkdir -p "$LOG_DIR"

LOG_FILE="$LOG_DIR/finance_cron.log"
LOCK_FILE="/tmp/finance_cron.lock"

# Sprawdź czy poprzednie wywołanie się zakończyło
if [ -f "$LOCK_FILE" ]; then
    PID=$(cat "$LOCK_FILE" 2>/dev/null)
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "$(date): Poprzednie wywołanie wciąż działa (PID: $PID). Pomijam." >> "$LOG_FILE"
        exit 0
    fi
fi

# Ustaw lock
echo $$ > "$LOCK_FILE"

# Funkcja z rate limit
call_with_delay() {
    local script=$1
    local symbol=$2
    local delay=${3:-2}  # domyślnie 2s między wywołaniami
    
    echo "$(date): Wywołuję $script $symbol" >> "$LOG_FILE"
    
    if [ -n "$symbol" ]; then
        python3 "$SCRIPT_DIR/$script" "$symbol" >> "$LOG_FILE" 2>&1
    else
        python3 "$SCRIPT_DIR/$script" >> "$LOG_FILE" 2>&1
    fi
    
    sleep "$delay"
}

{
    echo "=== $(date): Start finance cron ==="
    
    # 1. Gold trading bot (raz na 15 min w sesji)
    call_with_delay "gold_trading_bot.py" "" 3
    
    # 2. Crypto prices (CoinGecko - rate limit 2s)
    call_with_delay "fetch_crypto.py" "BTC" 2
    call_with_delay "fetch_crypto.py" "ETH" 2
    
    # 3. Stock prices (Yahoo Finance - rate limit 1s)
    call_with_delay "fetch_stock.py" "^IXIC" 1  # NASDAQ
    call_with_delay "fetch_stock.py" "AAPL" 1
    
    echo "=== $(date): Koniec finance cron ==="
} >> "$LOG_FILE" 2>&1

# Usuń lock
rm -f "$LOCK_FILE"
