#!/usr/bin/env python3
"""
Run backtests for multiple strategy configurations.
Compare results and pick the best one.
"""

import json
import subprocess
import sys
import os
from pathlib import Path

# Load strategy configs
with open(Path('~/.openclaw/workspace/backtest_strategies.json').expanduser()) as f:
    strategies = json.load(f)

RESULTS = []

print("="*70)
print("🧪 STRATEGY BACKTEST COMPARISON")
print("="*70)
print(f"Testing {len(strategies)} configurations...\n")

for i, strat in enumerate(strategies, 1):
    name = strat['name']
    print(f"\n[{i}/{len(strategies)}] Testing: {name}")
    print("-"*50)
    
    # Create temp config
    config = {
        'risk': strat['risk'],
        'grid': strat['grid'],
        'exchange': {
            'exchange': 'hyperliquid',
            'testnet': True,
            'symbols': ['BTC/USDC:USDC'],
            'fees': {'maker_fee': 0.0002, 'taker_fee': 0.0005}
        }
    }
    
    config_path = Path(f'~/.openclaw/workspace/config_temp_{name}.json').expanduser()
    with open(config_path, 'w') as f:
        json.dump(config, f)
    
    # Run backtest
    env = os.environ.copy()
    env['EXCHANGE_API_KEY'] = '0xb64995df52ea75ca8497d61e9e7e3ff185bf6787'
    env['EXCHANGE_API_SECRET'] = '0x839358e35f7155dfc8468a1d9d7d8c305b944b39db94ab9014cc11281ba65c7d'
    
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'scripts.main',
             '--config', str(config_path),
             '--mode', 'backtest',
             '--symbol', 'BTC/USDC:USDC',
             '--days', '60',
             '--log-level', 'ERROR'],
            cwd=Path('~/.openclaw/workspace/skills/passivbot-pro').expanduser(),
            env=env,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        # Parse results from output
        output = result.stdout + result.stderr
        
        # Extract metrics
        metrics = {
            'name': name,
            'grid_spacing': strat['grid']['grid_spacing_pct'],
            'markup': strat['grid']['markup_pct'],
            'entry_mult': strat['grid']['entry_multiplier'],
            'return_pct': 0.0,
            'drawdown_pct': 0.0,
            'sharpe': 0.0,
            'trades': 0,
            'win_rate': 0.0
        }
        
        for line in output.split('\n'):
            if 'Total Return:' in line:
                try:
                    metrics['return_pct'] = float(line.split(':')[1].strip().replace('%', ''))
                except:
                    pass
            elif 'Max Drawdown:' in line:
                try:
                    metrics['drawdown_pct'] = float(line.split(':')[1].strip().replace('%', ''))
                except:
                    pass
            elif 'Sharpe Ratio:' in line:
                try:
                    metrics['sharpe'] = float(line.split(':')[1].strip())
                except:
                    pass
            elif 'Total Trades:' in line:
                try:
                    metrics['trades'] = int(line.split(':')[1].strip())
                except:
                    pass
            elif 'Win Rate:' in line:
                try:
                    metrics['win_rate'] = float(line.split(':')[1].strip().replace('%', ''))
                except:
                    pass
        
        RESULTS.append(metrics)
        
        print(f"   Return: {metrics['return_pct']:.2f}%")
        print(f"   Drawdown: {metrics['drawdown_pct']:.2f}%")
        print(f"   Sharpe: {metrics['sharpe']:.2f}")
        print(f"   Trades: {metrics['trades']}")
        print(f"   Win Rate: {metrics['win_rate']:.1f}%")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        RESULTS.append({
            'name': name,
            'grid_spacing': strat['grid']['grid_spacing_pct'],
            'markup': strat['grid']['markup_pct'],
            'entry_mult': strat['grid']['entry_multiplier'],
            'return_pct': 0, 'drawdown_pct': 0, 'sharpe': 0, 'trades': 0, 'win_rate': 0,
            'error': str(e)
        })
    
    # Cleanup
    config_path.unlink(missing_ok=True)

# Summary
print("\n" + "="*70)
print("📊 RESULTS SUMMARY")
print("="*70)
print(f"{'Strategy':<15} {'Return':<10} {'DD':<10} {'Sharpe':<8} {'Trades':<8} {'Win%':<8}")
print("-"*70)

for r in RESULTS:
    print(f"{r['name']:<15} {r['return_pct']:>8.2f}% {r['drawdown_pct']:>8.2f}% {r['sharpe']:>7.2f} {r['trades']:>7} {r['win_rate']:>7.1f}%")

# Find best
if RESULTS:
    best = max(RESULTS, key=lambda x: x['return_pct'] - x['drawdown_pct'])
    print("\n" + "="*70)
    print(f"🏆 BEST STRATEGY: {best['name']}")
    print(f"   Return: {best['return_pct']:.2f}%")
    print(f"   Drawdown: {best['drawdown_pct']:.2f}%")
    print(f"   Grid Spacing: {best['grid_spacing']*100:.1f}%")
    print(f"   Markup: {best['markup']*100:.1f}%")
    print("="*70)
    
    # Save best config
    best_strat = next(s for s in strategies if s['name'] == best['name'])
    best_config = {
        'risk': best_strat['risk'],
        'grid': best_strat['grid'],
        'exchange': {
            'exchange': 'hyperliquid',
            'testnet': True,
            'symbols': ['BTC/USDC:USDC'],
            'fees': {'maker_fee': 0.0002, 'taker_fee': 0.0005}
        }
    }
    
    with open(Path('~/.openclaw/workspace/config_best.json').expanduser(), 'w') as f:
        json.dump(best_config, f, indent=2)
    
    print(f"\n✅ Best config saved to: config_best.json")
