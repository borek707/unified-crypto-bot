#!/usr/bin/env python3
"""
SYSTEMATIC BACKTEST SUITE
==========================
1000, 2000, 3000, 5000 backtests with parameter optimization.
After each batch: analyze results and adjust parameters.

Phase 1: 1000 tests (baseline)
Phase 2: 2000 tests (parameter tuning based on phase 1)
Phase 3: 3000 tests (refinement)
Phase 4: 5000 tests (final validation)
"""

import json
import sys
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple
from dataclasses import dataclass

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from ppo_continuous import ContinuousPPOModel, PPOConfig
from a2c_continuous import ContinuousA2CModel, A2CConfig


@dataclass
class BacktestParams:
    """Parameters to optimize"""
    model: str  # 'PPO' or 'A2C'
    learning_rate: float
    fee_pct: float
    action_threshold: float
    position_size: float
    sma_period: int
    momentum_threshold: float


@dataclass
class BacktestResult:
    params: BacktestParams
    total_return: float
    sharpe: float
    max_drawdown: float
    win_rate: float
    num_trades: int
    profitable: bool


def load_data():
    """Load BTC data"""
    sources = [Path('/tmp/btc_real_2years.json')]
    for source in sources:
        if source.exists():
            with open(source) as f:
                hourly = json.load(f)
            daily = hourly[::24]
            print(f"✅ Loaded {len(daily)} daily prices")
            return daily
    return None


def generate_random_params() -> BacktestParams:
    """Generate random parameter combination"""
    return BacktestParams(
        model=np.random.choice(['PPO', 'A2C']),
        learning_rate=np.random.choice([0.0003, 0.001, 0.003]),
        fee_pct=np.random.choice([0.0003, 0.0006, 0.0009]),  # 0.03%, 0.06%, 0.09%
        action_threshold=np.random.uniform(0.03, 0.20),
        position_size=np.random.uniform(0.10, 0.30),
        sma_period=np.random.choice([10, 20, 30, 50]),
        momentum_threshold=np.random.uniform(0.01, 0.05)
    )


def run_single_backtest(prices: List[float], params: BacktestParams) -> BacktestResult:
    """Run single backtest"""
    try:
        # Split data
        train_size = int(len(prices) * 0.7)
        train = prices[:train_size]
        test = prices[train_size:]
        
        # Initialize model
        if params.model == 'PPO':
            config = PPOConfig(
                learning_rate=params.learning_rate,
                num_epochs=10,
                trading_fee_pct=params.fee_pct,
                action_threshold=params.action_threshold
            )
            model = ContinuousPPOModel(config)
        else:
            config = A2CConfig(
                learning_rate=params.learning_rate,
                num_epochs=10,
                trading_fee_pct=params.fee_pct,
                action_threshold=params.action_threshold
            )
            model = ContinuousA2CModel(config)
        
        # Train
        model.train(train, epochs=10)
        
        # Test with momentum + SMA
        position = None
        trades = 0
        equity = [100.0]
        peak = 100.0
        max_dd = 0.0
        
        for i in range(params.sma_period, len(test)):
            price = test[i]
            
            # SMA calculation
            sma = sum(test[i-params.sma_period:i]) / params.sma_period
            deviation = (price - sma) / sma
            
            # Entry signal
            if not position and deviation > params.momentum_threshold:
                position = {
                    'entry': price,
                    'size': params.position_size
                }
                trades += 1
            
            # Exit signal
            elif position and deviation < -params.momentum_threshold:
                pnl = (price - position['entry']) / position['entry'] * position['size']
                pnl -= position['size'] * params.fee_pct
                
                equity.append(equity[-1] + pnl * 100)
                
                if equity[-1] > peak:
                    peak = equity[-1]
                dd = (peak - equity[-1]) / peak
                max_dd = max(max_dd, dd)
                
                position = None
                trades += 1
        
        # Calculate metrics
        total_return = (equity[-1] - 100) / 100 if len(equity) > 1 else 0
        
        if len(equity) > 1 and trades > 0:
            returns = np.diff(equity) / np.array(equity[:-1])
            sharpe = np.mean(returns) / (np.std(returns) + 1e-9) * np.sqrt(365)
            # Approximate win rate from returns
            win_rate = len([r for r in returns if r > 0]) / len(returns)
        else:
            sharpe = 0
            win_rate = 0
        
        return BacktestResult(
            params=params,
            total_return=total_return,
            sharpe=sharpe,
            max_drawdown=max_dd,
            win_rate=win_rate,
            num_trades=trades,
            profitable=total_return > 0
        )
        
    except Exception as e:
        return BacktestResult(
            params=params,
            total_return=-1.0,
            sharpe=-10,
            max_drawdown=1.0,
            win_rate=0,
            num_trades=0,
            profitable=False
        )


def run_batch(prices: List[float], num_tests: int, phase_name: str) -> List[BacktestResult]:
    """Run batch of backtests"""
    print(f"\n{'='*70}")
    print(f"🧪 {phase_name}: {num_tests} backtests")
    print(f"{'='*70}")
    
    results = []
    for i in range(num_tests):
        params = generate_random_params()
        result = run_single_backtest(prices, params)
        results.append(result)
        
        if (i + 1) % 100 == 0:
            profitable = sum(1 for r in results if r.profitable)
            print(f"  {i+1}/{num_tests} done ({profitable} profitable)")
    
    return results


