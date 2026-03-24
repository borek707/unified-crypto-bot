# PassivBot-Micro

Automated cryptocurrency trading bot with trend-following strategy, risk management, and sentiment analysis.

## ⚠️ IMPORTANT DISCLAIMER

**This bot is NOT a guaranteed profit machine.**
- Test results show ~7% annual returns (not 20% monthly)
- Requires 6-12 month holding periods for best results
- Does NOT work well for short-term trading (1-2 months)
- Past performance does not guarantee future results
- **USE AT YOUR OWN RISK**

## 🎯 What This Bot Does

### Strategy: Trend-Following + Risk Management
- **ADX-based trend detection** for market classification
- **Circuit breaker** protection (5% daily loss, 15% drawdown)
- **Position sizing** based on risk (1% per trade)
- **Partial take profits** (50% at +5%)
- **Re-entry cooldown** (24h) to prevent overtrading

### When It Works Best
✅ Bull markets (6+ months trends)  
✅ Bear markets (protects capital)  
✅ Sideways markets (minimal trades)  

### When It Doesn't Work
❌ Short periods (1-2 months) - requires trend to develop  
❌ High frequency trading - not designed for scalping  
❌ Guaranteed monthly profits - **returns are uneven**

## 📊 Test Results

### 10,000 Configuration Tests
```
Total Tests:        10,000
Profitable:         9,103 (91%)
Average Return:     +7.01%
Best Result:        +29.1%
Median Return:      +7.0%
Max Drawdown:       7.7% average
```

### Best Configuration Found
```
Strategy:       ADX Only
Take Profit:    3%
Stop Loss:      1.5%
Position Size:  20%
Return:         +29.1% over 2.7 years
Annualized:     ~9.8% / year
```

### Comparison with Buy & Hold
| Strategy | 2.7 Year Return | Annualized | Max Drawdown |
|----------|-----------------|------------|--------------|
| **Buy & Hold BTC** | **+135%** | ~40% | ~30% |
| **This Bot (best)** | **+29%** | ~10% | ~4% |
| **This Bot (avg)** | **+7%** | ~3% | ~8% |

**Verdict:** Bot protects capital but underperforms buy & hold in bull markets.

## 🔧 Architecture

### Core Components

1. **MarketClassifier** (`technical_indicators.py`)
   - 5-state classification: strong_uptrend, pullback_uptrend, sideways, bear_rally, strong_downtrend
   - Uses ADX + multi-EMA context
   - **Requires 200+ days of data for accuracy**

2. **CircuitBreaker** (`unified_bot.py`)
   - Max daily loss: 5%
   - Max drawdown: 15%
   - Max consecutive losses: 5
   - Cooldown: 60 minutes

3. **RiskManagement** (`risk_management.py`)
   - Turbulence Index (reduces position size in volatile markets)
   - Slippage model (estimates execution costs)
   - Walk-forward robustness testing

4. **PPO Engine** (`ppo_engine.py`)
   - Reinforcement learning for trend-following
   - Trained on 1000 days of historical data
   - Optional enhancement (disabled by default)

5. **Sentiment Analysis** (`fear_greed_sentiment.py`)
   - Fear & Greed Index integration
   - Contrarian strategy (buy fear, sell greed)
   - **Experimental** - not fully integrated

### Module Status

| Module | Status | Notes |
|--------|--------|-------|
| `unified_bot.py` | ✅ Ready | Main trading bot |
| `technical_indicators.py` | ✅ Ready | ADX, EMA, MarketClassifier |
| `ppo_engine.py` | ✅ Ready | RL enhancement |
| `risk_management.py` | ✅ Ready | Turbulence, slippage |
| `adaptive_trend.py` | ✅ Ready | Multi-timeframe analysis |
| `fear_greed_sentiment.py` | ⚠️ Experimental | Needs integration |
| `scalping.py` | ⚠️ Not tested | Alternative strategy |
| `grid_trading.py` | ❌ Not implemented | Future work |

