# Enhanced Unified Bot - CHANGELOG

## Etap 1: Circuit Breaker + Entry Filters + Risk Sizing ✅

### Dodano nowe komponenty:

#### 1. Circuit Breaker (`CircuitBreaker`)
Zatrzymuje trading przy przekroczeniu limitów:
- **Daily Loss**: 5% max dziennej straty
- **Max Drawdown**: 15% max spadku od szczytu
- **Consecutive Losses**: 5 strat pod rząd = STOP
- **Cooldown**: 60 minut przerwy po aktywacji

#### 2. Entry Filters (`EntryFilters`)
8 filtrów wejścia dla każdej pozycji:
1. Circuit breaker check
2. Max positions limit (4)
3. Exposure limit (50% kapitału)
4. Trend filter (ADX > 40 = skip)
5. Volatility filter (0.5% - 5%)
6. Volume filter (min 70% avg)
7. RSI filter (max 70)
8. Price position filter (max 3% od support)

#### 3. Risk-Based Position Sizing (`RiskBasedSizing`)
Oblicza wielkość pozycji na podstawie:
- Risk per trade: 1% kapitału
- Stop Loss distance
- Reduction after 3+ consecutive losses (-50%)
- Max position: 10% kapitału

### Pliki:
- `enhanced_unified_bot.py` - nowy bot z wszystkimi funkcjami
- `unified_bot.py` - oryginalny (zachowany dla backup)

### Config (`EnhancedConfig`):
Nowe parametry konfiguracyjne:
```python
# Circuit Breaker
circuit_breaker_enabled: bool = True
max_daily_loss_pct: float = 0.05
max_drawdown_pct: float = 0.15
max_consecutive_losses: int = 5
circuit_cooldown_minutes: int = 60

# Risk
risk_per_trade_pct: float = 0.01
max_total_exposure_pct: float = 0.50

# Filters
adx_threshold: float = 25.0
adx_strong_trend: float = 40.0
min_volatility_pct: float = 0.005
max_volatility_pct: float = 0.05
min_volume_ratio: float = 0.7
rsi_overbought: float = 70.0
max_distance_from_support: float = 0.03
```

### Testy:
```bash
cd scripts
python3 -c "from enhanced_unified_bot import *; print('✅ OK')"
```

### Następny krok (Etap 2):
- [ ] Moduł Technical Analysis (fix literówki)
- [ ] Choppiness Index, Keltner Channels, Squeeze
- [ ] Backtest engine

---
*Data: 2026-03-21*
