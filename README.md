# Unified Crypto Trading Bot

Automated trading bot with adaptive strategy (LONG/SHORT/SIDEWAYS) for BTC on Hyperliquid exchange.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

## 🎯 Features

- **Adaptive strategy switching** based on 48h trend detection:
  - 📈 **UPTREND**: Long Grid Strategy
  - 📉 **DOWNTREND**: Short 3x Leverage
  - ➡️ **SIDEWAYS**: Grid + DCA Hybrid

- **Circuit Breaker v3.0**: stops trading on excessive losses (daily loss limit / max drawdown / consecutive losses)
- **Technical Analysis module**: custom indicators (EMA, RSI, ADX, Bollinger Bands, Choppiness Index, VWAP, SuperTrend)
- **Backtest Engine**: historical simulation with PnL metrics and equity curve
- **Multi-Bot**: 3 risk profiles running simultaneously (Low / Medium / High)
- **Paper Trading**: test without real funds

## ✅ What Has Been Implemented (2026-03-23)

Current implementation status for anyone cloning this repository:

1. Unified live bot upgraded to a 5-state market regime flow in [skills/passivbot-micro/scripts/unified_bot.py](skills/passivbot-micro/scripts/unified_bot.py).
2. Trend-following layer added (separate position type with hard stop and trailing stop) in [skills/passivbot-micro/scripts/unified_bot.py](skills/passivbot-micro/scripts/unified_bot.py).
3. New unified backtest engine added in [scripts/backtest_unified.py](scripts/backtest_unified.py).
4. Backtest aligned closer to live logic (position types, exits, CB behavior, per-strategy and per-regime reporting) in [scripts/backtest_unified.py](scripts/backtest_unified.py).
5. Research roadmap added and extended (phase 2 classifier context, PPO track, A2C track, ensemble routing guidance) in [docs/BOT_ROADMAP.md](docs/BOT_ROADMAP.md).
6. Latest generated backtest snapshots are stored in:
  - [memory/backtest_results/unified_bot_backtest.json](memory/backtest_results/unified_bot_backtest.json)
  - [memory/backtest_results/unified_bot_comparison.json](memory/backtest_results/unified_bot_comparison.json)

For current priorities and next phases, use [docs/BOT_ROADMAP.md](docs/BOT_ROADMAP.md) as the source of truth.

## 📁 Repository Structure

```
.
├── skills/passivbot-micro/
│   ├── CHANGELOG.md                       # Development history
│   ├── SKILL.md
│   └── scripts/
│       ├── unified_bot.py                 # Main bot (Circuit Breaker v3.0)
│       ├── technical_analysis.py          # TA indicators module
│       ├── enhanced_backtest.py           # Backtest engine
│       └── enhanced_unified_bot.py        # Experimental variant
├── config_low_risk.json                   # 2x leverage, 5% daily limit
├── config_medium_risk.json                # 3x leverage, 10% daily limit
├── config_high_risk.json                  # 5x leverage, 20% daily limit
├── config_paper.json                      # Paper trading ($12 capital)
├── config_best.json                       # Optimised parameters
├── bot_monitor.py                         # Single bot monitor
├── multi_bot_monitor.py                   # Multi-bot monitor
├── run_3bots_paper.py                     # Launch 3 paper bots
├── rate_limiter.py                        # API rate limiter
├── cron_runner_v2.py                      # Price feed cron job
├── daily_report.py                        # Daily PnL report
├── scripts/
│   ├── start_bots.sh
│   ├── stop_bots.sh
│   ├── restart_bots.sh
│   └── status.sh
└── docs/
    ├── ARCHITECTURE.md
    ├── DEPLOYMENT.md
    └── OPERATIONS.md
```

## 🚀 Quick Start

### Prerequisites

```bash
pip install -r requirements.txt
```

Key dependencies: `ccxt`, `numpy`, `aiohttp`, `python-dotenv`

### Configuration

```bash
cp .env.example .env
# Set HYPERLIQUID_API_KEY and HYPERLIQUID_SECRET
```

### Paper Trading (testnet)

```bash
# Single bot, paper mode
python3 skills/passivbot-micro/scripts/unified_bot.py --testnet

# With specific risk profile
python3 skills/passivbot-micro/scripts/unified_bot.py --config config_low_risk.json --testnet

# 3 bots simultaneously
python3 run_3bots_paper.py
```

### Live Trading

```bash
# Set testnet: false in config and ensure API keys are set
python3 skills/passivbot-micro/scripts/unified_bot.py --config config_medium_risk.json --live
```

### Bot Management

```bash
./scripts/start_bots.sh    # Start
./scripts/status.sh        # Status
./scripts/stop_bots.sh     # Stop
./scripts/restart_bots.sh  # Restart
```

## 📊 Risk Profiles

| Profile | SHORT Leverage | Daily Loss Limit | Trend Lookback | Grid Spacing |
|---------|---------------|-----------------|----------------|--------------|
| Low     | 2x            | 5%              | 48h            | 1.5%         |
| Medium  | 3x            | 10%             | 48h            | 1.0%         |
| High    | 5x            | 20%             | 24h            | 0.5%         |

## 🧪 Backtest

```bash
python3 skills/passivbot-micro/scripts/enhanced_backtest.py
# unified strategy backtest (v1/v2/v3 compare)
python3 scripts/backtest_unified.py --days 365 --compare
```

## 🏗️ Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed design.

## 🚢 Deployment

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for VPS and Docker setup.

## 📋 Operations

Daily procedures and incident response in [docs/OPERATIONS.md](docs/OPERATIONS.md).

## 🙏 Credits

Exchange connectivity: [ccxt](https://github.com/ccxt/ccxt)