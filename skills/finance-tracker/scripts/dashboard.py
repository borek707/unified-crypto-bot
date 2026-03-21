#!/usr/bin/env python3
"""
Trading Dashboard for Gold Bot
Simple web interface to monitor performance
"""
import http.server
import socketserver
import sqlite3
import json
import os
from datetime import datetime, timedelta
from urllib.parse import parse_qs

DB_PATH = os.path.expanduser("~/.openclaw/workspace/memory/trading.db")
PORT = 8888

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>🥇 Gold Trading Bot Dashboard</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #fff;
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { 
            text-align: center; 
            margin-bottom: 30px;
            background: linear-gradient(90deg, #ffd700, #ffed4e);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 2.5em;
        }
        .status-bar {
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }
        .status-item {
            background: rgba(255,255,255,0.05);
            padding: 15px 25px;
            border-radius: 10px;
            text-align: center;
        }
        .status-label { color: #888; font-size: 0.85em; margin-bottom: 5px; }
        .status-value { font-size: 1.5em; font-weight: bold; }
        .green { color: #4ade80; }
        .red { color: #f87171; }
        .gold { color: #ffd700; }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .card {
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 20px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .card h2 {
            font-size: 1.1em;
            margin-bottom: 15px;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .metric {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .metric:last-child { border-bottom: none; }
        .metric-label { color: #aaa; }
        .metric-value { font-weight: bold; }
        .position {
            background: rgba(255,215,0,0.1);
            border-left: 3px solid #ffd700;
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 0 10px 10px 0;
        }
        .position-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
        }
        .position-type {
            font-weight: bold;
            font-size: 1.2em;
        }
        .position-type.buy { color: #4ade80; }
        .position-type.sell { color: #f87171; }
        .position-details {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            font-size: 0.9em;
            color: #aaa;
        }
        .trade-row {
            display: flex;
            justify-content: space-between;
            padding: 12px;
            margin-bottom: 8px;
            background: rgba(255,255,255,0.03);
            border-radius: 8px;
            align-items: center;
        }
        .trade-signal {
            font-weight: bold;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85em;
        }
        .trade-signal.buy { background: rgba(74,222,128,0.2); color: #4ade80; }
        .trade-signal.sell { background: rgba(248,113,113,0.2); color: #f87171; }
        .trade-pnl { font-weight: bold; }
        .trade-pnl.positive { color: #4ade80; }
        .trade-pnl.negative { color: #f87171; }
        .refresh-btn {
            display: block;
            margin: 30px auto;
            padding: 15px 40px;
            background: linear-gradient(90deg, #ffd700, #ffed4e);
            color: #1a1a2e;
            border: none;
            border-radius: 30px;
            font-size: 1.1em;
            font-weight: bold;
            cursor: pointer;
            transition: transform 0.2s;
        }
        .refresh-btn:hover { transform: scale(1.05); }
        .empty-state {
            text-align: center;
            padding: 40px;
            color: #666;
        }
        .timestamp {
            text-align: center;
            color: #666;
            margin-top: 30px;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🥇 Gold Trading Bot</h1>
        
        <div class="status-bar">
            <div class="status-item">
                <div class="status-label">STATUS</div>
                <div class="status-value green">● ACTIVE</div>
            </div>
            <div class="status-item">
                <div class="status-label">OPEN POSITIONS</div>
                <div class="status-value gold">{open_count}</div>
            </div>
            <div class="status-item">
                <div class="status-label">LAST UPDATE</div>
                <div class="status-value">{last_update}</div>
            </div>
        </div>

        <div class="grid">
            <div class="card">
                <h2>📊 7-Day Performance</h2>
                {stats_7d_html}
            </div>
            
            <div class="card">
                <h2>📈 30-Day Performance</h2>
                {stats_30d_html}
            </div>
            
            <div class="card">
                <h2>🎯 Key Metrics</h2>
                <div class="metric">
                    <span class="metric-label">Total Trades</span>
                    <span class="metric-value">{total_trades}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Win Rate</span>
                    <span class="metric-value {win_rate_class}">{win_rate}%</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Profit Factor</span>
                    <span class="metric-value {pf_class}">{profit_factor}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Total P&L</span>
                    <span class="metric-value {pnl_class}">${total_pnl}</span>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>📍 Open Positions</h2>
            {open_positions_html}
        </div>

        <div class="card">
            <h2>🕐 Recent Trades</h2>
            {recent_trades_html}
        </div>

        <button class="refresh-btn" onclick="location.reload()">🔄 Refresh Dashboard</button>
        
        <div class="timestamp">Dashboard generated: {timestamp}</div>
    </div>
</body>
</html>
"""

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
        SELECT id, timestamp, signal, entry_price, stop_loss, take_profit, session, notes
        FROM trades 
        WHERE status = 'OPEN'
        ORDER BY timestamp DESC
    ''')
    
    columns = [description[0] for description in cursor.description]
    positions = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return positions

def get_recent_trades(limit=10):
    conn = get_db_connection()
    if not conn:
        return []
    
    cursor = conn.cursor()
    cursor.execute('''
        SELECT timestamp, signal, entry_price, exit_price, pnl, status
        FROM trades 
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (limit,))
    
    columns = [description[0] for description in cursor.description]
    trades = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return trades

def format_stats_html(stats, title):
    if not stats:
        return '<div class="empty-state">No data available</div>'
    
    win_rate_class = 'green' if stats['win_rate'] >= 45 else 'red'
    pf_class = 'green' if stats['profit_factor'] >= 1.5 else 'red'
    pnl_class = 'green' if stats['total_pnl'] >= 0 else 'red'
    
    return f"""
        <div class="metric">
            <span class="metric-label">Trades</span>
            <span class="metric-value">{stats['total']}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Win Rate</span>
            <span class="metric-value {win_rate_class}">{stats['win_rate']}%</span>
        </div>
        <div class="metric">
            <span class="metric-label">Profit Factor</span>
            <span class="metric-value {pf_class}">{stats['profit_factor']}</span>
        </div>
        <div class="metric">
            <span class="metric-label">P&L</span>
            <span class="metric-value {pnl_class}">${stats['total_pnl']}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Avg Win</span>
            <span class="metric-value green">+${stats['avg_win']}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Avg Loss</span>
            <span class="metric-value red">-${abs(stats['avg_loss'])}</span>
        </div>
    """

def format_positions_html(positions):
    if not positions:
        return '<div class="empty-state">No open positions</div>'
    
    html = ""
    for pos in positions:
        signal_class = 'buy' if pos['signal'] == 'BUY' else 'sell'
        html += f"""
            <div class="position">
                <div class="position-header">
                    <span class="position-type {signal_class}">{pos['signal']} #{pos['id']}</span>
                    <span>{pos['session']}</span>
                </div>
                <div class="position-details">
                    <div>Entry: <strong>${pos['entry_price']}</strong></div>
                    <div>SL: <span class="red">${pos['stop_loss']}</span></div>
                    <div>TP: <span class="green">${pos['take_profit']}</span></div>
                </div>
                <div style="margin-top: 10px; color: #666; font-size: 0.85em;">
                    {pos['timestamp']} | {pos['notes'] or 'No notes'}
                </div>
            </div>
        """
    return html

def format_trades_html(trades):
    if not trades:
        return '<div class="empty-state">No trades yet</div>'
    
    html = ""
    for trade in trades:
        signal_class = 'buy' if trade['signal'] == 'BUY' else 'sell'
        
        if trade['status'] == 'CLOSED' and trade['pnl'] is not None:
            pnl_class = 'positive' if trade['pnl'] > 0 else 'negative'
            pnl_text = f"+${trade['pnl']:.2f}" if trade['pnl'] > 0 else f"-${abs(trade['pnl']):.2f}"
            result_html = f'<span class="trade-pnl {pnl_class}">{pnl_text}</span>'
        else:
            result_html = f'<span style="color: #ffd700;">● OPEN</span>'
        
        html += f"""
            <div class="trade-row">
                <div>
                    <span class="trade-signal {signal_class}">{trade['signal']}</span>
                    <span style="margin-left: 10px; color: #888;">${trade['entry_price']}</span>
                </div>
                <div style="color: #666; font-size: 0.85em;">
                    {trade['timestamp'].split(' ')[0]}
                </div>
                {result_html}
            </div>
        """
    return html

class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        stats_7d = get_stats(7)
        stats_30d = get_stats(30)
        open_positions = get_open_positions()
        recent_trades = get_recent_trades(10)
        
        # Calculate overall stats
        total_trades = (stats_7d['total'] if stats_7d else 0) + (stats_30d['total'] if stats_30d else 0)
        win_rate = stats_30d['win_rate'] if stats_30d else (stats_7d['win_rate'] if stats_7d else 0)
        profit_factor = stats_30d['profit_factor'] if stats_30d else (stats_7d['profit_factor'] if stats_7d else 0)
        total_pnl = (stats_7d['total_pnl'] if stats_7d else 0) + (stats_30d['total_pnl'] if stats_30d else 0)
        
        html = HTML_TEMPLATE.format(
            open_count=len(open_positions),
            last_update=datetime.now().strftime('%H:%M'),
            stats_7d_html=format_stats_html(stats_7d, "7-Day"),
            stats_30d_html=format_stats_html(stats_30d, "30-Day"),
            total_trades=total_trades,
            win_rate=win_rate,
            win_rate_class='green' if win_rate >= 45 else 'red',
            profit_factor=profit_factor,
            pf_class='green' if profit_factor >= 1.5 else 'red',
            total_pnl=round(total_pnl, 2),
            pnl_class='green' if total_pnl >= 0 else 'red',
            open_positions_html=format_positions_html(open_positions),
            recent_trades_html=format_trades_html(recent_trades),
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())
    
    def log_message(self, format, *args):
        pass  # Suppress logs

def main():
    with socketserver.TCPServer(("", PORT), DashboardHandler) as httpd:
        print(f"🚀 Dashboard running at: http://localhost:{PORT}")
        print("Press Ctrl+C to stop")
        httpd.serve_forever()

if __name__ == "__main__":
    main()
