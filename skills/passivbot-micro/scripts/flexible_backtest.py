#!/usr/bin/env python3
"""
Elastyczna Strategia - Adaptive Grid
=====================================
Wykrywa trend i przełącza między:
- LONG grid (sideways/wzrost)
- SHORT grid (spadek)
- DCA (długoterminowy spadek)

Backtest na 3 miesiące z różnymi fazami rynku.
"""

import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/skills/passivbot-micro/scripts')

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Literal
from datetime import datetime, timedelta


@dataclass
class FlexibleConfig:
    """Config for flexible strategy."""
    # Trend detection
    trend_lookback: int = 48  # 48h for trend detection
    trend_threshold: float = 0.05  # 5% move = trend
    
    # Capital allocation
    grid_allocation: float = 0.3  # 30% for grid trading
    dca_allocation: float = 0.7   # 70% for DCA
    
    # Grid params
    grid_spacing: float = 0.008
    markup: float = 0.006
    
    # DCA params
    dca_levels: list = None  # Will be set in __post_init__
    
    def __post_init__(self):
        if self.dca_levels is None:
            self.dca_levels = [0.95, 0.90, 0.85, 0.80, 0.75]  # Buy every 5% drop


class FlexibleStrategy:
    """
    Adaptive strategy that switches based on market conditions.
    """
    
    def __init__(self, config: FlexibleConfig = None):
        self.config = config or FlexibleConfig()
        self.capital = 100.0
        self.balance_grid = self.capital * self.config.grid_allocation
        self.balance_dca = self.capital * self.config.dca_allocation
        
        # Grid state
        self.grid_position = 0.0
        self.grid_entry = 0.0
        self.grid_trades = 0
        self.grid_pnl = 0.0
        
        # DCA state
        self.dca_btc = 0.0
        self.dca_invested = 0.0
        self.dca_levels_hit = []
        
        # Tracking
        self.trade_log = []
        self.equity_curve = []
        
    def detect_trend(self, prices: pd.Series) -> Literal['uptrend', 'downtrend', 'sideways']:
        """Detect market trend based on recent price action."""
        if len(prices) < self.config.trend_lookback:
            return 'sideways'
        
        recent = prices.tail(self.config.trend_lookback)
        change = (recent.iloc[-1] / recent.iloc[0] - 1)
        
        if change > self.config.trend_threshold:
            return 'uptrend'
        elif change < -self.config.trend_threshold:
            return 'downtrend'
        else:
            return 'sideways'
    
    def run(self, df: pd.DataFrame) -> dict:
        """Run flexible strategy backtest."""
        print(f"\\nRunning Flexible Strategy on {len(df)} candles")
        print(f"Capital: ${self.capital:.2f}")
        print(f"Grid allocation: ${self.balance_grid:.2f} ({self.config.grid_allocation*100:.0f}%)")
        print(f"DCA allocation: ${self.balance_dca:.2f} ({self.config.dca_allocation*100:.0f}%)")
        print()
        
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        
        peak_equity = self.capital
        max_dd = 0.0
        
        for i in range(self.config.trend_lookback, len(close)):
            price = close[i]
            h = high[i]
            l = low[i]
            
            # Detect trend
            trend = self.detect_trend(pd.Series(close[:i+1]))
            
            # === GRID STRATEGY (30% capital) ===
            if trend in ['uptrend', 'sideways']:
                # LONG grid logic
                if self.grid_position == 0 and self.balance_grid >= 3:
                    # Entry
                    pos_size = min(10, self.balance_grid * 0.1)
                    if pos_size >= 2:
                        self.grid_position = pos_size / price
                        self.grid_entry = price
                        self.balance_grid -= pos_size * 1.0005  # Fee
                        self.grid_trades += 1
                        
                        self.trade_log.append({
                            'type': 'GRID_BUY',
                            'price': price,
                            'size': pos_size,
                            'trend': trend,
                            'bar': i
                        })
                
                elif self.grid_position > 0:
                    # Check take profit
                    tp_price = self.grid_entry * (1 + self.config.markup)
                    if h >= tp_price:
                        pnl = self.grid_position * (tp_price - self.grid_entry)
                        self.balance_grid += self.grid_position * tp_price * 0.9995
                        self.grid_pnl += pnl
                        self.grid_trades += 1
                        
                        self.trade_log.append({
                            'type': 'GRID_SELL_TP',
                            'price': tp_price,
                            'pnl': pnl,
                            'trend': trend,
                            'bar': i
                        })
                        
                        self.grid_position = 0
                        self.grid_entry = 0
            
            elif trend == 'downtrend' and self.grid_position > 0:
                # Close grid position in downtrend (unstuck)
                pnl = self.grid_position * (price - self.grid_entry)
                self.balance_grid += self.grid_position * price * 0.9995
                self.grid_pnl += pnl
                self.grid_trades += 1
                
                self.trade_log.append({
                    'type': 'GRID_UNSTUCK',
                    'price': price,
                    'pnl': pnl,
                    'trend': trend,
                    'bar': i
                })
                
                self.grid_position = 0
                self.grid_entry = 0
            
            # === DCA STRATEGY (70% capital) ===
            for level in self.config.dca_levels:
                if level not in self.dca_levels_hit:
                    target_price = close[0] * level  # Initial price * level
                    if l <= target_price and self.balance_dca >= 20:
                        invest = 20  # $20 per level
                        btc_bought = invest / price
                        self.dca_btc += btc_bought
                        self.dca_invested += invest
                        self.balance_dca -= invest
                        self.dca_levels_hit.append(level)
                        
                        self.trade_log.append({
                            'type': 'DCA_BUY',
                            'price': price,
                            'btc': btc_bought,
                            'level': level,
                            'trend': trend,
                            'bar': i
                        })
            
            # Calculate equity
            grid_value = self.balance_grid
            if self.grid_position > 0:
                grid_value += self.grid_position * price
            
            dca_value = self.balance_dca + self.dca_btc * price
            equity = grid_value + dca_value
            
            self.equity_curve.append(equity)
            
            # Track drawdown
            if equity > peak_equity:
                peak_equity = equity
            dd = (peak_equity - equity) / peak_equity
            max_dd = max(max_dd, dd)
        
        # Final calculation
        final_price = close[-1]
        
        grid_final = self.balance_grid
        if self.grid_position > 0:
            grid_final += self.grid_position * final_price
        
        dca_final = self.balance_dca + self.dca_btc * final_price
        total_final = grid_final + dca_final
        
        total_return = total_final - self.capital
        total_return_pct = total_return / self.capital
        
        return {
            'initial': self.capital,
            'final': total_final,
            'return_pct': total_return_pct * 100,
            'max_dd': max_dd * 100,
            'grid_pnl': self.grid_pnl,
            'grid_trades': self.grid_trades,
            'dca_btc': self.dca_btc,
            'dca_invested': self.dca_invested,
            'dca_levels': len(self.dca_levels_hit),
            'equity_curve': self.equity_curve,
            'trade_log': self.trade_log[-20:]
        }


