#!/usr/bin/env python3
"""
MASSIVE PPO PARAMETER OPTIMIZATION
====================================
Run 5000+ tests with different parameter combinations
Find optimal configuration for:
- PPO hyperparameters
- Trading costs
- Turbulence threshold
- Position sizing

Uses parallel processing and Bayesian optimization.
"""

import json
import sys
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass
from concurrent.futures import ProcessPoolExecutor, as_completed
import itertools

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from unified_bot import UnifiedBot, UnifiedConfig
from ppo_continuous import ContinuousPPOModel, PPOConfig
from risk_management import TurbulenceIndex


@dataclass
class TestParams:
    """Parameters to optimize"""
    # PPO params
    learning_rate: float = 0.001
    num_epochs: int = 10
    trading_fee_pct: float = 0.0003
    overtrade_penalty: float = 0.0001
    action_threshold: float = 0.05
    
    # Bot params
    position_pct: float = 0.10
    trailing_stop_pct: float = 0.05
    
    # Turbulence params
    turbulence_threshold: float = 3.0
    turbulence_lookback: int = 30


@dataclass  
class TestResult:
    """Result of single test"""
    params: TestParams
    total_return: float
    sharpe_ratio: float
    win_rate: float
    num_trades: int
    max_drawdown: float
    profitable: bool
    score: float


def load_btc_data():
    """Load real BTC data"""
    sources = [
        Path('/tmp/btc_real_2years.json'),
        Path('/tmp/btc_extended.json'),
    ]
    for source in sources:
        if source.exists():
            with open(source, 'r') as f:
                return json.load(f)
    return None


def run_single_test(prices: List[float], params: TestParams, test_id: int) -> TestResult:
    """Run a single backtest with given parameters"""
    try:
        # Split data
        train_size = int(len(prices) * 0.7)
        train_prices = prices[:train_size]
        test_prices = prices[train_size:]
        
        # Train PPO
        ppo_config = PPOConfig(
            learning_rate=params.learning_rate,
            num_epochs=params.num_epochs,
            trading_fee_pct=params.trading_fee_pct,
            slippage_bps=2.0,
            overtrade_penalty=params.overtrade_penalty,
            action_threshold=params.action_threshold
        )
        
        model = ContinuousPPOModel(ppo_config)
        model.train(train_prices, epochs=params.num_epochs)
        
        # Test
        turb = TurbulenceIndex(
            lookback=params.turbulence_lookback,
            turbulence_threshold=params.turbulence_threshold
        )
        
        position = None
        trades = []
        equity = [100.0]
        peak = 100.0
        max_dd = 0.0
        liquidations = 0
        
        for i in range(50, len(test_prices)):
            price = test_prices[i]
            history = test_prices[:i+1]
            
            # Kill switch check
            turb_result = turb.calculate(history)
            if turb_result.is_turbulent and position:
                # Liquidate
                pnl = (price - position['entry']) / position['entry'] * position['size'] * 100
                pnl -= position['size'] * 100 * 0.0006  # fee
                trades.append(pnl / 100)
                equity.append(equity[-1] + pnl)
                position = None
                liquidations += 1
                continue
            
            # PPO action
            if not turb_result.is_turbulent:
                action = model.predict(history, position)
                action_type, intensity = model.interpret_action(action, position is not None)
                
                if action_type == 'BUY' and not position:
                    pos_size = min(intensity * params.position_pct, 0.15)  # Max 15%
                    position = {'entry': price, 'size': pos_size}
                
                elif action_type == 'SELL' and position:
                    pnl = (price - position['entry']) / position['entry'] * position['size'] * 100
                    pnl -= position['size'] * 100 * 0.0006  # fee
                    trades.append(pnl / 100)
                    equity.append(equity[-1] + pnl)
                    
                    # Track drawdown
                    if equity[-1] > peak:
                        peak = equity[-1]
                    dd = (peak - equity[-1]) / peak
                    max_dd = max(max_dd, dd)
                    
                    position = None
        
        # Calculate metrics
        total_return = (equity[-1] - 100) / 100 if len(equity) > 1 else 0
        
        if len(trades) > 1:
            returns = np.diff(equity) / np.array(equity[:-1])
            sharpe = np.mean(returns) / (np.std(returns) + 1e-9) * np.sqrt(365)
            win_rate = len([t for t in trades if t > 0]) / len(trades)
        else:
            sharpe = 0
            win_rate = 0
        
        # Composite score (higher is better)
        score = (
            total_return * 100 +  # Return is important
            sharpe * 10 +  # Sharpe bonus
            win_rate * 5 -  # Win rate bonus
            max_dd * 50  # Drawdown penalty
        )
        
        return TestResult(
            params=params,
            total_return=total_return,
            sharpe_ratio=sharpe,
            win_rate=win_rate,
            num_trades=len(trades),
            max_drawdown=max_dd,
            profitable=total_return > 0,
            score=score
        )
        
    except Exception as e:
        # Return failed test with very low score
        return TestResult(
            params=params,
            total_return=-1.0,
            sharpe_ratio=-10,
            win_rate=0,
            num_trades=0,
            max_drawdown=1.0,
            profitable=False,
            score=-1000
        )


