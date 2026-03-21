# 🤖 SYSTEM INVENTORY - Pełne Przegląd
*Wygenerowano: 2026-03-11 14:37 UTC*

---

## 🔄 CRON JOBS (Aktywne)

### 1. Finance Tracker Cron
```bash
*/15 * * * * /usr/bin/python3 /home/ubuntu/.openclaw/workspace/cron_runner.py
```
**Status:** ✅ AKTYWNY  
**Co robi:**
- Pobiera ceny BTC/ETH z CoinGecko (co 15 min)
- Pobiera ceny NASDAQ/AAPL z Yahoo Finance (co godzinę)
- Uruchamia Gold Trading Bot (w sesjach 8-21 UTC)
- Loguje do: `~/.openclaw/workspace/memory/logs/`

**Rate limiting:**
- CoinGecko: max 25/min (2s delay)
- Yahoo: max 80/h (5s delay)
- Gold: max 4/min (3s delay)

---

## 🤖 BOTY (Uruchomione Teraz)

### Aktywne Procesy:
| Bot | PID | Status | Kapitał | Ryzyko | Logi |
|-----|-----|--------|---------|--------|------|
| unified_bot LOW | 49445 | 🟢 Running | $100 paper | 2x lewar | ✅ live.log |
| unified_bot MEDIUM | 49447 | 🟢 Running | $100 paper | 3x lewar | ✅ live.log |
| unified_bot HIGH | 49449 | 🟢 Running | $100 paper | 5x lewar | ✅ live.log |

**Strategia:** LONG/SHORT/GRID z wykrywaniem trendu (48h / 5%)
**API:** Hyperliquid (Twoje klucze)
**Tryb:** Paper trading (symulacja, bez prawdziwych pieniędzy)

---

## 📁 SKRYPTY (Dostępne)

### 🔧 Bot Management
| Skrypt | Opis | Używany |
|--------|------|---------|
| `start_bots_with_api.sh` | Start 3 botów z kluczami API | ✅ TAK |
| `check_bots.sh` | Sprawdza status wszystkich botów | ✅ TAK |
| `status_3bots.sh` | Status + logi | ✅ TAK |
| `start_live_bots.sh` | Start bez API (nie działa) | ❌ NIE |
| `run_paper_trading.sh` | Stary paper trading | ❌ NIE |
| `run_unified_paper.sh` | Stary unified bot | ❌ NIE |

### 📊 Monitoring
| Skrypt | Opis | Używany |
|--------|------|---------|
| `bot_monitor.py` | Dashboard terminalowy | ✅ TAK |
| `multi_bot_monitor.py` | Dashboard 3 botów | ✅ TAK |
| `generate_dashboard.py` | Generuje HTML | ✅ TAK |
| `monitor_live.sh` | Live monitoring co 30s | ❌ NIE |
| `bot_help.sh` | Help menu | ✅ TAK |

### 🧪 Backtesting
| Skrypt | Opis | Używany |
|--------|------|---------|
| `run_3bots_paper.py` | Symulacja historyczna | ✅ TAK (raz) |
| `backtest_2years.py` | Backtest 2 lata | ✅ TAK (raz) |
| `backtest_2years_full.py` | Porównanie strategii | ✅ TAK (raz) |
| `view_backtest_results.py` | Przegląd wyników | ✅ TAK |
| `run_strategy_comparison.py` | Porównanie 4 strategii | ✅ TAK (raz) |

### ⚙️ Config & Utils
| Skrypt | Opis | Używany |
|--------|------|---------|
| `setup_hyperliquid.sh` | Setup API keys | ✅ TAK (raz) |
| `run_bot_12usd.sh` | Passivbot-pro runner | ❌ NIE (nieużywany) |
| `run_passivbot.sh` | Passivbot-pro | ❌ NIE |
| `test_api_now.py` | Test API | ✅ TAK (diagnostyka) |

---

## 📂 STRUKTURA PLIKÓW

```
~/.openclaw/workspace/
├── Konfiguracje bota:
│   ├── config_low_risk.json      ($100, 2x lewar)
│   ├── config_medium_risk.json   ($100, 3x lewar)
│   ├── config_high_risk.json     ($100, 5x lewar)
│   └── config_paper.json         (archiwum)
│
├── Bazy danych:
│   ├── memory/bot_monitor.db              (śledzenie pozycji)
│   ├── memory/paper_trading_results.json  (wyniki symulacji)
│   └── memory/trading.db                  (stare dane)
│
├── Logi:
│   ├── memory/passivbot_logs/low/live.log      (bot 1)
│   ├── memory/passivbot_logs/medium/live.log   (bot 2)
│   ├── memory/passivbot_logs/high/live.log     (bot 3)
│   ├── memory/logs/api_calls.log               (cron API calls)
│   └── memory/logs/cron.log                    (cron output)
│
├── Wyniki backtestów:
│   └── memory/backtest_results/
│       ├── detailed_results.json
│       ├── summary.csv
│       └── README.md
│
└── HTML Dashboard:
    └── memory/bot_dashboard.html
```

---

## 📊 CO JEST UŻYWANE vs CO NIE

### ✅ UŻYWANE AKTYWNIE:
1. **Cron** - Finance tracker co 15 min
2. **3 boty paper trading** - Unified bot LOW/MEDIUM/HIGH
3. **Monitoring** - bot_monitor.py, check_bots.sh
4. **API Hyperliquid** - klucze skonfigurowane, działają

### ⚠️ UŻYWANE RZADKO:
1. **Backtesty** - uruchamiane na żądanie
2. **Raporty HTML** - generowane na żądanie
3. **Testy API** - diagnostyka

### ❌ NIEUŻYWANE / ARCHIWUM:
1. **Passivbot-pro** - skills/passivbot-pro/ (nie działa poprawnie)
2. **Passivbot-micro inne boty** - short_3x_bot, scalping itp.
3. **Stare konfiguracje** - config_12usd.json
4. **SEO skill** - zainstalowany ale nieużywany

---

## 🎯 PODSUMOWANIE

| Kategoria | Aktywne | Nieaktywne |
|-----------|---------|------------|
| Cron jobs | 1 | - |
| Boty | 3 | 0 |
| Skrypty Python | 8 używanych | 9 nieużywanych |
| Konfiguracje | 3 | 4 |

**Całkowity rozmiar:** 3.6MB (logi + dane)
**API Keys:** Skonfigurowane (Hyperliquid)
**Boty działające:** 3 (wszystkie paper trading)
**Cron działa:** Tak (co 15 min)

---

## 💡 REKOMENDACJE

1. **Usunąć** nieużywane skrypty (passivbot-pro, stare boty)
2. **Zarchiwizować** wyniki backtestów starsze niż miesiąc
3. **Monitorować** logi botów codziennie
4. **Po 7 dniach** - decyzja: live trading czy zmiana strategii