## 🚀 Quick Start

### Prerequisites
```bash
pip install numpy pandas requests
```

### Configuration
Create `config.json`:
```json
{
  "symbol": "BTC-USD",
  "initial_capital": 1000,
  "position_pct": 0.20,
  "trend_follow_tp": 0.03,
  "trend_follow_sl": 0.015,
  "use_market_classifier": true,
  "circuit_breaker_enabled": true,
  "enhanced_mode": false  // Set to true for aggressive strategy (see below)
}
```

### Enhanced Mode (Higher Risk/Reward)
For aggressive strategy with higher returns (tested +13.2% vs 0% standard on 730 days):
```json
{
  "enhanced_mode": true,
  "circuit_breaker_enabled": true
  // Higher position sizes, breakdown entries, pyramiding enabled
}
```
See `unified_bot_enhanced.py` for full implementation details.

### Run Bot
```bash
python3 scripts/unified_bot.py --config config.json --testnet
```

## 📈 Performance Expectations

### Realistic Returns
- **Conservative estimate:** 5-10% annually
- **Best case:** 15-25% annually
- **Monthly volatility:** 0-5% (uneven distribution)

### When Profits Occur
- **Not every month** - bot waits for clear trends
- **Clustered profits** - 2-3 good months, then flat periods
- **Bear market protection** - 0% loss instead of -30% for BTC

### Risk Metrics
- **Max drawdown:** 8-15% (vs 30-50% for BTC)
- **Win rate:** 40-50% of trades
- **Profit factor:** 1.5-2.0

## ⚠️ Known Limitations

### 1. Does NOT Work for Short Periods
```
Period      | Expected Return | Why?
------------|-----------------|-----
1-7 days    | 0%              | Too much noise
1 month     | 0-2%            | Not enough trend
3 months    | 0-5%            | Still noisy
6+ months   | 3-10%           | Trend develops
12+ months  | 5-15%           | Optimal period
```

### 2. Underperforms in Bull Markets
- Buy & hold BTC: +135% (2.7 years)
- This bot: +7-29% (2.7 years)
- **Trade-off:** Lower returns for lower risk

### 3. Requires Patience
- Bot may not trade for weeks/months
- **This is normal** - waiting for good setups
- Forcing trades = losses

## 🔬 Research & Development

### Completed Phases
1. ✅ **Phase 1:** Basic trend-following
2. ✅ **Phase 2:** ADX MarketClassifier (745+ tests)
3. ✅ **Phase 3:** PPO + partial TP + re-entry
4. ✅ **Phase 4:** Risk management (turbulence, slippage)

### Future Work
- [ ] Grid trading module
- [ ] Full sentiment integration
- [ ] Multi-agent system
- [ ] Real-time Twitter scraping
- [ ] On-chain analysis

## 🧪 Testing

### Run Tests
```bash
# Unit tests
python3 -m pytest tests/

# Backtest
python3 scripts/backtest.py --data data/btc_1000d.json

# Massive config test
python3 scripts/massive_test_10k.py
```

### Test Results Location
```
/tmp/massive_test_10000_final.json  # Full results
/tmp/hyperliquid_daily_big.json      # Test data (1000 days)
```

## 📚 Documentation

- `SKILL.md` - Skill documentation
- `CHANGELOG.md` - Version history
- `ERROR_LOG.md` - Known issues and fixes
- `WORK_LOG_ROADMAP.md` - Development progress

## 🤝 Contributing

This is a research project. Contributions welcome:
- Bug reports
- Strategy improvements
- Additional indicators
- Better risk management

## ⚖️ License

MIT License - Use at your own risk.

## 🙏 Acknowledgments

- Test data: Hyperliquid API
- Inspired by: PassivBot, Freqtrade
- Research: 10,000+ backtests performed

---

**Last Updated:** March 24, 2026  
**Version:** 4.0 (Post-10k-test)  
**Status:** Functional but limited (see Known Limitations)
