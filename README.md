# Unified Crypto Trading Bot

Automated cryptocurrency trading bot with adaptive strategy (LONG/SHORT/SIDEWAYS) for BTC on Hyperliquid exchange.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

## ⚠️ IMPORTANT DISCLAIMER (Read This First!)

**This bot is NOT a guaranteed profit machine.**
- **Test results show ~7% annual returns** (not 20% monthly)
- **Requires 6-12 month holding periods** for best results
- **Does NOT work well for short-term trading** (1-2 months)
- **Underperforms buy & hold BTC** in bull markets (+7-29% vs +135%)
- Past performance does not guarantee future results
- **USE AT YOUR OWN RISK**

### What We Learned from 10,000 Tests
```
Total Tests:        10,000 configurations
Profitable:         9,103 (91%)
Average Return:     +7.01% annually
Best Result:        +29.1% over 2.7 years
Median Return:      +7.0% annually
Max Drawdown:       7.7% average (vs 30% for BTC)
```

**Verdict:** Bot protects capital in bear markets but **does NOT outperform buy & hold in bull markets.**

## 🎯 Features

- **Adaptive strategy switching** based on multi-timeframe trend detection (3/6/7/10/14/30 days):
  - 📈 **UPTREND**: Long Grid Strategy + Trend Following
  - 📉 **DOWNTREND**: Short 3x Leverage (or stay in cash)
  - ➡️ **SIDEWAYS**: Grid + DCA Hybrid (or wait)

- **ADX-Based Market Classification**: 5-state regime detection (strong_uptrend, pullback_uptrend, sideways, bear_rally, strong_downtrend)
- **Circuit Breaker v3.0**: stops trading on excessive losses (5% daily loss / 15% max drawdown / 5 consecutive losses)
- **PPO Engine**: Reinforcement learning for trend-following (optional)
- **Risk Management**: Turbulence Index, Slippage Model, Walk-forward robustness
- **Technical Analysis module**: custom indicators (EMA, RSI, ADX, Bollinger Bands, MACD, Choppiness Index)
- **Backtest Engine**: historical simulation with PnL metrics
- **Multi-Bot**: 3 risk profiles running simultaneously (Low / Medium / High)
- **Paper Trading**: test without real funds

## 📊 Test Results (March 2026)

### 10,000 Configuration Tests
See [skills/passivbot-micro/README.md](skills/passivbot-micro/README.md) for detailed results.

| Metric | Value |
|--------|-------|
| Total Tests | 10,000 |
| Profitable | 9,103 (91%) |
| Average Return | +7.01% annually |
| Best Result | +29.1% over 2.7 years |
| Median Return | +7.0% annually |
| Max Drawdown | 7.7% average |
| Best Config | ADX Only, TP 3%, SL 1.5%, Size 20% |

### Comparison with Buy & Hold (2.7 years, 2022-2025)
| Strategy | Return | Annualized | Max Drawdown | Risk |
|----------|--------|------------|--------------|------|
| **Buy & Hold BTC** | **+135%** | ~40% | ~30% | High |
| **This Bot (best)** | **+29%** | ~10% | ~4% | Low |
| **This Bot (avg)** | **+7%** | ~3% | ~8% | Medium |

**Key Insight:** Bot protects capital but significantly underperforms buy & hold in bull markets.

### When Does It Work?
✅ **Bull markets** (6+ months): +10-25% annually  
✅ **Bear markets**: 0% loss (vs -50% for BTC)  
✅ **Sideways markets**: +2-5% (small profits from volatility)  

### When Does It NOT Work?
❌ **Short periods (1-2 months)**: Trend-following requires time to develop  
❌ **Guaranteed monthly profits**: Returns are uneven and clustered  
❌ **Outperforming buy & hold**: Not designed for maximum gains  
❌ **High frequency trading**: 1-4 trades per month, not per day  

## ✅ Latest Implementation (March 24, 2026)

### Phase 2 Complete: Better Market Logic
- **ADX MarketClassifier** with 5-state regime detection
- 745+ tests confirming ADX superiority over EMA
- Branch: `feature/adx-classifier`
- [skills/passivbot-micro/scripts/technical_indicators.py](skills/passivbot-micro/scripts/technical_indicators.py)

### Phase 3 Complete: Real Trend-Following
- **PPO Engine** for RL-based trend detection
- **Partial take profit** (50% at +5%)
- **Re-entry cooldown** (24h)
- **Dynamic trailing stop**
- [skills/passivbot-micro/scripts/ppo_engine.py](skills/passivbot-micro/scripts/ppo_engine.py)

### Phase 4 Complete: Risk Management
- **Turbulence Index** (reduces size in volatile markets)
- **Slippage Model** (estimates execution costs)
- **Walk-forward robustness** testing
- [skills/passivbot-micro/scripts/risk_management.py](skills/passivbot-micro/scripts/risk_management.py)

### New Modules
- **adaptive_trend.py**: Multi-timeframe analysis (3/6/7/10/14/30 days)
- **fear_greed_sentiment.py**: Fear & Greed Index integration (experimental)
- **flexible_bot.py**: Adaptive strategies for different data lengths
- **massive_test_10k.py**: Large-scale configuration testing

## 📁 Repository Structure

```
.
├── skills/passivbot-micro/
│   ├── README.md                          # Detailed bot documentation
│   ├── CHANGELOG.md                       # Development history
│   ├── SKILL.md
│   ├── WORK_LOG_ROADMAP.md                # Development progress
│   └── scripts/
│       ├── unified_bot.py                 # Main bot (Circuit Breaker v3.0)
│       ├── technical_indicators.py        # ADX/EMA MarketClassifier
│       ├── technical_analysis.py          # TA indicators module
│       ├── ppo_engine.py                  # RL trend-following
│       ├── risk_management.py             # Turbulence, slippage
│       ├── adaptive_trend.py              # Multi-timeframe analysis
│       ├── fear_greed_sentiment.py        # Sentiment analysis
│       ├── flexible_bot.py                # Adaptive strategies
│       ├── massive_test_10k.py            # Large-scale testing
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

Key dependencies: `ccxt`, `numpy`, `pandas`, `aiohttp`, `python-dotenv`

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

| Profile | SHORT Leverage | Daily Loss Limit | Trend Lookback | Grid Spacing | Max Positions |
|---------|---------------|-----------------|----------------|--------------|---------------|
| Low     | 2x            | 5%              | 48h            | 1.5%         | 3             |
| Medium  | 3x            | 10%             | 48h            | 1.0%         | 5             |
| High    | 5x            | 20%             | 24h            | 0.5%         | 10            |

## 🧪 Testing

### Run Massive Configuration Tests
```bash
cd skills/passivbot-micro/scripts
python3 massive_test_10k.py
```
Results saved to: `/tmp/massive_test_10000_final.json`

### Backtest
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

## ⚠️ Known Limitations

1. **Short Periods (1-2 months)**: Trend-following requires 6-12 months to work effectively
2. **Bull Market Underperformance**: Significantly underperforms buy & hold BTC
3. **Uneven Returns**: Profits come in clusters (2-3 good months, then flat periods)
4. **No Guaranteed Monthly Profits**: Some months will be 0% or small losses
5. **Requires Patience**: Bot may not trade for weeks/months waiting for good setups

See [skills/passivbot-micro/README.md](skills/passivbot-micro/README.md) for detailed analysis.

## 🙏 Credits

Exchange connectivity: [ccxt](https://github.com/ccxt/ccxt)

---

**Last Updated:** March 24, 2026  
**Version:** 4.0 (Post-10k-test)  
**Status:** Functional with documented limitations
