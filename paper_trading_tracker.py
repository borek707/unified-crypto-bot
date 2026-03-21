#!/usr/bin/env python3
"""
Paper Trading Tracker - symuluje handel bez prawdziwych pieniędzy.
Zapisuje "paper trades" do bazy SQLite.
"""

import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path

DB_PATH = Path("~/.openclaw/workspace/memory/paper_trading.db").expanduser()

class PaperTradingTracker:
    def __init__(self, initial_balance=100.0):
        self.db_path = DB_PATH
        self.initial_balance = initial_balance
        self.init_database()
        
    def init_database(self):
        """Initialize paper trading database."""
        os.makedirs(self.db_path.parent, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS paper_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                symbol TEXT,
                side TEXT,
                entry_price REAL,
                exit_price REAL,
                size REAL,
                pnl REAL,
                pnl_pct REAL,
                status TEXT,
                notes TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS paper_balance (
                id INTEGER PRIMARY KEY,
                balance REAL,
                total_pnl REAL,
                win_rate REAL,
                updated_at TEXT
            )
        ''')
        
        # Insert initial balance if not exists
        cursor.execute('SELECT COUNT(*) FROM paper_balance')
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO paper_balance (id, balance, total_pnl, win_rate, updated_at)
                VALUES (1, ?, 0.0, 0.0, ?)
            ''', (self.initial_balance, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def record_trade(self, symbol, side, entry_price, exit_price, size, status='CLOSED'):
        """Record a paper trade."""
        pnl = (exit_price - entry_price) * size if side == 'LONG' else (entry_price - exit_price) * size
        pnl_pct = (pnl / (entry_price * size)) * 100
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO paper_trades (timestamp, symbol, side, entry_price, exit_price, size, pnl, pnl_pct, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (datetime.now().isoformat(), symbol, side, entry_price, exit_price, size, pnl, pnl_pct, status))
        
        conn.commit()
        conn.close()
        
        return {'pnl': pnl, 'pnl_pct': pnl_pct}
    
    def get_stats(self):
        """Get paper trading statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*), SUM(pnl), AVG(pnl) FROM paper_trades WHERE status = "CLOSED"')
        total_trades, total_pnl, avg_pnl = cursor.fetchone()
        
        cursor.execute('SELECT COUNT(*) FROM paper_trades WHERE pnl > 0')
        winning_trades = cursor.fetchone()[0]
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        cursor.execute('SELECT balance FROM paper_balance WHERE id = 1')
        current_balance = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_trades': total_trades or 0,
            'total_pnl': total_pnl or 0,
            'avg_pnl': avg_pnl or 0,
            'win_rate': win_rate,
            'current_balance': current_balance,
            'initial_balance': self.initial_balance
        }
    
    def report(self):
        """Print paper trading report."""
        stats = self.get_stats()
        
        print("\n" + "="*50)
        print("📊 PAPER TRADING REPORT")
        print("="*50)
        print(f"Initial Balance: ${stats['initial_balance']:.2f}")
        print(f"Current Balance: ${stats['current_balance']:.2f}")
        print(f"Total P&L:       ${stats['total_pnl']:.2f}")
        print(f"Total Trades:    {stats['total_trades']}")
        print(f"Win Rate:        {stats['win_rate']:.1f}%")
        print(f"Avg P&L/Trade:   ${stats['avg_pnl']:.2f}")
        print("="*50)

if __name__ == '__main__':
    tracker = PaperTradingTracker(initial_balance=12.0)
    tracker.report()
