#!/usr/bin/env python3
"""
Backtest na 2 lata - używa danych dziennych BTC.
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass
from datetime import datetime
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/skills/passivbot-micro/scripts')

# Load 2 years daily data
df = pd.read_csv('/home/ubuntu/.openclaw/workspace/memory/passivbot_data/BTC_2years_daily.csv')
print(f"Dane: {len(df)} dni (2 lata)")
print(f"Zakres: {df['timestamp'].iloc[0]} do {df['timestamp'].iloc[-1]}")
print(f"Cena start: ${df['close'].iloc[0]:.2f}")
print(f"Cena koniec: ${df['close'].iloc[-1]:.2f}")

# Simple grid backtest
initial_capital = 100
grid_spacing = 0.08  # 8% for daily candles
markup = 0.06        # 6% take profit
leverage = 1.0

capital = initial_capital
position = None
entry_price = 0
position_size = 0
trades = 0
wins = 0
pnl_total = 0

for i, row in df.iterrows():
    price = row['close']
    
    if position is None:
        # Open position
        if capital >= 10:
            position = 'LONG'
            entry_price = price
            position_size = 10  # $10 position
            capital -= 10
    else:
        # Check take profit
        if price >= entry_price * (1 + markup):
            profit = position_size * markup * leverage
            capital += position_size + profit
            pnl_total += profit
            trades += 1
            wins += 1
            position = None
        # Check grid re-entry
        elif price <= entry_price * (1 - grid_spacing):
            # Add to position
            if capital >= 10:
                capital -= 10
                position_size += 10
                entry_price = (entry_price + price) / 2  # Avg entry

# Results
final_value = capital + (position_size * (df['close'].iloc[-1] / entry_price) if position else 0)
return_pct = (final_value / initial_capital - 1) * 100
win_rate = (wins / trades * 100) if trades > 0 else 0

print("\n" + "="*50)
print("BACKTEST 2 LATA (dane dzienne)")
print("="*50)
print(f"Kapitał start: ${initial_capital:.2f}")
print(f"Kapitał koniec: ${final_value:.2f}")
print(f"Zwrot: {return_pct:.2f}%")
print(f"Trade'y: {trades}")
print(f"Win rate: {win_rate:.1f}%")
print(f"PnL: ${pnl_total:.2f}")
print("="*50)
