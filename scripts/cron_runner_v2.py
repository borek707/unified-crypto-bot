#!/usr/bin/env python3
"""
Unified cron runner z multi-source crypto API.
Wywoływany co 15 minut przez cron.
"""

import sys
import os
import time
import json
import sqlite3
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.expanduser('~/.openclaw/workspace'))
sys.path.insert(0, os.path.expanduser('~/.openclaw/workspace/skills/finance-tracker/scripts'))
from rate_limiter import check_rate_limit, log_call
from crypto_price_fetcher import CryptoPriceFetcher

LOG_DIR = Path('~/.openclaw/workspace/memory/logs').expanduser()
DB_PATH = Path('~/.openclaw/workspace/memory/crypto_prices.db').expanduser()
LOG_DIR.mkdir(parents=True, exist_ok=True)

def init_database():
    """Initialize price tracking database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Crypto prices table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crypto_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            coin TEXT,
            price REAL,
            ath REAL,
            change_24h REAL,
            source TEXT
        )
    ''')
    
    # Stock prices table - FIX: Added for NASDAQ/AAPL persistence
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            symbol TEXT,
            name TEXT,
            price REAL,
            previous_close REAL,
            change REAL,
            change_percent REAL,
            volume INTEGER,
            high_24h REAL,
            low_24h REAL,
            source TEXT DEFAULT 'yahoo'
        )
    ''')
    
    conn.commit()
    conn.close()

def save_price(coin, price_data):
    """Save crypto price to database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO crypto_prices (timestamp, coin, price, ath, change_24h, source)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        datetime.now().isoformat(),
        coin,
        price_data.get('price'),
        price_data.get('ath'),
        price_data.get('change_24h'),
        price_data.get('source', 'unknown')
    ))
    
    conn.commit()
    conn.close()


def save_stock_price(symbol, stock_data):
    """Save stock price to database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO stock_prices 
        (timestamp, symbol, name, price, previous_close, change, change_percent, volume, high_24h, low_24h, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        datetime.now().isoformat(),
        symbol,
        stock_data.get('name', symbol),
        stock_data.get('current_price'),
        stock_data.get('previous_close'),
        stock_data.get('change'),
        stock_data.get('change_percent'),
        stock_data.get('volume_24h'),
        stock_data.get('high_24h'),
        stock_data.get('low_24h'),
        'yahoo'
    ))
    
    conn.commit()
    conn.close()

def fetch_and_save_crypto():
    """Fetch crypto prices from multiple sources and save to DB."""
    fetcher = CryptoPriceFetcher()
    
    # Try to get BTC price with fallback
    result = fetcher.get_price_with_fallback()
    
    if result:
        save_price('BTC', result)
        log_call('crypto_api', result['source'], f"BTC: ${result['price']:,.2f}")
        print(f"✓ BTC: ${result['price']:,.2f} from {result['source']}")
        
        if 'ath' in result:
            print(f"  ATH: ${result['ath']:,.2f} ({((result['price']/result['ath'])-1)*100:.1f}% from ATH)")
        
        return True
    else:
        log_call('crypto_api', 'all_sources', 'FAILED')
        print("✗ Failed to fetch BTC price from all sources")
        return False

def main():
    """Main cron routine."""
    init_database()
    log_call('system', 'cron_start', 'RUNNING')
    
    now = datetime.now()
    hour = now.hour
    minute = now.minute
    
    print(f"=== Cron started at {now} ===\n")
    
    # Crypto prices - co 15 minut (reliable multi-source API)
    if minute % 15 == 0:
        print("Fetching crypto prices...")
        fetch_and_save_crypto()
        print()
    
    # Gold trading bot - co 15 min w sesjach handlowych (8-21 UTC)
    if 8 <= hour <= 21 and minute % 15 == 0:
        print("Running gold trading bot...")
        SCRIPT_DIR = Path('~/.openclaw/workspace/skills/finance-tracker/scripts').expanduser()
        script_path = SCRIPT_DIR / 'gold_trading_bot.py'
        if script_path.exists():
            import subprocess
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=30
            )
            # Log output
            if result.stdout:
                print(result.stdout)
            status = 'SUCCESS' if result.returncode == 0 else 'FAILED'
            log_call('gold', 'gold_bot', status)
            print(f"Gold bot: {status}")
        print()
    
    # Yahoo Finance - co godzinę - FIX: Now saves to database
    if minute == 0:
        SCRIPT_DIR = Path('~/.openclaw/workspace/skills/finance-tracker/scripts').expanduser()
        for symbol in ['^IXIC', 'AAPL']:
            script_path = SCRIPT_DIR / 'fetch_stock.py'
            if script_path.exists():
                import subprocess
                result = subprocess.run(
                    [sys.executable, str(script_path), symbol],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                provider = 'yahoo'
                can_call, error = check_rate_limit(provider)
                if can_call:
                    if result.returncode == 0:
                        try:
                            stock_data = json.loads(result.stdout)
                            if 'error' not in stock_data:
                                save_stock_price(symbol, stock_data)
                                status = 'SUCCESS'
                            else:
                                status = f"ERROR: {stock_data['error']}"
                        except json.JSONDecodeError:
                            status = 'ERROR: Invalid JSON response'
                    else:
                        status = f'ERROR: {result.stderr[:50]}'
                    log_call(provider, f'fetch_stock_{symbol}', status)
                    print(f"Stock {symbol}: {status}")
                time.sleep(5)
        print()
    
    log_call('system', 'cron_end', 'COMPLETE')
    print(f"=== Cron completed at {datetime.now()} ===")

if __name__ == '__main__':
    main()