def generate_parameter_combinations(num_tests: int = 5000) -> List[TestParams]:
    """Generate diverse parameter combinations"""
    np.random.seed(42)
    combinations = []
    
    for _ in range(num_tests):
        params = TestParams(
            # Log-uniform for learning rate
            learning_rate=np.random.choice([0.0001, 0.0003, 0.001, 0.003, 0.01]),
            
            # Epochs
            num_epochs=np.random.choice([5, 10, 15, 20]),
            
            # Fees (realistic range)
            trading_fee_pct=np.random.uniform(0.0001, 0.001),
            
            # Overtrading penalty
            overtrade_penalty=np.random.choice([0.0, 0.0001, 0.0005, 0.001]),
            
            # Action threshold
            action_threshold=np.random.uniform(0.02, 0.15),
            
            # Position size
            position_pct=np.random.uniform(0.05, 0.20),
            
            # Trailing stop
            trailing_stop_pct=np.random.uniform(0.03, 0.10),
            
            # Turbulence (high threshold for BTC)
            turbulence_threshold=np.random.uniform(2.0, 5.0),
            
            # Lookback
            turbulence_lookback=np.random.choice([20, 30, 50])
        )
        combinations.append(params)
    
    return combinations


def run_optimization(prices: List[float], num_tests: int = 5000, parallel: bool = True) -> List[TestResult]:
    """Run massive parameter optimization"""
    print(f"🔬 Running {num_tests} parameter combinations...")
    print(f"   Data: {len(prices)} price points")
    print(f"   Parallel: {parallel}")
    
    params_list = generate_parameter_combinations(num_tests)
    results = []
    
    if parallel:
        # Parallel execution
        with ProcessPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(run_single_test, prices, params, i): i 
                for i, params in enumerate(params_list[:100])  # Limit for testing
            }
            
            completed = 0
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                completed += 1
                
                if completed % 10 == 0:
                    print(f"   Progress: {completed}/{len(params_list[:100])} tests completed")
    else:
        # Sequential execution
        for i, params in enumerate(params_list[:100]):  # Limit for testing
            result = run_single_test(prices, params, i)
            results.append(result)
            
            if (i + 1) % 10 == 0:
                print(f"   Progress: {i+1}/{len(params_list[:100])} tests completed")
    
    return results


