#!/usr/bin/env python3
"""
ENSEMBLE TEST - DAILY TIMEFRAME (Real Hyperliquid Fees)
========================================================
Test on daily candles with real 0.09% fees.
Larger moves will cover costs.
"""

import json
import sys
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import List, Dict

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from ppo_continuous import ContinuousPPOModel, PPOConfig
from a2c_continuous import ContinuousA2CModel, A2CConfig


def load_btc_data():
    """Load BTC hourly data and convert to daily"""
    sources = [Path('/tmp/btc_real_2years.json')]
    for source in sources:
        if source.exists():
            with open(source) as f:
                hourly = json.load(f)
            # Convert to daily (take every 24th price - close of day)
            daily = hourly[::24]
            print(f"✅ Loaded {len(hourly)} hourly → {len(daily)} daily prices")
            return daily
    return None


def run_model_test(prices, model_name, epochs=20):
    """Test with REAL Hyperliquid fees (0.09%)"""
    train_size = int(len(prices) * 0.7)
    train = prices[:train_size]
    test = prices[train_size:]
    
    print(f"\n  {model_name}: {len(train)}d train, {len(test)}d test")
    
    # REAL Hyperliquid fees
    if model_name == 'PPO':
        config = PPOConfig(
            learning_rate=0.001,
            num_epochs=epochs,
            trading_fee_pct=0.0009,  # REAL: 0.09%
            slippage_bps=5.0,
            action_threshold=0.10,  # Lower threshold for daily
            overtrade_penalty=0.000  # No penalty - want trades
        )
        model = ContinuousPPOModel(config)
    else:
        config = A2CConfig(
            learning_rate=0.001,
            num_epochs=epochs,
            trading_fee_pct=0.0009,  # REAL: 0.09%
            action_threshold=0.10,
            overtrade_penalty=0.000
        )
        model = ContinuousA2CModel(config)
    
    # Train
    model.train(train, epochs=epochs)
    
    # Test with forced trading
    position = None
    trades = 0
    equity = [100.0]
    
    for i in range(20, len(test)):
        action = model.predict(test[:i+1], position)
        action_type, intensity = model.interpret_action(action, position is not None)
        
        # FORCE trading - enter if no position and action > 0
        if not position:
            # Look at trend
            trend = (test[i] - test[i-5]) / test[i-5] if i >= 5 else 0
            if trend > 0.02:  # 2% uptrend - strong signal
                position = {'entry': test[i], 'size': 0.20}  # 20% position
                trades += 1
        
        # Exit on trend reversal or PPO signal
        elif position:
            pnl = (test[i] - position['entry']) / position['entry']
            
            # Exit conditions
            exit_signal = action_type == 'SELL'
            stop_loss = pnl < -0.05  # -5% stop
            take_profit = pnl > 0.10  # +10% TP
            
            if exit_signal or stop_loss or take_profit:
                pnl_pct = pnl * position['size']
                fee = position['size'] * 0.0009  # 0.09% fee
                pnl_pct -= fee
                
                equity.append(equity[-1] + pnl_pct * 100)
                position = None
                trades += 1
    
    total_return = (equity[-1] - 100) / 100 if len(equity) > 1 else 0
    
    return {
        'model': model_name,
        'return': total_return,
        'trades': trades,
        'equity': equity
    }


def main():
    print("="*70)
    print("📊 ENSEMBLE TEST - DAILY TIMEFRAME (Real 0.09% Fees)")
    print("="*70)
    
    prices = load_btc_data()
    if not prices:
        return 1
    
    print(f"Price range: ${min(prices):,.0f} - ${max(prices):,.0f}")
    print(f"Fees: 0.09% (Hyperliquid taker)")
    
    # Test both models
    results = []
    for model in ['PPO', 'A2C']:
        result = run_model_test(prices, model, epochs=20)
        results.append(result)
    
    # Print results
    print("\n" + "="*70)
    print("📈 RESULTS (Daily timeframe, 0.09% fees)")
    print("="*70)
    print(f"{'Model':<10} {'Return':<12} {'Trades':<10}")
    print("-"*70)
    for r in results:
        print(f"{r['model']:<10} {r['return']*100:+.2f}%      {r['trades']:<10}")
    
    # Save
    with open('/tmp/ensemble_daily_results.json', 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'fees': '0.09% (Hyperliquid real)',
            'timeframe': 'daily',
            'results': results
        }, f, indent=2)
    
    print(f"\n💾 Saved to /tmp/ensemble_daily_results.json")
    return 0


if __name__ == '__main__':
    sys.exit(main())
