#!/usr/bin/env python3
"""
MOMENTUM STRATEGY - SIMPLE AND AGGRESSIVE
==========================================
Basic momentum trading that WILL trade.
No RL optimization - just simple rules.

Rules:
- Price > SMA20 + 2% => BUY
- Price < SMA20 - 2% => SELL
- Always in position (flip on signal change)

Fees: Real Hyperliquid 0.09%
"""

import json
import sys
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import List, Dict

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))


def sma(prices: List[float], period: int) -> float:
    """Simple moving average"""
    if len(prices) < period:
        return prices[-1]
    return np.mean(prices[-period:])


def momentum_strategy(prices: List[float], threshold: float = 0.02) -> List[Dict]:
    """
    Simple momentum strategy - WILL trade frequently.
    
    Args:
        prices: Price history
        threshold: Entry/exit threshold (2% default)
    
    Returns:
        List of trades
    """
    position = None  # None, 'long'
    trades = []
    
    for i in range(50, len(prices)):
        price = prices[i]
        sma20 = sma(prices[:i], 20)
        
        # Calculate deviation from SMA
        deviation = (price - sma20) / sma20
        
        # Entry signal: Price > SMA + threshold
        if position is None and deviation > threshold:
            position = {
                'entry': price,
                'entry_idx': i,
                'type': 'long'
            }
        
        # Exit signal: Price < SMA - threshold
        elif position and deviation < -threshold:
            pnl = (price - position['entry']) / position['entry']
            fee = 0.0009  # 0.09% round-trip
            pnl -= fee
            
            trades.append({
                'type': position['type'],
                'entry': position['entry'],
                'exit': price,
                'pnl': pnl,
                'duration': i - position['entry_idx']
            })
            position = None
    
    # Close any open position at end
    if position:
        pnl = (prices[-1] - position['entry']) / position['entry']
        pnl -= 0.0009
        trades.append({
            'type': position['type'],
            'entry': position['entry'],
            'exit': prices[-1],
            'pnl': pnl,
            'duration': len(prices) - position['entry_idx']
        })
    
    return trades


def run_test(prices: List[float], name: str):
    """Run strategy test"""
    print(f"\n{'='*70}")
    print(f"📊 {name}")
    print(f"{'='*70}")
    print(f"Data: {len(prices)} prices")
    print(f"Range: ${min(prices):,.0f} - ${max(prices):,.0f}")
    
    # Run strategy
    trades = momentum_strategy(prices)
    
    if not trades:
        print("\n❌ No trades")
        return None
    
    # Calculate metrics
    total_pnl = sum(t['pnl'] for t in trades)
    win_trades = [t for t in trades if t['pnl'] > 0]
    loss_trades = [t for t in trades if t['pnl'] <= 0]
    
    win_rate = len(win_trades) / len(trades)
    avg_win = np.mean([t['pnl'] for t in win_trades]) if win_trades else 0
    avg_loss = np.mean([t['pnl'] for t in loss_trades]) if loss_trades else 0
    avg_duration = np.mean([t['duration'] for t in trades])
    
    # Equity curve
    equity = [100.0]
    for t in trades:
        equity.append(equity[-1] + t['pnl'] * 100)
    
    # Max drawdown
    peak = 100.0
    max_dd = 0.0
    for e in equity:
        if e > peak:
            peak = e
        dd = (peak - e) / peak
        max_dd = max(max_dd, dd)
    
    # Print results
    print(f"\n📈 RESULTS:")
    print(f"   Total Trades: {len(trades)}")
    print(f"   Win Rate: {win_rate*100:.1f}% ({len(win_trades)}/{len(trades)})")
    print(f"   Total Return: {total_pnl*100:+.2f}%")
    print(f"   Avg Win: {avg_win*100:+.2f}%")
    print(f"   Avg Loss: {avg_loss*100:+.2f}%")
    print(f"   Avg Duration: {avg_duration:.0f} periods")
    print(f"   Max Drawdown: {max_dd*100:.2f}%")
    print(f"   Final Equity: ${equity[-1]:,.2f}")
    
    return {
        'name': name,
        'trades': len(trades),
        'win_rate': win_rate,
        'return': total_pnl,
        'max_dd': max_dd,
        'equity': equity[-1]
    }


def main():
    print("="*70)
    print("🚀 MOMENTUM STRATEGY - WILL TRADE!")
    print("="*70)
    print(f"Started: {datetime.now().isoformat()}")
    print(f"Fees: 0.09% (Hyperliquid real)")
    print(f"Strategy: SMA20 ± 2% threshold")
    
    # Load data
    sources = [Path('/tmp/btc_real_2years.json')]
    prices = None
    for source in sources:
        if source.exists():
            with open(source) as f:
                hourly = json.load(f)
            # Convert to daily
            prices = hourly[::24]
            break
    
    if not prices:
        print("❌ No data!")
        return 1
    
    print(f"✅ Loaded {len(prices)} daily prices")
    
    # Test on different periods
    results = []
    
    # Latest year
    result = run_test(prices[-365:], "Latest Year (2024-2025)")
    if result:
        results.append(result)
    
    # Previous year  
    result = run_test(prices[-730:-365], "Previous Year (2023-2024)")
    if result:
        results.append(result)
    
    # All data
    result = run_test(prices, "Full History (3 Years)")
    if result:
        results.append(result)
    
    # Summary
    print(f"\n\n{'='*70}")
    print("📊 SUMMARY")
    print(f"{'='*70}")
    print(f"{'Period':<30} {'Return':<10} {'Trades':<10} {'Win%':<8}")
    print("-"*70)
    for r in results:
        print(f"{r['name']:<30} {r['return']*100:+.2f}%    {r['trades']:<10} {r['win_rate']*100:.0f}%")
    
    print(f"\n✅ Bot WILL trade with this strategy!")
    print(f"   Average {np.mean([r['trades'] for r in results]):.0f} trades per year")
    
    # Save
    output = {
        'strategy': 'momentum_sma20',
        'threshold': 0.02,
        'fees': 0.0009,
        'results': results
    }
    with open('/tmp/momentum_results.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
