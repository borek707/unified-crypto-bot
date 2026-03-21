#!/bin/bash
# ============================================================
# PASSIVBOT BENCHMARK & OPTIMAL CONFIG FINDER
# For: 4 vCPU + 24GB RAM
# ============================================================

echo "============================================================"
echo "MICRO-PASSIVBOT HARDWARE BENCHMARK"
echo "============================================================"
echo ""
echo "Hardware: $(nproc) vCPU, $(free -h | grep Mem | awk '{print $2}') RAM"
echo "Date: $(date)"
echo ""

# Change to skill directory
cd /home/ubuntu/.openclaw/workspace/skills/passivbot-micro/scripts

# Create results directory
mkdir -p /home/ubuntu/.openclaw/workspace/memory/passivbot_results

# ============================================================
# BENCHMARK 1: Single Backtest Speed
# ============================================================
echo "BENCHMARK 1: Single Backtest Speed"
echo "-----------------------------------"

for candles in 10000 50000 100000; do
    echo -n "  $candles candles: "
    start=$(date +%s.%N)
    python3 backtest.py --generate --candles $candles --capital 100 > /dev/null 2>&1
    end=$(date +%s.%N)
    runtime=$(python3 -c "print(f'{$end - $start:.3f}')")
    speed=$(python3 -c "print(f'{$candles / ($end - $start):.0f}')")
    echo "${runtime}s (${speed} candles/s)"
done

echo ""

# ============================================================
# BENCHMARK 2: Optimization Speed
# ============================================================
echo "BENCHMARK 2: Optimization Speed (4 workers)"
echo "--------------------------------------------"

# Quick optimization test
echo -n "  Quick (pop=20, gen=5, total=100): "
start=$(date +%s.%N)
python3 optimize.py --candles 10000 --population 20 --generations 5 --workers 4 --seed 42 > /dev/null 2>&1
end=$(date +%s.%N)
runtime=$(python3 -c "print(f'{$end - $start:.1f}')")
echo "${runtime}s"

echo ""

# ============================================================
# BENCHMARK 3: Memory Estimation
# ============================================================
echo "BENCHMARK 3: Memory Estimation"
echo "-------------------------------"

for candles in 10000 50000 100000 250000; do
    # Each candle: ~48 bytes (OHLCV as float64)
    bytes=$((candles * 48))
    mb=$(python3 -c "print(f'{$bytes / 1048576:.1f}')")
    # With numpy arrays, ATR, volatility, equity curve
    total_mb=$(python3 -c "print(f'{$bytes / 1048576 * 5:.1f}')")
    echo "  $candles candles: ~${total_mb}MB RAM"
done

echo ""

# ============================================================
# RECOMMENDED CONFIGURATIONS
# ============================================================
echo "============================================================"
echo "RECOMMENDED CONFIGURATIONS FOR YOUR HARDWARE"
echo "============================================================"
echo ""
echo "┌─────────────────────────────────────────────────────────┐"
echo "│ QUICK TEST (< 1 min)                                    │"
echo "│   python3 backtest.py --generate --candles 50000        │"
echo "│   python3 optimize.py --quick                           │"
echo "└─────────────────────────────────────────────────────────┘"
echo ""
echo "┌─────────────────────────────────────────────────────────┐"
echo "│ STANDARD (2-3 min)                                      │"
echo "│   python3 backtest.py --generate --candles 100000       │"
echo "│   python3 optimize.py --candles 50000 \                 │"
echo "│     --population 80 --generations 30 --workers 4        │"
echo "└─────────────────────────────────────────────────────────┘"
echo ""
echo "┌─────────────────────────────────────────────────────────┐"
echo "│ FULL OPTIMIZATION (10-15 min)                           │"
echo "│   python3 backtest.py --generate --candles 500000       │"
echo "│   python3 optimize.py --candles 100000 \                │"
echo "│     --population 100 --generations 50 --workers 4       │"
echo "└─────────────────────────────────────────────────────────┘"
echo ""
echo "============================================================"
echo "BENCHMARK COMPLETE"
echo "============================================================"