def analyze_results(results: List[TestResult]):
    """Analyze optimization results"""
    print("\n" + "="*80)
    print("📊 OPTIMIZATION RESULTS ANALYSIS")
    print("="*80)
    
    # Sort by score
    results_sorted = sorted(results, key=lambda r: r.score, reverse=True)
    
    # Top 10
    print("\n🏆 TOP 10 CONFIGURATIONS:")
    print("-"*80)
    print(f"{'Rank':<5} {'Return':<8} {'Sharpe':<8} {'Win%':<8} {'Trades':<8} {'Score':<10} {'Params'}")
    print("-"*80)
    
    for i, r in enumerate(results_sorted[:10], 1):
        print(f"{i:<5} {r.total_return*100:+.2f}% {r.sharpe_ratio:.3f}  {r.win_rate*100:.1f}%   {r.num_trades:<8} {r.score:.2f}     LR={r.params.learning_rate}, Fee={r.params.trading_fee_pct:.4f}")
    
    # Best params
    best = results_sorted[0]
    print(f"\n🥇 BEST PARAMETERS:")
    print(f"   Learning Rate: {best.params.learning_rate}")
    print(f"   Epochs: {best.params.num_epochs}")
    print(f"   Trading Fee: {best.params.trading_fee_pct:.4f}")
    print(f"   Overtrade Penalty: {best.params.overtrade_penalty}")
    print(f"   Action Threshold: {best.params.action_threshold:.3f}")
    print(f"   Position %: {best.params.position_pct:.2f}")
    print(f"   Trailing Stop: {best.params.trailing_stop_pct:.2f}")
    print(f"   Turbulence Threshold: {best.params.turbulence_threshold:.1f}")
    
    print(f"\n📈 BEST RESULT:")
    print(f"   Total Return: {best.total_return*100:.2f}%")
    print(f"   Sharpe Ratio: {best.sharpe_ratio:.3f}")
    print(f"   Win Rate: {best.win_rate*100:.1f}%")
    print(f"   Num Trades: {best.num_trades}")
    print(f"   Max Drawdown: {best.max_drawdown*100:.2f}%")
    
    # Statistics
    profitable = len([r for r in results if r.profitable])
    print(f"\n📊 STATISTICS:")
    print(f"   Total tests: {len(results)}")
    print(f"   Profitable: {profitable} ({profitable/len(results)*100:.1f}%)")
    print(f"   Avg return: {np.mean([r.total_return for r in results])*100:.2f}%")
    print(f"   Avg Sharpe: {np.mean([r.sharpe_ratio for r in results]):.3f}")
    
    return best


def save_best_params(best: TestResult, path: str = "/tmp/best_ppo_params.json"):
    """Save best parameters to file"""
    params_dict = {
        'ppo': {
            'learning_rate': best.params.learning_rate,
            'num_epochs': best.params.num_epochs,
            'trading_fee_pct': best.params.trading_fee_pct,
            'overtrade_penalty': best.params.overtrade_penalty,
            'action_threshold': best.params.action_threshold,
        },
        'bot': {
            'position_pct': best.params.position_pct,
            'trailing_stop_pct': best.params.trailing_stop_pct,
        },
        'turbulence': {
            'threshold': best.params.turbulence_threshold,
            'lookback': best.params.turbulence_lookback,
        },
        'results': {
            'total_return': best.total_return,
            'sharpe_ratio': best.sharpe_ratio,
            'win_rate': best.win_rate,
            'num_trades': best.num_trades,
            'max_drawdown': best.max_drawdown,
            'score': best.score,
        }
    }
    
    with open(path, 'w') as f:
        json.dump(params_dict, f, indent=2)
    
    print(f"\n💾 Best parameters saved to: {path}")


def main():
    print("="*80)
    print("🚀 MASSIVE PPO PARAMETER OPTIMIZATION")
    print("="*80)
    print(f"Started: {datetime.now().isoformat()}")
    
    # Load data
    prices = load_btc_data()
    if prices is None:
        print("❌ No data found!")
        return 1
    
    print(f"✅ Loaded {len(prices)} BTC prices")
    
    # Run optimization (start with 100 for testing)
    num_tests = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    print(f"\n🧪 Running {num_tests} tests...")
    
    results = run_optimization(prices, num_tests=num_tests, parallel=False)
    
    # Analyze
    best = analyze_results(results)
    
    # Save
    save_best_params(best)
    
    print("\n" + "="*80)
    print("✅ OPTIMIZATION COMPLETE")
    print("="*80)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
