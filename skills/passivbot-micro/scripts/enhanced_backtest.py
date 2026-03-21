"""
ENHANCED BACKTEST ENGINE
========================
Silnik backtestu dla EnhancedUnifiedBot z metrykami i wykresami.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import json
import os

# Import our modules
try:
    from technical_analysis import SidewaysAnalyzer, TechnicalIndicators
    from enhanced_unified_bot import EnhancedConfig, RiskMetrics
except ImportError:
    import sys
    sys.path.append(os.path.dirname(__file__))
    from technical_analysis import SidewaysAnalyzer, TechnicalIndicators
    from enhanced_unified_bot import EnhancedConfig, RiskMetrics


@dataclass
class BacktestTrade:
    """Pojedynczy trade w backteście"""
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    pnl_pct: float
    exit_reason: str
    dca_count: int
    max_drawdown: float


@dataclass
class BacktestResult:
    """Wyniki backtestu"""
    trades: List[BacktestTrade]
    total_return: float
    total_return_pct: float
    win_rate: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: float
    avg_trade_duration: float
    avg_win: float
    avg_loss: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    final_balance: float
    equity_curve: List[Dict]


class EnhancedBacktestEngine:
    """Silnik backtestu dla strategii sideways"""
    
    def __init__(
        self,
        config: EnhancedConfig,
        initial_balance: float = 100.0,
        fee_rate: float = 0.0007,  # 0.07% round trip
        slippage: float = 0.0001   # 0.01% slippage
    ):
        self.config = config
        self.initial_balance = initial_balance
        self.fee_rate = fee_rate
        self.slippage = slippage
        self.balance = initial_balance
        self.peak_balance = initial_balance
        self.max_drawdown = 0.0
        
        # Tracking
        self.equity_curve = []
        self.trades: List[BacktestTrade] = []
        self.positions: Dict[str, Dict] = {}
        self.daily_returns = []
        self.risk_metrics = RiskMetrics(initial_balance=initial_balance)
    
    def run_backtest(
        self,
        df: pd.DataFrame,
        verbose: bool = True
    ) -> BacktestResult:
        """
        Uruchom backtest na danych historycznych.
        
        Args:
            df: DataFrame z kolumnami: open, high, low, close, volume (opcjonalnie)
            verbose: Czy wypisywać postęp
        
        Returns:
            BacktestResult z pełnymi wynikami
        """
        # Reset state
        self.balance = self.initial_balance
        self.peak_balance = self.initial_balance
        self.max_drawdown = 0.0
        self.equity_curve = []
        self.trades = []
        self.positions = {}
        self.risk_metrics = RiskMetrics(initial_balance=self.initial_balance)
        self.risk_metrics.peak_balance = self.initial_balance
        
        # Warm up period
        warmup = 50
        
        for i in range(warmup, len(df)):
            current_time = df.index[i] if hasattr(df.index, 'strftime') else i
            current_price = df['close'].iloc[i]
            
            # Update market analysis
            df_slice = df.iloc[:i+1]
            analyzer = SidewaysAnalyzer(df_slice)
            
            # Check if sideways
            is_sideways, sideways_conf = analyzer.is_sideways_market()
            
            # Get S/R levels
            supports, resistances = analyzer.find_support_resistance()
            support = supports[0] if supports else current_price * 0.98
            resistance = resistances[0] if resistances else current_price * 1.02
            
            # Process existing positions
            self._process_positions(
                current_price, current_time, is_sideways, support, resistance
            )
            
            # Check for new entries
            if is_sideways and sideways_conf > 0.6:
                self._check_new_entry(
                    analyzer, current_price, current_time, support, resistance
                )
            
            # Update equity
            unrealized = self._calculate_unrealized(current_price)
            total_equity = self.balance + unrealized
            
            # Track drawdown
            if total_equity > self.peak_balance:
                self.peak_balance = total_equity
            
            current_dd = (self.peak_balance - total_equity) / self.peak_balance
            self.max_drawdown = max(self.max_drawdown, current_dd)
            self.risk_metrics.max_drawdown = self.max_drawdown
            
            # Record equity
            self.equity_curve.append({
                'time': str(current_time),
                'equity': total_equity,
                'balance': self.balance,
                'price': current_price,
                'positions': len(self.positions),
                'drawdown': current_dd
            })
            
            if verbose and i % 100 == 0:
                print(f"Progress: {i}/{len(df)} | Equity: ${total_equity:.2f} | "
                      f"Trades: {len(self.trades)} | DD: {current_dd:.2%}")
        
        # Close remaining positions at last price
        final_price = df['close'].iloc[-1]
        final_time = df.index[-1] if hasattr(df.index, 'strftime') else len(df) - 1
        
        for pos_id in list(self.positions.keys()):
            self._close_position(pos_id, final_price, final_time, "BACKTEST_END")
        
        return self._calculate_results()
    
    def _process_positions(
        self,
        current_price: float,
        current_time,
        is_sideways: bool,
        support: float,
        resistance: float
    ):
        """Przetwórz aktywne pozycje"""
        for pos_id in list(self.positions.keys()):
            pos = self.positions[pos_id]
            
            # Update trailing stop if active
            if pos['trailing_active']:
                new_trailing = current_price * (1 - self.config.stop_loss_multiplier * 0.005)
                if new_trailing > pos['trailing_sl']:
                    pos['trailing_sl'] = new_trailing
            
            # Calculate PnL
            pnl_pct = (current_price - pos['avg_entry']) / pos['avg_entry']
            
            # Check take profit
            if pnl_pct >= self.config.sideways_markup:
                if not pos['trailing_active']:
                    # Activate trailing stop
                    pos['trailing_active'] = True
                    pos['trailing_sl'] = current_price * (1 - self.config.stop_loss_multiplier * 0.005)
                continue
            
            # Check stop loss
            sl_price = pos['stop_loss']
            if pos['trailing_active'] and current_price <= pos['trailing_sl']:
                self._close_position(pos_id, current_price, current_time, "TRAILING_SL")
                continue
            elif current_price <= sl_price:
                self._close_position(pos_id, current_price, current_time, "STOP_LOSS")
                continue
            
            # Check if still sideways (exit if trend starts)
            if not is_sideways and pnl_pct > 0:
                self._close_position(pos_id, current_price, current_time, "TREND_CHANGE")
                continue
            
            # Update max drawdown for position
            pos['max_dd'] = min(pos.get('max_dd', 0), pnl_pct)
    
    def _check_new_entry(
        self,
        analyzer: SidewaysAnalyzer,
        current_price: float,
        current_time,
        support: float,
        resistance: float
    ):
        """Sprawdź czy otworzyć nową pozycję"""
        # Limit positions
        if len(self.positions) >= self.config.max_grid_positions:
            return
        
        # Generate signal
        signal = analyzer.generate_signal()
        
        if signal.signal != 'BUY':
            return
        
        # Calculate position size
        stop_loss = current_price * (1 - self.config.sideways_spacing * self.config.stop_loss_multiplier)
        risk_amount = self.balance * self.config.risk_per_trade_pct
        sl_distance = abs(current_price - stop_loss)
        
        if sl_distance > 0:
            position_size = risk_amount / sl_distance * current_price
        else:
            position_size = self.balance * 0.10
        
        # Cap at max
        max_position = self.balance * 0.10
        position_size = min(position_size, max_position)
        
        # Apply fees
        position_size *= (1 - self.fee_rate)
        
        # Create position
        pos_id = f"pos_{len(self.positions)}_{current_time}"
        
        self.positions[pos_id] = {
            'entry_time': current_time,
            'entry_price': current_price,
            'avg_entry': current_price,
            'size': position_size,
            'stop_loss': stop_loss,
            'take_profit': current_price * (1 + self.config.sideways_markup),
            'trailing_active': False,
            'trailing_sl': 0,
            'dca_count': 0,
            'max_dd': 0
        }
    
    def _close_position(
        self,
        pos_id: str,
        exit_price: float,
        exit_time,
        exit_reason: str
    ):
        """Zamknij pozycję"""
        if pos_id not in self.positions:
            return
        
        pos = self.positions[pos_id]
        
        # Apply slippage
        if exit_reason == "STOP_LOSS" or exit_reason == "TRAILING_SL":
            exit_price *= (1 - self.slippage)  # Worse exit
        
        # Calculate PnL
        pnl = (exit_price - pos['avg_entry']) * pos['size'] / pos['avg_entry']
        pnl -= pos['size'] * self.fee_rate  # Exit fee
        pnl_pct = (exit_price - pos['avg_entry']) / pos['avg_entry'] - self.fee_rate
        
        # Update balance
        self.balance += pnl
        
        # Update risk metrics
        self.risk_metrics.update_after_trade(pnl)
        
        # Record trade
        trade = BacktestTrade(
            entry_time=pos['entry_time'] if isinstance(pos['entry_time'], datetime) else datetime.now(),
            exit_time=exit_time if isinstance(exit_time, datetime) else datetime.now(),
            entry_price=pos['entry_price'],
            exit_price=exit_price,
            size=pos['size'],
            pnl=pnl,
            pnl_pct=pnl_pct,
            exit_reason=exit_reason,
            dca_count=pos['dca_count'],
            max_drawdown=pos.get('max_dd', 0)
        )
        self.trades.append(trade)
        
        # Remove position
        del self.positions[pos_id]
    
    def _calculate_unrealized(self, current_price: float) -> float:
        """Oblicz unrealized PnL"""
        total = 0
        for pos in self.positions.values():
            pnl = (current_price - pos['avg_entry']) * pos['size'] / pos['avg_entry']
            total += pnl
        return total
    
    def _calculate_results(self) -> BacktestResult:
        """Oblicz końcowe wyniki"""
        if not self.trades:
            return BacktestResult(
                trades=[], total_return=0, total_return_pct=0,
                win_rate=0, profit_factor=0, max_drawdown=0,
                sharpe_ratio=0, avg_trade_duration=0,
                avg_win=0, avg_loss=0, total_trades=0,
                winning_trades=0, losing_trades=0,
                final_balance=self.balance, equity_curve=self.equity_curve
            )
        
        # Basic stats
        total_return = self.balance - self.initial_balance
        total_return_pct = total_return / self.initial_balance
        
        wins = [t for t in self.trades if t.pnl > 0]
        losses = [t for t in self.trades if t.pnl <= 0]
        
        win_rate = len(wins) / len(self.trades) if self.trades else 0
        
        total_wins = sum(t.pnl for t in wins)
        total_losses = abs(sum(t.pnl for t in losses))
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        avg_win = total_wins / len(wins) if wins else 0
        avg_loss = total_losses / len(losses) if losses else 0
        
        # Duration
        durations = []
        for t in self.trades:
            if isinstance(t.exit_time, datetime) and isinstance(t.entry_time, datetime):
                dur = (t.exit_time - t.entry_time).total_seconds() / 3600
                durations.append(dur)
        avg_duration = np.mean(durations) if durations else 0
        
        # Sharpe ratio (simplified)
        if len(self.equity_curve) > 1:
            equity_values = [e['equity'] for e in self.equity_curve]
            returns = np.diff(equity_values) / equity_values[:-1]
            if len(returns) > 1 and np.std(returns) > 0:
                sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252 * 24)  # Hourly to annual
            else:
                sharpe = 0
        else:
            sharpe = 0
        
        return BacktestResult(
            trades=self.trades,
            total_return=total_return,
            total_return_pct=total_return_pct,
            win_rate=win_rate,
            profit_factor=profit_factor,
            max_drawdown=self.max_drawdown,
            sharpe_ratio=sharpe,
            avg_trade_duration=avg_duration,
            avg_win=avg_win,
            avg_loss=avg_loss,
            total_trades=len(self.trades),
            winning_trades=len(wins),
            losing_trades=len(losses),
            final_balance=self.balance,
            equity_curve=self.equity_curve
        )
    
    def print_results(self, result: BacktestResult):
        """Wypisz wyniki"""
        print("\n" + "=" * 60)
        print("BACKTEST RESULTS")
        print("=" * 60)
        print(f"Initial Balance:    ${self.initial_balance:,.2f}")
        print(f"Final Balance:      ${result.final_balance:,.2f}")
        print(f"Total Return:       ${result.total_return:,.2f} ({result.total_return_pct:+.2%})")
        print(f"Max Drawdown:       {result.max_drawdown:.2%}")
        print(f"Sharpe Ratio:       {result.sharpe_ratio:.2f}")
        print("-" * 60)
        print(f"Total Trades:       {result.total_trades}")
        print(f"Win Rate:           {result.win_rate:.2%}")
        print(f"Profit Factor:      {result.profit_factor:.2f}")
        print(f"Avg Win:            ${result.avg_win:.2f}")
        print(f"Avg Loss:           ${result.avg_loss:.2f}")
        print(f"Avg Duration:       {result.avg_trade_duration:.1f}h")
        print("=" * 60)
    
    def save_results(self, result: BacktestResult, path: str):
        """Zapisz wyniki do JSON"""
        data = {
            'summary': {
                'initial_balance': self.initial_balance,
                'final_balance': result.final_balance,
                'total_return_pct': result.total_return_pct,
                'max_drawdown': result.max_drawdown,
                'sharpe_ratio': result.sharpe_ratio,
                'win_rate': result.win_rate,
                'profit_factor': result.profit_factor,
                'total_trades': result.total_trades
            },
            'trades': [
                {
                    'entry_time': str(t.entry_time),
                    'exit_time': str(t.exit_time),
                    'entry_price': t.entry_price,
                    'exit_price': t.exit_price,
                    'pnl': t.pnl,
                    'pnl_pct': t.pnl_pct,
                    'exit_reason': t.exit_reason
                }
                for t in result.trades
            ],
            'equity_curve': result.equity_curve
        }
        
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"✅ Results saved to {path}")


def generate_sample_data(n: int = 2000, regime: str = 'sideways', seed: int = 42) -> pd.DataFrame:
    """Generuj przykładowe dane do testów"""
    np.random.seed(seed)
    
    dates = pd.date_range(start='2024-01-01', periods=n, freq='1h')
    
    if regime == 'sideways':
        # Mean-reverting price
        base_price = 100
        prices = base_price + np.cumsum(np.random.randn(n) * 0.3)
        prices = prices - 0.05 * (prices - base_price)  # Mean reversion
    elif regime == 'uptrend':
        prices = 100 + np.cumsum(np.random.randn(n) * 0.3 + 0.02)
    elif regime == 'downtrend':
        prices = 100 + np.cumsum(np.random.randn(n) * 0.3 - 0.02)
    else:
        prices = 100 + np.cumsum(np.random.randn(n) * 0.5)
    
    df = pd.DataFrame({
        'open': prices + np.random.rand(n) * 0.5,
        'high': prices + np.random.rand(n) * 1.0,
        'low': prices - np.random.rand(n) * 1.0,
        'close': prices,
        'volume': np.random.randint(1000, 10000, n)
    }, index=dates)
    
    return df


def run_demo():
    """Demo backtestu"""
    print("=" * 60)
    print("ENHANCED BACKTEST ENGINE DEMO")
    print("=" * 60)
    
    # Config
    config = EnhancedConfig()
    config.max_grid_positions = 3
    config.sideways_spacing = 0.015
    config.sideways_markup = 0.01
    config.risk_per_trade_pct = 0.01
    
    # Test na rynku sideways
    print("\n🔄 Testing on SIDEWAYS market...")
    df_sideways = generate_sample_data(n=500, regime='sideways')
    
    engine = EnhancedBacktestEngine(config, initial_balance=100.0)
    result = engine.run_backtest(df_sideways, verbose=False)
    engine.print_results(result)
    
    # Test na trendzie
    print("\n🔄 Testing on UPTREND market...")
    df_trend = generate_sample_data(n=500, regime='uptrend')
    
    engine2 = EnhancedBacktestEngine(config, initial_balance=100.0)
    result2 = engine2.run_backtest(df_trend, verbose=False)
    engine2.print_results(result2)
    
    # Save results
    engine.save_results(result, '/tmp/backtest_sideways.json')
    
    print("\n✅ Demo complete!")


if __name__ == "__main__":
    run_demo()
