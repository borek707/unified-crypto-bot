#!/usr/bin/env python3
"""
ENSEMBLE SCENARIO TESTS
=======================
Test PPO vs A2C on specific market regimes:
- Scenario A: Bull market (Dec 2023 - Mar 2024)
- Scenario B: Bear market/correction (Apr-Jun 2024)
- Scenario C: Sideways (Jul-Oct 2023)

Metrics: Sharpe, Max Drawdown, Win Rate, Total Return, Fee Impact
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
class Scenario:
    name: str
    start_idx: int
    end_idx: int
    description: str
    expected_winner: str


@dataclass
class TestResult:
    model_name: str
    scenario: str
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    num_trades: int
    fee_impact: float


def load_btc_data():
    """Load BTC hourly data"""
    sources = [Path('/tmp/btc_real_2years.json')]
    for source in sources:
        if source.exists():
            with open(source) as f:
                return json.load(f)
    return None


def extract_period(prices: List[float], start_hour: int, duration_hours: int) -> Tuple[List[float], str]:
    """Extract specific time period from data"""
    # Assuming data is hourly and recent first
    # start_hour = hours from end
    end_idx = len(prices)
    start_idx = max(0, end_idx - start_hour - duration_hours)
    end_idx = end_idx - start_hour
    
    period_prices = prices[start_idx:end_idx]
    
    # Determine regime
    if len(period_prices) > 100:
        total_return = (period_prices[-1] - period_prices[0]) / period_prices[0]
        if total_return > 0.3:
            regime = 'strong_bull'
        elif total_return > 0.1:
            regime = 'bull'
        elif total_return < -0.2:
            regime = 'bear'
        else:
            regime = 'sideways'
    else:
        regime = 'unknown'
    
    return period_prices, regime


def run_model_test(prices: List[float], model_name: str, epochs: int = 10) -> Dict:
    """Run single model test"""
    # Split: 70% train, 30% test
    train_size = int(len(prices) * 0.7)
    train = prices[:train_size]
    test = prices[train_size:]
    
    print(f"\n  Training {model_name} on {len(train)} prices...")
    
    # Initialize model with MAKER FEES (0.03% total)
    if model_name == 'PPO':
        config = PPOConfig(
            learning_rate=0.001,
            num_epochs=epochs,
            trading_fee_pct=0.0003,  # MAKER: 0.015% + 0.015% = 0.03%
            action_threshold=0.15  # Higher threshold for stronger signals
        )
        model = ContinuousPPOModel(config)
    else:  # A2C
        config = A2CConfig(
            learning_rate=0.001,
            num_epochs=epochs,
            trading_fee_pct=0.0003,  # MAKER: 0.03% total
            action_threshold=0.15  # Higher threshold
        )
        model = ContinuousA2CModel(config)
    
    # Train
    model.train(train, epochs=epochs)
    
    # Test
    print(f"  Testing {model_name} on {len(test)} prices...")
    position = None
    trades = []
    equity = [100.0]
    peak = 100.0
    max_dd = 0.0
    total_fees = 0.0
    
    for i in range(50, len(test)):
        action = model.predict(test[:i+1], position)
        action_type, intensity = model.interpret_action(action, position is not None)
        
        if action_type == 'BUY' and not position:
            pos_size = min(intensity * 0.15, 0.15)
            position = {'entry': test[i], 'size': pos_size}
        
        elif action_type == 'SELL' and position:
            pnl = (test[i] - position['entry']) / position['entry'] * position['size'] * 100
            fee = position['size'] * 100 * 0.0003  # MAKER FEE: 0.03%
            pnl -= fee
            total_fees += fee
            
            trades.append(pnl / 100)
            equity.append(equity[-1] + pnl)
            
            if equity[-1] > peak:
                peak = equity[-1]
            dd = (peak - equity[-1]) / peak
            max_dd = max(max_dd, dd)
            
            position = None
    
    # Calculate metrics
    total_return = (equity[-1] - 100) / 100 if len(equity) > 1 else 0
    
    if len(trades) > 1:
        returns = np.diff(equity) / np.array(equity[:-1])
        sharpe = np.mean(returns) / (np.std(returns) + 1e-9) * np.sqrt(365 * 24)
        win_rate = len([t for t in trades if t > 0]) / len(trades)
    else:
        sharpe = 0
        win_rate = 0
    
    return {
        'model': model_name,
        'total_return': total_return,
        'sharpe': sharpe,
        'max_drawdown': max_dd,
        'win_rate': win_rate,
        'num_trades': len(trades),
        'fee_impact': total_fees / 100 if trades else 0
    }


def run_scenario_test(prices: List[float], scenario: Scenario) -> List[TestResult]:
    """Run test for one scenario with both models"""
    print(f"\n{'='*70}")
    print(f"📊 SCENARIO: {scenario.name}")
    print(f"   {scenario.description}")
    print(f"   Expected winner: {scenario.expected_winner}")
    print(f"{'='*70}")
    
    # Extract period
    period_prices, regime = extract_period(
        prices, 
        scenario.start_idx, 
        scenario.end_idx - scenario.start_idx
    )
    
    print(f"\nData: {len(period_prices)} hours ({regime})")
    print(f"Price: ${min(period_prices):,.0f} → ${max(period_prices):,.0f}")
    
    # Test both models
    results = []
    
    for model_name in ['PPO', 'A2C']:
        result = run_model_test(period_prices, model_name, epochs=10)
        results.append(TestResult(
            model_name=model_name,
            scenario=scenario.name,
            total_return=result['total_return'],
            sharpe_ratio=result['sharpe'],
            max_drawdown=result['max_drawdown'],
            win_rate=result['win_rate'],
            num_trades=result['num_trades'],
            fee_impact=result['fee_impact']
        ))
    
    # Print comparison
    print(f"\n📈 RESULTS:")
    print(f"{'Model':<10} {'Return':<10} {'Sharpe':<8} {'MaxDD':<8} {'Win%':<8} {'Trades':<8}")
    print("-" * 60)
    for r in results:
        print(f"{r.model_name:<10} {r.total_return*100:+.2f}%    {r.sharpe_ratio:.3f}   {r.max_drawdown*100:.1f}%    {r.win_rate*100:.0f}%     {r.num_trades}")
    
    # Determine winner
    winner = max(results, key=lambda r: r.sharpe_ratio)
    print(f"\n🏆 Winner by Sharpe: {winner.model_name}")
    print(f"   {'✅ Expected' if winner.model_name == scenario.expected_winner else '❌ Unexpected'}")
    
    return results


def main():
    print("="*70)
    print("🧪 ENSEMBLE SCENARIO TESTS")
    print("="*70)
    print(f"Started: {datetime.now().isoformat()}")
    
    # Load data
    prices = load_btc_data()
    if not prices:
        print("❌ No data!")
        return 1
    
    print(f"✅ Loaded {len(prices)} BTC prices")
    
    # Define scenarios based on approximate hours from end
    # 28k total hours (3 years)
    scenarios = [
        Scenario(
            name="Scenario A: Bull Market",
            start_idx=0,
            end_idx=2880,  # ~4 months
            description="Dec 2023 - Mar 2024: BTC $40k → $73k",
            expected_winner="PPO"
        ),
        Scenario(
            name="Scenario B: Correction",
            start_idx=2880,
            end_idx=5040,  # ~2.5 months
            description="Apr-Jun 2024: BTC $73k → $55k",
            expected_winner="A2C"
        ),
        Scenario(
            name="Scenario C: Sideways",
            start_idx=13000,
            end_idx=16000,  # ~3.5 months
            description="Jul-Oct 2023: BTC $25k-30k",
            expected_winner="A2C"
        ),
    ]
    
    # Run all scenarios
    all_results = []
    for scenario in scenarios:
        results = run_scenario_test(prices, scenario)
        all_results.extend(results)
    
    # Final summary
    print(f"\n\n{'='*70}")
    print("📊 FINAL SUMMARY")
    print(f"{'='*70}")
    
    print(f"\n{'Scenario':<30} {'PPO Return':<12} {'A2C Return':<12} {'Winner':<10}")
    print("-" * 70)
    
    for scenario in scenarios:
        ppo_result = next(r for r in all_results if r.scenario == scenario.name and r.model_name == 'PPO')
        a2c_result = next(r for r in all_results if r.scenario == scenario.name and r.model_name == 'A2C')
        
        winner = 'PPO' if ppo_result.sharpe_ratio > a2c_result.sharpe_ratio else 'A2C'
        expected = '✅' if winner == scenario.expected_winner else '❌'
        
        print(f"{scenario.name:<30} {ppo_result.total_return*100:+.2f}%      {a2c_result.total_return*100:+.2f}%      {winner} {expected}")
    
    # Save results
    output = {
        'timestamp': datetime.now().isoformat(),
        'results': [
            {
                'model': r.model_name,
                'scenario': r.scenario,
                'return': r.total_return,
                'sharpe': r.sharpe_ratio,
                'max_dd': r.max_drawdown,
                'win_rate': r.win_rate,
                'trades': r.num_trades
            }
            for r in all_results
        ]
    }
    
    with open('/tmp/ensemble_scenario_results.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n💾 Results saved to /tmp/ensemble_scenario_results.json")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
