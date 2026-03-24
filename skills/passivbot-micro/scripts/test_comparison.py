#!/usr/bin/env python3
"""
BACKTEST COMPARISON: Original vs Enhanced Strategy
===================================================
Compare original config with enhanced high-risk/reward version.

Usage:
    python test_comparison.py --data btc_prices.json --days 365
"""

import json
import numpy as np
import argparse
from datetime import datetime
from typing import List, Dict, Tuple
import sys

# Simple EMA calculation
def calculate_ema(prices: List[float], period: int) -> float:
    if len(prices) < period:
        return prices[-1] if prices else 0.0
    alpha = 2 / (period + 1)
    ema = prices[0]
    for p in prices[1:]:
        ema = alpha * p + (1 - alpha) * ema
    return ema


def pct_change(prices: List[float], lookback: int) -> float:
    if len(prices) <= lookback or prices[-lookback - 1] <= 0:
        return 0.0
    return (prices[-1] / prices[-lookback - 1]) - 1


class OriginalStrategy:
    """Original unified bot strategy (conservative)."""
    
    def __init__(self, capital: float = 1000.0):
        self.capital = capital
        self.balance = capital
        self.peak = capital
        self.positions = []
        self.trades = 0
        self.wins = 0
        
        # Original config
        self.short_position_pct = 0.15
        self.short_leverage = 3.0
        self.short_tp = 0.04
        self.short_sl = 0.025
        self.short_bounce = 0.015
        
        self.long_position_pct = 0.10
        self.long_grid_spacing = 0.008
        self.long_markup = 0.006
        
        self.trend_lookback = 48
    
    def detect_trend(self, prices: List[float]) -> str:
        if len(prices) < 48:
            return 'sideways'
        
        change_48h = pct_change(prices, 48)
        change_7d = pct_change(prices, 168) if len(prices) >= 168 else change_48h
        
        if change_48h > 0.05 and change_7d > 0.02:
            return 'uptrend'
        elif change_48h < -0.05 and change_7d < -0.02:
            return 'downtrend'
        return 'sideways'
    
    def simulate(self, prices: List[float]) -> Dict:
        """Run simulation on price data."""
        for i in range(100, len(prices)):
            price_slice = prices[:i+1]
            current_price = prices[i]
            
            trend = self.detect_trend(price_slice)
            
            # Close positions
            for pos in self.positions[:]:
                if pos['type'] == 'short':
                    pnl = (pos['entry'] - current_price) / pos['entry'] * pos['notional']
                    if current_price <= pos['entry'] * (1 - self.short_tp):
                        self.close_position(pos, pnl, 'tp')
                    elif current_price >= pos['entry'] * (1 + self.short_sl):
                        self.close_position(pos, pnl, 'sl')
                
                elif pos['type'] == 'long_grid':
                    pnl = (current_price - pos['entry']) / pos['entry'] * pos['size']
                    if current_price >= pos['tp_price']:
                        self.close_position(pos, pnl, 'tp')
            
            # Enter positions
            if trend == 'downtrend' and len(self.positions) < 2:
                recent_low = min(price_slice[-24:])
                bounce = (current_price - recent_low) / recent_low
                if bounce >= self.short_bounce:
                    self.enter_short(current_price)
            
            elif trend == 'uptrend' and not any(p['type'] == 'long_grid' for p in self.positions):
                recent_high = max(price_slice[-24:])
                dip = (recent_high - current_price) / recent_high
                if dip >= self.long_grid_spacing:
                    self.enter_long_grid(current_price)
            
            # Update peak
            if self.balance > self.peak:
                self.peak = self.balance
        
        return self.get_stats()
    
    def enter_short(self, price: float):
        size = self.capital * self.short_position_pct
        notional = size * self.short_leverage
        self.positions.append({
            'type': 'short',
            'entry': price,
            'notional': notional,
            'size': size
        })
    
    def enter_long_grid(self, price: float):
        size = self.capital * self.long_position_pct
        self.positions.append({
            'type': 'long_grid',
            'entry': price,
            'size': size,
            'tp_price': price * (1 + self.long_markup)
        })
    
    def close_position(self, pos: Dict, pnl: float, reason: str):
        self.balance += pnl
        self.positions.remove(pos)
        self.trades += 1
        if pnl > 0:
            self.wins += 1
    
    def get_stats(self) -> Dict:
        total_return = (self.balance - self.capital) / self.capital
        max_dd = (self.peak - min(self.balance, self.capital)) / self.peak if self.peak > 0 else 0
        win_rate = self.wins / self.trades if self.trades > 0 else 0
        
        return {
            'final_balance': self.balance,
            'total_return': total_return,
            'max_drawdown': max_dd,
            'trades': self.trades,
            'win_rate': win_rate,
            'profit_factor': self.balance / self.capital
        }


