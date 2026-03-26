#!/usr/bin/env python3
"""
PPO LONG WINDOW TEST (Hyperliquid Fees)
=========================================
Test PPO with correct Hyperliquid fees on extended training window.

Fees:
- Taker entry: 0.045%
- Taker exit: 0.045%
- Total round-trip: 0.09%

Training: 1 year (~8760 hours)
Testing: 3 months (~2190 hours)
Epochs: 10-20
"""

import json
import sys
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from ppo_continuous import ContinuousPPOModel, PPOConfig
from risk_management import TurbulenceIndex


def load_btc_data():
    """Load real BTC data"""
    sources = [
        Path('/tmp/btc_real_2years.json'),
        Path('/tmp/btc_extended.json'),
    ]
    for source in sources:
        if source.exists():
            with open(source, 'r') as f:
                prices = json.load(f)
            print(f"✅ Loaded {len(prices)} BTC prices from {source.name}")
            print(f"   Range: ${min(prices):,.0f} - ${max(prices):,.0f}")
            return prices
    return None


def classify_market_regime(prices: List[float]) -> str:
    """Classify market regime for reporting"""
    if len(prices) < 100:
        return 'unknown'
    
    returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
    total_return = (prices[-1] - prices[0]) / prices[0]
    volatility = np.std(returns) * np.sqrt(365 * 24)
    
    if total_return > 0.5:
        return 'strong_bull'
    elif total_return > 0.2:
        return 'bull'
    elif total_return < -0.3:
        return 'strong_bear'
    elif total_return < -0.1:
        return 'bear'
    else:
        return 'sideways'


def test_ppo_with_fees(prices: List[float], train_window: int = 8760, 
                       test_window: int = 2190, epochs: int = 15) -> Dict:
    """
    Test PPO with correct Hyperliquid fees.
    
    Args:
        prices: Full price history
        train_window: Training period in hours (default: 1 year = 8760)
        test_window: Testing period in hours (default: 3 months = 2190)
        epochs: Number of training epochs
    """
    print(f"\n{'='*70}")
    print(f"🧪 PPO TEST: {epochs} epochs, {train_window}h training, {test_window}h testing")
    print(f"{'='*70}")
    
    # Split data
    total_needed = train_window + test_window
    if len(prices) < total_needed:
        print(f"⚠️ Warning: Only {len(prices)} prices available, using all")
        prices = prices
    else:
        prices = prices[-total_needed:]
    
    train_prices = prices[:train_window]
    test_prices = prices[train_window:]
    
    train_regime = classify_market_regime(train_prices)
    test_regime = classify_market_regime(test_prices)
    
    print(f"\n📊 Data:")
    print(f"   Training: {len(train_prices)} hours ({train_regime})")
    print(f"   Testing:  {len(test_prices)} hours ({test_regime})")
    print(f"   Train range: ${min(train_prices):,.0f} - ${max(train_prices):,.0f}")
    print(f"   Test range:  ${min(test_prices):,.0f} - ${max(test_prices):,.0f}")
    
    # Configure PPO with Hyperliquid fees
    print(f"\n⚙️  Configuration:")
    print(f"   Trading fee: 0.09% (0.045% entry + 0.045% exit)")
    print(f"   Slippage: 2 bps")
    print(f"   Overtrade penalty: 0.0001")
    print(f"   Learning rate: 0.001")
    print(f"   Epochs: {epochs}")
    
    config = PPOConfig(
        learning_rate=0.001,
        num_epochs=epochs,
        trading_fee_pct=0.0009,  # 0.09% total (0.045% + 0.045%)
        slippage_bps=2.0,
        overtrade_penalty=0.0001,
        action_threshold=0.05
    )
    
    # Train
    print(f"\n🎓 Training PPO...")
    model = ContinuousPPOModel(config)
    avg_reward = model.train(train_prices, epochs=epochs)
    
    # Test
    print(f"\n📈 Testing on out-of-sample data...")
    position = None
    trades = []
    equity = [100.0]
    peak = 100.0
    max_drawdown = 0.0
    
    # Turbulence for kill switch
    turb = TurbulenceIndex(lookback=30, turbulence_threshold=3.0)
    
    for i in range(50, len(test_prices)):
        price = test_prices[i]
        history = test_prices[:i+1]
        
        # Kill switch check
        turb_result = turb.calculate(history)
        if turb_result.is_turbulent and position:
            # Liquidate immediately
            pnl = (price - position['entry']) / position['entry'] * position['size'] * 100
            pnl -= position['size'] * 100 * 0.0009  # fee
            trades.append({
                'type': 'liquidation',
                'pnl': pnl,
                'price': price
            })
            equity.append(equity[-1] + pnl)
            position = None
            continue
        
        # Normal PPO trading
        if not turb_result.is_turbulent:
            action = model.predict(history, position)
            action_type, intensity = model.interpret_action(action, position is not None)
            
            if action_type == 'BUY' and not position:
                # Enter position
                pos_size = min(intensity * 0.15, 0.15)  # Max 15%
                position = {
                    'entry': price,
                    'size': pos_size
                }
            
            elif action_type == 'SELL' and position:
                # Exit position
                pnl = (price - position['entry']) / position['entry'] * position['size'] * 100
                pnl -= position['size'] * 100 * 0.0009  # fee
                
                trades.append({
                    'type': 'exit',
                    'pnl': pnl,
                    'entry': position['entry'],
                    'exit': price
                })
                
                equity.append(equity[-1] + pnl)
                
                # Track drawdown
                if equity[-1] > peak:
                    peak = equity[-1]
                dd = (peak - equity[-1]) / peak
                max_drawdown = max(max_drawdown, dd)
                
                position = None
    
    # Calculate metrics
    total_return = (equity[-1] - 100) / 100
    
    if len(trades) > 1:
        returns = np.diff(equity) / np.array(equity[:-1])
        sharpe = np.mean(returns) / (np.std(returns) + 1e-9) * np.sqrt(365 * 24)
        win_rate = len([t for t in trades if t['pnl'] > 0]) / len(trades)
    else:
        sharpe = 0
        win_rate = 0
    
    results = {
        'train_regime': train_regime,
        'test_regime': test_regime,
        'total_return': total_return,
        'sharpe_ratio': sharpe,
        'win_rate': win_rate,
        'num_trades': len(trades),
        'max_drawdown': max_drawdown,
        'avg_reward': avg_reward,
        'equity_curve': equity,
        'trades': trades
    }
    
    return results


