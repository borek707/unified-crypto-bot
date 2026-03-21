#!/usr/bin/env python3
"""
View and compare backtest results.
"""
import json
import pandas as pd
from pathlib import Path

def show_results():
    """Display all backtest results."""
    results_file = Path('~/.openclaw/workspace/memory/backtest_results/detailed_results.json').expanduser()
    
    if not results_file.exists():
        print("No results found. Run backtests first.")
        return
    
    with open(results_file) as f:
        data = json.load(f)
    
    print("="*70)
    print("📊 BACKTEST RESULTS DATABASE")
    print("="*70)
    
    for run in data['backtest_runs']:
        print(f"\n🔹 {run['id']}")
        print(f"   Period: {run['data_range']['start']} to {run['data_range']['end']}")
        print(f"   Symbol: {run['data_range']['symbol']}")
        print(f"   Market: {run['market_conditions']['total_change_pct']:+.1f}% ({run['market_conditions']['trend']})")
        print(f"\n   Strategy Results:")
        
        # Sort by return
        strategies = sorted(run['strategies'], key=lambda x: x['results']['total_return_pct'], reverse=True)
        
        for s in strategies:
            r = s['results']
            print(f"   • {s['name']:<25} {r['total_return_pct']:+>7.2f}%", end='')
            if 'total_trades' in r:
                wr = r.get('win_rate', 0)
                print(f" ({r['total_trades']} trades, {wr:.0f}% WR)", end='')
            print()
        
        print(f"\n   🏆 Best: {run['conclusion']['best_strategy']}")
        print(f"   💡 {run['conclusion']['recommendation']}")
        print("-"*70)
    
    print("\n📁 Files:")
    print(f"   • detailed_results.json - Full JSON data")
    print(f"   • summary.csv - CSV summary table")
    print(f"   • README.md - Documentation")

def compare_strategies():
    """Create comparison table."""
    results_file = Path('~/.openclaw/workspace/memory/backtest_results/detailed_results.json').expanduser()
    
    with open(results_file) as f:
        data = json.load(f)
    
    print("\n" + "="*90)
    print("📈 STRATEGY COMPARISON ACROSS ALL BACKTESTS")
    print("="*90)
    print(f"{'Backtest':<25} {'Strategy':<20} {'Return':<10} {'Max DD':<10} {'Trades':<10}")
    print("-"*90)
    
    for run in data['backtest_runs']:
        period = f"{run['data_range']['start'][:4]}-{run['data_range']['end'][:4]}"
        for s in run['strategies']:
            r = s['results']
            dd = r.get('max_drawdown_pct', 0)
            trades = r.get('total_trades', '-')
            print(f"{period:<25} {s['name']:<20} {r['total_return_pct']:>+8.2f}% {dd:>7.2f}% {str(trades):>8}")

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'compare':
        compare_strategies()
    else:
        show_results()