class EnhancedStrategy:
    """Enhanced strategy with higher risk/reward."""
    
    def __init__(self, capital: float = 1000.0):
        self.capital = capital
        self.balance = capital
        self.peak = capital
        self.positions = []
        self.pyramid_positions = []
        self.trades = 0
        self.wins = 0
        
        # Enhanced config
        self.short_position_pct = 0.25
        self.short_leverage = 3.0
        self.short_tp = 0.025  # Tighter
        self.short_sl = 0.018
        self.short_bounce = 0.008
        self.short_breakdown = 0.01
        
        self.long_position_pct = 0.20  # Bigger
        self.long_grid_spacing = 0.005  # Tighter
        self.long_markup = 0.004
        
        self.trend_follow_pct = 0.25
        self.trend_follow_tp = 0.03
        self.trend_follow_sl = 0.03
        
        self.trend_lookback = 24  # Faster
        self.dynamic_sizing = True
    
    def detect_trend(self, prices: List[float]) -> str:
        if len(prices) < 24:
            return 'sideways'
        
        change_24h = pct_change(prices, 24)
        change_48h = pct_change(prices, 48)
        change_7d = pct_change(prices, 168) if len(prices) >= 168 else change_48h
        
        # More granular classification
        if change_24h > 0.03 and change_48h > 0.05:
            return 'strong_uptrend'
        elif change_7d > 0.02 and change_24h < 0:
            return 'pullback_uptrend'
        elif change_24h < -0.03 and change_48h < -0.05:
            return 'strong_downtrend'
        elif change_7d < -0.02 and change_24h > 0:
            return 'bear_rally'
        return 'sideways'
    
    def get_position_size(self, base_pct: float, trend: str) -> float:
        if not self.dynamic_sizing:
            return base_pct
        
        multipliers = {
            'strong_uptrend': 1.5,
            'strong_downtrend': 1.3,
            'sideways': 0.5,
            'pullback_uptrend': 1.0,
            'bear_rally': 0.8
        }
        return base_pct * multipliers.get(trend, 1.0)
    
    def simulate(self, prices: List[float]) -> Dict:
        last_trend = 'sideways'
        
        for i in range(100, len(prices)):
            price_slice = prices[:i+1]
            current_price = prices[i]
            
            trend = self.detect_trend(price_slice)
            
            # Dynamic sizing based on trend
            short_size = self.get_position_size(self.short_position_pct, trend)
            long_size = self.get_position_size(self.long_position_pct, trend)
            trend_size = self.get_position_size(self.trend_follow_pct, trend)
            
            # Close positions
            for pos in self.positions[:]:
                if pos['type'] == 'short':
                    pnl = (pos['entry'] - current_price) / pos['entry'] * pos['notional']
                    if current_price <= pos['entry'] * (1 - self.short_tp):
                        self.close_position(pos, pnl, 'tp')
                    elif current_price >= pos['entry'] * (1 + self.short_sl):
                        self.close_position(pos, pnl, 'sl')
                    elif trend == 'strong_uptrend':  # Exit on trend reversal
                        self.close_position(pos, pnl, 'trend_reversal')
                
                elif pos['type'] == 'long_grid':
                    pnl = (current_price - pos['entry']) / pos['entry'] * pos['size']
                    if current_price >= pos['tp_price']:
                        self.close_position(pos, pnl, 'tp')
                
                elif pos['type'] == 'trend_follow':
                    pnl = (current_price - pos['entry']) / pos['entry'] * pos['size']
                    if current_price >= pos['entry'] * (1 + self.trend_follow_tp):
                        self.close_position(pos, pnl * 0.3, 'partial_tp')  # Partial close
                    elif current_price <= pos['entry'] * (1 - self.trend_follow_sl):
                        self.close_position(pos, pnl, 'sl')
            
            # Enhanced entry logic
            if trend in ('strong_downtrend', 'bear_rally'):
                # Breakdown entry
                if len(self.positions) < 3:
                    change_6h = pct_change(price_slice, 6)
                    if change_6h < -self.short_breakdown:
                        self.enter_short(current_price, short_size)
                    else:
                        recent_low = min(price_slice[-24:])
                        bounce = (current_price - recent_low) / recent_low
                        if bounce >= self.short_bounce:
                            self.enter_short(current_price, short_size)
            
            elif trend == 'strong_uptrend':
                # Trend follow with pyramiding
                trend_positions = [p for p in self.positions if p['type'] == 'trend_follow']
                if len(trend_positions) < 2:  # Main + 1 pyramid
                    self.enter_trend_follow(current_price, trend_size)
            
            elif trend == 'pullback_uptrend':
                # Grid buying
                if not any(p['type'] == 'long_grid' for p in self.positions):
                    recent_high = max(price_slice[-24:])
                    dip = (recent_high - current_price) / recent_high
                    if dip >= self.long_grid_spacing:
                        self.enter_long_grid(current_price, long_size)
            
            # Update peak
            if self.balance > self.peak:
                self.peak = self.balance
            
            last_trend = trend
        
        return self.get_stats()
    
    def enter_short(self, price: float, size_pct: float):
        size = self.capital * size_pct
        notional = size * self.short_leverage
        self.positions.append({
            'type': 'short',
            'entry': price,
            'notional': notional,
            'size': size
        })
    
    def enter_long_grid(self, price: float, size_pct: float):
        size = self.capital * size_pct
        self.positions.append({
            'type': 'long_grid',
            'entry': price,
            'size': size,
            'tp_price': price * (1 + self.long_markup)
        })
    
    def enter_trend_follow(self, price: float, size_pct: float):
        size = self.capital * size_pct
        self.positions.append({
            'type': 'trend_follow',
            'entry': price,
            'size': size
        })
    
    def close_position(self, pos: Dict, pnl: float, reason: str):
        self.balance += pnl
        if pos in self.positions:
            self.positions.remove(pos)
        self.trades += 1
        if pnl > 0:
            self.wins += 1
    
    def get_stats(self) -> Dict:
        total_return = (self.balance - self.capital) / self.capital
        max_dd = (self.peak - min(self.balance, self.capital)) / self.peak if self.peak > 0 else 0
        win_rate = self.wins / self.trades if self.trades > 0 else 0
        
        return {
            'final_balance': self.balance,
            'total_return': total_return,
            'max_drawdown': max_dd,
            'trades': self.trades,
            'win_rate': win_rate,
            'profit_factor': self.balance / self.capital
        }


