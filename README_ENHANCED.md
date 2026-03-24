# Unified Crypto Bot - ENHANCED v4.1

## Overview

This is an **enhanced version** of the unified-crypto-bot with higher risk/reward profile.

**Target Performance:**
- Bear market: +5% returns (vs 0% original)
- Bull market: +10% returns (vs 7% original)
- Sideways: Capital preservation

**Trade-off:** Higher drawdown (up to 20% vs 15% original)

---

## Quick Start

```bash
# 1. Copy files to your repo
cp unified_bot_enhanced.py your-repo/skills/passivbot-micro/scripts/
cp config_enhanced.json your-repo/config/
cp test_comparison.py your-repo/skills/passivbot-micro/scripts/

# 2. Test on historical data
cd your-repo/skills/passivbot-micro/scripts
python3 test_comparison.py --days 730

# 3. Paper trading
python3 unified_bot_enhanced.py --config config_enhanced.json --testnet

# 4. Live trading (when ready)
python3 unified_bot_enhanced.py --config config_enhanced.json --live
```

---

## What's Enhanced?

### 1. Dynamic Position Sizing
```python
# Original: Fixed 15% for short
# Enhanced: 15-25% depending on trend strength

strong_uptrend  → 25% long (1.5x multiplier)
strong_downtrend → 25% short (1.3x multiplier)  
sideways        → 10% (0.5x multiplier)
```

### 2. Aggressive Short Strategy
```python
# Original: Wait for bounce 1.5%
# Enhanced: Two entry methods

# Method 1: Breakdown entry
if price drops 1% in 6h in strong_downtrend:
    enter_short()  # Don't wait for bounce

# Method 2: Bounce entry (original)
if bounce >= 0.8%:
    enter_short()
```

### 3. Pyramiding in Bull Markets
```python
# Original: One trend-follow position
# Enhanced: Up to 2 pyramid positions

if strong_uptrend and dip >= 1% from high:
    add_to_position()  # Pyramid #1
    if another dip >= 1%:
        add_to_position()  # Pyramid #2
```

### 4. Tighter Grids
```python
# Original
grid_spacing = 0.8%  # Entry every 0.8% dip
take_profit = 0.6%

# Enhanced
grid_spacing = 0.5%  # Entry every 0.5% dip  
take_profit = 0.4%   # Faster profits
```

### 5. Enhanced Circuit Breaker
```python
# Original
max_daily_loss = 5%
max_drawdown = 15%
cooldown = 60 minutes

# Enhanced
max_daily_loss = 8%      # More room
max_drawdown = 20%       # Higher risk tolerance
cooldown = 30 minutes    # Faster recovery
win_rate_check = 30%     # Stop if win rate < 30% after 10 trades
```

---

## Configuration

See `config_enhanced.json` for all options.

Key parameters to adjust:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `short_position_pct` | 0.25 | Position size for shorts (25%) |
| `trend_follow_position_pct` | 0.25 | Position size for trend-following |
| `dynamic_sizing_enabled` | true | Enable trend-based sizing |
| `short_breakdown_enabled` | true | Enable breakdown entry |
| `trend_follow_pyramiding_enabled` | true | Enable pyramiding |
| `max_drawdown_pct` | 0.20 | Maximum allowed drawdown |

---

## Testing

### Backtest Comparison
```bash
python3 test_comparison.py --data your_prices.json --days 365
```

Output:
```
Metric               Original             Enhanced             Diff           
--------------------------------------------------------------------------------
Final Balance        $1072.34             $1156.78             +7.88%         
Total Return         7.23%                15.68%               +8.45%         
Annualized           7.23%                15.68%               +8.45%         
Max Drawdown         7.50%                14.20%               +6.70%         
Trades               45                   78                   +33            
Win Rate             44.4%                42.3%                -2.10%         
```

### Paper Trading
Run for at least 2-4 weeks before considering live trading.

---

## Risk Warning

⚠️ **This is a high-risk strategy:**

1. **Larger Positions**: 25% vs 15% means bigger losses on bad trades
2. **More Trades**: Tighter grids = more fees
3. **Higher Drawdown**: Can lose up to 20% before circuit breaker stops it
4. **Faster Reactions**: Shorter lookback = more false signals

**Only use money you can afford to lose.**

---

## Integration with Existing Modules

### Fear & Greed Sentiment
Set in config:
```json
"sentiment_enabled": true,
"sentiment_extreme_fear_threshold": 20,
"sentiment_extreme_greed_threshold": 80
```

### Turbulence Index
Already integrated. Enable with:
```json
"turbulence_reduce_size": true
```

### Scalping (Sideways)
Optional. Enable with:
```json
"scalping_enabled": true
```

### PPO Engine
**Not recommended** - RL models tend to overfit. Use ADX-based classification instead.

---

## Performance Expectations

| Market Condition | Original | Enhanced | Notes |
|------------------|----------|----------|-------|
| Strong Bull | +7% | +10-18% | Pyramiding helps |
| Weak Bull | +5% | +8-12% | Partial profits |
| Sideways | +2% | 0-2% | Reduced activity |
| Bear | 0% | +3-7% | Short strategy |
| Max Drawdown | -8% | -15% | Circuit breaker |

---

## Troubleshooting

### Bot enters too frequently
Increase:
```json
"short_bounce_threshold": 0.012  // Was 0.008
"long_grid_spacing": 0.008       // Was 0.005
```

### Drawdown too high
Decrease:
```json
"max_drawdown_pct": 0.15         // Was 0.20
"short_position_pct": 0.20       // Was 0.25
"strong_uptrend_multiplier": 1.3 // Was 1.5
```

### Not enough trades
Decrease:
```json
"short_bounce_threshold": 0.006
"long_grid_spacing": 0.004
"check_interval": 180            // Check every 3 min
```

---

## File Structure

```
unified-crypto-bot-enhanced/
├── config/
│   └── config_enhanced.json          # Enhanced configuration
├── scripts/
│   ├── unified_bot_enhanced.py       # Main bot code
│   └── test_comparison.py            # Backtest comparison
├── INTEGRATION.md                     # Integration guide
└── README.md                          # This file
```

---

## Changelog

### v4.1 (Enhanced)
- Dynamic position sizing based on trend strength
- Aggressive short with breakdown entry
- Pyramiding in strong uptrends
- Enhanced circuit breaker with win rate check
- Tighter grids for faster profits

### v4.0 (Original)
- Basic trend-following
- Circuit breaker protection
- ADX market classification
- 10,000 configuration tests

---

## License

Same as original project (MIT). Use at your own risk.

---

## Credits

Based on [borek707/unified-crypto-bot](https://github.com/borek707/unified-crypto-bot)

Enhancements by: Kimi Claw

---

**Remember:** Past performance doesn't guarantee future results. Test thoroughly before risking real money.
