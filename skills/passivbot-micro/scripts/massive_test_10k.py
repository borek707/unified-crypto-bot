#!/usr/bin/env python3
"""
MASSIVE TEST SUITE - 10,000 Tests
=================================
Test all strategy variants with all parameter combinations.
"""

import json
import numpy as np
from datetime import datetime
from typing import List, Dict, Tuple
from dataclasses import dataclass
import itertools
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/skills/passivbot-micro/scripts')

from technical_indicators import TechnicalIndicators, MarketClassifier
from ppo_engine import PPOModel
from risk_management import TurbulenceIndex, SlippageModel


@dataclass
class TestConfig:
    """Configuration for a single test run"""
    name: str
    # Market classifier
    use_adx: bool
    adx_window: int
    adx_threshold: int
    
    # Trend following
    use_ppo: bool
    trend_follow_tp: float
    trend_follow_sl: float
    partial_tp_pct: float
    partial_tp_size: float
    
    # Risk management
    use_turbulence: bool
    turbulence_threshold: float
    
    # Position sizing
    position_pct: float


class MassiveTester:
    """Run 10,000+ tests across all strategy variants"""
    
    def __init__(self, prices: List[float]):
        self.prices = prices
        self.results = []
        self.total_tests = 0
    
    def generate_configs(self) -> List[TestConfig]:
        """Generate all parameter combinations"""
        configs = []
        
        # Parameter ranges
        adx_windows = [50, 100, 150, 200]
        adx_thresholds = [20, 25, 30]
        trend_tps = [0.03, 0.05, 0.08, 0.10]
        trend_sls = [0.015, 0.025, 0.035]
        partial_tp_pcts = [0.03, 0.05, 0.08]
        partial_tp_sizes = [0.30, 0.50, 0.70]
        turbulence_thresholds = [1.5, 2.0, 2.5]
        position_pcts = [0.10, 0.15, 0.20]
        
        # Strategy variants
        variants = [
            ('ADX_Only', True, False, False),
            ('ADX_PPO', True, True, False),
            ('ADX_Risk', True, False, True),
            ('ADX_PPO_Risk', True, True, True),
            ('PPO_Only', False, True, False),
            ('Risk_Only', False, False, True),
            ('Full_Stack', True, True, True),
        ]
        
        test_num = 0
        for variant_name, use_adx, use_ppo, use_turb in variants:
            # Generate combinations based on what's enabled
            if use_adx:
                adx_combos = list(itertools.product(adx_windows, adx_thresholds))
            else:
                adx_combos = [(100, 25)]  # Default
            
            turb_combos = turbulence_thresholds if use_turb else [1.5]
            
            for adx_w, adx_t in adx_combos:
                for tp in trend_tps:
                    for sl in trend_sls:
                        for ptp in partial_tp_pcts:
                            for pts in partial_tp_sizes:
                                for tt in turb_combos:
                                    for pos_pct in position_pcts:
                                        test_num += 1
                                        configs.append(TestConfig(
                                            name=f"{variant_name}_{test_num:04d}",
                                            use_adx=use_adx,
                                            adx_window=adx_w,
                                            adx_threshold=adx_t,
                                            use_ppo=use_ppo,
                                            trend_follow_tp=tp,
                                            trend_follow_sl=sl,
                                            partial_tp_pct=ptp,
                                            partial_tp_size=pts,
                                            use_turbulence=use_turb,
                                            turbulence_threshold=tt,
                                            position_pct=pos_pct
                                        ))
        
        print(f"Generated {len(configs)} test configurations")
        return configs[:10000]  # Cap at 10,000
    
    def run_single_test(self, config: TestConfig) -> Dict:
        """Run a single backtest with given configuration"""
        
        # Initialize components
        if config.use_adx:
            # Create mock config for MarketClassifier
            class MockConfig:
                adx_window = config.adx_window
                adx_threshold = config.adx_threshold
            mc = MarketClassifier(MockConfig())
        else:
            mc = None
        
        if config.use_ppo:
            ppo = PPOModel()
        else:
            ppo = None
        
        if config.use_turbulence:
            turb = TurbulenceIndex(turbulence_threshold=config.turbulence_threshold)
        else:
            turb = None
        
        # Backtest state
        capital = 1000.0
        position = None
        trades = 0
        wins = 0
        losses = 0
        max_drawdown = 0.0
        peak_capital = capital
        
        # Simulate
        for i in range(200, len(self.prices)):
            price_slice = self.prices[:i+1]
            current_price = self.prices[i]
            
            # Determine trend
            if mc:
                trend = mc.classify(price_slice)
                is_bullish = trend in ['strong_uptrend', 'pullback_uptrend']
            else:
                # Simple EMA trend
                if len(price_slice) >= 100:
                    ema_fast = np.mean(price_slice[-20:])
                    ema_slow = np.mean(price_slice[-100:])
                    is_bullish = ema_fast > ema_slow
                else:
                    is_bullish = True
            
            # Check turbulence
            size_factor = 1.0
            if turb:
                turb_result = turb.calculate(price_slice)
                size_factor = turb_result.adjusted_size_factor
            
            # Trading logic
            if position is None:
                # Entry logic
                should_enter = False
                
                if is_bullish:
                    if ppo:
                        action = ppo.predict(price_slice)
                        should_enter = (action == 1)
                    else:
                        should_enter = True
                
                if should_enter and size_factor > 0:
                    position_size = config.position_pct * size_factor
                    entry_amount = capital * position_size
                    
                    position = {
                        'entry_price': current_price,
                        'amount': entry_amount,
                        'highest_price': current_price,
                        'partial_tp_done': False
                    }
                    trades += 1
            
            else:
                # Exit logic
                entry = position['entry_price']
                pnl_pct = (current_price - entry) / entry
                
                # Update highest price
                position['highest_price'] = max(position['highest_price'], current_price)
                
                exit_reason = None
                
                # Partial TP
                if not position.get('partial_tp_done'):
                    partial_tp_price = entry * (1 + config.partial_tp_pct)
                    if current_price >= partial_tp_price:
                        # Close partial
                        closed_pnl = pnl_pct * position['amount'] * config.partial_tp_size
                        capital += closed_pnl
                        position['amount'] *= (1 - config.partial_tp_size)
                        position['partial_tp_done'] = True
                
                # SL
                sl_price = entry * (1 - config.trend_follow_sl)
                if current_price <= sl_price:
                    exit_reason = 'stop_loss'
                
                # TP
                tp_price = entry * (1 + config.trend_follow_tp)
                if current_price >= tp_price:
                    exit_reason = 'take_profit'
                
                # PPO exit
                if ppo and not exit_reason:
                    action = ppo.predict(price_slice, position)
                    if action == 2:  # Exit
                        exit_reason = 'ppo_exit'
                
                if exit_reason:
                    pnl = pnl_pct * position['amount']
                    capital += pnl
                    
                    if pnl > 0:
                        wins += 1
                    else:
                        losses += 1
                    
                    position = None
            
            # Track drawdown
            peak_capital = max(peak_capital, capital)
            drawdown = (peak_capital - capital) / peak_capital
            max_drawdown = max(max_drawdown, drawdown)
        
        # Calculate metrics
        total_return = (capital - 1000.0) / 1000.0 * 100
        win_rate = wins / trades * 100 if trades > 0 else 0
        
        return {
            'config': config.name,
            'variant': config.name.split('_')[0] if '_' in config.name else 'Unknown',
            'use_adx': config.use_adx,
            'use_ppo': config.use_ppo,
            'use_turbulence': config.use_turbulence,
            'adx_window': config.adx_window if config.use_adx else None,
            'trend_follow_tp': config.trend_follow_tp,
            'trend_follow_sl': config.trend_follow_sl,
            'partial_tp_pct': config.partial_tp_pct,
            'partial_tp_size': config.partial_tp_size,
            'position_pct': config.position_pct,
            'trades': trades,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'total_return_pct': total_return,
            'max_drawdown_pct': max_drawdown * 100,
            'profit_factor': (wins * config.trend_follow_tp) / (losses * config.trend_follow_sl) if losses > 0 else float('inf'),
            'sharpe': total_return / (max_drawdown * 100) if max_drawdown > 0 else total_return
        }
    
    def run_all_tests(self):
        """Run all 10,000 tests"""
        configs = self.generate_configs()
        
        print(f"\n{'='*60}")
        print(f"MASSIVE TEST SUITE - {len(configs):,} TESTS")
        print(f"{'='*60}\n")
        
        start_time = datetime.now()
        
        for i, config in enumerate(configs):
            try:
                result = self.run_single_test(config)
                self.results.append(result)
                
                # Progress
                if (i + 1) % 100 == 0:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    rate = (i + 1) / elapsed
                    remaining = (len(configs) - i - 1) / rate if rate > 0 else 0
                    
                    print(f"Progress: {i+1}/{len(configs)} | "
                          f"Rate: {rate:.1f} tests/sec | "
                          f"ETA: {remaining/60:.1f} min")
                
                # Save intermediate results every 500 tests
                if (i + 1) % 500 == 0:
                    self.save_results(f"/tmp/massive_test_partial_{i+1}.json")
                
            except Exception as e:
                print(f"Error in test {i+1}: {e}")
                continue
        
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"\n{'='*60}")
        print(f"ALL TESTS COMPLETE - {len(self.results)} successful")
        print(f"Total time: {elapsed/60:.1f} minutes")
        print(f"Average: {len(self.results)/elapsed:.1f} tests/sec")
        print(f"{'='*60}\n")
    
    def analyze_results(self):
        """Analyze and report results"""
        if not self.results:
            print("No results to analyze")
            return
        
        # Convert to arrays for analysis
        returns = [r['total_return_pct'] for r in self.results]
        win_rates = [r['win_rate'] for r in self.results]
        drawdowns = [r['max_drawdown_pct'] for r in self.results]
        trades_list = [r['trades'] for r in self.results]
        
        # Overall stats
        profitable = len([r for r in self.results if r['total_return_pct'] > 0])
        
        print(f"\n{'='*60}")
        print("OVERALL RESULTS")
        print(f"{'='*60}")
        print(f"Total configurations tested: {len(self.results)}")
        print(f"Profitable configs: {profitable} ({profitable/len(self.results)*100:.1f}%)")
        print(f"\nReturns:")
        print(f"  Best:  +{max(returns):.2f}%")
        print(f"  Worst: {min(returns):.2f}%")
        print(f"  Mean:  {np.mean(returns):.2f}%")
        print(f"  Median: {np.median(returns):.2f}%")
        print(f"\nWin Rates:")
        print(f"  Best:  {max(win_rates):.1f}%")
        print(f"  Mean:  {np.mean(win_rates):.1f}%")
        print(f"\nMax Drawdown:")
        print(f"  Worst: {max(drawdowns):.1f}%")
        print(f"  Mean:  {np.mean(drawdowns):.1f}%")
        print(f"\nTrades per config:")
        print(f"  Mean:  {np.mean(trades_list):.1f}")
        print(f"  Max:   {max(trades_list)}")
        
        # Top 10 configs
        print(f"\n{'='*60}")
        print("TOP 10 CONFIGURATIONS (by total return)")
        print(f"{'='*60}")
        
        sorted_results = sorted(self.results, key=lambda x: x['total_return_pct'], reverse=True)
        
        for i, r in enumerate(sorted_results[:10], 1):
            print(f"\n{i}. {r['config']}")
            print(f"   Return: +{r['total_return_pct']:.2f}% | Win Rate: {r['win_rate']:.1f}% | "
                  f"Trades: {r['trades']} | DD: {r['max_drawdown_pct']:.1f}%")
            print(f"   Features: ADX={r['use_adx']} PPO={r['use_ppo']} Turb={r['use_turbulence']}")
            print(f"   Params: TP={r['trend_follow_tp']:.1%} SL={r['trend_follow_sl']:.1%} "
                  f"Size={r['position_pct']:.0%}")
        
        # By variant
        print(f"\n{'='*60}")
        print("RESULTS BY STRATEGY VARIANT")
        print(f"{'='*60}")
        
        variants = {}
        for r in self.results:
            v = r['variant']
            if v not in variants:
                variants[v] = []
            variants[v].append(r)
        
        for v, results in sorted(variants.items(), key=lambda x: np.mean([r['total_return_pct'] for r in x[1]]), reverse=True):
            v_returns = [r['total_return_pct'] for r in results]
            v_profitable = len([r for r in results if r['total_return_pct'] > 0])
            print(f"\n{v}: {len(results)} configs")
            print(f"  Avg Return: {np.mean(v_returns):.2f}%")
            print(f"  Profitable: {v_profitable}/{len(results)} ({v_profitable/len(results)*100:.1f}%)")
            print(f"  Best: +{max(v_returns):.2f}%")
    
    def save_results(self, path: str):
        """Save results to JSON"""
        with open(path, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'total_tests': len(self.results),
                'results': self.results
            }, f, indent=2)
        print(f"Results saved to {path}")


def main():
    print("MASSIVE TEST SUITE - 10,000 Tests")
    print("Loading price data...")
    
    # Load prices
    with open('/tmp/hyperliquid_daily_big.json', 'r') as f:
        prices = json.load(f)
    
    print(f"Loaded {len(prices)} prices")
    print(f"Range: ${prices[0]:.0f} → ${prices[-1]:.0f}")
    
    # Run tests
    tester = MassiveTester(prices)
    tester.run_all_tests()
    
    # Analyze
    tester.analyze_results()
    
    # Save final results
    tester.save_results('/tmp/massive_test_results_10k.json')
    
    print("\n✅ ALL TESTS COMPLETE!")


if __name__ == "__main__":
    main()
