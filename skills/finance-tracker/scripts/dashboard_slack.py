#!/usr/bin/env python3
"""
Generate dashboard report as text/JSON for Slack
"""
import sqlite3
import json
import os
from datetime import datetime, timedelta

DB_PATH = os.path.expanduser("~/.openclaw/workspace/memory/trading.db")

def get_db_connection():
    if not os.path.exists(DB_PATH):
        return None
    return sqlite3.connect(DB_PATH)

def get_stats(days=7):
    conn = get_db_connection()
    if not conn:
        return None
    
    cursor = conn.cursor()
    since = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    cursor.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winners,
            SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losers,
            SUM(pnl) as total_pnl,
            AVG(CASE WHEN pnl > 0 THEN pnl END) as avg_win,
            AVG(CASE WHEN pnl < 0 THEN pnl END) as avg_loss
        FROM trades 
        WHERE date >= ? AND status = 'CLOSED'
    ''', (since,))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row or row[0] == 0:
        return None
    
    total, winners, losers, total_pnl, avg_win, avg_loss = row
    win_rate = (winners / total * 100) if total > 0 else 0
    
    total_wins = winners * (avg_win or 0)
    total_losses = abs(losers * (avg_loss or 0))
    profit_factor = total_wins / total_losses if total_losses > 0 else 0
    
    return {
        "total": total,
        "winners": winners or 0,
        "losers": losers or 0,
        "win_rate": round(win_rate, 1),
        "total_pnl": round(total_pnl or 0, 2),
        "profit_factor": round(profit_factor, 2),
        "avg_win": round(avg_win or 0, 2),
        "avg_loss": round(avg_loss or 0, 2)
    }

def get_open_positions():
    conn = get_db_connection()
    if not conn:
        return []
    
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, timestamp, signal, entry_price, stop_loss, take_profit, session
        FROM trades 
        WHERE status = 'OPEN'
        ORDER BY timestamp DESC
    ''')
    
    columns = [description[0] for description in cursor.description]
    positions = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return positions

def get_recent_trades(limit=5):
    conn = get_db_connection()
    if not conn:
        return []
    
    cursor = conn.cursor()
    cursor.execute('''
        SELECT timestamp, signal, entry_price, pnl, status
        FROM trades 
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (limit,))
    
    columns = [description[0] for description in cursor.description]
    trades = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return trades

def generate_slack_report():
    """Generate a formatted report for Slack."""
    stats_7d = get_stats(7)
    stats_30d = get_stats(30)
    open_positions = get_open_positions()
    recent_trades = get_recent_trades(5)
    
    report = f"""
🥇 *GOLD TRADING BOT - DASHBOARD*
_Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}_

"""
    
    # Open positions
    if open_positions:
        report += "📍 *OPEN POSITIONS*\n"
        for pos in open_positions:
            emoji = "🟢" if pos['signal'] == 'BUY' else "🔴"
            report += f"{emoji} *{pos['signal']}* #{pos['id']} | Entry: ${pos['entry_price']} | SL: ${pos['stop_loss']} | TP: ${pos['take_profit']}\n"
        report += "\n"
    else:
        report += "📍 *OPEN POSITIONS:* None\n\n"
    
    # 7-day stats
    if stats_7d:
        wr_emoji = "✅" if stats_7d['win_rate'] >= 45 else "⚠️"
        pf_emoji = "✅" if stats_7d['profit_factor'] >= 1.5 else "⚠️"
        pnl_emoji = "✅" if stats_7d['total_pnl'] >= 0 else "🔴"
        
        report += f"""📊 *7-DAY PERFORMANCE*
{wr_emoji} Win Rate: *{stats_7d['win_rate']}%* ({stats_7d['winners']}W/{stats_7d['losers']}L)
{pf_emoji} Profit Factor: *{stats_7d['profit_factor']}*
{pnl_emoji} Total P&L: *${stats_7d['total_pnl']}*
💰 Avg Win: +${stats_7d['avg_win']} | Avg Loss: -${abs(stats_7d['avg_loss'])}

"""
    else:
        report += "📊 *7-DAY PERFORMANCE:* No data yet\n\n"
    
    # 30-day stats
    if stats_30d:
        report += f"""📈 *30-DAY PERFORMANCE*
Win Rate: *{stats_30d['win_rate']}%* | Profit Factor: *{stats_30d['profit_factor']}* | P&L: *${stats_30d['total_pnl']}*

"""
    
    # Recent trades
    if recent_trades:
        report += "🕐 *RECENT TRADES*\n"
        for trade in recent_trades:
            emoji = "🟢" if trade['signal'] == 'BUY' else "🔴"
            date = trade['timestamp'].split(' ')[0]
            if trade['status'] == 'CLOSED' and trade['pnl'] is not None:
                pnl_emoji = "✅" if trade['pnl'] > 0 else "🔴"
                pnl_str = f"+${trade['pnl']:.2f}" if trade['pnl'] > 0 else f"-${abs(trade['pnl']):.2f}"
                report += f"{emoji} {trade['signal']} ${trade['entry_price']} | {pnl_emoji} {pnl_str} | {date}\n"
            else:
                report += f"{emoji} {trade['signal']} ${trade['entry_price']} | 🟡 OPEN | {date}\n"
    
    report += f"""

🤖 *BOT STATUS:* ACTIVE
Strategy: First Candle 15m XAU/USD
Next Signal Check: Top of next hour (8:00, 13:00, 16:00 GMT)
"""
    
    return report

def generate_json_report():
    """Generate JSON report for programmatic access."""
    return {
        "timestamp": datetime.now().isoformat(),
        "stats_7d": get_stats(7),
        "stats_30d": get_stats(30),
        "open_positions": get_open_positions(),
        "recent_trades": get_recent_trades(10)
    }

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--json":
        print(json.dumps(generate_json_report(), indent=2))
    else:
        print(generate_slack_report())
