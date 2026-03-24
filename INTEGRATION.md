# INTEGRATION GUIDE - Enhanced Bot

## Co zostało przygotowane

### 1. `config_enhanced.json`
Podrasowana konfiguracja z:
- Większymi pozycjami (25% short, 20% long, 25% trend-follow)
- Dynamicznym sizingiem (1.5x w bull, 1.3x w bear, 0.5x w sideways)
- Ciaśniejszymi gridami (0.5% spacing vs 0.8%)
- Agresywnym shortem (breakdown entry na -1% w 6h)
- Pyramidingiem (dodawanie do pozycji w bull)
- Zwiększonym drawdown limitem (20% vs 15%)

### 2. `unified_bot_enhanced.py`
Główny bot z nowymi funkcjami:
- `get_position_size()` - dynamiczny sizing
- `should_enter_short()` - breakdown entry
- `should_add_pyramid()` - pyramiding w bull
- Enhanced trend detection (24h + 48h + 7d)

### 3. `test_comparison.py`
Skrypt porównujący stary vs nowy config na danych historycznych.

---

## Jak wdrożyć

### Krok 1: Utwórz branch
```bash
git checkout -b feature/enhanced-risk-reward
```

### Krok 2: Skopiuj pliki
```bash
# Skopiuj do repo
cp unified_bot_enhanced.py skills/passivbot-micro/scripts/
cp config_enhanced.json config/
cp test_comparison.py skills/passivbot-micro/scripts/
```

### Krok 3: Commit
```bash
git add .
git commit -m "feat: enhanced strategy with dynamic sizing and breakdown entries

- Target: 5% bear / 10% bull returns
- Dynamic position sizing based on trend strength
- Aggressive short with breakdown entry
- Pyramiding in strong uptrends
- Enhanced circuit breaker (20% max DD)"
```

### Krok 4: Testy
```bash
# Test porównawczy
cd skills/passivbot-micro/scripts
python3 test_comparison.py --days 730

# Paper trading
python3 unified_bot_enhanced.py --config config_enhanced.json --testnet
```

---

## Integracja pozostałych modułów

### `fear_greed_sentiment.py`
Dodać do `UnifiedBotEnhanced.__init__`:
```python
from fear_greed_sentiment import FearGreedSentiment

self.sentiment = FearGreedSentiment()
```

Dodać check w `run()` przed wejściem:
```python
if self.config.sentiment_enabled:
    sentiment = self.sentiment.get_index()
    if sentiment > 80:  # Extreme greed
        logger.info("🚫 Extreme greed - no new longs")
        allow_longs = False
    elif sentiment < 20:  # Extreme fear
        logger.info("🚫 Extreme fear - no new shorts")
        allow_shorts = False
```

### `scalping.py`
Opcjonalny moduł dla sideways:
```python
if self.current_trend == 'sideways' and self.config.scalping_enabled:
    from scalping import ScalpingStrategy
    self.scalping.execute(price, price_history)
```

### `risk_management.py` (TurbulenceIndex)
Już zintegrowane - włączyć przez config:
```json
"turbulence_reduce_size": true
```

### `ppo_engine.py`
**NIE zalecam integracji** - RL modele są prone do overfittingu. Lepiej polegać na ADX + EMA.

---

## Parametry do dostrojenia (tuning)

Jeśli wyniki nie są zadowalające, dostosuj:

### Za duży drawdown:
```json
"max_drawdown_pct": 0.15  // Zmniejsz z 20%
"short_position_pct": 0.20  // Zmniejsz z 25%
"trend_follow_position_pct": 0.20  // Zmniejsz z 25%
```

### Za mało trades:
```json
"short_bounce_threshold": 0.006  // Zmniejsz z 0.8%
"long_grid_spacing": 0.004  // Zmniejsz z 0.5%
"sideways_multiplier": 0.7  // Zwiększ z 0.5
```

### Za wolna reakcja:
```json
"trend_lookback": 18  // Zmniejsz z 24
"check_interval": 180  // Zmniejsz z 300 (5min -> 3min)
```

---

## Oczekiwane wyniki

| Scenariusz | Oryginał | Enhanced | Ryzyko |
|------------|----------|----------|--------|
| Bear market | 0% | +3-7% | Większy DD |
| Bull market | +7% | +10-18% | Więcej trades |
| Sideways | +2% | 0-2% | Mniej aktywny |
| Max DD | -8% | -15% | Circuit breaker |

---

## Co dalej?

1. **Testy paper** (2-4 tygodnie)
   - Uruchom na testnecie
   - Monitoruj drawdown
   - Sprawdź czy target 5%/10% jest realny

2. **A/B test** (jeśli masz kapitał)
   - 50% kapitału na oryginalnym bocie
   - 50% na enhanced
   - Porównaj po 3 miesiącach

3. **Live trading**
   - Zacznij od małej kwoty ($100)
   - Zwiększaj tylko jeśli działa
   - Nie inwestuj więcej niż możesz stracić

---

## Warnings

⚠️ **To jest agresywna strategia**:
- Większe pozycje = większe ryzyko
- Więcej trades = więcej fees
- Krótszy lookback = więcej false signals

⚠️ **Nie działa na każdym rynku**:
- Wymaga trendów (bear lub bull)
- W sideways może krwawić na fees
- Black swan events mogą zabić

⚠️ **Wymaga monitoringu**:
- Sprawdzaj codziennie czy bot działa
- Ustaw alerty na circuit breaker
- Miej plan wyjścia (stop loss globalny)

---

## Support

Jak coś nie działa:
1. Sprawdź logi w `~/.crypto_bot/logs/unified_bot_enhanced.log`
2. Uruchom z `--testnet` przed live
3. Porównaj wyniki z `test_comparison.py`

Powodzenia! 🚀
