#!/usr/bin/env python3
"""
Micro-PassivBot Backtest
=========================
Optimized for $100 account with $2-10 position sizes.

The key challenge: FEES EAT PROFITS on small trades!
- $2 trade with 0.05% fee = $0.001 fee (need 0.5% move just to break even!)
- $10 trade with 0.05% fee = $0.005 fee

This is why Hyperliquid (0.02% maker) is CRITICAL for micro-accounts.
"""

import argparse
import sys
import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional
import time


# ============================================================
# CONFIGURATION FOR MICRO-ACCOUNTS
# ============================================================
@dataclass
class MicroGridConfig:
    """Grid config optimized for $2-10 positions."""
    grid_spacing_pct: float = 0.008      # 0.8% - larger spacing for small positions
    entry_multiplier: float = 1.5        # More aggressive re-entry
    markup_pct: float = 0.006            # 0.6% take profit (must be > fees!)
    initial_entry_pct: float = 0.02      # 2% of balance = $2 initial
    max_position_usd: float = 10.0       # Max $10 per position
    min_position_usd: float = 2.0        # Min $2 per position


@dataclass  
class MicroRiskConfig:
    """Risk config for $100 account."""
    initial_capital: float = 100.0
    stop_loss_balance: float = 80.0      # Stop at $80
    max_leverage: float = 5.0
    max_wallet_exposure: float = 0.25    # Max 25% per pair = $25
    max_positions: int = 3               # Max 3 positions at once


@dataclass
class ExchangeFees:
    """Fee structure comparison."""
    name: str
    maker_fee: float
    taker_fee: float
    
    def round_trip_cost(self, position_usd: float) -> float:
        """Calculate round-trip cost for a position."""
        return position_usd * (self.maker_fee + self.taker_fee)
    
    def break_even_pct(self) -> float:
        """Minimum price move needed to break even."""
        return self.maker_fee + self.taker_fee


# Exchange fee comparison
EXCHANGES = {
    'hyperliquid': ExchangeFees('Hyperliquid', 0.0002, 0.0005),  # 0.07% round trip
    'bybit': ExchangeFees('Bybit', 0.0002, 0.00055),              # 0.075% round trip
    'binance': ExchangeFees('Binance', 0.0002, 0.0005),           # 0.07% round trip
    'binance_standard': ExchangeFees('Binance Standard', 0.001, 0.001),  # 0.2% round trip!
}


# ============================================================
# MICRO POSITION SIZE CALCULATOR
# ============================================================
class MicroPositionSizer:
    """Calculate optimal position sizes for micro-accounts."""
    
    @staticmethod
    def calculate_position_size(
        balance: float,
        price: float,
        min_usd: float = 2.0,
        max_usd: float = 10.0,
        risk_pct: float = 0.02
    ) -> tuple:
        """
        Calculate position size for micro-account.
        
        Returns: (size_in_base, position_value_usd)
        """
        # Start with risk percentage
        desired_usd = balance * risk_pct
        
        # Clamp to min/max
        position_usd = max(min_usd, min(max_usd, desired_usd))
        
        # Convert to base currency
        size = position_usd / price
        
        return size, position_usd
    
    @staticmethod
    def calculate_grid_levels(
        balance: float,
        current_price: float,
        grid_spacing_pct: float,
        entry_multiplier: float,
        min_usd: float = 2.0,
        max_usd: float = 10.0,
        max_levels: int = 5
    ) -> list:
        """
        Calculate grid levels for micro-account.
        
        Returns list of (price, size_usd, level)
        """
        levels = []
        cumulative_usd = 0
        
        base_size_usd = max(min_usd, min(max_usd, balance * 0.02))
        
        for level in range(max_levels):
            # Price level
            price = current_price * (1 - grid_spacing_pct * (level + 1))
            
            # Size with multiplier
            size_usd = base_size_usd * (entry_multiplier ** level)
            
            # Cap at max
            size_usd = min(size_usd, max_usd)
            
            # Check total exposure
            if cumulative_usd + size_usd > balance * 0.25:
                break
            
            cumulative_usd += size_usd
            levels.append({
                'level': level + 1,
                'price': price,
                'size_usd': size_usd,
                'size_base': size_usd / price,
                'cumulative_usd': cumulative_usd
            })
        
        return levels