def generate_sample_data(days: int = 365) -> List[float]:
    """Generate sample BTC-like price data for testing."""
    np.random.seed(42)
    prices = [50000.0]
    
    for i in range(days * 24):  # Hourly data
        # Trend component
        trend = 0.0001 * np.sin(i / (30 * 24))  # Monthly cycle
        
        # Volatility
        vol = 0.0015
        change = np.random.normal(trend, vol)
        
        new_price = prices[-1] * (1 + change)
        prices.append(max(new_price, 1000))  # Floor at 1000
    
    return prices


def print_comparison(original: Dict, enhanced: Dict, days: int):
    """Print comparison table."""
    print("\n" + "="*80)
    print("BACKTEST COMPARISON: Original vs Enhanced Strategy")
    print("="*80)
    print(f"Period: {days} days | Initial Capital: $1000")
    print("-"*80)
    
    metrics = [
        ('Final Balance', f"${original['final_balance']:.2f}", f"${enhanced['final_balance']:.2f}"),
        ('Total Return', f"{original['total_return']:.2%}", f"{enhanced['total_return']:.2%}"),
        ('Annualized', f"{original['total_return'] * 365 / days:.2%}", f"{enhanced['total_return'] * 365 / days:.2%}"),
        ('Max Drawdown', f"{original['max_drawdown']:.2%}", f"{enhanced['max_drawdown']:.2%}"),
        ('Trades', str(original['trades']), str(enhanced['trades'])),
        ('Win Rate', f"{original['win_rate']:.1%}", f"{enhanced['win_rate']:.1%}"),
    ]
    
    print(f"{'Metric':<20} {'Original':<20} {'Enhanced':<20} {'Diff':<15}")
    print("-"*80)
    
    for metric, orig, enh in metrics:
        if metric == 'Trades':
            diff = f"+{int(enh) - int(orig)}"
        elif metric == 'Final Balance':
            orig_val = float(orig.replace('$', ''))
            enh_val = float(enh.replace('$', ''))
            diff_pct = (enh_val - orig_val) / orig_val
            diff = f"{diff_pct:+.2%}"
        else:
            # Parse percentages
            try:
                orig_val = float(orig.replace('%', '')) / 100 if '%' in orig else float(orig)
                enh_val = float(enh.replace('%', '')) / 100 if '%' in enh else float(enh)
                diff_val = enh_val - orig_val
                diff = f"{diff_val:+.2%}" if '%' in orig else f"{diff_val:+.2f}"
            except:
                diff = "N/A"
        
        print(f"{metric:<20} {orig:<20} {enh:<20} {diff:<15}")
    
    print("="*80)
    
    # Analysis
    orig_annual = original['total_return'] * 365 / days
    enh_annual = enhanced['total_return'] * 365 / days
    
    print("\n📊 ANALYSIS:")
    print(f"  Original: {orig_annual:.1%} annual return, {original['max_drawdown']:.1%} max DD")
    print(f"  Enhanced: {enh_annual:.1%} annual return, {enhanced['max_drawdown']:.1%} max DD")
    
    if enh_annual > orig_annual:
        print(f"  ✅ Enhanced outperforms by {enh_annual - orig_annual:.1%} annually")
    else:
        print(f"  ⚠️  Enhanced underperforms by {orig_annual - enh_annual:.1%} annually")
    
    if enhanced['max_drawdown'] > original['max_drawdown']:
        print(f"  ⚠️  Drawdown increased by {enhanced['max_drawdown'] - original['max_drawdown']:.1%}")
    
    # Risk-adjusted
    orig_sharpe = orig_annual / original['max_drawdown'] if original['max_drawdown'] > 0 else 0
    enh_sharpe = enh_annual / enhanced['max_drawdown'] if enhanced['max_drawdown'] > 0 else 0
    
    print(f"\n  Risk-adjusted (return/DD):")
    print(f"    Original: {orig_sharpe:.2f}")
    print(f"    Enhanced: {enh_sharpe:.2f}")
    
    if enh_sharpe > orig_sharpe:
        print(f"  ✅ Better risk-adjusted returns")
    else:
        print(f"  ⚠️  Worse risk-adjusted returns")
    
    print("\n" + "="*80)


