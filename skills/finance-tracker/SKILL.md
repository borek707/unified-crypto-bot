---
name: finance-tracker
description: Track cryptocurrency, stock prices, and trade gold (XAU/USD) using automated strategies. Use for crypto (CoinGecko), stocks (Yahoo Finance), gold trading bot with First Candle strategy, OHLC analysis, and paper trading with performance tracking.
---

# Finance Tracker

Complete trading and market analysis toolkit.

## Features

- **Cryptocurrency tracking**: 10,000+ coins via CoinGecko
- **Stock/Indices tracking**: Yahoo Finance data
- **Gold Trading Bot (XAU/USD)**: Automated "First Candle" strategy
- **Paper trading**: Track performance without real money
- **Performance analytics**: Win rate, P&L, profit factor

## Quick Start

### 1. Crypto & Stock Prices

```bash
# Bitcoin price
python3 scripts/fetch_crypto.py BTC

# Apple stock
python3 scripts/fetch_stock.py AAPL
```

### 2. Gold Trading Bot (🤖 NEW!)

**Generate trading signal:**
```bash
python3 scripts/gold_trading_bot.py
```

**View performance stats:**
```bash
python3 scripts/gold_trading_bot.py --stats 7    # Last 7 days
python3 scripts/gold_trading_bot.py --stats 30   # Last 30 days
```

**View open positions:**
```bash
python3 scripts/gold_trading_bot.py --open
```

**Generate daily report:**
```bash
python3 scripts/gold_trading_bot.py --report
```

### 3. Strategy Backtesting

```bash
python3 scripts/fetch_ohlc.py --analyze ^IXIC 20
```

## Dashboard - Jak Sprawdzać Wyniki

Masz 3 opcje podglądu dashboardu:

### Opcja 1: Terminal (najszybsza)
```bash
python3 skills/finance-tracker/scripts/dashboard_slack.py
```
Pokazuje wyniki w formacie tekstowym.

### Opcja 2: JSON (do przetwarzania)
```bash
python3 skills/finance-tracker/scripts/dashboard_slack.py --json
```

### Opcja 3: Web Dashboard
```bash
python3 skills/finance-tracker/scripts/dashboard.py
# Otwórz: http://localhost:8080
```

### Opcja 4: Automatyczne raporty na Slacku
Bot wysyła raporty automatycznie:
- **Sygnały tradingowe**: 8:00, 13:00, 16:00 GMT
- **Podsumowanie dnia**: 9:00 GMT

## Gold Trading Bot Strategy

### "First Candle" Strategy

Based on the premise that the first 15-minute candle after session open contains strong directional momentum.

**Rules:**
1. Trade only during London/NY sessions (08:00-21:00 GMT)
2. Analyze first 15min candle after session starts
3. **BUY**: Large green candle (body > 1.1×ATR)
4. **SELL**: Large red candle (body > 1.1×ATR)
5. **HOLD**: Small/medium candle (wait for confirmation)

**Risk Management:**
- Stop Loss: Below candle low (long) / above candle high (short)
- Take Profit: 1:1.5 risk-reward ratio
- Position sizing: Fixed fractional (1-2% risk per trade)

**Example Output:**
```json
{
  "signal": "BUY",
  "confidence": 0.75,
  "entry_price": 2925.50,
  "sl_price": 2915.20,
  "tp_price": 2940.65,
  "body_class": "large",
  "reason": "Large bullish candle (body=12.5 > 9.8 ATR)"
}
```

### Trading Sessions

| Session | Hours (GMT) | Priority |
|:---|:---|:---|
| London-NY Overlap | 13:00-16:00 | ⭐⭐⭐ Highest |
| London | 08:00-13:00 | ⭐⭐ High |
| New York | 16:00-21:00 | ⭐⭐ High |
| Asian | 00:00-08:00 | ❌ No trading |

### Database Schema

All trades stored in SQLite (`memory/trading.db`):
- `trades` - Entry/exit data, P&L, candle data
- `performance` - Daily/weekly statistics
- `strategy_params` - Adaptive parameters based on performance

## Common Symbols

### Gold/Silver
- XAU/USD (Gold) - via GC=F futures with price conversion to spot
- XAG/USD (Silver) - via SI=F futures

### Indices
- ^IXIC (NASDAQ)
- ^GSPC (S&P 500)
- ^DJI (Dow Jones)

### Crypto
- BTC, ETH, SOL, ADA, XRP

### Stocks
- AAPL, MSFT, GOOGL, TSLA, AMZN

## Paper Trading Workflow

1. Bot generates signals based on live market data
2. Signals saved to database as "paper trades"
3. Next day: bot checks if trade would have hit SL or TP
4. Performance calculated and tracked
5. Strategy adapts based on win rate

## API Limits

- CoinGecko: 10-50 calls/min (free tier)
- Yahoo Finance: No key, occasional rate limits
- Recommended: Add delays between requests

## Learning & Adaptation

The bot tracks:
- Win rate (7-day and 30-day rolling)
- Average win vs average loss
- Profit factor (gross wins / gross losses)
- Max drawdown
- Best/worst trading sessions

Use this data to optimize:
- Body size thresholds
- SL/TP multipliers
- Session filters
- Position sizing
