---
name: passivbot-micro
description: Run autonomous crypto trading bots optimized for $100 accounts with vectorized backtesting, genetic optimization, and risk management.
---

# PassivBot Micro

Autonomous crypto trading bot optimized for $100 accounts with micro-trades ($2-$10).

## Quick Commands

### Run Backtest
```
Run backtest with default parameters
```

### Optimize Parameters
```
Optimize grid parameters using genetic algorithm
```

### Calculate Risk
```
Calculate liquidation price for entry 50000 leverage 5 side long
```

## Scripts

### backtest.py
Run vectorized backtests:
```bash
python scripts/backtest.py --generate --candles 10000
python scripts/backtest.py --symbol BTC/USDC --days 30
```

### optimize.py
Optimize parameters with GA:
```bash
python scripts/optimize.py --quick
python scripts/optimize.py --candles 50000 --generations 30
```

### risk_calc.py
Calculate risk metrics:
```bash
python scripts/risk_calc.py liquidation --entry 50000 --leverage 5 --side long
python scripts/risk_calc.py position --balance 100 --risk 0.02 --entry 50000 --stop 48000
```

### setup.py
Verify installation:
```bash
python scripts/setup.py verify
```

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| grid_spacing_pct | 0.5% | Distance between grid orders |
| entry_multiplier | 1.3x | Position size on re-entry |
| markup_pct | 0.4% | Take profit distance |
| initial_capital | $100 | Starting balance |
| min_position_size | $2 | Minimum trade size |
| max_position_size | $10 | Maximum trade size |
| max_leverage | 5x | Maximum leverage |

## File Structure

```
passivbot-micro/
├── SKILL.md                 # This file
├── __init__.py              # Package initialization
├── scripts/
│   ├── backtest.py          # Vectorized backtesting
│   ├── optimize.py          # Genetic algorithm optimizer
│   ├── risk_calc.py         # Risk calculations
│   └── setup.py             # Setup verification
├── templates/
│   └── config_template.json # Configuration template
└── resources/
    ├── requirements.txt     # Python dependencies
    └── exchanges.md         # Exchange setup guide
```

## Examples

### Example 1: Quick Backtest
```python
from skills.passivbot_micro.scripts.backtest import VectorizedBacktester, GridConfig, generate_sample_data

df = generate_sample_data(n_candles=10000, seed=42)
config = GridConfig(grid_spacing_pct=0.005, entry_multiplier=1.3)
backtester = VectorizedBacktester(grid_config=config)
result = backtester.run(df)

print(f"Return: {result.total_return_pct:.2%}")
print(f"Drawdown: {result.max_drawdown_pct:.2%}")
print(f"Trades: {result.total_trades}")
```

### Example 2: Risk Calculation
```python
from skills.passivbot_micro.scripts.risk_calc import RiskCalculator, OrderSide

liq_price = RiskCalculator.calculate_liquidation_price(
    entry_price=50000,
    side=OrderSide.LONG,
    leverage=5
)
print(f"Liquidation: ${liq_price:.2f}")
```

## Safety Warnings

⚠️ **Real-money trading. Past performance ≠ future results.**

- Test on testnet first
- Never risk more than you can afford to lose
- Monitor the bot actively
- Unstucking mechanism may realize losses