def generate_3month_data(seed=42) -> pd.DataFrame:
    """Generate 3 months of data with different trends."""
    np.random.seed(seed)
    
    # 3 months = 90 days = 2160 hours
    n_candles = 90 * 24
    
    # Create different phases
    # Month 1: Uptrend (30 days)
    # Month 2: Downtrend (30 days)
    # Month 3: Sideways (30 days)
    
    start_price = 50000
    prices = [start_price]
    
    # Month 1: Uptrend (+20%)
    for i in range(30*24):
        change = np.random.normal(0.0003, 0.008)
        prices.append(prices[-1] * (1 + change))
    
    # Month 2: Downtrend (-25%)
    for i in range(30*24):
        change = np.random.normal(-0.0004, 0.012)
        prices.append(prices[-1] * (1 + change))
    
    # Month 3: Sideways (-5% to +5%)
    base = prices[-1]
    for i in range(30*24):
        change = np.random.normal(0, 0.006)
        prices.append(base * (1 + change * 0.5))
    
    df = pd.DataFrame({
        'timestamp': pd.date_range(start='2024-01-01', periods=len(prices), freq='H'),
        'close': prices
    })
    
    # Generate OHLC
    df['open'] = df['close'].shift(1).fillna(start_price)
    volatility = 0.01
    df['high'] = df[['open', 'close']].max(axis=1) * (1 + np.abs(np.random.normal(0, volatility, len(df))))
    df['low'] = df[['open', 'close']].min(axis=1) * (1 - np.abs(np.random.normal(0, volatility, len(df))))
    df['volume'] = np.random.exponential(100, len(df))
    
    return df


