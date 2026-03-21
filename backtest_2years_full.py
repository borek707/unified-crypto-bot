#!/usr/bin/env python3
"""
Kompleksowy backtest 2 lata - porównanie strategii.
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass
from datetime import datetime
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/skills/passivbot-micro/scripts')

# Load 2 years daily data
df = pd.read_csv('/home/ubuntu/.openclaw/workspace/memory/passivbot_data/BTC_2years_daily.csv')
prices = df['close'].values

print("="*60)
print("BACKTEST 2 LATA (2024-01-01 do 2026-03-01)")
print(f"Dane: {len(prices)} dni")
print(f"Cena: ${prices[0]:.0f} → ${prices[-1]:.0f}")
print(f"Trend: {((prices[-1]/prices[0])-1)*100:.1f}%")
print("="*60)

def backtest_grid(prices, initial=100, spacing=0.08, markup=0.06, max_positions=3):
    """Simple grid strategy."""
    capital = initial
    positions = []  # (entry_price, size)
    trades = 0
    wins = 0
    
    for price in prices:
        # Check take profits
        new_positions = []
        for entry, size in positions:
            if price >= entry * (1 + markup):
                profit = size * markup
                capital += size + profit
                trades += 1
                wins += 1
            else:
                new_positions.append((entry, size))
        positions = new_positions
        
        # Open new grid position
        if len(positions) < max_positions and capital >= 10:
            # Check if we have gap for new position
            if not positions or price <= positions[-1][0] * (1 - spacing):
                capital -= 10
                positions.append((price, 10))
    
    # Close remaining at last price
    final_value = capital
    for entry, size in positions:
        final_value += size * (price / entry)
    
    return_pct = (final_value / initial - 1) * 100
    win_rate = (wins / trades * 100) if trades > 0 else 0
    
    return {
        'final': final_value,
        'return': return_pct,
        'trades': trades,
        'win_rate': win_rate
    }

def backtest_dca(prices, initial=100, levels=[0.95, 0.90, 0.85, 0.80, 0.75]):
    """DCA strategy - buy on dips."""
    capital = initial
    btc = 0
    invested = 0
    
    max_price = prices[0]
    
    for price in prices:
        if price > max_price:
            max_price = price
        
        # Check DCA levels
        for level in levels:
            target_price = max_price * level
            if price <= target_price and capital >= 10:
                btc += 10 / price
                capital -= 10
                invested += 10
                break  # Only one buy per day
    
    final_value = capital + btc * prices[-1]
    return_pct = (final_value / initial - 1) * 100
    
    return {
        'final': final_value,
        'return': return_pct,
        'btc': btc,
        'invested': invested
    }

def backtest_hodl(prices, initial=100):
    """Simple buy and hold."""
    btc = initial / prices[0]
    final_value = btc * prices[-1]
    return_pct = (final_value / initial - 1) * 100
    return {'final': final_value, 'return': return_pct}

# Run all strategies
print("\n1. GRID STRATEGY (8% spacing, 6% markup)")
grid = backtest_grid(prices)
print(f"   Zwrot: {grid['return']:.2f}%")
print(f"   Trade'y: {grid['trades']}")
print(f"   Win Rate: {grid['win_rate']:.1f}%")

print("\n2. DCA STRATEGY (buy every 5% dip)")
dca = backtest_dca(prices)
print(f"   Zwrot: {dca['return']:.2f}%")
print(f"   BTC zakupione: {dca['btc']:.6f}")
print(f"   Zainwestowane: ${dca['invested']:.0f}")

print("\n3. HODL (buy & hold)")
hodl = backtest_hodl(prices)
print(f"   Zwrot: {hodl['return']:.2f}%")

print("\n" + "="*60)
print("PODSUMOWANIE 2 LATA")
print("="*60)
print(f"{'Strategia':<20} {'Zwrot':<12} {'vs HODL':<12}")
print("-"*60)
print(f"{'GRID':<20} {grid['return']:>10.2f}% {grid['return']-hodl['return']:>10.2f}%")
print(f"{'DCA':<20} {dca['return']:>10.2f}% {dca['return']-hodl['return']:>10.2f}%")
print(f"{'HODL':<20} {hodl['return']:>10.2f}% {'-':>10}")
print("="*60)

# Best strategy
best = max([grid, dca, hodl], key=lambda x: x['return'])
print(f"\n🏆 NAJLEPSZA: {['GRID', 'DCA', 'HODL'][[grid, dca, hodl].index(best)]}")
