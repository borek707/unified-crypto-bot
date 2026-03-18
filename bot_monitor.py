#!/usr/bin/env python3
"""
Bot Monitor - śledzenie zysków, strat i pozycji w czasie rzeczywistym.
"""
import json
import sqlite3
import os
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional

DB_PATH = Path("~/.openclaw/workspace/memory/bot_monitor.db").expanduser()
LOG_DIR = Path("~/.openclaw/workspace/memory/passivbot_logs").expanduser()

@dataclass
class Position:
    symbol: str
    side: str  # LONG, SHORT
    entry_price: float
    size: float
    leverage: float
    open_time: str
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    status: str = "OPEN"

@dataclass
class Trade:
    timestamp: str
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    pnl_pct: float
    status: str

class BotMonitor:
    def __init__(self, initial_balance: float = 12.0):
        self.db_path = DB_PATH
        self.initial_balance = initial_balance
        self.init_database()
        
    def init_database(self):
        """Initialize monitoring database."""
        os.makedirs(self.db_path.parent, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Positions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                side TEXT,
                entry_price REAL,
                size REAL,
                leverage REAL,
                open_time TEXT,
                unrealized_pnl REAL DEFAULT 0,
                realized_pnl REAL DEFAULT 0,
                status TEXT DEFAULT 'OPEN'
            )
        ''')
        
        # Trades history
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                symbol TEXT,
                side TEXT,
                entry_price REAL,
                exit_price REAL,
                size REAL,
                pnl REAL,
                pnl_pct REAL,
                status TEXT
            )
        ''')
        
        # Daily P&L tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_pnl (
                date TEXT PRIMARY KEY,
                starting_balance REAL,
                ending_balance REAL,
                total_pnl REAL,
                num_trades INTEGER,
                win_count INTEGER,
                loss_count INTEGER
            )
        ''')
        
        # Bot status
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_status (
                id INTEGER PRIMARY KEY,
                last_update TEXT,
                current_trend TEXT,
                active_strategy TEXT,
                total_positions INTEGER,
                total_trades INTEGER,
                total_pnl REAL
            )
        ''')
        
        conn.commit()
        conn.close()
        
    def record_position(self, position: Position):
        """Record new position."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO positions (symbol, side, entry_price, size, leverage, open_time, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (position.symbol, position.side, position.entry_price, position.size, 
              position.leverage, position.open_time, position.status))
        
        conn.commit()
        conn.close()
        
    def close_position(self, position_id: int, exit_price: float, pnl: float):
        """Close position and record P&L."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE positions 
            SET status = 'CLOSED', realized_pnl = ?, exit_price = ?
            WHERE id = ?
        ''', (pnl, exit_price, position_id))
        
        conn.commit()
        conn.close()
        
    def record_trade(self, trade: Trade):
        """Record completed trade."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO trades (timestamp, symbol, side, entry_price, exit_price, size, pnl, pnl_pct, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (trade.timestamp, trade.symbol, trade.side, trade.entry_price,
              trade.exit_price, trade.size, trade.pnl, trade.pnl_pct, trade.status))
        
        conn.commit()
        conn.close()
        
    def get_open_positions(self) -> List[dict]:
        """Get all open positions."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM positions WHERE status = 'OPEN' ORDER BY open_time DESC
        ''')
        
        columns = [description[0] for description in cursor.description]
        positions = []
        
        for row in cursor.fetchall():
            positions.append(dict(zip(columns, row)))
        
        conn.close()
        return positions
        
    def get_stats(self) -> dict:
        """Get trading statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total trades
        cursor.execute('SELECT COUNT(*), SUM(pnl) FROM trades')
        total_trades, total_pnl = cursor.fetchone()
        
        # Win/Loss count
        cursor.execute('SELECT COUNT(*) FROM trades WHERE pnl > 0')
        wins = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM trades WHERE pnl < 0')
        losses = cursor.fetchone()[0]
        
        # Open positions
        cursor.execute('SELECT COUNT(*), SUM(size) FROM positions WHERE status = "OPEN"')
        open_count, open_value = cursor.fetchone()
        
        # Today's P&L
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('SELECT SUM(pnl) FROM trades WHERE timestamp LIKE ?', (f'{today}%',))
        today_pnl = cursor.fetchone()[0] or 0
        
        conn.close()
        
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        current_balance = self.initial_balance + (total_pnl or 0)
        
        return {
            'initial_balance': self.initial_balance,
            'current_balance': current_balance,
            'total_pnl': total_pnl or 0,
            'total_pnl_pct': ((current_balance / self.initial_balance) - 1) * 100,
            'today_pnl': today_pnl,
            'total_trades': total_trades or 0,
            'wins': wins or 0,
            'losses': losses or 0,
            'win_rate': win_rate,
            'open_positions': open_count or 0,
            'open_value': open_value or 0
        }
        
    def display_dashboard(self):
        """Display live dashboard."""
        stats = self.get_stats()
        positions = self.get_open_positions()
        
        print("\n" + "="*70)
        print("📊 BOT MONITOR DASHBOARD")
        print("="*70)
        print(f"Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Balance section
        print("💰 BALANCE")
        print(f"   Initial:    ${stats['initial_balance']:.2f}")
        print(f"   Current:    ${stats['current_balance']:.2f}")
        pnl_emoji = "🟢" if stats['total_pnl'] >= 0 else "🔴"
        print(f"   Total P&L:  {pnl_emoji} ${stats['total_pnl']:.2f} ({stats['total_pnl_pct']:+.2f}%)")
        print(f"   Today P&L:  ${stats['today_pnl']:+.2f}")
        print()
        
        # Performance section
        print("📈 PERFORMANCE")
        print(f"   Total Trades: {stats['total_trades']}")
        print(f"   Wins:         {stats['wins']} 🟢")
        print(f"   Losses:       {stats['losses']} 🔴")
        print(f"   Win Rate:     {stats['win_rate']:.1f}%")
        print()
        
        # Open positions
        print(f"📂 OPEN POSITIONS ({stats['open_positions']})")
        if positions:
            print(f"   {'Symbol':<10} {'Side':<8} {'Entry':<12} {'Size':<10} {'P&L':<12}")
            print("   " + "-"*52)
            for pos in positions:
                pnl_emoji = "🟢" if pos['unrealized_pnl'] >= 0 else "🔴"
                print(f"   {pos['symbol']:<10} {pos['side']:<8} ${pos['entry_price']:<11.2f} ${pos['size']:<9.2f} {pnl_emoji} ${pos['unrealized_pnl']:.2f}")
        else:
            print("   No open positions")
        print()
        
        print("="*70)
        
    def export_report(self, filename: str = None):
        """Export trading report."""
        if filename is None:
            filename = f"trading_report_{datetime.now().strftime('%Y%m%d')}.json"
        
        filepath = Path('~/.openclaw/workspace/memory/backtest_results').expanduser() / filename
        
        stats = self.get_stats()
        positions = self.get_open_positions()
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'statistics': stats,
            'open_positions': positions
        }
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"✅ Report exported to: {filepath}")

if __name__ == '__main__':
    import sys
    
    monitor = BotMonitor(initial_balance=12.0)
    
    if len(sys.argv) > 1:
        if sys.argv[1] == 'export':
            monitor.export_report()
        elif sys.argv[1] == 'stats':
            import json
            print(json.dumps(monitor.get_stats(), indent=2))
    else:
        monitor.display_dashboard()
