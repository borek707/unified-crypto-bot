#!/usr/bin/env python3
"""
Paper Trading Simulation - 3 Risk Profiles
Runs bots on historical data without live API.
"""
import json
import sys
import os
from pathlib import Path
from datetime import datetime
import time
import random

sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/skills/passivbot-micro/scripts')

# Load historical data
df_path = Path('~/.openclaw/workspace/memory/passivbot_data/BTC_USDC_1m.csv').expanduser()

def load_data():
    """Load BTC price data."""
    import pandas as pd
    df = pd.read_csv(df_path)
    return df['close'].values[-10080:]  # Last 7 days of 1m data

class PaperBot:
    """Paper trading bot simulation."""
    
    def __init__(self, config_path, name):
        self.name = name
        self.config_path = config_path
        with open(config_path) as f:
            self.config = json.load(f)
        
        self.initial = self.config['initial_capital']
        self.balance = self.initial
        self.positions = []
        self.trades = []
        self.pnl = 0.0
        
        # Log file
        self.log_dir = Path(f'~/.openclaw/workspace/memory/passivbot_logs/{name.lower()}').expanduser()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / 'bot.log'
        
    def log(self, msg):
        """Log message."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"{timestamp} | {self.name} | {msg}"
        print(log_line)
        with open(self.log_file, 'a') as f:
            f.write(log_line + '\n')
    
    def run_simulation(self, prices):
        """Run simulation on price data."""
        self.log(f"🚀 STARTING PAPER TRADING - ${self.initial}")
        self.log(f"Config: {self.config['short_leverage']}x max leverage")
        
        for i, price in enumerate(prices):
            if i < 100:
                continue
            
            # Simple trend detection
            lookback = prices[i-48:i]
            change = (price / lookback[0] - 1) if lookback[0] > 0 else 0
            
            # Trading logic based on risk profile
            if change > 0.02:  # Uptrend
                if random.random() < 0.1:  # 10% chance to trade
                    profit = self.simulate_long(price, change)
                    self.pnl += profit
                    
            elif change < -0.02:  # Downtrend
                if random.random() < 0.1:
                    profit = self.simulate_short(price, change)
                    self.pnl += profit
            
            # Log every 1000 candles
            if i % 1000 == 0:
                current_balance = self.initial + self.pnl
                pnl_pct = (self.pnl / self.initial) * 100
                self.log(f"Balance: ${current_balance:.2f} | PnL: {pnl_pct:+.2f}% | Trades: {len(self.trades)}")
        
        # Final report
        final_balance = self.initial + self.pnl
        return_pct = (self.pnl / self.initial) * 100
        self.log(f"🏁 FINAL: ${final_balance:.2f} ({return_pct:+.2f}%) | Trades: {len(self.trades)}")
        
        return {
            'name': self.name,
            'initial': self.initial,
            'final': final_balance,
            'pnl': self.pnl,
            'return_pct': return_pct,
            'trades': len(self.trades)
        }
    
    def simulate_long(self, price, trend):
        """Simulate LONG trade."""
        size = self.config['long_position_pct'] * self.initial
        markup = self.config['long_markup']
        
        # Simulate take profit
        if random.random() < 0.6:  # 60% win rate
            profit = size * markup
            self.trades.append({'side': 'LONG', 'pnl': profit})
            self.log(f"📈 LONG WIN: +${profit:.2f}")
            return profit
        else:
            loss = -size * (markup * 0.5)
            self.trades.append({'side': 'LONG', 'pnl': loss})
            self.log(f"📈 LONG LOSS: ${loss:.2f}")
            return loss
    
    def simulate_short(self, price, trend):
        """Simulate SHORT trade."""
        leverage = self.config['short_leverage']
        size = self.config['short_position_pct'] * self.initial * leverage
        tp = self.config['short_tp']
        
        if random.random() < 0.55:  # 55% win rate (harder to short)
            profit = size * tp
            self.trades.append({'side': 'SHORT', 'pnl': profit})
            self.log(f"📉 SHORT WIN: +${profit:.2f}")
            return profit
        else:
            loss = -size * (self.config['short_sl'])
            self.trades.append({'side': 'SHORT', 'pnl': loss})
            self.log(f"📉 SHORT LOSS: ${loss:.2f}")
            return loss


def main():
    print("="*70)
    print("🚀 PAPER TRADING - 3 RISK PROFILES")
    print("="*70)
    print("\nLoading BTC data...")
    
    prices = load_data()
    print(f"Data loaded: {len(prices)} candles (7 days)\n")
    
    configs = [
        (Path('~/.openclaw/workspace/config_low_risk.json').expanduser(), 'LOW'),
        (Path('~/.openclaw/workspace/config_medium_risk.json').expanduser(), 'MEDIUM'),
        (Path('~/.openclaw/workspace/config_high_risk.json').expanduser(), 'HIGH')
    ]
    
    results = []
    
    for config_path, name in configs:
        print(f"\n{'='*70}")
        print(f"Starting {name} RISK bot...")
        print('='*70)
        
        bot = PaperBot(config_path, name)
        result = bot.run_simulation(prices)
        results.append(result)
        
        time.sleep(1)
    
    # Summary
    print("\n" + "="*70)
    print("📊 FINAL RESULTS")
    print("="*70)
    print(f"{'Bot':<15} {'Initial':<10} {'Final':<12} {'PnL':<12} {'Return':<10} {'Trades':<8}")
    print("-"*70)
    
    for r in results:
        print(f"{r['name']:<15} ${r['initial']:<9.0f} ${r['final']:<11.2f} ${r['pnl']:<11.2f} {r['return_pct']:>+8.2f}% {r['trades']:<8}")
    
    print("="*70)
    
    # Winner
    winner = max(results, key=lambda x: x['return_pct'])
    print(f"\n🏆 WINNER: {winner['name']} RISK ({winner['return_pct']:+.2f}%)")
    
    # Save results
    results_file = Path('~/.openclaw/workspace/memory/paper_trading_results.json').expanduser()
    with open(results_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'results': results
        }, f, indent=2)
    
    print(f"\n💾 Results saved to: {results_file}")

if __name__ == '__main__':
    main()
