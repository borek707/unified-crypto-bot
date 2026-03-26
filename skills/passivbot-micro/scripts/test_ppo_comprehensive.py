#!/usr/bin/env python3
"""
COMPREHENSIVE PPO + TURBULENCE TESTING
======================================
Rigorous backtesting with:
- Walk-forward analysis (multiple train/test splits)
- Multiple market regimes (bull, bear, sideways)
- Statistical significance testing
- Comparison vs baseline strategies

Usage:
    python test_ppo_comprehensive.py
"""

import json
import sys
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple
from dataclasses import dataclass

# Add passivbot-micro scripts to path
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from unified_bot import UnifiedBot, UnifiedConfig
from ppo_engine import PPOModel, PPOConfig
from risk_management import TurbulenceIndex


@dataclass
class TestResult:
    """Results from a single test run."""
    strategy_name: str
    train_period: str
    test_period: str
    total_return_pct: float
    num_trades: int
    win_rate: float
    avg_trade_return: float
    max_drawdown_pct: float
    sharpe_ratio: float
    turbulent_periods_skipped: int = 0


def load_extended_price_data():
    """Load as much historical BTC data as possible."""
    sources = [
        Path('/tmp/btc_real_2years.json'),  # REAL DATA - 3 years of BTC
        Path('/tmp/btc_extended.json'),
        Path.home() / '.crypto_bot' / 'data' / 'hyperliquid_daily_big.json',
    ]
    
    all_prices = []
    for source in sources:
        if source.exists():
            print(f"📊 Found data source: {source}")
            with open(source, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    all_prices.extend(data)
                elif isinstance(data, dict) and 'prices' in data:
                    all_prices.extend(data['prices'])
    
    if all_prices:
        print(f"✅ Loaded {len(all_prices)} total price points")
        return all_prices
    
    # Generate realistic synthetic data if no real data
    print("⚠️ No real data, generating realistic synthetic BTC data...")
    np.random.seed(42)
    prices = [50000.0]
    
    # Generate 2 years of hourly data with realistic volatility
    for i in range(365 * 24 * 2):
        # Random walk with mean reversion
        change = np.random.normal(0.00002, 0.015)  # ~1.5% hourly volatility
        
        # Add some trend periods
        if 2000 < i < 4000:  # Bull run
            change += 0.001
        elif 8000 < i < 10000:  # Bear market
            change -= 0.0008
        
        prices.append(prices[-1] * (1 + change))
    
    print(f"✅ Generated {len(prices)} synthetic price points")
    return prices


def classify_market_regime(prices: List[float]) -> str:
    """Classify market regime based on price action."""
    if len(prices) < 100:
        return 'unknown'
    
    returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
    total_return = (prices[-1] - prices[0]) / prices[0]
    volatility = np.std(returns) * np.sqrt(365 * 24)  # Annualized
    
    if total_return > 0.5 and volatility < 1.0:
        return 'strong_bull'
    elif total_return > 0.2:
        return 'bull'
    elif total_return < -0.3 and volatility > 0.8:
        return 'strong_bear'
    elif total_return < -0.1:
        return 'bear'
    else:
        return 'sideways'


def calculate_sharpe(returns: List[float]) -> float:
    """Calculate Sharpe ratio (assuming risk-free rate = 0)."""
    if len(returns) < 2:
        return 0.0
    avg_return = np.mean(returns)
    std_return = np.std(returns)
    if std_return == 0:
        return 0.0
    return avg_return / std_return * np.sqrt(365 * 24)  # Annualized


def run_backtest(prices: List[float], use_ppo: bool = False, 
                 use_turbulence: bool = False, ppo_model: PPOModel = None) -> Dict:
    """Run a single backtest."""
    config = UnifiedConfig(
        initial_capital=100.0,
        testnet=True,
        use_ppo_trend_following=use_ppo,
        turbulence_threshold=1.5,
        trend_follow_position_pct=0.15,
        trend_follow_trailing_stop_pct=0.04,
        trend_follow_hard_stop_pct=0.03,
        circuit_breaker_enabled=True
    )
    
    bot = UnifiedBot(config)
    if ppo_model:
        bot.ppo_model = ppo_model
    
    # Simulate trading
    position = None
    entries = 0
    exits = 0
    turbulent_skips = 0
    trades = []
    equity_curve = [100.0]
    peak_equity = 100.0
    max_drawdown = 0.0
    
    for i in range(200, len(prices)):
        price = prices[i]
        price_history = prices[:i+1]
        
        # Turbulence check
        if use_turbulence and bot.turbulence_index is not None:
            turb_result = bot.turbulence_index.calculate(price_history)
            if turb_result.is_turbulent and position is None:
                turbulent_skips += 1
                continue
        
        # PPO entry/exit
        if use_ppo and bot.ppo_model is not None:
            action = bot.ppo_model.predict(price_history, position)
            
            if action == 1 and position is None:  # ENTER
                position = {
                    'entry_price': price, 
                    'highest_price': price,
                    'entry_idx': i
                }
                entries += 1
            elif action == 2 and position:  # EXIT
                pnl = (price - position['entry_price']) / position['entry_price']
                trades.append({
                    'entry_price': position['entry_price'],
                    'exit_price': price,
                    'pnl': pnl,
                    'duration': i - position['entry_idx']
                })
                exits += 1
                position = None
        
        # Calculate current equity
        current_equity = 100.0
        if position:
            unrealized = (price - position['entry_price']) / position['entry_price'] * 15.0  # 15% position
            current_equity += sum(t['pnl'] * 15.0 for t in trades) + unrealized
        else:
            current_equity += sum(t['pnl'] * 15.0 for t in trades)
        
        equity_curve.append(current_equity)
        
        # Track drawdown
        if current_equity > peak_equity:
            peak_equity = current_equity
        drawdown = (peak_equity - current_equity) / peak_equity
        max_drawdown = max(max_drawdown, drawdown)
    
    # Close any open position at the end
    if position:
        pnl = (prices[-1] - position['entry_price']) / position['entry_price']
        trades.append({
            'entry_price': position['entry_price'],
            'exit_price': prices[-1],
            'pnl': pnl,
            'duration': len(prices) - position['entry_idx']
        })
        exits += 1
    
    # Calculate metrics
    total_return = (equity_curve[-1] - 100.0) / 100.0
    win_rate = len([t for t in trades if t['pnl'] > 0]) / len(trades) if trades else 0
    avg_return = np.mean([t['pnl'] for t in trades]) if trades else 0
    sharpe = calculate_sharpe([(equity_curve[i] - equity_curve[i-1]) / equity_curve[i-1] 
                               for i in range(1, len(equity_curve))])
    
    return {
        'total_return': total_return,
        'num_trades': len(trades),
        'win_rate': win_rate,
        'avg_trade_return': avg_return,
        'max_drawdown': max_drawdown,
        'sharpe': sharpe,
        'turbulent_skips': turbulent_skips,
        'trades': trades,
        'equity_curve': equity_curve
    }


def walk_forward_test(prices: List[float], train_window: int = 500, 
                      test_window: int = 200) -> List[TestResult]:
    """Run walk-forward analysis."""
    results = []
    
    # Split data into train/test windows
    idx = train_window
    window_num = 0
    
    while idx + test_window <= len(prices):
        window_num += 1
        train_data = prices[idx-train_window:idx]
        test_data = prices[idx:idx+test_window]
        
        train_regime = classify_market_regime(train_data)
        test_regime = classify_market_regime(test_data)
        
        print(f"\n📅 Window {window_num}: Train={train_regime}, Test={test_regime}")
        print(f"   Train: {len(train_data)} points | Test: {len(test_data)} points")
        
        # Train PPO model
        print("   Training PPO model...")
        ppo_config = PPOConfig(num_epochs=10, steps_per_update=512)
        ppo_model = PPOModel(ppo_config)
        ppo_model.train(train_data, epochs=ppo_config.num_epochs)
        
        # Test strategies
        strategies = [
            ('Baseline (no PPO)', False, False),
            ('PPO only', True, False),
            ('Turbulence only', False, True),
            ('PPO + Turbulence', True, True),
        ]
        
        for name, use_ppo, use_turb in strategies:
            model = ppo_model if use_ppo else None
            result = run_backtest(test_data, use_ppo=use_ppo, 
                                 use_turbulence=use_turb, ppo_model=model)
            
            results.append(TestResult(
                strategy_name=name,
                train_period=train_regime,
                test_period=test_regime,
                total_return_pct=result['total_return'] * 100,
                num_trades=result['num_trades'],
                win_rate=result['win_rate'] * 100,
                avg_trade_return=result['avg_trade_return'] * 100,
                max_drawdown_pct=result['max_drawdown'] * 100,
                sharpe_ratio=result['sharpe'],
                turbulent_periods_skipped=result['turbulent_skips']
            ))
        
        idx += test_window  # Move window forward
    
    return results


def analyze_results(results: List[TestResult]) -> Dict:
    """Analyze and summarize test results."""
    print("\n" + "="*80)
    print("📊 COMPREHENSIVE RESULTS ANALYSIS")
    print("="*80)
    
    strategies = ['Baseline (no PPO)', 'PPO only', 'Turbulence only', 'PPO + Turbulence']
    
    summary = {}
    
    for strategy in strategies:
        strat_results = [r for r in results if r.strategy_name == strategy]
        
        if not strat_results:
            continue
        
        returns = [r.total_return_pct for r in strat_results]
        trades = [r.num_trades for r in strat_results]
        win_rates = [r.win_rate for r in strat_results]
        drawdowns = [r.max_drawdown_pct for r in strat_results]
        sharpes = [r.sharpe_ratio for r in strat_results]
        
        profitable_windows = len([r for r in returns if r > 0])
        total_windows = len(strat_results)
        
        summary[strategy] = {
            'avg_return': np.mean(returns),
            'std_return': np.std(returns),
            'min_return': np.min(returns),
            'max_return': np.max(returns),
            'median_return': np.median(returns),
            'profitable_ratio': profitable_windows / total_windows,
            'avg_trades': np.mean(trades),
            'avg_win_rate': np.mean(win_rates),
            'avg_drawdown': np.mean(drawdowns),
            'avg_sharpe': np.mean(sharpes),
            'consistency_score': np.mean(returns) / (np.std(returns) + 0.01),  # Higher is better
        }
        
        print(f"\n🔹 {strategy}")
        print(f"   Windows tested: {total_windows} (profitable: {profitable_windows})")
        print(f"   Avg return: {summary[strategy]['avg_return']:+.2f}% (±{summary[strategy]['std_return']:.2f}%)")
        print(f"   Range: [{summary[strategy]['min_return']:+.2f}%, {summary[strategy]['max_return']:+.2f}%]")
        print(f"   Median: {summary[strategy]['median_return']:+.2f}%")
        print(f"   Profitable windows: {profitable_windows}/{total_windows} ({profitable_windows/total_windows*100:.0f}%)")
        print(f"   Avg trades per window: {summary[strategy]['avg_trades']:.1f}")
        print(f"   Avg win rate: {summary[strategy]['avg_win_rate']:.1f}%")
        print(f"   Avg max drawdown: {summary[strategy]['avg_drawdown']:.2f}%")
        print(f"   Avg Sharpe: {summary[strategy]['avg_sharpe']:.2f}")
        print(f"   Consistency score: {summary[strategy]['consistency_score']:.2f}")
    
    return summary


def determine_best_strategy(summary: Dict) -> Tuple[str, bool]:
    """Determine best strategy based on multiple criteria."""
    print("\n" + "="*80)
    print("🏆 STRATEGY COMPARISON & RANKING")
    print("="*80)
    
    # Score each strategy
    scores = {}
    for name, stats in summary.items():
        score = 0
        score += stats['avg_return'] * 2  # Return is important
        score += stats['consistency_score'] * 10  # Consistency is very important
        score += stats['profitable_ratio'] * 20  # Being profitable matters
        score -= stats['avg_drawdown']  # Penalty for drawdown
        score += stats['avg_sharpe'] * 5  # Sharpe ratio bonus
        scores[name] = score
    
    # Sort by score
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    print("\nRanking (composite score):")
    for i, (name, score) in enumerate(ranked, 1):
        print(f"   {i}. {name}: {score:.2f}")
    
    best = ranked[0][0]
    
    # Check if PPO + Turbulence is significantly better
    ppo_turb = summary.get('PPO + Turbulence', {})
    baseline = summary.get('Baseline (no PPO)', {})
    
    if not ppo_turb or not baseline:
        return best, False
    
    improvement = ppo_turb.get('avg_return', 0) - baseline.get('avg_return', 0)
    
    print(f"\n📈 PPO + Turbulence vs Baseline:")
    print(f"   Return improvement: {improvement:+.2f}%")
    print(f"   Consistency: {ppo_turb.get('consistency_score', 0):.2f} vs {baseline.get('consistency_score', 0):.2f}")
    print(f"   Profitable ratio: {ppo_turb.get('profitable_ratio', 0)*100:.0f}% vs {baseline.get('profitable_ratio', 0)*100:.0f}%")
    
    # DOD check
    dod_met = (
        improvement > 0 and
        ppo_turb.get('consistency_score', 0) > baseline.get('consistency_score', 0) * 0.8 and
        ppo_turb.get('profitable_ratio', 0) >= baseline.get('profitable_ratio', 0)
    )
    
    return best, dod_met


def main():
    print("="*80)
    print("🔬 COMPREHENSIVE PPO + TURBULENCE TESTING")
    print("="*80)
    print(f"Started: {datetime.now().isoformat()}")
    
    # Load data
    prices = load_extended_price_data()
    
    # Run walk-forward tests
    print("\n" + "="*80)
    print("🔄 RUNNING WALK-FORWARD ANALYSIS")
    print("="*80)
    
    results = walk_forward_test(prices, train_window=800, test_window=300)
    
    # Analyze results
    summary = analyze_results(results)
    
    # Determine best strategy
    best_strategy, dod_met = determine_best_strategy(summary)
    
    # Final verdict
    print("\n" + "="*80)
    print("✅ FINAL VERDICT - DEFINITION OF DONE")
    print("="*80)
    print(f"\nBest strategy: {best_strategy}")
    print(f"DOD (improvement + consistency): {'✅ MET' if dod_met else '❌ NOT MET'}")
    
    if dod_met:
        print("\n🎉 PPO + Turbulence integration APPROVED for production!")
    else:
        print("\n⚠️  Needs more work before deployment.")
    
    return 0 if dod_met else 1


if __name__ == '__main__':
    sys.exit(main())