# ============================================================
# MICRO BACKTESTER
# ============================================================
class MicroBacktester:
    """
    Backtester optimized for $2-10 position sizes.
    
    Key considerations for micro-trades:
    1. Fees are HUGE percentage of trade
    2. Minimum trade sizes on exchanges
    3. Spread matters more
    4. Slippage modeling critical
    """
    
    def __init__(
        self,
        grid_config: Optional[MicroGridConfig] = None,
        risk_config: Optional[MicroRiskConfig] = None,
        exchange: str = 'hyperliquid'
    ):
        self.grid = grid_config or MicroGridConfig()
        self.risk = risk_config or MicroRiskConfig()
        self.fees = EXCHANGES.get(exchange, EXCHANGES['hyperliquid'])
        
    def _calculate_realistic_slippage(self, position_usd: float, volatility: float) -> float:
        """
        Calculate realistic slippage for small positions.
        
        Small positions actually have BETTER slippage (less market impact).
        """
        # Base slippage
        base = 0.0001  # 0.01%
        
        # Volatility adjustment
        vol_adj = volatility * 0.1
        
        # Size adjustment (smaller = better)
        if position_usd < 5:
            size_adj = -0.00005  # Tiny positions get better fills
        elif position_usd < 20:
            size_adj = 0
        else:
            size_adj = 0.0001
        
        return max(0.00005, base + vol_adj + size_adj)
    
    def run(self, df: pd.DataFrame, verbose: bool = True) -> dict:
        """Run micro-position backtest."""
        start_time = time.perf_counter()
        
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        
        # Calculate volatility
        returns = np.diff(np.log(close))
        returns = np.insert(returns, 0, 0)
        volatility = pd.Series(returns).rolling(20).std().fillna(0.02).values
        
        # State
        balance = self.risk.initial_capital
        equity_curve = np.zeros(len(close))
        equity_curve[0] = balance
        
        position_size = 0.0
        position_cost = 0.0
        avg_entry = 0.0
        in_position = False
        
        total_trades = 0
        winning_trades = 0
        total_fees = 0.0
        total_pnl = 0.0
        max_dd = 0.0
        peak_equity = balance
        
        trade_log = []
        
        for i in range(1, len(close)):
            price = close[i]
            h = high[i]
            l = low[i]
            vol = volatility[i]
            
            # Update equity
            if in_position:
                unrealized = (price - avg_entry) * position_size
                equity = balance + unrealized
            else:
                equity = balance
            
            equity_curve[i] = equity
            
            # Track max drawdown
            if equity > peak_equity:
                peak_equity = equity
            dd = (peak_equity - equity) / peak_equity
            max_dd = max(max_dd, dd)
            
            # Safety check
            if balance < self.risk.stop_loss_balance:
                break
            
            # Position management
            if not in_position:
                # Entry signal - price dropped
                if l < close[i-1] * (1 - self.grid.grid_spacing_pct):
                    # Calculate position size
                    pos_usd = max(self.grid.min_position_usd, 
                                 min(self.grid.max_position_usd, balance * self.grid.initial_entry_pct))
                    
                    # Slippage
                    slippage = self._calculate_realistic_slippage(pos_usd, vol)
                    entry_price = price * (1 + slippage)  # Buy slightly higher
                    
                    size = pos_usd / entry_price
                    
                    # Fee
                    fee = pos_usd * self.fees.maker_fee
                    total_fees += fee
                    
                    position_size = size
                    position_cost = pos_usd
                    avg_entry = entry_price
                    in_position = True
                    
                    trade_log.append({
                        'type': 'BUY',
                        'price': entry_price,
                        'size': size,
                        'value_usd': pos_usd,
                        'fee': fee,
                        'bar': i
                    })
                    
                    total_trades += 1
            
            else:
                # In position - check take profit or add
                tp_price = avg_entry * (1 + self.grid.markup_pct)
                add_price = avg_entry * (1 - self.grid.grid_spacing_pct)
                
                # Take profit
                if h >= tp_price:
                    # Slippage on exit
                    slippage = self._calculate_realistic_slippage(position_cost, vol)
                    exit_price = tp_price * (1 - slippage)
                    
                    gross = position_size * exit_price
                    fee = gross * self.fees.maker_fee
                    pnl = (exit_price - avg_entry) * position_size - fee
                    
                    balance += pnl
                    total_fees += fee
                    total_pnl += pnl
                    total_trades += 1
                    
                    if pnl > 0:
                        winning_trades += 1
                    
                    trade_log.append({
                        'type': 'SELL_TP',
                        'price': exit_price,
                        'size': position_size,
                        'pnl': pnl,
                        'fee': fee,
                        'bar': i
                    })
                    
                    position_size = 0
                    position_cost = 0
                    in_position = False
                
                # Add to position (martingale)
                elif l <= add_price and position_cost < self.grid.max_position_usd:
                    add_usd = min(self.grid.max_position_usd - position_cost,
                                 position_cost * (self.grid.entry_multiplier - 1))
                    add_usd = max(self.grid.min_position_usd, add_usd)
                    
                    if add_usd > 0 and position_cost + add_usd <= balance * 0.25:
                        slippage = self._calculate_realistic_slippage(add_usd, vol)
                        add_price_actual = add_price * (1 + slippage)
                        add_size = add_usd / add_price_actual
                        
                        fee = add_usd * self.fees.maker_fee
                        total_fees += fee
                        
                        new_cost = position_cost + add_usd
                        new_size = position_size + add_size
                        avg_entry = (position_cost + add_usd) / new_size
                        
                        position_size = new_size
                        position_cost = new_cost
                        
                        trade_log.append({
                            'type': 'BUY_ADD',
                            'price': add_price_actual,
                            'size': add_size,
                            'value_usd': add_usd,
                            'fee': fee,
                            'bar': i
                        })
                        
                        total_trades += 1
        
        elapsed = time.perf_counter() - start_time
        
        # Final stats
        final_equity = balance
        if in_position:
            final_equity += (close[-1] - avg_entry) * position_size
        
        total_return = final_equity - self.risk.initial_capital
        total_return_pct = total_return / self.risk.initial_capital
        
        win_rate = winning_trades / max(total_trades, 1)
        
        # Calculate Sharpe
        clean_equity = equity_curve[equity_curve > 0]
        if len(clean_equity) > 1:
            eq_returns = np.diff(clean_equity) / clean_equity[:-1]
            sharpe = np.mean(eq_returns) / max(np.std(eq_returns), 0.001) * np.sqrt(525600)
        else:
            sharpe = 0
        
        result = {
            'initial_capital': self.risk.initial_capital,
            'final_balance': final_equity,
            'total_return': total_return,
            'total_return_pct': total_return_pct,
            'max_drawdown_pct': max_dd,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'win_rate': win_rate,
            'total_fees': total_fees,
            'total_pnl': total_pnl,
            'sharpe_ratio': sharpe,
            'processing_time': elapsed,
            'candles_per_sec': len(df) / elapsed,
            'exchange': self.fees.name,
            'avg_trade_value': self.grid.max_position_usd / 2,
            'trade_log': trade_log[-20:] if trade_log else []  # Last 20 trades
        }
        
        if verbose:
            self._print_results(result)
        
        return result
    
    def _print_results(self, r: dict):
        """Print formatted results."""
        print("\n" + "=" * 60)
        print("MICRO-PASSIVBOT BACKTEST RESULTS")
        print("=" * 60)
        print(f"  Exchange:           {r['exchange']}")
        print(f"  Avg Trade Size:     ${r['avg_trade_value']:.2f}")
        print("-" * 60)
        print(f"  Initial Capital:    ${r['initial_capital']:.2f}")
        print(f"  Final Balance:      ${r['final_balance']:.2f}")
        print(f"  Total Return:       ${r['total_return']:.2f} ({r['total_return_pct']:.2%})")
        print(f"  Max Drawdown:       {r['max_drawdown_pct']:.2%}")
        print("-" * 60)
        print(f"  Total Trades:       {r['total_trades']}")
        print(f"  Winning Trades:     {r['winning_trades']}")
        print(f"  Win Rate:           {r['win_rate']:.1%}")
        print(f"  Total Fees:         ${r['total_fees']:.2f}")
        print(f"  Sharpe Ratio:       {r['sharpe_ratio']:.2f}")
        print("-" * 60)
        print(f"  Processing:         {r['processing_time']:.3f}s ({r['candles_per_sec']:,.0f} candles/s)")
        print("=" * 60)


