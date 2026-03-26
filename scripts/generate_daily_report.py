#!/usr/bin/env python3
"""
Daily Report Generator - generuje wypełniony raport dzienny
Uruchamiany przez cron o 8:00 rano
"""

import json
import re
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

def get_bot_stats(bot_type):
    """Extract trading stats from bot logs - TODAY only."""
    log_path = Path(f'~/.openclaw/workspace/memory/passivbot_logs/{bot_type}/live.log').expanduser()
    
    if not log_path.exists():
        return None
    
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    stats = {
        'trades': [],
        'open_positions': [],
        'total_pnl': 0,
        'wins': 0,
        'losses': 0,
        'last_price': None,
        'status': 'unknown'
    }
    
    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        # Check if bot is running (look at last 100 lines)
        for line in reversed(lines[-100:]):
            if 'Unified Bot initialized' in line:
                stats['status'] = 'running'
                break
            if 'ERROR' in line or 'CRITICAL' in line:
                stats['status'] = 'error'
                break
        
        # Extract trades from TODAY only
        for line in lines:
            # Only process lines from today
            if not line.startswith(today_str):
                continue
            
            # OPEN positions - only track today's opens
            open_match = re.search(r'OPEN (\w+).*\$(\d+\.\d+).*@ \$(\d+\.\d+).*TP @ \$(\d+\.\d+)', line)
            if open_match:
                stats['open_positions'].append({
                    'type': open_match.group(1),
                    'amount': float(open_match.group(2)),
                    'entry': float(open_match.group(3)),
                    'tp': float(open_match.group(4)),
                    'timestamp': line[:19] if len(line) > 20 else 'unknown'
                })
            
            # CLOSED trades with PnL from today
            close_match = re.search(r'CLOSE.*PnL \$([\-\d\.]+)', line)
            if close_match:
                pnl = float(close_match.group(1))
                stats['trades'].append({'pnl': pnl, 'line': line[:50]})
                stats['total_pnl'] += pnl
                if pnl > 0:
                    stats['wins'] += 1
                else:
                    stats['losses'] += 1
            
            # Last price
            price_match = re.search(r'Hyperliquid price: \$(\d+\.\d+)', line)
            if price_match:
                stats['last_price'] = float(price_match.group(1))
        
        # Get currently open positions (last open that wasn't closed)
        # This is simplified - assume last open is still open if no close after it
        if stats['open_positions']:
            stats['open_positions'] = [stats['open_positions'][-1]]  # Only show most recent
        
        return stats
    except Exception as e:
        return {'error': str(e), 'status': 'error'}


def get_crypto_prices():
    """Get latest crypto prices from database."""
    db_path = Path('~/.openclaw/workspace/memory/crypto_prices.db').expanduser()
    
    if not db_path.exists():
        return []
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        cursor.execute('''
            SELECT coin, price, ath, change_24h, source, timestamp
            FROM crypto_prices
            WHERE timestamp > ?
            ORDER BY timestamp DESC
            LIMIT 5
        ''', (yesterday,))
        
        results = cursor.fetchall()
        conn.close()
        
        prices = []
        for row in results:
            prices.append({
                'coin': row[0],
                'price': row[1],
                'ath': row[2],
                'change_24h': row[3],
                'source': row[4],
                'timestamp': row[5][:16] if row[5] else 'unknown'
            })
        return prices
    except Exception as e:
        return [{'error': str(e)}]


