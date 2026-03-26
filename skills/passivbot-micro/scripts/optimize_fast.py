#!/usr/bin/env python3
"""
FAST PPO PARAMETER OPTIMIZATION
================================
Quick parameter search with reduced training epochs.
For 5000 tests - use minimal training to find promising regions.
"""

import json
import sys
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List
from dataclasses import dataclass

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from ppo_continuous import ContinuousPPOModel, PPOConfig
from risk_management import TurbulenceIndex


@dataclass
class TestParams:
    learning_rate: float = 0.001
    trading_fee_pct: float = 0.0003
    overtrade_penalty: float = 0.0001
    action_threshold: float = 0.05
    turbulence_threshold: float = 3.0


@dataclass  
class TestResult:
    params: TestParams
    total_return: float
    num_trades: int
    score: float


def load_data():
    sources = [Path('/tmp/btc_real_2years.json'), Path('/tmp/btc_extended.json')]
    for source in sources:
        if source.exists():
            with open(source, 'r') as f:
                prices = json.load(f)
            print(f"✅ Loaded {len(prices)} prices")
            return prices
    return None


def quick_test(prices: List[float], params: TestParams) -> TestResult:
    """Quick test with minimal training"""
    try:
        # Use smaller dataset for speed
        prices = prices[-5000:]  # Last 5000 points
        train_size = 3500
        train = prices[:train_size]
        test = prices[train_size:]
        
        # Fast training (3 epochs only)
        cfg = PPOConfig(
            learning_rate=params.learning_rate,
            num_epochs=3,  # Fast!
            trading_fee_pct=params.trading_fee_pct,
            slippage_bps=2.0,
            overtrade_penalty=params.overtrade_penalty,
            action_threshold=params.action_threshold
        )
        
        model = ContinuousPPOModel(cfg)
        model.train(train, epochs=3)
        
        # Quick test
        turb = TurbulenceIndex(lookback=30, turbulence_threshold=params.turbulence_threshold)
        
        position = None
        trades = 0
        pnl = 0.0
        
        for i in range(50, len(test)):
            price = test[i]
            history = test[:i+1]
            
            # Kill switch
            if turb.calculate(history).is_turbulent and position:
                pnl += (price - position['entry']) / position['entry'] * 0.1
                trades += 1
                position = None
                continue
            
            if not turb.calculate(history).is_turbulent:
                action = model.predict(history, position)
                atype, intensity = model.interpret_action(action, position is not None)
                
                if atype == 'BUY' and not position:
                    position = {'entry': price}
                elif atype == 'SELL' and position:
                    pnl += (price - position['entry']) / position['entry'] * 0.1
                    pnl -= 0.0006  # fee
                    trades += 1
                    position = None
        
        score = pnl * 100 - trades * 0.01  # Penalty for overtrading
        
        return TestResult(params, pnl, trades, score)
        
    except Exception as e:
        return TestResult(params, -1.0, 0, -100)


def main():
    print("="*70)
    print("⚡ FAST PPO OPTIMIZATION")
    print("="*70)
    
    prices = load_data()
    if prices is None:
        return 1
    
    # Number of tests
    n_tests = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    print(f"\nRunning {n_tests} quick tests...\n")
    
    # Generate random params
    np.random.seed(42)
    results = []
    
    for i in range(n_tests):
        params = TestParams(
            learning_rate=np.random.choice([0.0003, 0.001, 0.003]),
            trading_fee_pct=np.random.uniform(0.0001, 0.001),
            overtrade_penalty=np.random.choice([0.0, 0.0001, 0.001]),
            action_threshold=np.random.uniform(0.03, 0.12),
            turbulence_threshold=np.random.uniform(2.5, 5.0)
        )
        
        result = quick_test(prices, params)
        results.append(result)
        
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{n_tests} done...")
    
    # Sort by score
    results.sort(key=lambda r: r.score, reverse=True)
    
    # Show top 10
    print("\n" + "="*70)
    print("🏆 TOP 10 RESULTS")
    print("="*70)
    print(f"{'Rank':<5} {'Return':<10} {'Trades':<8} {'Score':<8} {'Params'}")
    print("-"*70)
    
    for i, r in enumerate(results[:10], 1):
        print(f"{i:<5} {r.total_return*100:+.3f}%   {r.num_trades:<8} {r.score:.2f}    LR={r.params.learning_rate}, Fee={r.params.trading_fee_pct:.4f}, Turb={r.params.turbulence_threshold:.1f}")
    
    # Best
    best = results[0]
    print(f"\n🥇 BEST:")
    print(f"   Learning Rate: {best.params.learning_rate}")
    print(f"   Trading Fee: {best.params.trading_fee_pct:.4f}")
    print(f"   Overtrade Penalty: {best.params.overtrade_penalty}")
    print(f"   Action Threshold: {best.params.action_threshold:.3f}")
    print(f"   Turbulence Threshold: {best.params.turbulence_threshold:.1f}")
    print(f"\n   Return: {best.total_return*100:.3f}%")
    print(f"   Trades: {best.num_trades}")
    
    # Save
    best_dict = {
        'learning_rate': best.params.learning_rate,
        'trading_fee_pct': best.params.trading_fee_pct,
        'overtrade_penalty': best.params.overtrade_penalty,
        'action_threshold': best.params.action_threshold,
        'turbulence_threshold': best.params.turbulence_threshold,
        'expected_return': best.total_return,
        'expected_trades': best.num_trades
    }
    
    with open('/tmp/best_params_fast.json', 'w') as f:
        json.dump(best_dict, f, indent=2)
    
    print(f"\n💾 Saved to /tmp/best_params_fast.json")
    
    # Stats
    profitable = len([r for r in results if r.total_return > 0])
    print(f"\n📊 Stats: {profitable}/{n_tests} profitable ({profitable/n_tests*100:.1f}%)")
    print(f"   Avg return: {np.mean([r.total_return for r in results])*100:.3f}%")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
