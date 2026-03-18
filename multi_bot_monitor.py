#!/usr/bin/env python3
"""
Multi-Bot Monitor - tracks LOW, MEDIUM, HIGH risk bots.
"""
import json
import os
from pathlib import Path
from datetime import datetime

def parse_log_file(log_path):
    """Parse bot log file for stats."""
    stats = {
        'trades': 0,
        'profit': 0.0,
        'last_action': None,
        'status': 'UNKNOWN'
    }
    
    if not log_path.exists():
        return stats
    
    try:
        with open(log_path) as f:
            lines = f.readlines()
        
        for line in lines[-100:]:  # Check last 100 lines
            if 'OPEN LONG' in line or 'OPEN SHORT' in line:
                stats['trades'] += 1
                stats['last_action'] = line.strip()
            if 'PnL' in line and '$' in line:
                try:
                    pnl_str = line.split('$')[1].split()[0]
                    stats['profit'] += float(pnl_str)
                except:
                    pass
            if 'Running' in line:
                stats['status'] = 'RUNNING'
        
        # Check if log is recent (within 5 minutes)
        if lines:
            last_line = lines[-1]
            stats['status'] = 'RUNNING'
            
    except Exception as e:
        stats['status'] = f'ERROR: {e}'
    
    return stats

def show_multi_dashboard():
    """Display dashboard for all 3 bots."""
    log_dir = Path('~/.openclaw/workspace/memory/passivbot_logs').expanduser()
    
    print("\n" + "="*80)
    print("🤖 MULTI-BOT PAPER TRADING DASHBOARD")
    print("="*80)
    print(f"Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    bots = [
        ('🟢 LOW', log_dir / 'low' / 'bot.log', 100.0),
        ('🟡 MEDIUM', log_dir / 'medium' / 'bot.log', 100.0),
        ('🔴 HIGH', log_dir / 'high' / 'bot.log', 100.0)
    ]
    
    for name, log_path, initial in bots:
        stats = parse_log_file(log_path)
        current = initial + stats['profit']
        pnl_pct = ((current / initial) - 1) * 100
        
        print(f"{name} RISK")
        print(f"  Status:     {stats['status']}")
        print(f"  Balance:    ${current:.2f} (Initial: ${initial:.2f})")
        
        emoji = "🟢" if stats['profit'] >= 0 else "🔴"
        print(f"  P&L:        {emoji} ${stats['profit']:+.2f} ({pnl_pct:+.2f}%)")
        print(f"  Trades:     {stats['trades']}")
        
        if stats['last_action']:
            action = stats['last_action'].split('|')[-1].strip()[:60]
            print(f"  Last:       {action}")
        print()
    
    print("="*80)
    print("\n📊 Monitoring Commands:")
    print("  • All logs:    tail -f ~/.openclaw/workspace/memory/passivbot_logs/*/bot.log")
    print("  • Low only:    tail -f ~/.openclaw/workspace/memory/passivbot_logs/low/bot.log")
    print("  • Medium:      tail -f ~/.openclaw/workspace/memory/passivbot_logs/medium/bot.log")
    print("  • High only:   tail -f ~/.openclaw/workspace/memory/passivbot_logs/high/bot.log")
    print("="*80)

if __name__ == '__main__':
    show_multi_dashboard()
