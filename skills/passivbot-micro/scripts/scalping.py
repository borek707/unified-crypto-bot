#!/usr/bin/env python3
"""
Scalping Strategy Backtest
==========================
Short-term trading with tight stops and quick profits.

Strategy:
- Enter on momentum (price breakout from recent range)
- Tight stop loss (0.3%)
- Quick take profit (0.5%)
- Max position: $10 per trade
- Only trade when volatility is sufficient
"""

import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/skills/passivbot-micro/scripts')

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional


@dataclass
class ScalpingResult:
    """Results from scalping backtest."""
    total_return_pct: float
    max_drawdown_pct: float
    total_trades: int
    winning_trades: int
    win_rate: float
    avg_profit: float
    avg_loss: float
    profit_factor: float
    final_balance: float


class ScalpingStrategy:
    """
    Simple scalping strategy for $100 account.
    """
    
    def __init__(
        self,
        initial_capital: float = 100.0,
        position_size: float = 10.0,      # $10 per trade
        stop_loss_pct: float = 0.003,     # 0.3% stop loss
        take_profit_pct: float = 0.005,   # 0.5% take profit
        min_volatility: float = 0.002,    # Min 0.2% volatility to trade
        lookback: int = 10                # Lookback for momentum
    ):
        self.initial_capital = initial_capital
        self.position_size = position_size
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.min_volatility = min_volatility
        self.lookback = lookback
    
    def run(self, df: pd.DataFrame, verbose: bool = False) -> ScalpingResult:
        """Run scalping backtest."""
        
        balance = self.initial_capital
        position = 0.0  # Current position size
        entry_price = 0.0
        
        trades = []
        peak_balance = balance
        max_drawdown = 0.0
        
        for i in range(self.lookback, len(df)):
            price = df['close'].iloc[i]
            high = df['high'].iloc[i]
            low = df['low'].iloc[i]
            
            # Update peak and drawdown
            if balance > peak_balance:
                peak_balance = balance
            drawdown = (peak_balance - balance) / peak_balance
            if drawdown > max_drawdown:
                max_drawdown = drawdown
            
            # Check if we have an open position
            if position > 0:
                # Check stop loss
                stop_price = entry_price * (1 - self.stop_loss_pct)
                if low <= stop_price:
                    # Stop loss hit
                    loss = self.position_size * self.stop_loss_pct
                    balance -= loss
                    trades.append(-loss)
                    position = 0.0
                    entry_price = 0.0
                    continue
                
                # Check take profit
                tp_price = entry_price * (1 + self.take_profit_pct)
                if high >= tp_price:
                    # Take profit hit
                    profit = self.position_size * self.take_profit_pct
                    balance += profit
                    trades.append(profit)
                    position = 0.0
                    entry_price = 0.0
                    continue
            
            # No position - look for entry
            else:
                # Calculate recent volatility
                recent = df['close'].iloc[i-self.lookback:i]
                volatility = recent.std() / recent.mean()
                
                # Need minimum volatility
                if volatility < self.min_volatility:
                    continue
                
                # Check if we have enough balance
                if balance < self.position_size:
                    continue
                
                # Momentum entry: price breaking above recent high
                recent_high = df['high'].iloc[i-self.lookback:i].max()
                
                if high >= recent_high * 1.001:  # 0.1% breakout
                    # Enter long
                    position = self.position_size / price
                    entry_price = price
        
        # Close any open position at last price
        final_balance = balance
        if position > 0:
            final_price = df['close'].iloc[-1]
            pnl = position * (final_price - entry_price)
            final_balance += pnl
            trades.append(pnl)
        
        # Calculate metrics
        winning_trades = len([t for t in trades if t > 0])
        total_trades = len(trades)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        profits = [t for t in trades if t > 0]
        losses = [abs(t) for t in trades if t < 0]
        
        avg_profit = np.mean(profits) if profits else 0
        avg_loss = np.mean(losses) if losses else 0
        
        total_profit = sum(profits)
        total_loss = sum(losses)
        profit_factor = total_profit / total_loss if total_loss > 0 else 0
        
        total_return = (final_balance - self.initial_capital) / self.initial_capital
        
        return ScalpingResult(
            total_return_pct=total_return * 100,
            max_drawdown_pct=max_drawdown * 100,
            total_trades=total_trades,
            winning_trades=winning_trades,
            win_rate=win_rate,
            avg_profit=avg_profit,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            final_balance=final_balance
        )


def main():
    """Run scalping backtest on real BTC data."""
    print("="*60)
    print("SCALPING STRATEGY BACKTEST")
    print("="*60)
    print()
    
    # Load data
    print("Loading BTC/USDC data...")
    df = pd.read_csv('/home/ubuntu/.openclaw/workspace/memory/passivbot_data/BTC_USDC_1m.csv')
    print(f"Loaded {len(df)} candles ({len(df)/(24*60):.1f} days)")
    
    # Use last 30 days
    df_test = df.tail(30 * 24 * 60).reset_index(drop=True)
    print(f"Testing on last {len(df_test)} candles (30 days)")
    print(f"Price range: ${df_test['close'].min():.2f} - ${df_test['close'].max():.2f}")
    print(f"Trend: {(df_test['close'].iloc[-1] / df_test['close'].iloc[0] - 1) * 100:.2f}%")
    print()
    
    # Test different scalping configurations
    configs = [
        {
            'name': 'Conservative Scalping',
            'params': {
                'position_size': 5.0,
                'stop_loss_pct': 0.002,
                'take_profit_pct': 0.004,
                'lookback': 5
            }
        },
        {
            'name': 'Standard Scalping',
            'params': {
                'position_size': 10.0,
                'stop_loss_pct': 0.003,
                'take_profit_pct': 0.005,
                'lookback': 10
            }
        },
        {
            'name': 'Aggressive Scalping',
            'params': {
                'position_size': 15.0,
                'stop_loss_pct': 0.004,
                'take_profit_pct': 0.008,
                'lookback': 15
            }
        }
    ]
    
    results = []
    
    for config in configs:
        print(f"\n{'='*60}")
        print(config['name'].upper())
        print(f"{'='*60}")
        
        strategy = ScalpingStrategy(**config['params'])
        result = strategy.run(df_test)
        results.append((config['name'], result))
        
        print(f"Return: {result.total_return_pct:.2f}%")
        print(f"Max Drawdown: {result.max_drawdown_pct:.2f}%")
        print(f"Total Trades: {result.total_trades}")
        print(f"Win Rate: {result.win_rate:.1%}")
        print(f"Profit Factor: {result.profit_factor:.2f}")
        print(f"Avg Profit: ${result.avg_profit:.2f}")
        print(f"Avg Loss: ${result.avg_loss:.2f}")
        print(f"Final Balance: ${result.final_balance:.2f}")
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY - SCALPING ON REAL BTC/USDC (30 days, -22.5% trend)")
    print(f"{'='*60}")
    print(f"{'Strategy':<25} {'Return':>10} {'DD':>8} {'Trades':>8} {'Win%':>8}")
    print("-"*60)
    for name, result in results:
        print(f"{name:<25} {result.total_return_pct:>9.2f}% {result.max_drawdown_pct:>7.2f}% {result.total_trades:>8} {result.win_rate*100:>7.1f}%")
    
    print()
    print("Note: Scalping works best in high volatility, not strong trends.")


if __name__ == '__main__':
    main()
