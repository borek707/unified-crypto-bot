# PassivBot Pro - Setup

## Prerequisites

```bash
# Python 3.10+
python3 --version

# pip
pip --version
```

## Installation

```bash
# 1. Navigate to skill directory
cd ~/.openclaw/workspace/skills/passivbot-pro

# 2. Install dependencies
pip install -r scripts/requirements.txt

# 3. Verify installation
python3 -c "from scripts.config.settings import GridConfig; print('✅ OK')"
```

## Configuration

```bash
# Set API credentials (for live trading)
export EXCHANGE_API_KEY="your_api_key"
export EXCHANGE_API_SECRET="your_api_secret"

# Optional: Set exchange (default: hyperliquid)
export EXCHANGE="binance"  # or bybit, hyperliquid
```

## First Run

```bash
# 1. Download data
python3 -m passivbot_pro.scripts.main --mode download --symbol BTC/USDC:USDC --days 30

# 2. Run backtest
python3 -m passivbot_pro.scripts.main --mode backtest --symbol BTC/USDC:USDC

# 3. Check results
ls ~/.openclaw/workspace/memory/passivbot_results/
```

## Verification Checklist

- [ ] Dependencies installed without errors
- [ ] Can import GridConfig, RiskConfig
- [ ] Can import VectorizedBacktester
- [ ] Data download works
- [ ] Backtest runs and produces results

## Troubleshooting

**ImportError: No module named 'numba'**
```bash
pip install numba
```

**ImportError: attempted relative import**
```bash
# Always run from skill root with python3 -m
python3 -m passivbot_pro.scripts.main [args]
```

**Data not found**
```bash
# Run download first
python3 -m passivbot_pro.scripts.main --mode download --symbol BTC/USDC:USDC
```
