#!/usr/bin/env python3
"""
ULTRA-FAST PARAMETER SWEEP
==========================
Minimal training for rapid parameter exploration.
Uses random search with very short training.
"""

import json
import sys
import numpy as np
from pathlib import Path
from datetime import datetime

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from ppo_continuous import ContinuousPPOModel, PPOConfig


def load_data():
    for p in [Path('/tmp/btc_real_2years.json'), Path('/tmp/btc_extended.json')]:
        if p.exists():
            with open(p) as f:
                return json.load(f)
    return None


def ultra_fast_test(prices, lr, fee, penalty, threshold):
    """Ultra fast - 2 epochs, small data"""
    try:
        # Tiny dataset
        prices = prices[-3000:]
        train = prices[:2000]
        test = prices[2000:]
        
        # Minimal training
        cfg = PPOConfig(
            learning_rate=lr,
            num_epochs=2,
            trading_fee_pct=fee,
            overtrade_penalty=penalty,
            action_threshold=threshold
        )
        model = ContinuousPPOModel(cfg)
        model.train(train, epochs=2)
        
        # Quick eval (no turbulence for speed)
        position = None
        pnl = 0
        trades = 0
        
        for i in range(50, len(test), 5):  # Skip every 5 for speed
            action = model.predict(test[:i+1], position)
            atype, intensity = model.interpret_action(action, position is not None)
            
            if atype == 'BUY' and not position:
                position = {'entry': test[i], 'size': 0.1}
            elif atype == 'SELL' and position:
                gain = (test[i] - position['entry']) / position['entry'] * 0.1
                gain -= 0.0006  # fee
                pnl += gain
                trades += 1
                position = None
        
        return pnl, trades
    except:
        return -1, 0


def main():
    print("="*60)
    print("⚡ ULTRA-FAST PARAMETER SWEEP")
    print("="*60)
    
    prices = load_data()
    if not prices:
        return 1
    
    n_tests = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    print(f"\nRunning {n_tests} ultra-fast tests...\n")
    
    results = []
    for i in range(n_tests):
        lr = np.random.choice([0.0003, 0.001, 0.003])
        fee = np.random.uniform(0.0001, 0.001)
        penalty = np.random.choice([0, 0.0001, 0.001])
        threshold = np.random.uniform(0.03, 0.12)
        
        pnl, trades = ultra_fast_test(prices, lr, fee, penalty, threshold)
        score = pnl * 100 - trades * 0.005
        
        results.append({
            'lr': lr, 'fee': fee, 'penalty': penalty, 
            'threshold': threshold, 'pnl': pnl, 'trades': trades, 'score': score
        })
        
        if (i+1) % 50 == 0:
            print(f"  {i+1}/{n_tests} done")
    
    # Sort
    results.sort(key=lambda x: x['score'], reverse=True)
    
    print("\n" + "="*60)
    print("🏆 TOP 10")
    print("="*60)
    print(f"{'#':<4} {'PnL%':<8} {'Trades':<7} {'Score':<7} {'Params'}")
    print("-"*60)
    
    for i, r in enumerate(results[:10], 1):
        print(f"{i:<4} {r['pnl']*100:+.3f}  {r['trades']:<7} {r['score']:.2f}   LR={r['lr']}, Fee={r['fee']:.4f}")
    
    # Best
    best = results[0]
    print(f"\n🥇 BEST PARAMETERS:")
    print(f"   Learning Rate: {best['lr']}")
    print(f"   Trading Fee: {best['fee']:.4f}")
    print(f"   Overtrade Penalty: {best['penalty']}")
    print(f"   Action Threshold: {best['threshold']:.3f}")
    print(f"\n   Expected Return: {best['pnl']*100:.3f}%")
    print(f"   Expected Trades: {best['trades']}")
    
    # Stats
    profitable = sum(1 for r in results if r['pnl'] > 0)
    print(f"\n📊 {profitable}/{n_tests} profitable ({profitable/n_tests*100:.1f}%)")
    
    # Save best
    with open('/tmp/best_params_ultra.json', 'w') as f:
        json.dump(best, f, indent=2)
    print(f"\n💾 Saved to /tmp/best_params_ultra.json")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