# ============================================================
# FEE IMPACT ANALYZER
# ============================================================
def analyze_fee_impact():
    """Show how fees impact small positions."""
    print("\n" + "=" * 60)
    print("FEE IMPACT ON MICRO-POSITIONS ($2-10)")
    print("=" * 60)
    
    positions = [2, 3, 4, 5, 10]
    
    print(f"\n{'Position':>10} | {'Hyperliquid':>15} | {'Bybit':>15} | {'Binance Std':>15}")
    print("-" * 60)
    
    for pos in positions:
        h_fee = EXCHANGES['hyperliquid'].round_trip_cost(pos)
        b_fee = EXCHANGES['bybit'].round_trip_cost(pos)
        bn_fee = EXCHANGES['binance_standard'].round_trip_cost(pos)
        
        print(f"${pos:>9} | ${h_fee:>14.4f} | ${b_fee:>14.4f} | ${bn_fee:>14.4f}")
    
    print("\n" + "-" * 60)
    print("BREAK-EVEN PRICE MOVE NEEDED:")
    print("-" * 60)
    
    for name, ex in EXCHANGES.items():
        be = ex.break_even_pct()
        print(f"  {ex.name}: {be:.3%} move needed to break even")
    
    print("\n" + "-" * 60)
    print("PROFIT AFTER 0.5% PRICE MOVE:")
    print("-" * 60)
    
    price_move = 0.005  # 0.5%
    
    for pos in positions:
        gross_profit = pos * price_move
        print(f"\n  ${pos} position, ${gross_profit:.3f} gross profit:")
        for name, ex in EXCHANGES.items():
            fee = ex.round_trip_cost(pos)
            net = gross_profit - fee
            print(f"    {ex.name}: ${net:.4f} net ({net/gross_profit*100:.0f}% of gross)")


