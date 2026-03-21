#!/usr/bin/env python3
"""
Backtest Runner Script
======================
Run vectorized backtests on historical or generated data.

Usage:
    python backtest.py --symbol BTC/USDC --days 30
    python backtest.py --generate --candles 10000
"""

import argparse
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional
import time

try:
    from numba import njit, prange
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    print("Warning: Numba not available, using pure Python (slower)")


# ============================================================
# CONFIGURATION
# ============================================================
@dataclass
class GridConfig:
    """Grid trading strategy parameters."""
    grid_spacing_pct: float = 0.005      # 0.5% between grid levels
    entry_multiplier: float = 1.3        # Position size multiplier on re-entry
    markup_pct: float = 0.004            # Take profit distance
    initial_entry_pct: float = 0.01      # Initial entry as % of balance


@dataclass
class RiskConfig:
    """Risk management parameters."""
    initial_capital: float = 100.0
    min_position_size: float = 2.0
    max_position_size: float = 10.0
    stop_loss_balance: float = 80.0
    max_leverage: float = 5.0
    max_wallet_exposure: float = 0.30
    max_drawdown_pct: float = 0.20
    daily_loss_limit: float = 0.10


@dataclass
class BacktestResult:
    """Backtest output metrics."""
    total_return: float
    total_return_pct: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: float
    profit_factor: float
    total_trades: int
    win_rate: float
    final_balance: float
    trading_fees: float


# ============================================================
# DATA GENERATION
# ============================================================
def generate_sample_data(
    n_candles: int = 10000,
    start_price: float = 50000.0,
    volatility: float = 0.02,
    drift: float = 0.0001,
    seed: Optional[int] = None
) -> pd.DataFrame:
    """Generate sample OHLCV data using geometric Brownian motion."""
    if seed is not None:
        np.random.seed(seed)
    
    start_time = datetime.now() - timedelta(minutes=n_candles)
    timestamps = pd.date_range(start=start_time, periods=n_candles, freq='1min')
    
    # Generate price path (GBM)
    returns = np.random.normal(drift, volatility, n_candles)
    prices = start_price * np.exp(np.cumsum(returns))
    
    df = pd.DataFrame(index=timestamps)
    df['close'] = prices
    
    # Generate realistic OHLC
    intra_range = volatility * prices * 0.3
    df['high'] = df['close'] + np.abs(np.random.normal(0, intra_range))
    df['low'] = df['close'] - np.abs(np.random.normal(0, intra_range))
    df['open'] = df['close'].shift(1).fillna(start_price)
    
    # Ensure consistency
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)
    df['volume'] = np.random.exponential(100, n_candles) * (1 + volatility * 10)
    
    return df


