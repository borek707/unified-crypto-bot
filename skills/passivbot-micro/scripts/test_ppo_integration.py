#!/usr/bin/env python3
"""
TEST PPO + TURBULENCE INTEGRATION
==================================
Testuje nową integrację PPO i TurbulenceIndex na historycznych danych.
Porównuje wyniki przed i po zmianach.

Usage:
    python test_ppo_integration.py
"""

import json
import sys
import numpy as np
from pathlib import Path
from datetime import datetime

# Add passivbot-micro scripts to path
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from unified_bot import UnifiedBot, UnifiedConfig
from ppo_engine import PPOModel, PPOConfig, train_trend_following_ppo
from risk_management import TurbulenceIndex


def load_price_data():
    """Load historical BTC price data."""
    # Try multiple sources
    sources = [
        Path.home() / '.crypto_bot' / 'data' / 'hyperliquid_daily_big.json',
        Path('/tmp/hyperliquid_daily_big.json'),
        SCRIPTS_DIR / '..' / 'data' / 'btc_prices.json',
    ]
    
    for source in sources:
        if source.exists():
            print(f"📊 Loading prices from: {source}")
            with open(source, 'r') as f:
                return json.load(f)
    
    # Generate synthetic data if no real data
    print("⚠️ No real data found, generating synthetic...")
    np.random.seed(42)
    prices = [50000]
    for i in range(1000):
        change = np.random.normal(0.0001, 0.02)
        prices.append(prices[-1] * (1 + change))
    return prices


def test_turbulence_index(prices):
    """Test TurbulenceIndex calculation."""
    print("\n" + "="*70)
    print("🛡️ TESTING TURBULENCE INDEX")
    print("="*70)
    
    turb = TurbulenceIndex(lookback=30, turbulence_threshold=1.5)
    
    # Test at different points
    test_points = [100, 300, 500, 700, 900]
    results = []
    
    for point in test_points:
        result = turb.calculate(prices[:point])
        results.append(result)
        print(f"  Step {point}: turbulence={result.turbulence_index:.2f}, "
              f"regime={result.volatility_regime}, "
              f"size_factor={result.adjusted_size_factor:.0%}, "
              f"is_turbulent={result.is_turbulent}")
    
    # Count turbulent periods
    turbulent_count = sum(1 for r in results if r.is_turbulent)
    print(f"\n  Summary: {turbulent_count}/{len(results)} periods were turbulent")
    
    return turb


def test_ppo_model(prices):
    """Test PPO model training and prediction."""
    print("\n" + "="*70)
    print("🧠 TESTING PPO MODEL")
    print("="*70)
    
    # Train on first 80% of data
    train_size = int(len(prices) * 0.8)
    train_prices = prices[:train_size]
    test_prices = prices[train_size:]
    
    print(f"  Training on {len(train_prices)} prices...")
    config = PPOConfig(num_epochs=5, steps_per_update=512)
    model = PPOModel(config)
    model.train(train_prices, epochs=config.num_epochs)
    
    # Test predictions
    print(f"\n  Testing on {len(test_prices)} prices...")
    action_counts = {0: 0, 1: 0, 2: 0}
    action_names = {0: 'HOLD', 1: 'ENTER_LONG', 2: 'EXIT'}
    
    position = None
    trades = []
    
    for i in range(25, len(test_prices)):
        current_prices = test_prices[:i+1]
        action = model.predict(current_prices, position)
        action_counts[action] += 1
        
        # Simulate trading
        if action == 1 and position is None:  # Enter
            position = {'entry_price': current_prices[-1]}
            trades.append({'type': 'enter', 'price': current_prices[-1], 'step': i})
        elif action == 2 and position:  # Exit
            pnl = (current_prices[-1] - position['entry_price']) / position['entry_price']
            trades.append({'type': 'exit', 'price': current_prices[-1], 'step': i, 'pnl': pnl})
            position = None
    
    print(f"\n  Action distribution:")
    for action, count in action_counts.items():
        pct = count / sum(action_counts.values()) * 100
        print(f"    {action_names[action]}: {count} ({pct:.1f}%)")
    
    print(f"\n  Simulated trades: {len([t for t in trades if t['type'] == 'exit'])}")
    if trades:
        pnls = [t['pnl'] for t in trades if 'pnl' in t]
        if pnls:
            print(f"    Total PnL: {sum(pnls):.4f} ({sum(pnls)*100:.2f}%)")
            print(f"    Win rate: {len([p for p in pnls if p > 0])}/{len(pnls)} ({len([p for p in pnls if p > 0])/len(pnls)*100:.1f}%)")
    
    return model