def run_multiple_tests(prices: List[float], num_tests: int = 5):
    """Run multiple tests with different time windows"""
    print("="*70)
    print("🔬 PPO LONG WINDOW TEST SUITE")
    print("="*70)
    print(f"Running {num_tests} tests on different market periods")
    print(f"Each test: 1 year training + 3 months testing")
    
    all_results = []
    
    # Test on different periods
    test_periods = [
        # (start_offset, description)
        (0, "Latest period"),
        (2190, "3 months earlier"),
        (4380, "6 months earlier"),
        (6570, "9 months earlier"),
        (8760, "1 year earlier"),
    ]
    
    for i, (offset, desc) in enumerate(test_periods[:num_tests], 1):
        print(f"\n\n{'='*70}")
        print(f"TEST {i}/{num_tests}: {desc}")
        print(f"{'='*70}")
        
        # Adjust prices for this test period
        total_needed = 8760 + 2190 + offset
        if len(prices) < total_needed:
            print(f"⚠️ Skipping - not enough data")
            continue
        
        test_prices = prices[-total_needed:-offset] if offset > 0 else prices[-total_needed:]
        
        result = test_ppo_with_fees(test_prices, epochs=15)
        all_results.append(result)
        
        # Print results
        print(f"\n📊 RESULTS:")
        print(f"   Total Return: {result['total_return']*100:+.2f}%")
        print(f"   Sharpe Ratio: {result['sharpe_ratio']:.3f}")
        print(f"   Win Rate: {result['win_rate']*100:.1f}%")
        print(f"   Trades: {result['num_trades']}")
        print(f"   Max Drawdown: {result['max_drawdown']*100:.2f}%")
        print(f"   Train Regime: {result['train_regime']}")
        print(f"   Test Regime: {result['test_regime']}")
    
    # Summary
    print(f"\n\n{'='*70}")
    print("📈 SUMMARY ACROSS ALL TESTS")
    print(f"{'='*70}")
    
    returns = [r['total_return'] for r in all_results]
    sharpes = [r['sharpe_ratio'] for r in all_results]
    win_rates = [r['win_rate'] for r in all_results]
    
    print(f"\nReturns: {[f'{r*100:+.2f}%' for r in returns]}")
    print(f"Avg Return: {np.mean(returns)*100:+.2f}%")
    print(f"Avg Sharpe: {np.mean(sharpes):.3f}")
    print(f"Avg Win Rate: {np.mean(win_rates)*100:.1f}%")
    print(f"Profitable tests: {len([r for r in returns if r > 0])}/{len(returns)}")
    
    return all_results


def main():
    print("="*70)
    print("🚀 PPO HYPERLIQUID FEE TEST (0.09%)")
    print("="*70)
    print(f"Started: {datetime.now().isoformat()}")
    
    # Load data
    prices = load_btc_data()
    if prices is None:
        print("❌ No data found!")
        return 1
    
    # Run tests
    results = run_multiple_tests(prices, num_tests=5)
    
    # Save results
    output = {
        'timestamp': datetime.now().isoformat(),
        'fee_config': '0.09% (Hyperliquid taker)',
        'train_window': '1 year (8760h)',
        'test_window': '3 months (2190h)',
        'epochs': 15,
        'results': [
            {
                'train_regime': r['train_regime'],
                'test_regime': r['test_regime'],
                'total_return': r['total_return'],
                'sharpe_ratio': r['sharpe_ratio'],
                'win_rate': r['win_rate'],
                'num_trades': r['num_trades'],
                'max_drawdown': r['max_drawdown'],
            }
            for r in results
        ]
    }
    
    with open('/tmp/ppo_long_window_results.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n💾 Results saved to /tmp/ppo_long_window_results.json")
    
    print("\n" + "="*70)
    print("✅ TEST COMPLETE")
    print("="*70)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
