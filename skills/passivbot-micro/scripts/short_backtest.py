#!/usr/bin/env python3
"""
Micro SHORT Grid Strategy
=========================
Grid trading dla pozycji SHORT - zarabia gdy cena spada.

Dla $100 konta:
- Otwiera SHORT gdy cena rośnie (sell high)
- Zamyka z zyskiem gdy cena spada (buy back lower)
- Stop loss gdy cena wzrośnie za bardzo
"""

import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/skills/passivbot-micro/scripts')

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional
import time


@dataclass
class ShortGridConfig:
    """Short grid configuration."""
    grid_spacing_pct: float = 0.005      # 0.5% - otwieraj short co 0.5% wzrostu
    entry_multiplier: float = 1.5        # Mnożnik przy dodawaniu
    markup_pct: float = 0.006            # 0.6% - zamykaj gdy cena spadnie o 0.6%
    initial_entry_pct: float = 0.02      # 2% kapitału na start
    max_position_usd: float = 10.0       # Max $10 pozycja
    min_position_usd: float = 2.0        # Min $2 pozycja
    stop_loss_pct: float = 0.03          # 3% stop loss


@dataclass  
class ShortRiskConfig:
    """Risk config for short strategy."""
    initial_capital: float = 100.0
    stop_loss_balance: float = 80.0
    max_wallet_exposure: float = 0.25    # Max 25% w short


@dataclass
class ExchangeFees:
    """Fee structure."""
    name: str
    maker_fee: float
    taker_fee: float


EXCHANGES = {
    'hyperliquid': ExchangeFees('Hyperliquid', 0.0002, 0.0005),
    'bybit': ExchangeFees('Bybit', 0.0002, 0.00055),
}


class ShortGridBacktester:
    """
    Backtester dla strategii SHORT grid.
    
    Jak działa:
    1. Gdy cena WZRASTA o grid_spacing% → otwieraj SHORT (sprzedaj)
    2. Gdy cena SPADA o markup% → zamykaj SHORT (kup z powrotem)
    3. Jeśli cena wzrośnie o stop_loss% → zamknij stratę
    """
    
    def __init__(
        self,
        grid_config: Optional[ShortGridConfig] = None,
        risk_config: Optional[ShortRiskConfig] = None,
        exchange: str = 'hyperliquid'
    ):
        self.grid = grid_config or ShortGridConfig()
        self.risk = risk_config or ShortRiskConfig()
        self.fees = EXCHANGES.get(exchange, EXCHANGES['hyperliquid'])
        
    def run(self, df: pd.DataFrame, verbose: bool = True) -> dict:
        """Run short grid backtest."""
        start_time = time.perf_counter()
        
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        
        # State
        balance = self.risk.initial_capital
        equity_curve = np.zeros(len(close))
        equity_curve[0] = balance
        
        # Short position tracking
        position_size = 0.0      # Ile BTC jest short
        position_entry_price = 0.0  # Po ile otworzyliśmy short
        position_value = 0.0     # Wartość w USD
        in_position = False
        
        total_trades = 0
        winning_trades = 0
        total_fees = 0.0
        total_pnl = 0.0
        max_dd = 0.0
        peak_equity = balance
        
        trade_log = []
        last_entry_price = close[0]
        
        for i in range(1, len(close)):
            price = close[i]
            h = high[i]
            l = low[i]
            
            # Calculate equity (for short: profit when price drops)
            if in_position:
                # Short PnL: (entry_price - current_price) * size
                unrealized = (position_entry_price - price) * position_size
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
            
            if not in_position:
                # Entry signal: price went UP by grid_spacing
                if price > last_entry_price * (1 + self.grid.grid_spacing_pct):
                    # Open SHORT position
                    pos_usd = max(self.grid.min_position_usd,
                                 min(self.grid.max_position_usd, balance * self.grid.initial_entry_pct))
                    
                    # Check exposure limit
                    if pos_usd <= balance * self.risk.max_wallet_exposure:
                        fee = pos_usd * self.fees.maker_fee
                        total_fees += fee
                        
                        # Short: borrow and sell
                        position_size = pos_usd / price  # Ile BTC shortujemy
                        position_entry_price = price
                        position_value = pos_usd
                        in_position = True
                        last_entry_price = price
                        
                        trade_log.append({
                            'type': 'OPEN_SHORT',
                            'price': price,
                            'size': position_size,
                            'value_usd': pos_usd,
                            'fee': fee,
                            'bar': i
                        })
                        
                        total_trades += 1
            
            else:
                # In short position - check take profit or stop loss
                tp_price = position_entry_price * (1 - self.grid.markup_pct)
                sl_price = position_entry_price * (1 + self.grid.stop_loss_pct)
                add_price = position_entry_price * (1 + self.grid.grid_spacing_pct)
                
                # Take profit: price dropped
                if l <= tp_price:
                    # Close short at profit
                    pnl = (position_entry_price - tp_price) * position_size
                    close_value = position_size * tp_price
                    fee = close_value * self.fees.maker_fee
                    
                    balance += pnl - fee
                    total_fees += fee
                    total_pnl += pnl
                    total_trades += 1
                    
                    if pnl > 0:
                        winning_trades += 1
                    
                    trade_log.append({
                        'type': 'CLOSE_TP',
                        'price': tp_price,
                        'pnl': pnl,
                        'fee': fee,
                        'bar': i
                    })
                    
                    position_size = 0
                    position_value = 0
                    in_position = False
                    last_entry_price = tp_price
                
                # Stop loss: price rose too much
                elif h >= sl_price:
                    # Close short at loss
                    loss = (sl_price - position_entry_price) * position_size
                    close_value = position_size * sl_price
                    fee = close_value * self.fees.maker_fee
                    
                    balance -= loss + fee
                    total_fees += fee
                    total_pnl -= loss
                    total_trades += 1
                    
                    trade_log.append({
                        'type': 'CLOSE_SL',
                        'price': sl_price,
                        'loss': loss,
                        'fee': fee,
                        'bar': i
                    })
                    
                    position_size = 0
                    position_value = 0
                    in_position = False
                    last_entry_price = sl_price
                
                # Add to position (grid up)
                elif h >= add_price and position_value < self.grid.max_position_usd:
                    add_usd = min(self.grid.max_position_usd - position_value,
                                 position_value * (self.grid.entry_multiplier - 1))
                    add_usd = max(self.grid.min_position_usd, add_usd)
                    
                    if add_usd > 0 and position_value + add_usd <= balance * self.risk.max_wallet_exposure:
                        fee = add_usd * self.fees.maker_fee
                        total_fees += fee
                        
                        add_size = add_usd / price
                        
                        # Update average entry price for short
                        new_size = position_size + add_size
                        new_value = position_value + add_usd
                        avg_entry = (position_entry_price * position_size + price * add_size) / new_size
                        
                        position_size = new_size
                        position_value = new_value
                        position_entry_price = avg_entry
                        
                        trade_log.append({
                            'type': 'ADD_SHORT',
                            'price': price,
                            'size': add_size,
                            'value_usd': add_usd,
                            'fee': fee,
                            'bar': i
                        })
                        
                        total_trades += 1
                        last_entry_price = price
        
        elapsed = time.perf_counter() - start_time
        
        # Final stats
        final_equity = balance
        if in_position:
            final_price = close[-1]
            pnl = (position_entry_price - final_price) * position_size
            final_equity += pnl
        
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
            'trade_log': trade_log[-10:] if trade_log else []
        }
        
        if verbose:
            self._print_results(result)
        
        return result
    
    def _print_results(self, r: dict):
        """Print formatted results."""
        print("\n" + "=" * 60)
        print("SHORT GRID BACKTEST RESULTS")
        print("=" * 60)
        print(f"  Strategy:           SHORT (zarabia na spadkach)")
        print(f"  Exchange:           {r['exchange']}")
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
        print(f"  Processing:         {r['processing_time']:.3f}s")
        print("=" * 60)