def main():
    parser = argparse.ArgumentParser(description='Compare Original vs Enhanced Strategy')
    parser.add_argument('--data', type=str, help='Path to price data JSON (list of prices)')
    parser.add_argument('--days', type=int, default=365, help='Number of days to simulate')
    parser.add_argument('--capital', type=float, default=1000.0, help='Initial capital')
    
    args = parser.parse_args()
    
    # Load or generate data
    if args.data:
        with open(args.data, 'r') as f:
            prices = json.load(f)
    else:
        print("Generating sample BTC data...")
        prices = generate_sample_data(args.days)
    
    print(f"\nRunning backtest on {len(prices)} price points ({len(prices)/24:.0f} days)...")
    
    # Run original strategy
    print("\n1. Testing ORIGINAL strategy...")
    original = OriginalStrategy(capital=args.capital)
    original_results = original.simulate(prices)
    
    # Run enhanced strategy
    print("2. Testing ENHANCED strategy...")
    enhanced = EnhancedStrategy(capital=args.capital)
    enhanced_results = enhanced.simulate(prices)
    
    # Print comparison
    print_comparison(original_results, enhanced_results, len(prices) // 24)
    
    # Save results
    results = {
        'timestamp': datetime.now().isoformat(),
        'days': len(prices) // 24,
        'original': original_results,
        'enhanced': enhanced_results
    }
    
    output_file = 'comparison_results.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Results saved to: {output_file}")


if __name__ == '__main__':
    main()
