#!/usr/bin/env python3
import json
import sys
import time
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/skills/passivbot-micro/scripts')

from massive_test_10k import MassiveTester

print(f"=== 10,000 TESTS (CPU capped) ===")
print(f"Start: {time.strftime('%H:%M:%S')}")

with open("/tmp/hyperliquid_daily_big.json", "r") as f:
    prices = json.load(f)

tester = MassiveTester(prices)
configs = tester.generate_configs()[:10000]

print(f"Testing {len(configs)} configs...\n")
start = time.time()

for i, config in enumerate(configs):
    result = tester.run_single_test(config)
    tester.results.append(result)
    
    if (i + 1) % 500 == 0:
        elapsed = time.time() - start
        print(f"[{time.strftime('%H:%M:%S')}] {i+1}/{len(configs)} | {elapsed:.0f}s elapsed")
        time.sleep(2)  # Sleep to reduce CPU

elapsed = time.time() - start
print(f"\nDone! {len(tester.results)} tests in {elapsed/60:.1f}m")

if tester.results:
    returns = [r["total_return_pct"] for r in tester.results]
    profitable = len([r for r in tester.results if r["total_return_pct"] > 0])
    print(f"Profitable: {profitable}/{len(tester.results)} ({profitable/len(tester.results)*100:.1f}%)")
    print(f"Avg: {sum(returns)/len(returns):.1f}% | Best: {max(returns):.1f}%")
    
    sorted_results = sorted(tester.results, key=lambda x: x["total_return_pct"], reverse=True)
    print(f"\nTop 10:")
    for i, r in enumerate(sorted_results[:10], 1):
        print(f"{i:2d}. {r['variant']:12s} | {r['total_return_pct']:+6.1f}% | {r['trades']:3d}tr")

with open("/tmp/massive_test_10000_capped.json", "w") as f:
    json.dump({"count": len(tester.results), "results": tester.results}, f)
print(f"Saved to /tmp/massive_test_10000_capped.json")
