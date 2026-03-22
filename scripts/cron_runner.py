#!/usr/bin/env python3
"""
Unified cron runner z rate limitami.
Wywoływany co 15 minut przez cron.
"""

import sys
import os
import time
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.expanduser('~/.openclaw/workspace'))
from rate_limiter import check_rate_limit, log_call

SCRIPT_DIR = Path('~/.openclaw/workspace/skills/finance-tracker/scripts').expanduser()
LOG_DIR = Path('~/.openclaw/workspace/memory/logs').expanduser()
LOG_DIR.mkdir(parents=True, exist_ok=True)

def run_script(name, *args, provider=None, delay=0):
    """Run a script with rate limiting."""
    script_path = SCRIPT_DIR / name
    
    if not script_path.exists():
        log_call('system', name, f'ERROR: Script not found')
        return False
    
    # Check rate limit
    if provider:
        can_call, error = check_rate_limit(provider)
        if not can_call:
            log_call(provider, name, f'SKIPPED: {error}')
            return False
    
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, str(script_path)] + list(args),
            capture_output=True,
            text=True,
            timeout=30
        )
        
        status = 'SUCCESS' if result.returncode == 0 else f'ERROR: {result.stderr[:100]}'
        log_call(provider or 'system', name, status)
        
        if delay:
            time.sleep(delay)
        
        return result.returncode == 0
        
    except Exception as e:
        log_call(provider or 'system', name, f'EXCEPTION: {str(e)[:100]}')
        return False

def main():
    """Main cron routine."""
    log_call('system', 'cron_start', 'RUNNING')
    
    now = datetime.now()
    hour = now.hour
    minute = now.minute
    
    # Gold bot - tylko w sesjach handlowych (8-21 UTC)
    if 8 <= hour <= 21:
        run_script('gold_trading_bot.py', provider='gold', delay=3)
    
    # CoinGecko - co 15 min, max 4 calls
    if minute % 15 == 0:
        run_script('fetch_crypto.py', 'BTC', provider='coingecko', delay=2)
        run_script('fetch_crypto.py', 'ETH', provider='coingecko', delay=2)
    
    # Yahoo Finance - co godzinę, max 2 calls
    if minute == 0:
        run_script('fetch_stock.py', '^IXIC', provider='yahoo', delay=5)
        run_script('fetch_stock.py', 'AAPL', provider='yahoo', delay=5)
    
    log_call('system', 'cron_end', 'COMPLETE')

if __name__ == '__main__':
    main()