def get_gold_price():
    """Get latest gold price from gold_trading_bot.py directly."""
    try:
        # Run the gold bot and capture output
        result = subprocess.run(
            ['python3', str(Path('~/.openclaw/workspace/skills/finance-tracker/scripts/gold_trading_bot.py').expanduser())],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Look for current price in output
        for line in result.stdout.split('\n'):
            if 'Current Price:' in line and '$' in line:
                match = re.search(r'\$(\d+\.?\d*)', line)
                if match:
                    price = float(match.group(1))
                    # Sanity check - if price > 4000 it's the bugged Yahoo data
                    if price < 4000:
                        return price
        
        # Fallback to checking cached data
        cache_files = list(Path('~/.openclaw/workspace/.cache').expanduser().glob('gold_*.json'))
        if cache_files:
            # Get most recent cache file
            newest = max(cache_files, key=lambda p: p.stat().st_mtime)
            with open(newest, 'r') as f:
                data = json.load(f)
                candles = data.get('data', {}).get('candles', [])
                if candles:
                    last_close = candles[-1].get('close', 0)
                    if last_close and last_close < 4000:
                        return last_close
        
        return None
    except:
        return None


def generate_filled_report():
    """Generate a filled daily report."""
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    
    report_lines = []
    report_lines.append(f"# Raport Dzienny - {today.strftime('%Y-%m-%d')}")
    report_lines.append("")
    report_lines.append("## Co zrobiliśmy dzisiaj")
    report_lines.append("")
    
    # Bot stats
    bots = ['low', 'medium', 'high']
    bot_names = {'low': 'LOW RISK (2x)', 'medium': 'MEDIUM RISK (3x)', 'high': 'HIGH RISK (5x)'}
    
    total_pnl = 0
    total_trades = 0
    open_positions = []
    
    for bot in bots:
        stats = get_bot_stats(bot)
        if stats:
            bot_pnl = stats.get('total_pnl', 0)
            bot_trades = len(stats.get('trades', []))
            total_pnl += bot_pnl
            total_trades += bot_trades
            
            if stats.get('open_positions'):
                for pos in stats['open_positions']:
                    open_positions.append(f"{bot_names[bot]}: {pos['type']} @ ${pos['entry']:,.2f}")
            
            if bot_trades > 0:
                report_lines.append(f"- **[{bot.upper()}]** {bot_trades} trades, PnL: ${bot_pnl:+.2f}")
            else:
                report_lines.append(f"- **[{bot.upper()}]** No closed trades today")
    
    if total_trades == 0:
        report_lines.append("- Brak zamkniętych transakcji dzisiaj")
    else:
        report_lines.append(f"")
        report_lines.append(f"**Podsumowanie botów:** {total_trades} transakcji, total PnL: ${total_pnl:+.2f}")
    
    report_lines.append("")
    report_lines.append("## Incydenty / Problemy")
    report_lines.append("| Godzina | Problem | Severity | Status |")
    report_lines.append("|---------|---------|----------|--------|")
    
    # Check for issues
    issues_found = False
    for bot in bots:
        stats = get_bot_stats(bot)
        if stats and stats.get('status') == 'error':
            report_lines.append(f"| {today.strftime('%H:%M')} | {bot.upper()} bot error | medium | 🔴 open |")
            issues_found = True
    
    if not issues_found:
        report_lines.append("| - | Brak incydentów | - | ✅ all good |")
    
    report_lines.append("")
    report_lines.append("## Auto-Fix próby")
    report_lines.append("| Problem | Wynik | Szczegóły |")
    report_lines.append("|---------|-------|-----------|")
    report_lines.append("| - | - | - |")
    
    report_lines.append("")
    report_lines.append("## Co nie działało (i dlaczego)")
    report_lines.append("- ")
    
    report_lines.append("")
    report_lines.append("## Zmiany / Nowe funkcje")
    report_lines.append("- ")
    
    report_lines.append("")
    report_lines.append("## Decyzje podjęte")
    report_lines.append("- ")
    
    report_lines.append("")
    report_lines.append("## Do zrobienia jutro")
    report_lines.append("- [ ] Monitorować boty")
    if open_positions:
        report_lines.append("- [ ] Sprawdzić otwarte pozycje:")
        for pos in open_positions:
            report_lines.append(f"  - {pos}")
    report_lines.append("- [ ] ")
    
    report_lines.append("")
    report_lines.append("## Wnioski / Lekcje")
    report_lines.append("- ")
    
    # Market data section
    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")
    report_lines.append("## 📊 Dane rynkowe")
    report_lines.append("")
    
    # Crypto prices
    prices = get_crypto_prices()
    if prices and 'error' not in prices[0]:
        report_lines.append("### Ceny Crypto")
        seen = set()
        for p in prices:
            if p['coin'] in seen:
                continue
            seen.add(p['coin'])
            from_ath = ((p['price'] / p['ath']) - 1) * 100 if p['ath'] else 0
            report_lines.append(f"- **{p['coin']}**: ${p['price']:,.2f} ({p['change_24h']:+.2f}% 24h) | ATH: {from_ath:.1f}%")
            if len(seen) >= 3:
                break
    
    # Stock prices (new)
    try:
        conn = sqlite3.connect(Path('~/.openclaw/workspace/memory/crypto_prices.db').expanduser())
        cursor = conn.cursor()
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        cursor.execute('''
            SELECT symbol, name, price, change_percent, timestamp
            FROM stock_prices
            WHERE timestamp > ?
            ORDER BY timestamp DESC
            LIMIT 5
        ''', (yesterday,))
        stocks = cursor.fetchall()
        conn.close()
        
        if stocks:
            report_lines.append("")
            report_lines.append("### Akcje / Indeksy")
            seen = set()
            for row in stocks:
                symbol, name, price, change, ts = row
                if symbol in seen:
                    continue
                seen.add(symbol)
                report_lines.append(f"- **{name}** ({symbol}): ${price:,.2f} ({change:+.2f}%)")
                if len(seen) >= 2:
                    break
    except:
        pass
    
    # Gold price
    gold = get_gold_price()
    if gold:
        report_lines.append("")
        report_lines.append("### Złoto (XAU/USD)")
        report_lines.append(f"- **Cena**: ${gold:,.2f}")
    
    report_lines.append("")
    report_lines.append("---")
    report_lines.append(f"*Raport wygenerowany: {today.strftime('%Y-%m-%d %H:%M')} UTC*")
    report_lines.append("*Auto-review: `python3 scripts/daily_review.py`*")
    
    return "\n".join(report_lines)


def save_report():
    """Generate and save the daily report."""
    report = generate_filled_report()
    
    today = datetime.now().strftime('%Y-%m-%d')
    report_path = Path(f'~/.openclaw/workspace/memory/{today}.md').expanduser()
    
    with open(report_path, 'w') as f:
        f.write(report)
    
    print(f"✅ Daily report saved to: {report_path}")
    return report_path


if __name__ == '__main__':
    save_report()