# ============================================================
# GENERATE SAMPLE DATA
# ============================================================
def generate_sample_data(n_candles: int = 10000, seed: int = 42) -> pd.DataFrame:
    """Generate realistic crypto price data."""
    np.random.seed(seed)
    
    start_time = datetime.now() - timedelta(minutes=n_candles)
    timestamps = pd.date_range(start=start_time, periods=n_candles, freq='1min')
    
    # More realistic crypto volatility
    volatility = 0.015
    drift = 0.00001
    
    returns = np.random.normal(drift, volatility, n_candles)
    prices = 50000 * np.exp(np.cumsum(returns))
    
    df = pd.DataFrame(index=timestamps)
    df['close'] = prices
    
    # Realistic OHLC
    spread = volatility * prices * 0.3
    df['high'] = df['close'] + np.abs(np.random.normal(0, spread, n_candles))
    df['low'] = df['close'] - np.abs(np.random.normal(0, spread, n_candles))
    df['open'] = df['close'].shift(1).fillna(50000)
    
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)
    df['volume'] = np.random.exponential(100, n_candles)
    
    return df


# ============================================================
# CLI
# ============================================================
def main():
    parser = argparse.ArgumentParser(description='Micro-PassivBot Backtest for $2-10 positions')
    
    parser.add_argument('--candles', type=int, default=50000, help='Number of candles')
    parser.add_argument('--capital', type=float, default=100, help='Initial capital')
    parser.add_argument('--min-pos', type=float, default=2, help='Minimum position USD')
    parser.add_argument('--max-pos', type=float, default=10, help='Maximum position USD')
    parser.add_argument('--exchange', type=str, default='hyperliquid',
                       choices=['hyperliquid', 'bybit', 'binance', 'binance_standard'])
    parser.add_argument('--grid-spacing', type=float, default=0.008, help='Grid spacing %')
    parser.add_argument('--markup', type=float, default=0.006, help='Take profit %')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--analyze-fees', action='store_true', help='Show fee analysis')
    
    args = parser.parse_args()
    
    if args.analyze_fees:
        analyze_fee_impact()
        return
    
    print("=" * 60)
    print("MICRO-PASSIVBOT BACKTEST")
    print("Optimized for $2-10 position sizes")
    print("=" * 60)
    
    # Generate data
    print(f"\nGenerating {args.candles:,} candles...")
    df = generate_sample_data(n_candles=args.candles, seed=args.seed)
    print(f"Price range: ${df['close'].min():,.2f} - ${df['close'].max():,.2f}")
    
    # Configure
    grid_config = MicroGridConfig(
        grid_spacing_pct=args.grid_spacing,
        markup_pct=args.markup,
        min_position_usd=args.min_pos,
        max_position_usd=args.max_pos
    )
    
    risk_config = MicroRiskConfig(
        initial_capital=args.capital
    )
    
    # Run backtest
    backtester = MicroBacktester(
        grid_config=grid_config,
        risk_config=risk_config,
        exchange=args.exchange
    )
    
    result = backtester.run(df)
    
    # Show fee impact
    print("\n" + "-" * 60)
    print("FEE ANALYSIS FOR THIS BACKTEST:")
    print("-" * 60)
    print(f"  Total fees paid: ${result['total_fees']:.2f}")
    print(f"  Fees as % of PnL: {result['total_fees']/max(abs(result['total_pnl']), 0.01)*100:.1f}%")
    print(f"  Avg fee per trade: ${result['total_fees']/max(result['total_trades'], 1):.4f}")


if __name__ == '__main__':
    main()