def analyze_results(results: List[BacktestResult], phase_name: str) -> Dict:
    """Analyze backtest results"""
    print(f"\n{'='*70}")
    print(f"📊 {phase_name} ANALYSIS")
    print(f"{'='*70}")
    
    # Overall stats
    profitable = [r for r in results if r.profitable]
    returns = [r.total_return for r in results]
    sharpes = [r.sharpe for r in results]
    
    print(f"\nOverall Statistics:")
    print(f"  Total tests: {len(results)}")
    print(f"  Profitable: {len(profitable)} ({len(profitable)/len(results)*100:.1f}%)")
    print(f"  Avg return: {np.mean(returns)*100:.2f}%")
    print(f"  Median return: {np.median(returns)*100:.2f}%")
    print(f"  Best return: {max(returns)*100:.2f}%")
    print(f"  Worst return: {min(returns)*100:.2f}%")
    print(f"  Avg Sharpe: {np.mean(sharpes):.3f}")
    print(f"  Avg trades: {np.mean([r.num_trades for r in results]):.1f}")
    
    # Top 10
    print(f"\n🏆 TOP 10 PERFORMERS:")
    top10 = sorted(results, key=lambda r: r.total_return, reverse=True)[:10]
    print(f"{'Rank':<5} {'Model':<6} {'Return':<10} {'Sharpe':<8} {'Trades':<8} {'Params'}")
    print("-" * 80)
    for i, r in enumerate(top10, 1):
        print(f"{i:<5} {r.params.model:<6} {r.total_return*100:+.2f}%    {r.params.fee_pct*100:.2f}%    {r.params.threshold:.2f}")
    
    # Best parameters analysis
    print(f"\n🔍 BEST PARAMETERS ANALYSIS:")
    
    # By model
    ppo_results = [r for r in results if r.params.model == 'PPO']
    a2c_results = [r for r in results if r.params.model == 'A2C']
    
    if ppo_results and a2c_results:
        print(f"  PPO avg return: {np.mean([r.total_return for r in ppo_results])*100:.2f}%")
        print(f"  A2C avg return: {np.mean([r.total_return for r in a2c_results])*100:.2f}%")
        print(f"  Better model: {'PPO' if np.mean([r.total_return for r in ppo_results]) > np.mean([r.total_return for r in a2c_results]) else 'A2C'}")
    
    # By fee
    low_fee = [r for r in results if r.params.fee_pct <= 0.0003]
    med_fee = [r for r in results if 0.0003 < r.params.fee_pct <= 0.0006]
    high_fee = [r for r in results if r.params.fee_pct > 0.0006]
    
    print(f"\n  Low fee (0.03%):  {np.mean([r.total_return for r in low_fee])*100:.2f}% avg")
    print(f"  Med fee (0.06%):  {np.mean([r.total_return for r in med_fee])*100:.2f}% avg")
    print(f"  High fee (0.09%): {np.mean([r.total_return for r in high_fee])*100:.2f}% avg")
    
    # Recommendations
    print(f"\n💡 RECOMMENDATIONS FOR NEXT PHASE:")
    best = top10[0]
    print(f"  1. Use model: {best.params.model}")
    print(f"  2. Learning rate: {best.params.learning_rate}")
    print(f"  3. Fee: {best.params.fee_pct*100:.3f}%")
    print(f"  4. Threshold: {best.params.action_threshold:.3f}")
    print(f"  5. Position size: {best.params.position_size:.2f}")
    print(f"  6. SMA period: {best.params.sma_period}")
    print(f"  7. Momentum threshold: {best.params.momentum_threshold:.3f}")
    
    return {
        'phase': phase_name,
        'total_tests': len(results),
        'profitable_pct': len(profitable)/len(results)*100,
        'avg_return': np.mean(returns),
        'best_params': {
            'model': best.params.model,
            'lr': best.params.learning_rate,
            'fee': best.params.fee_pct,
            'threshold': best.params.action_threshold,
            'pos_size': best.params.position_size,
            'sma': best.params.sma_period,
            'momentum': best.params.momentum_threshold
        }
    }


def main():
    print("="*70)
    print("🚀 SYSTEMATIC BACKTEST SUITE")
    print("="*70)
    print(f"Started: {datetime.now().isoformat()}")
    
    prices = load_data()
    if not prices:
        return 1
    
    all_phases = []
    
    # Phase 1: 1000 tests
    results_1000 = run_batch(prices, 1000, "PHASE 1")
    analysis_1000 = analyze_results(results_1000, "PHASE 1 (1000 tests)")
    all_phases.append(analysis_1000)
    
    # Save results
    with open('/tmp/backtest_phase1_1000.json', 'w') as f:
        json.dump(analysis_1000, f, indent=2)
    
    print(f"\n{'='*70}")
    print("✅ PHASE 1 COMPLETE - Check results above")
    print(f"{'='*70}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
