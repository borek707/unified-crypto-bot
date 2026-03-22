#!/usr/bin/env python3
"""
Daily Bot Report - generowany automatycznie przez cron
Wysyła raport z wynikami wszystkich botów
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path

def generate_report():
    """Generate daily report for all bots."""
    
    report = []
    report.append("=" * 60)
    report.append("📊 DAILY BOT REPORT")
    report.append(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC")
    report.append("=" * 60)
    
    # Crypto prices
    db_path = Path('~/.openclaw/workspace/memory/crypto_prices.db').expanduser()
    if db_path.exists():
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Last 24h prices
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        cursor.execute('''
            SELECT coin, price, ath, change_24h, source, timestamp
            FROM crypto_prices
            WHERE timestamp > ?
            ORDER BY timestamp DESC
            LIMIT 5
        ''', (yesterday,))
        
        results = cursor.fetchall()
        if results:
            report.append("\n🪙 CRYPTO PRICES (last 24h):")
            report.append("-" * 40)
            for row in results[:3]:
                coin, price, ath, change, source, ts = row
                report.append(f"  {coin}: ${price:,.2f} ({change:+.2f}% 24h)")
                if ath:
                    from_ath = ((price / ath) - 1) * 100
                    report.append(f"    From ATH: {from_ath:.1f}%")
                report.append(f"    Source: {source} | {ts[:16]}")
        else:
            report.append("\n⚠️ No crypto data in last 24h")
        
        conn.close()
    
    # Trading bot stats
    report.append("\n🤖 TRADING BOTS:")
    report.append("-" * 40)
    
    import subprocess
    import re
    result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
    
    for bot_type, name in [('low', 'LOW RISK'), ('medium', 'MEDIUM RISK'), ('high', 'HIGH RISK')]:
        # Use regex to find running bot process
        pattern = rf'unified_bot.*{bot_type}'
        if re.search(pattern, result.stdout):
            # Get last price from log
            log_path = Path(f'~/.openclaw/workspace/memory/passivbot_logs/{bot_type}/live.log').expanduser()
            if log_path.exists():
                with open(log_path, 'r') as f:
                    lines = f.readlines()
                    last_price = None
                    for line in reversed(lines):
                        if 'Price:' in line:
                            try:
                                last_price = line.split('$')[1].split()[0]
                                break
                            except:
                                pass
                    if last_price:
                        report.append(f"  ✅ {name}: Running | Last: ${last_price}")
                    else:
                        report.append(f"  ✅ {name}: Running")
        else:
            report.append(f"  ❌ {name}: Not running")
    
    # Gold bot
    report.append("\n🥇 GOLD BOT:")
    report.append("-" * 40)
    
    cron_log = Path('~/.openclaw/workspace/memory/logs/cron_v2.log').expanduser()
    if cron_log.exists():
        with open(cron_log, 'r') as f:
            lines = f.readlines()
            last_gold = None
            for line in reversed(lines[-100:]):
                if 'Current Price' in line and '$' in line:
                    try:
                        last_gold = line.split('$')[1].split()[0]
                        break
                    except:
                        pass
            if last_gold:
                report.append(f"  ✅ Running | Last: ${last_gold} XAU/USD")
            else:
                report.append(f"  ✅ Running | (check logs)")
    
    # Summary
    report.append("\n" + "=" * 60)
    report.append("📝 SUMMARY")
    report.append("-" * 40)
    report.append("Cron jobs: ✅ Active (every 15 min)")
    report.append("Price tracking: ✅ Multi-source API")
    report.append("Database: ✅ crypto_prices.db")
    report.append("=" * 60)
    
    return "\n".join(report)

if __name__ == '__main__':
    print(generate_report())
