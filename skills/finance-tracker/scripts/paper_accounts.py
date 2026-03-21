#!/usr/bin/env python3
"""
Paper Trading Configuration - 3 Account Sizes
"""
import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.expanduser("~/.openclaw/workspace/memory/trading.db")

def init_paper_accounts():
    """Initialize 3 paper trading accounts with different sizes."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create accounts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            initial_balance REAL,
            current_balance REAL,
            risk_per_trade REAL,
            max_positions INTEGER,
            active BOOLEAN DEFAULT 1,
            created_at TEXT
        )
    ''')
    
    # Check if accounts exist
    cursor.execute("SELECT COUNT(*) FROM accounts")
    if cursor.fetchone()[0] > 0:
        print("Paper accounts already initialized")
        conn.close()
        return
    
    # Create 3 paper trading accounts
    accounts = [
        {
            "name": "SMALL ($1K)",
            "initial": 1000.0,
            "risk": 0.02,  # 2% risk
            "max_pos": 1
        },
        {
            "name": "MEDIUM ($5K)", 
            "initial": 5000.0,
            "risk": 0.015,  # 1.5% risk
            "max_pos": 2
        },
        {
            "name": "STANDARD ($10K)",
            "initial": 10000.0,
            "risk": 0.01,  # 1% risk
            "max_pos": 3
        }
    ]
    
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    for acc in accounts:
        cursor.execute('''
            INSERT INTO accounts (name, initial_balance, current_balance, 
                                risk_per_trade, max_positions, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (acc['name'], acc['initial'], acc['initial'], 
              acc['risk'], acc['max_pos'], now))
    
    conn.commit()
    conn.close()
    print("✅ 3 paper trading accounts created:")
    print("   - SMALL: $1,000 (2% risk, 1 position max)")
    print("   - MEDIUM: $5,000 (1.5% risk, 2 positions max)")
    print("   - STANDARD: $10,000 (1% risk, 3 positions max)")

def get_account_summary():
    """Get summary of all paper accounts."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT name, initial_balance, current_balance, 
               risk_per_trade, max_positions, active
        FROM accounts
        ORDER BY initial_balance
    ''')
    
    accounts = []
    for row in cursor.fetchall():
        name, initial, current, risk, max_pos, active = row
        pnl = current - initial
        pnl_pct = (pnl / initial * 100) if initial > 0 else 0
        
        accounts.append({
            "name": name,
            "initial": initial,
            "current": current,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "risk": risk,
            "max_positions": max_pos,
            "active": active
        })
    
    conn.close()
    return accounts

def generate_accounts_report():
    """Generate report for all paper accounts."""
    accounts = get_account_summary()
    
    report = """
💰 **PAPER TRADING ACCOUNTS**

"""
    for acc in accounts:
        emoji = "🟢" if acc['pnl'] >= 0 else "🔴"
        status = "ACTIVE" if acc['active'] else "PAUSED"
        
        report += f"""{emoji} **{acc['name']}**
   Balance: ${acc['current']:.2f} | P&L: ${acc['pnl']:.2f} ({acc['pnl_pct']:.1f}%)
   Risk: {acc['risk']*100:.0f}% | Max positions: {acc['max_positions']} | {status}

"""
    
    return report

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--init":
        init_paper_accounts()
    elif len(sys.argv) > 1 and sys.argv[1] == "--report":
        print(generate_accounts_report())
    else:
        print("Usage: paper_accounts.py --init | --report")