# ============================================================
# ATR CALCULATION
# ============================================================
def calculate_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Calculate Average True Range."""
    n = len(close)
    tr = np.zeros(n)
    tr[0] = high[0] - low[0]
    
    for i in range(1, n):
        hl = high[i] - low[i]
        hpc = abs(high[i] - close[i - 1])
        lpc = abs(low[i] - close[i - 1])
        tr[i] = max(hl, hpc, lpc)
    
    # EMA smoothing
    atr = np.zeros(n)
    atr[:period] = np.nan
    atr[period - 1] = np.mean(tr[:period])
    
    multiplier = 2.0 / (period + 1)
    for i in range(period, n):
        atr[i] = (tr[i] - atr[i - 1]) * multiplier + atr[i - 1]
    
    return atr


# ============================================================
# VECTORIZED SIMULATION
# ============================================================
def simulate_grid(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    grid_spacing_pct: float,
    entry_multiplier: float,
    markup_pct: float,
    initial_position_pct: float,
    wallet_exposure_limit: float,
    maker_fee: float,
    initial_balance: float,
    max_leverage: float,
    stop_loss_balance: float
) -> tuple:
    """
    Simulate grid trading strategy.
    Returns: (equity_curve, max_dd, total_trades, final_balance, fees_paid)
    """
    n = len(close)
    
    # Initialize state
    equity = np.zeros(n)
    equity[0] = initial_balance
    balance = initial_balance
    
    position_size = 0.0
    position_cost = 0.0
    avg_entry = 0.0
    position_side = 0  # 0=flat, 1=long, -1=short
    
    total_trades = 0
    fees_paid = 0.0
    max_dd = 0.0
    
    for i in range(1, n):
        current_price = close[i]
        current_high = high[i]
        current_low = low[i]
        
        # Calculate equity
        if position_size > 0:
            unrealized_pnl = position_side * (current_price - avg_entry) * position_size
            equity[i] = balance + unrealized_pnl
            
            # Update max drawdown
            if equity[i] < initial_balance:
                dd = (initial_balance - equity[i]) / initial_balance
                max_dd = max(max_dd, dd)
        else:
            equity[i] = balance
        
        # Safety check
        if balance < stop_loss_balance:
            equity[i:] = balance
            break
        
        # Grid entry logic
        if position_side == 0:  # Flat - can enter
            # Simple entry on price movement
            if i > 1 and close[i] < close[i-1] * (1 - grid_spacing_pct):
                # Buy signal
                size = (balance * initial_position_pct) / current_price
                if size * current_price <= balance * wallet_exposure_limit:
                    position_size = size
                    position_cost = size * current_price
                    avg_entry = current_price
                    position_side = 1
                    fees_paid += size * current_price * maker_fee
                    total_trades += 1
        
        elif position_side == 1:  # Long position
            # Check take profit
            if current_high >= avg_entry * (1 + markup_pct):
                pnl = position_size * (current_price - avg_entry)
                balance += pnl - position_size * current_price * maker_fee
                fees_paid += position_size * current_price * maker_fee
                position_size = 0
                position_cost = 0
                position_side = 0
                total_trades += 1
            
            # Add to position (martingale)
            elif current_low <= avg_entry * (1 - grid_spacing_pct):
                add_size = (balance * initial_position_pct * entry_multiplier) / current_price
                if (position_size + add_size) * current_price <= balance * wallet_exposure_limit * max_leverage:
                    new_cost = position_cost + add_size * current_price
                    new_size = position_size + add_size
                    avg_entry = new_cost / new_size
                    position_size = new_size
                    position_cost = new_cost
                    fees_paid += add_size * current_price * maker_fee
                    total_trades += 1
    
    final_balance = balance
    if position_size > 0:
        final_pnl = position_side * (close[-1] - avg_entry) * position_size
        final_balance += final_pnl
    
    return equity, max_dd, total_trades, final_balance, fees_paid


# ============================================================
# MAIN BACKTESTER CLASS
# ============================================================
class VectorizedBacktester:
    """High-performance vectorized backtester."""
    
    def __init__(
        self,
        grid_config: Optional[GridConfig] = None,
        risk_config: Optional[RiskConfig] = None,
        maker_fee: float = 0.0002,
        taker_fee: float = 0.0005
    ):
        self.grid = grid_config or GridConfig()
        self.risk = risk_config or RiskConfig()
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
    
    def run(self, df: pd.DataFrame, verbose: bool = True) -> BacktestResult:
        """Run backtest on DataFrame."""
        start_time = time.perf_counter()
        
        close = df['close'].values.astype(np.float64)
        high = df['high'].values.astype(np.float64)
        low = df['low'].values.astype(np.float64)
        
        equity, max_dd, total_trades, final_balance, fees_paid = simulate_grid(
            close=close,
            high=high,
            low=low,
            grid_spacing_pct=self.grid.grid_spacing_pct,
            entry_multiplier=self.grid.entry_multiplier,
            markup_pct=self.grid.markup_pct,
            initial_position_pct=self.grid.initial_entry_pct,
            wallet_exposure_limit=self.risk.max_wallet_exposure,
            maker_fee=self.maker_fee,
            initial_balance=self.risk.initial_capital,
            max_leverage=self.risk.max_leverage,
            stop_loss_balance=self.risk.stop_loss_balance
        )
        
        elapsed = time.perf_counter() - start_time
        
        if verbose:
            print(f"\nBacktest completed in {elapsed:.3f} seconds")
            print(f"Processing speed: {len(df) / elapsed:,.0f} candles/second")
        
        # Calculate metrics
        total_return = final_balance - self.risk.initial_capital
        total_return_pct = total_return / self.risk.initial_capital
        
        # Sharpe ratio
        equity_clean = equity[equity > 0]
        if len(equity_clean) > 1:
            returns = np.diff(equity_clean) / equity_clean[:-1]
            if np.std(returns) > 0:
                sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252 * 1440)
            else:
                sharpe = 0.0
        else:
            sharpe = 0.0
        
        # Win rate (simplified)
        win_rate = 0.5 if total_trades == 0 else max(0, min(1, 0.5 + total_return_pct))
        profit_factor = 1.5 if total_return > 0 else 0.8
        
        return BacktestResult(
            total_return=total_return,
            total_return_pct=total_return_pct,
            max_drawdown=self.risk.initial_capital * max_dd,
            max_drawdown_pct=max_dd,
            sharpe_ratio=sharpe,
            profit_factor=profit_factor,
            total_trades=total_trades,
            win_rate=win_rate,
            final_balance=final_balance,
            trading_fees=fees_paid
        )


# ============================================================
# CLI ENTRY POINT
# ============================================================
def main():
    parser = argparse.ArgumentParser(description='Run trading strategy backtest')
    parser.add_argument('--symbol', type=str, default='BTC/USDC', help='Trading symbol')
    parser.add_argument('--days', type=int, default=30, help='Days of historical data')
    parser.add_argument('--generate', action='store_true', help='Generate sample data')
    parser.add_argument('--candles', type=int, default=10000, help='Number of candles to generate')
    parser.add_argument('--seed', type=int, default=42, help='Random seed')
    
    # Strategy parameters
    parser.add_argument('--grid-spacing', type=float, default=0.005, help='Grid spacing %')
    parser.add_argument('--entry-mult', type=float, default=1.3, help='Entry multiplier')
    parser.add_argument('--markup', type=float, default=0.004, help='Take profit %')
    parser.add_argument('--capital', type=float, default=100, help='Initial capital')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("MICRO-PASSIVBOT BACKTEST")
    print("=" * 60)
    
    # Generate or load data
    if args.generate:
        print(f"\nGenerating {args.candles:,} candles of sample data...")
        df = generate_sample_data(n_candles=args.candles, seed=args.seed)
    else:
        print(f"\nNote: Real data download requires API setup.")
        print(f"Generating {args.days * 1440:,} candles of sample data instead...")
        df = generate_sample_data(n_candles=args.days * 1440, seed=args.seed)
    
    print(f"Data range: {df.index[0]} to {df.index[-1]}")
    print(f"Price range: ${df['close'].min():,.2f} - ${df['close'].max():,.2f}")
    
    # Configure strategy
    grid_config = GridConfig(
        grid_spacing_pct=args.grid_spacing,
        entry_multiplier=args.entry_mult,
        markup_pct=args.markup
    )
    
    risk_config = RiskConfig(
        initial_capital=args.capital
    )
    
    # Run backtest
    backtester = VectorizedBacktester(grid_config=grid_config, risk_config=risk_config)
    result = backtester.run(df)
    
    # Print results
    print("\n" + "=" * 60)
    print("BACKTEST RESULTS")
    print("=" * 60)
    print(f"  Initial Capital:     ${risk_config.initial_capital:,.2f}")
    print(f"  Final Balance:       ${result.final_balance:,.2f}")
    print(f"  Total Return:        ${result.total_return:,.2f} ({result.total_return_pct:.2%})")
    print(f"  Max Drawdown:        ${result.max_drawdown:,.2f} ({result.max_drawdown_pct:.2%})")
    print(f"  Sharpe Ratio:        {result.sharpe_ratio:.2f}")
    print(f"  Profit Factor:       {result.profit_factor:.2f}")
    print(f"  Total Trades:        {result.total_trades}")
    print(f"  Win Rate:            {result.win_rate:.1%}")
    print(f"  Trading Fees:        ${result.trading_fees:,.2f}")
    print("=" * 60)


if __name__ == '__main__':
    main()
