# Unified Crypto Bot

Repozytorium zawiera moduł badawczo-rozwojowy bota tradingowego w katalogu skills/passivbot-micro.

Główny cel tego README: opisać faktyczny stan repozytorium (bez nieistniejących plików i komend).

## Co Jest W Repo

- skills/passivbot-micro/README.md: szczegółowy opis projektu i wyników
- skills/passivbot-micro/SKILL.md: opis skilla i szybkie komendy
- skills/passivbot-micro/config/config_100usd_fixed.json: przykładowa konfiguracja
- skills/passivbot-micro/resources/requirements.txt: zależności Pythona
- skills/passivbot-micro/scripts/: bot, backtesty, optymalizacja PPO/A2C, testy integracyjne
- skills/passivbot-micro/templates/config_template.json: szablon konfiguracji

## Szybki Start

Wymagany Python 3.12+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r skills/passivbot-micro/resources/requirements.txt
```

## Najczęściej Używane Komendy

### 1) Uruchomienie bota (testnet)

```bash
python3 skills/passivbot-micro/scripts/unified_bot.py --testnet
```

### 2) Wygenerowanie domyślnego pliku konfiguracyjnego bota

```bash
python3 skills/passivbot-micro/scripts/unified_bot.py --create-config --config unified_config.json
```

### 3) Backtest mikro-pozycji

```bash
python3 skills/passivbot-micro/scripts/backtest.py --candles 50000 --capital 100 --exchange hyperliquid
```

### 4) Systematyczny pakiet backtestów

```bash
python3 skills/passivbot-micro/scripts/backtest_suite.py
```

### 5) Szybka optymalizacja PPO

```bash
python3 skills/passivbot-micro/scripts/optimize_fast.py 100
python3 skills/passivbot-micro/scripts/optimize_ultra.py 100
python3 skills/passivbot-micro/scripts/optimize_ppo_params.py 100
```

## Struktura Skryptów

Aktualnie dostępne główne pliki wykonywalne w skills/passivbot-micro/scripts:

- unified_bot.py
- backtest.py
- backtest_suite.py
- optimize_fast.py
- optimize_ultra.py
- optimize_ppo_params.py
- ppo_engine.py
- ppo_continuous.py
- a2c_continuous.py
- risk_management.py
- technical_indicators.py
- momentum_strategy.py
- test_ppo_integration.py
- test_ppo_long_window.py
- test_ppo_research.py
- test_ppo_comprehensive.py
- test_ensemble_daily.py
- test_ensemble_scenarios.py

## Dane Testowe

Część skryptów oczekuje danych historycznych BTC w /tmp (np. /tmp/btc_real_2years.json albo /tmp/btc_extended.json). Jeżeli plików nie ma, skrypt może zakończyć się błędem albo użyć danych syntetycznych (zależnie od implementacji).

## Ważne Ostrzeżenie

To jest projekt researchowy. Wyniki historyczne nie gwarantują przyszłych wyników. Handel realnym kapitałem wiąże się z ryzykiem.

## Dokumentacja Szczegółowa

- skills/passivbot-micro/README.md
- skills/passivbot-micro/SKILL.md
