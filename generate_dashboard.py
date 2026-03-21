#!/usr/bin/env python3
"""
Generate HTML report for bot performance.
"""
import json
from datetime import datetime
from pathlib import Path
import sqlite3

DB_PATH = Path("~/.openclaw/workspace/memory/bot_monitor.db").expanduser()

def generate_html():
    """Generate HTML report."""
    
    # Read stats
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT SUM(pnl), COUNT(*) FROM trades')
    total_pnl, total_trades = cursor.fetchone()
    total_pnl = total_pnl or 0
    
    cursor.execute('SELECT COUNT(*) FROM trades WHERE pnl > 0')
    wins = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT * FROM positions WHERE status = "OPEN"')
    positions = cursor.fetchall()
    
    conn.close()
    
    initial = 12.0
    current = initial + total_pnl
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    pnl_pct = ((current / initial) - 1) * 100
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Bot Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M')}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #1a1a2e; color: #eee; }}
        .container {{ max-width: 800px; margin: 0 auto; }}
        .header {{ text-align: center; padding: 20px; background: #16213e; border-radius: 10px; margin-bottom: 20px; }}
        .card {{ background: #0f3460; padding: 20px; border-radius: 10px; margin-bottom: 15px; }}
        .stat {{ display: inline-block; margin: 10px 20px; text-align: center; }}
        .stat-value {{ font-size: 28px; font-weight: bold; }}
        .stat-label {{ font-size: 12px; color: #aaa; }}
        .positive {{ color: #4ecca3; }}
        .negative {{ color: #ff6b6b; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #333; }}
        th {{ background: #16213e; }}
        .badge {{ padding: 5px 10px; border-radius: 5px; font-size: 12px; }}
        .badge-long {{ background: #4ecca3; color: #000; }}
        .badge-short {{ background: #ff6b6b; color: #fff; }}
    </style>
    <meta http-equiv="refresh" content="30">
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Bot Monitor Dashboard</h1>
            <p>Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        
        <div class="card">
            <h2>💰 Balance</h2>
            <div class="stat">
                <div class="stat-value">${initial:.2f}</div>
                <div class="stat-label">Initial</div>
            </div>
            <div class="stat">
                <div class="stat-value">${current:.2f}</div>
                <div class="stat-label">Current</div>
            </div>
            <div class="stat">
                <div class="stat-value {'positive' if total_pnl >= 0 else 'negative'}">${total_pnl:+.2f}</div>
                <div class="stat-label">Total P&L ({pnl_pct:+.2f}%)</div>
            </div>
        </div>
        
        <div class="card">
            <h2>📈 Performance</h2>
            <div class="stat">
                <div class="stat-value">{total_trades}</div>
                <div class="stat-label">Total Trades</div>
            </div>
            <div class="stat">
                <div class="stat-value">{wins}</div>
                <div class="stat-label">Wins 🟢</div>
            </div>
            <div class="stat">
                <div class="stat-value">{total_trades - wins}</div>
                <div class="stat-label">Losses 🔴</div>
            </div>
            <div class="stat">
                <div class="stat-value">{win_rate:.1f}%</div>
                <div class="stat-label">Win Rate</div>
            </div>
        </div>
        
        <div class="card">
            <h2>📂 Open Positions ({len(positions)})</h2>
            {'<p>No open positions</p>' if not positions else '''
            <table>
                <tr>
                    <th>Symbol</th>
                    <th>Side</th>
                    <th>Entry Price</th>
                    <th>Size</th>
                    <th>P&L</th>
                </tr>
            '''}
            {''.join([f"<tr><td>{p[1]}</td><td><span class='badge badge-{p[2].lower()}'>{p[2]}</span></td><td>${p[3]:.2f}</td><td>${p[4]:.2f}</td><td class='{'positive' if p[7] >= 0 else 'negative'}'>${p[7]:.2f}</td></tr>" for p in positions]) if positions else ''}
            {'</table>' if positions else ''}
        </div>
        
        <div style="text-align: center; color: #666; margin-top: 30px;">
            <p>Auto-refresh every 30 seconds</p>
            <p>Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </div>
</body>
</html>
"""
    
    output_path = Path('~/.openclaw/workspace/memory/bot_dashboard.html').expanduser()
    with open(output_path, 'w') as f:
        f.write(html)
    
    print(f"✅ Dashboard generated: {output_path}")
    return output_path

if __name__ == '__main__':
    path = generate_html()
    print(f"\nOpen in browser: file://{path}")
