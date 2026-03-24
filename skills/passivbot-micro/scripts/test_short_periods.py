#!/usr/bin/env python3
import json
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/skills/passivbot-micro/scripts')
from massive_test_10k import MassiveTester, TestConfig

with open('/tmp/hyperliquid_daily_big.json', 'r') as f:
    prices = json.load(f)

# Test on different periods
periods = [
    ("Ostatnie 365 dni (1 rok)", prices[-365:]),
    ("Ostatnie 180 dni (6 mies)", prices[-180:]),
    ("Ostatnie 90 dni (3 mies)", prices[-90:]),
]

print(f"=== TESTY NA KRÓTSZYCH OKRESACH ===\n")
print(f"Dane: BTC/USD z Hyperliquid\n")

for label, period_prices in periods:
    print(f"\n{'='*60}")
    print(f"{label}: {len(period_prices)} dni")
    print(f"Cena: ${period_prices[0]:,.0f} → ${period_prices[-1]:,.0f}")
    change = ((period_prices[-1]/period_prices[0])-1)*100
    print(f"Zmiana BTC: {change:+.1f}%")
    print(f"{'='*60}")
    
    tester = MassiveTester(period_prices)
    configs = tester.generate_configs()[:100]  # 100 configs per period
    
    for config in configs:
        result = tester.run_single_test(config)
        tester.results.append(result)
    
    if tester.results:
        returns = [r['total_return_pct'] for r in tester.results]
        profitable = len([r for r in tester.results if r['total_return_pct'] > 0])
        
        print(f"Testów: {len(tester.results)}")
        print(f"Zyskownych: {profitable}/{len(tester.results)} ({profitable/len(tester.results)*100:.0f}%)")
        print(f"Średni zwrot: {sum(returns)/len(returns):+.2f}%")
        print(f"Najlepszy: +{max(returns):.1f}%")
        print(f"Najgorszy: {min(returns):.1f}%")
        print(f"Mediana: {sorted(returns)[len(returns)//2]:+.1f}%")
        
        # Annualized
        days = len(period_prices)
        years = days / 365
        avg_return = sum(returns)/len(returns)
        if years > 0:
            annualized = ((1 + avg_return/100) ** (1/years) - 1) * 100
            print(f"Roczna stopa zwrotu: {annualized:+.1f}%")

print(f"\n{'='*60}")
print(f"✅ TESTY ZAKOŃCZONE")
