---
name: passivbot-pro
description: Execute grid trading strategies with genetic optimization, vectorized backtesting, and live trading execution for cryptocurrency markets.
metadata:
  openclaw:
    requires:
      bins: [python3, pip]
      python_packages: [numba, pandas, numpy, pydantic, loguru, ccxt, pyarrow, deap, optuna]
    os: [linux, darwin]
---

# PassivBot Pro

Grid trading bot with genetic algorithm optimization and vectorized backtesting.

## When to Use

User wants to:
- Run backtests on trading strategies
- Optimize parameters using genetic algorithms
- Execute live grid trading on crypto exchanges
- Analyze performance metrics (Sharpe, drawdown, profit factor)

## Data Storage

Results and data stored in:
- `~/.openclaw/workspace/memory/passivbot_data/` - Historical price data
- `~/.openclaw/workspace/memory/passivbot_results/` - Backtest results and logs

Always ask user before creating new files.

## External Endpoints

| Endpoint | Purpose | Data Sent |
|----------|---------|-----------|
| Binance API | Price data, orderbook | Trading pair symbols |
| Bybit API | Alternative price source | Trading pair symbols |
| Hyperliquid API | Live trading execution | Orders (when live trading enabled) |

## Quick Commands

```bash
# Download historical data
python3 -m passivbot_pro.scripts.main --mode download --symbol BTC/USDC:USDC

# Run backtest
python3 -m passivbot_pro.scripts.main --mode backtest --symbol BTC/USDC:USDC --days 30

# Optimize parameters (takes 1-2 hours)
python3 -m passivbot_pro.scripts.main --mode optimize --symbol BTC/USDC:USDC --days 60

# Live trading (PAPER MODE by default)
python3 -m passivbot_pro.scripts.main --mode live --testnet
```

## Core Rules

1. **ALWAYS use testnet first** - Never go live without testing
2. **Check API keys** - Ensure EXCHANGE_API_KEY and EXCHANGE_API_SECRET are set
3. **Verify data exists** - Run download before backtest/optimize
4. **Monitor drawdown** - Stop if max_drawdown exceeds 20%
5. **Use unstucking** - Critical for preventing liquidation

## Configuration

Edit `config/settings.py` or use environment variables:

```python
RiskConfig(
    initial_capital=100.0,
    min_position_size=2.0,
    max_position_size=10.0,
    stop_loss_balance=80.0,
    max_leverage=5.0,
    max_drawdown_pct=0.20
)
```

## Security

- API keys stored in environment variables only
- Never commit credentials to git
- Testnet mode enabled by default
- Unstucking mechanism prevents margin calls

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No module named 'numba'" | Run: `pip install -r requirements.txt` |
| "Data file not found" | Run download mode first |
| "API credentials not found" | Set EXCHANGE_API_KEY and EXCHANGE_API_SECRET |
| Import errors | Ensure running from skill root with `python3 -m` |

## References

- `references/backtest_guide.md` - Detailed backtesting documentation
- `references/optimization_guide.md` - GA optimization parameters
- `references/live_trading.md` - Live trading setup and safety