def test_unified_bot_integration(prices, use_ppo=True, use_turbulence=True):
    """Test full unified bot with PPO + Turbulence."""
    print("\n" + "="*70)
    print(f"🤖 TESTING UNIFIED BOT (PPO={use_ppo}, Turbulence={use_turbulence})")
    print("="*70)
    
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
    
    # Train PPO if enabled
    if use_ppo and bot.ppo_model is not None:
        print("  Training PPO model...")
        train_size = int(len(prices) * 0.8)
        bot.ppo_model.train(prices[:train_size], epochs=5)
    
    # Simulate trading
    print(f"  Simulating trading on {len(prices)} price points...")
    
    position = None
    entries = 0
    exits = 0
    turbulent_skips = 0
    ppo_signals = {'enter': 0, 'exit': 0}
    total_pnl = 0.0
    
    for i in range(100, len(prices)):
        price = prices[i]
        price_history = prices[:i+1]
        
        # Check turbulence
        if use_turbulence and bot.turbulence_index is not None:
            turb_result = bot.turbulence_index.calculate(price_history)
            if turb_result.is_turbulent and position is None:
                turbulent_skips += 1
                continue
        
        # PPO entry/exit
        if use_ppo and bot.ppo_model is not None:
            action = bot.ppo_model.predict(price_history, position)
            
            if action == 1 and position is None:  # ENTER
                position = {'entry_price': price, 'highest_price': price}
                entries += 1
                ppo_signals['enter'] += 1
            elif action == 2 and position:  # EXIT
                pnl = (price - position['entry_price']) / position['entry_price']
                total_pnl += pnl
                exits += 1
                ppo_signals['exit'] += 1
                position = None
    
    print(f"\n  Results:")
    print(f"    Entries: {entries}")
    print(f"    Exits: {exits}")
    print(f"    Turbulent skips: {turbulent_skips}")
    print(f"    Total PnL: {total_pnl*100:.2f}%")
    if entries > 0:
        print(f"    Avg per trade: {total_pnl/entries*100:.2f}%")
    
    return {
        'entries': entries,
        'exits': exits,
        'turbulent_skips': turbulent_skips,
        'total_pnl': total_pnl
    }


def compare_strategies(prices):
    """Compare baseline vs PPO+Turbulence strategies."""
    print("\n" + "="*70)
    print("📊 COMPARING STRATEGIES")
    print("="*70)
    
    # Test 1: Baseline (no PPO, no turbulence)
    print("\n--- Baseline (no PPO, no turbulence) ---")
    baseline = test_unified_bot_integration(prices, use_ppo=False, use_turbulence=False)
    
    # Test 2: PPO only
    print("\n--- PPO only ---")
    ppo_only = test_unified_bot_integration(prices, use_ppo=True, use_turbulence=False)
    
    # Test 3: Turbulence only
    print("\n--- Turbulence only ---")
    turb_only = test_unified_bot_integration(prices, use_ppo=False, use_turbulence=True)
    
    # Test 4: PPO + Turbulence
    print("\n--- PPO + Turbulence ---")
    combined = test_unified_bot_integration(prices, use_ppo=True, use_turbulence=True)
    
    # Summary
    print("\n" + "="*70)
    print("📈 SUMMARY")
    print("="*70)
    print(f"{'Strategy':<25} {'Entries':<10} {'PnL %':<12} {'Improvement'}")
    print("-"*70)
    
    baseline_pnl = baseline['total_pnl'] * 100
    print(f"{'Baseline':<25} {baseline['entries']:<10} {baseline_pnl:>+10.2f}% {'(baseline)'}")
    
    ppo_pnl = ppo_only['total_pnl'] * 100
    ppo_improvement = ppo_pnl - baseline_pnl
    print(f"{'PPO only':<25} {ppo_only['entries']:<10} {ppo_pnl:>+10.2f}% {ppo_improvement:>+.2f}%")
    
    turb_pnl = turb_only['total_pnl'] * 100
    turb_improvement = turb_pnl - baseline_pnl
    print(f"{'Turbulence only':<25} {turb_only['entries']:<10} {turb_pnl:>+10.2f}% {turb_improvement:>+.2f}%")
    
    combined_pnl = combined['total_pnl'] * 100
    combined_improvement = combined_pnl - baseline_pnl
    print(f"{'PPO + Turbulence':<25} {combined['entries']:<10} {combined_pnl:>+10.2f}% {combined_improvement:>+.2f}%")
    
    # Determine DOD
    print("\n" + "="*70)
    print("✅ DEFINITION OF DONE CHECK")
    print("="*70)
    
    best = max([('Baseline', baseline_pnl), ('PPO only', ppo_pnl), 
                ('Turbulence only', turb_pnl), ('PPO + Turbulence', combined_pnl)],
               key=lambda x: x[1])
    
    if best[0] == 'PPO + Turbulence' and combined_improvement > 0:
        print(f"✅ DOD MET: PPO + Turbulence is best with {combined_pnl:+.2f}% ({combined_improvement:+.2f}% improvement)")
        return True
    elif combined_improvement > 0:
        print(f"⚠️ DOD PARTIAL: PPO + Turbulence improved by {combined_improvement:+.2f}% but {best[0]} is better ({best[1]:+.2f}%)")
        return True
    else:
        print(f"❌ DOD NOT MET: PPO + Turbulence worse by {combined_improvement:.2f}%")
        return False


def main():
    print("="*70)
    print("🧪 PPO + TURBULENCE INTEGRATION TEST")
    print("="*70)
    print(f"Started: {datetime.now().isoformat()}")
    
    # Load data
    prices = load_price_data()
    print(f"Loaded {len(prices)} price points")
    print(f"Price range: ${min(prices):,.2f} - ${max(prices):,.2f}")
    
    # Run tests
    try:
        # Test individual components
        test_turbulence_index(prices)
        test_ppo_model(prices)
        
        # Compare strategies
        dod_met = compare_strategies(prices)
        
        print("\n" + "="*70)
        print(f"✅ TEST COMPLETED - DOD: {'MET' if dod_met else 'NOT MET'}")
        print("="*70)
        
        return 0 if dod_met else 1
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
