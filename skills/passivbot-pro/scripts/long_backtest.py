#!/usr/bin/env python3
"""
Extended 30-minute backtest and optimization
More data, larger population, thorough testing
"""
import sys
import os
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/skills/passivbot-pro')

import pandas as pd
import numpy as np
import json
from datetime import datetime
import time

from scripts.config.settings import GridConfig, RiskConfig, UnstuckingConfig
from scripts.backtest.engine import VectorizedBacktester

# Setup
log_file = '/home/ubuntu/.openclaw/workspace/memory/passivbot_results/long_backtest_log.txt'
results_file = '/home/ubuntu/.openclaw/workspace/memory/passivbot_results/long_backtest_results.json'

def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line)
    with open(log_file, 'a') as f:
        f.write(line + '\n')

# Load data (60 days for thorough testing)
data_path = '/home/ubuntu/.openclaw/workspace/memory/passivbot_data/BTC_USDC_1m.csv'
df = pd.read_csv(data_path, index_col='timestamp', parse_dates=True)

# Use 45 days for training, 15 for testing
total_days = 60
train_days = 45
test_days = 15

full_df = df.tail(total_days * 24 * 60)
train_df = full_df.head(train_days * 24 * 60)
test_df = full_df.tail(test_days * 24 * 60)

log("="*70)
log("30-MINUTE EXTENDED BACKTEST SESSION")
log("="*70)
log(f"Total data: {len(full_df)} candles ({total_days} days)")
log(f"Training: {len(train_df)} candles ({train_days} days)")
log(f"Testing: {len(test_df)} candles ({test_days} days)")

# Test 8 different parameter combinations (each takes ~3-4 min)
scenarios = [
    {'name': 'Ultra_Conservative', 'grid': 0.015, 'markup': 0.012, 'mult': 1.1},
    {'name': 'Conservative', 'grid': 0.010, 'markup': 0.008, 'mult': 1.2},
    {'name': 'Moderate_Wide', 'grid': 0.008, 'markup': 0.006, 'mult': 1.3},
    {'name': 'Moderate', 'grid': 0.006, 'markup': 0.005, 'mult': 1.4},
    {'name': 'Balanced', 'grid': 0.005, 'markup': 0.004, 'mult': 1.5},
    {'name': 'Aggressive', 'grid': 0.004, 'markup': 0.003, 'mult': 1.7},
    {'name': 'Very_Aggressive', 'grid': 0.003, 'markup': 0.0025, 'mult': 2.0},
    {'name': 'GA_Optimized', 'grid': 0.01496, 'markup': 0.0125, 'mult': 1.13},  # From previous GA
]

all_results = []
start_time = time.time()

for i, scenario in enumerate(scenarios, 1):
    scenario_start = time.time()
    
    log(f"\n{'='*70}")
    log(f"[{i}/{len(scenarios)}] Testing: {scenario['name']}")
    log(f"Grid: {scenario['grid']:.4f}, Markup: {scenario['markup']:.4f}, Mult: {scenario['mult']:.2f}")
    log(f"{'='*70}")
    
    # Create configs
    risk_config = RiskConfig(
        initial_capital=100.0,
        min_position_size=2.0,
        max_position_size=10.0,
        stop_loss_balance=80.0,
        max_leverage=5.0,
        max_wallet_exposure=0.3,
        max_open_positions=3,
        max_grid_orders=10,
        max_drawdown_pct=0.20,
        daily_loss_limit=0.10
    )
    
    grid_config = GridConfig(
        grid_spacing_pct=scenario['grid'],
        grid_spacing_atr_multiplier=0.5,
        entry_multiplier=scenario['mult'],
        max_entry_multiplier=3.0,
        markup_pct=scenario['markup'],
        min_markup_usd=0.10,
        initial_entry_pct=0.01,
        auto_compound=True,
        compound_threshold=10.0
    )
    
    unstucking_config = UnstuckingConfig(
        unstuck_threshold_pct=0.05,
        unstuck_chunk_pct=0.1,
        max_unstuck_per_day=3
    )
    
    # Run backtest on training data
    log("  Running backtest on training data...")
    backtester = VectorizedBacktester(
        grid_config=grid_config,
        risk_config=risk_config,
        unstucking_config=unstucking_config
    )
    
    train_result = backtester.run_vectorized(train_df, verbose=False)
    
    # Run on test data (out-of-sample)
    log("  Running backtest on test data...")
    test_result = backtester.run_vectorized(test_df, verbose=False)
    
    # Full period
    log("  Running backtest on full period...")
    full_result = backtester.run_vectorized(full_df, verbose=False)
    
    result = {
        'scenario': scenario['name'],
        'params': scenario,
        'train': {
            'return': train_result.total_return_pct,
            'drawdown': train_result.max_drawdown_pct,
            'trades': train_result.total_trades,
            'sharpe': train_result.sharpe_ratio,
            'pf': train_result.profit_factor
        },
        'test': {
            'return': test_result.total_return_pct,
            'drawdown': test_result.max_drawdown_pct,
            'trades': test_result.total_trades,
            'sharpe': test_result.sharpe_ratio,
            'pf': test_result.profit_factor
        },
        'full': {
            'return': full_result.total_return_pct,
            'drawdown': full_result.max_drawdown_pct,
            'trades': full_result.total_trades,
            'sharpe': full_result.sharpe_ratio,
            'pf': full_result.profit_factor
        }
    }
    
    all_results.append(result)
    
    scenario_time = time.time() - scenario_start
    log(f"  Train: Return={train_result.total_return_pct:.2f}%, DD={train_result.max_drawdown_pct:.2f}%")
    log(f"  Test:  Return={test_result.total_return_pct:.2f}%, DD={test_result.max_drawdown_pct:.2f}%")
    log(f"  Full:  Return={full_result.total_return_pct:.2f}%, DD={full_result.max_drawdown_pct:.2f}%")
    log(f"  Time: {scenario_time:.1f}s")
    
    # Progress
    elapsed = time.time() - start_time
    remaining = (elapsed / i) * (len(scenarios) - i)
    log(f"  Progress: {elapsed/60:.1f}min elapsed, ~{remaining/60:.1f}min remaining")

# Find best scenario (best test return with acceptable drawdown)
best = max(all_results, key=lambda x: x['test']['return'] if x['test']['drawdown'] < 0.30 else -999)

log(f"\n{'='*70}")
log("SUMMARY - ALL SCENARIOS")
log(f"{'='*70}")
for r in all_results:
    log(f"{r['scenario']:20s} | Test Return: {r['test']['return']:6.2f}% | DD: {r['test']['drawdown']:5.2f}% | Trades: {r['test']['trades']:3d}")

log(f"\n{'='*70}")
log(f"BEST SCENARIO: {best['scenario']}")
log(f"Params: grid={best['params']['grid']}, markup={best['params']['markup']}, mult={best['params']['mult']}")
log(f"Test Return: {best['test']['return']:.2f}%")
log(f"Test Drawdown: {best['test']['drawdown']:.2f}%")
log(f"{'='*70}")

# Save results
with open(results_file, 'w') as f:
    json.dump({
        'timestamp': datetime.now().isoformat(),
        'duration_minutes': (time.time() - start_time) / 60,
        'total_scenarios': len(scenarios),
        'best_scenario': best,
        'all_results': all_results
    }, f, indent=2)

log(f"\nResults saved to: {results_file}")
log(f"Total time: {(time.time() - start_time)/60:.1f} minutes")
log("="*70)