def main():
    """Run short grid test on BTC data."""
    print("=" * 60)
    print("SHORT GRID STRATEGY TEST")
    print("=" * 60)
    
    # Load BTC data
    df = pd.read_csv('/home/ubuntu/.openclaw/workspace/memory/passivbot_data/BTC_USDC_1m.csv')
    print(f"\nLoaded BTC: {len(df)} candles ({len(df)/(24*60):.0f} days)")
    print(f"Trend: {(df['close'].iloc[-1] / df['close'].iloc[0] - 1) * 100:.2f}%")
    
    # Use last 30 days
    df_test = df.tail(30 * 24 * 60).reset_index(drop=True)
    
    print(f"\nTesting on last {len(df_test)} candles (30 days)")
    print(f"Period trend: {(df_test['close'].iloc[-1] / df_test['close'].iloc[0] - 1) * 100:.2f}%")
    
    # Test different short grid configs
    configs = [
        ('Conservative Short', 0.008, 1.3, 0.010, 0.025),
        ('Standard Short', 0.005, 1.5, 0.006, 0.030),
        ('Aggressive Short', 0.003, 1.8, 0.005, 0.040),
    ]
    
    print("\n" + "=" * 60)
    print("COMPARING SHORT STRATEGIES")
    print("=" * 60)
    
    results = []
    
    for name, spacing, mult, markup, sl in configs:
        print(f"\n{name}:")
        print(f"  Grid: {spacing:.2%}, Mult: {mult}x, Markup: {markup:.2%}, SL: {sl:.2%}")
        
        grid = ShortGridConfig(
            grid_spacing_pct=spacing,
            entry_multiplier=mult,
            markup_pct=markup,
            stop_loss_pct=sl
        )
        risk = ShortRiskConfig()
        
        bt = ShortGridBacktester(grid_config=grid, risk_config=risk)
        result = bt.run(df_test, verbose=False)
        
        results.append((name, result))
        
        print(f"  Return: {result['total_return_pct']*100:+.2f}%")
        print(f"  DD: {result['max_drawdown_pct']*100:.2f}%")
        print(f"  Trades: {result['total_trades']}")
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY - SHORT vs LONG on BTC (-22.5% trend)")
    print("=" * 60)
    print(f"{'Strategy':<20} {'Return':>10} {'DD':>8} {'Trades':>8}")
    print("-" * 60)
    
    for name, result in results:
        ret = result['total_return_pct'] * 100
        dd = result['max_drawdown_pct'] * 100
        trades = result['total_trades']
        print(f"{name:<20} {ret:>+9.2f}% {dd:>7.2f}% {trades:>8}")
    
    print("\nNote: Short strategy zarabia gdy cena spada.")
    print("W trendzie spadkowym (-22.5%) powinno to działać lepiej niż LONG.")


if __name__ == '__main__':
    main()
