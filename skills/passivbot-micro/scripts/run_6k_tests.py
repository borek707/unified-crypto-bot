#!/usr/bin/env python3
import json
import sys
import time
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/skills/passivbot-micro/scripts')

from massive_test_10k import MassiveTester

print(f"=== 6000 TESTÓW (70% CPU) ===")
print(f"Start: {time.strftime('%H:%M:%S')}")

with open("/tmp/hyperliquid_daily_big.json", "r") as f:
    prices = json.load(f)

tester = MassiveTester(prices)
configs = tester.generate_configs()[4000:10000]  # Only remaining 6000

print(f"Testing {len(configs)} configurations...\n")
start = time.time()

for i, config in enumerate(configs):
    result = tester.run_single_test(config)
    tester.results.append(result)
    
    if (i + 1) % 500 == 0:
        elapsed = time.time() - start
        rate = (i + 1) / elapsed
        remaining = (len(configs) - i - 1) / rate if rate > 0 else 0
        print(f"[{time.strftime('%H:%M:%S')}] {i+1}/{len(configs)} | {elapsed:.0f}s | {rate:.1f}/sec | ETA: {remaining/60:.1f}m")

elapsed = time.time() - start
print(f"\n{'='*60}")
print(f"GOTOWE! {len(tester.results)} testów w {elapsed/60:.1f} minut")

if tester.results:
    returns = [r["total_return_pct"] for r in tester.results]
    profitable = len([r for r in tester.results if r["total_return_pct"] > 0])
    print(f"Zyskownych: {profitable}/{len(tester.results)} ({profitable/len(tester.results)*100:.1f}%)")
    print(f"Średni zwrot: {sum(returns)/len(returns):+.2f}% | Best: {max(returns):.1f}%")
    
    sorted_results = sorted(tester.results, key=lambda x: x["total_return_pct"], reverse=True)
    print(f"\nTop 10:")
    for i, r in enumerate(sorted_results[:10], 1):
        print(f"{i:2d}. {r['variant']:12s} | {r['total_return_pct']:+6.1f}% | {r['trades']:3d}tr")

with open("/tmp/massive_test_6000_final.json", "w") as f:
    json.dump({"count": len(tester.results), "results": tester.results}, f)
print(f"\nZapisano do /tmp/massive_test_6000_final.json")
print(f"Koniec: {time.strftime('%H:%M:%S')}")