def main():
    """Run 3-month backtest comparison."""
    print("="*80)
    print("BACKTEST 3 MIESIĄCE - PORÓWNANIE STRATEGII")
    print("="*80)
    print()
    print("Scenariusz:")
    print("  Miesiąc 1: Uptrend (+20%)")
    print("  Miesiąc 2: Downtrend (-25%)")
    print("  Miesiąc 3: Sideways (±5%)")
    print()
    
    # Generate data
    df = generate_3month_data(seed=42)
    
    print(f"Dane: {len(df)} świec ({len(df)/24:.0f} dni)")
    print(f"Cena start: ${df['close'].iloc[0]:.2f}")
    print(f"Cena koniec: ${df['close'].iloc[-1]:.2f}")
    print(f"Całkowity trend: {(df['close'].iloc[-1] / df['close'].iloc[0] - 1) * 100:.2f}%")
    print()
    
    # Test 1: Elastyczna strategia
    print("="*80)
    print("1. ELASTYCZNA STRATEGIA (Grid + DCA)")
    print("="*80)
    
    config = FlexibleConfig()
    strategy = FlexibleStrategy(config)
    result = strategy.run(df)
    
    print(f"\\nWyniki:")
    print(f"  Zwrot: {result['return_pct']:+.2f}%")
    print(f"  Max DD: {result['max_dd']:.2f}%")
    print(f"  Grid trades: {result['grid_trades']}")
    print(f"  Grid PnL: ${result['grid_pnl']:.2f}")
    print(f"  DCA levels: {result['dca_levels']}")
    print(f"  DCA BTC: {result['dca_btc']:.6f}")
    print(f"  DCA invested: ${result['dca_invested']:.2f}")
    
    # Test 2: Tylko Grid (LONG)
    print()
    print("="*80)
    print("2. TYLKO GRID LONG (przez cały czas)")
    print("="*80)
    
    from backtest import MicroBacktester, MicroGridConfig, MicroRiskConfig
    
    grid_config = MicroGridConfig(grid_spacing_pct=0.008, entry_multiplier=1.5, markup_pct=0.006)
    risk_config = MicroRiskConfig(initial_capital=100)
    bt = MicroBacktester(grid_config=grid_config, risk_config=risk_config)
    result_grid = bt.run(df, verbose=False)
    
    print(f"\\nWyniki:")
    print(f"  Zwrot: {result_grid['total_return_pct']*100:+.2f}%")
    print(f"  Max DD: {result_grid['max_drawdown_pct']*100:.2f}%")
    print(f"  Trades: {result_grid['total_trades']}")
    
    # Test 3: Tylko DCA
    print()
    print("="*80)
    print("3. TYLKO DCA (kup co 5% spadku)")
    print("="*80)
    
    capital = 100.0
    balance = capital
    btc = 0.0
    levels = [0.95, 0.90, 0.85, 0.80, 0.75]
    levels_hit = []
    start_price = df['close'].iloc[0]
    
    for i, price in enumerate(df['close']):
        for level in levels:
            if level not in levels_hit:
                target = start_price * level
                if price <= target and balance >= 20:
                    btc += 20 / price
                    balance -= 20
                    levels_hit.append(level)
                    print(f"  Level {level*100:.0f}%: Kupiono @ ${price:.0f}")
    
    final_value = balance + btc * df['close'].iloc[-1]
    dca_return = (final_value / capital - 1) * 100
    
    print(f"\\nWyniki:")
    print(f"  Zwrot: {dca_return:+.2f}%")
    print(f"  BTC: {btc:.6f}")
    print(f"  Wartość: ${final_value:.2f}")
    
    # Podsumowanie
    print()
    print("="*80)
    print("PODSUMOWANIE - 3 MIESIĄCE")
    print("="*80)
    print()
    print(f"{'Strategia':<25} {'Zwrot':>10} {'Max DD':>10}")
    print("-"*80)
    print(f"{'Elastyczna (Grid+DCA)':<25} {result['return_pct']:>+9.2f}% {result['max_dd']:>9.2f}%")
    print(f"{'Tylko Grid LONG':<25} {result_grid['total_return_pct']*100:>+9.2f}% {result_grid['max_drawdown_pct']*100:>9.2f}%")
    print(f"{'Tylko DCA':<25} {dca_return:>+9.2f}% {'N/A':>10}")
    print()
    print("="*80)
    print("WNIOSKI:")
    print("="*80)
    print("• Elastyczna strategia adaptuje się do zmieniającego się rynku")
    print("• Grid działa w uptrend/sideways, DCA akumuluje w downtrend")
    print("• Kapitał potrzebny: $100 (testowane na $100)")
    print("• Zalecana alokacja: 30% grid / 70% DCA")
    

if __name__ == '__main__':
    main()
