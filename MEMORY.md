# MEMORY.md - Long-term memory

## System Raportowania
Codzienne raporty są w `memory/YYYY-MM-DD.md`.

### Jak prowadzić raport:
```bash
./scripts/create_daily_report.sh    # Utwórz szablon na dziś
nano memory/2026-03-20.md           # Edytuj
```

### Auto-Review System:
```bash
python3 scripts/daily_review.py              # Analiza + auto-fix
python3 scripts/daily_review.py --report     # Tylko raport
python3 scripts/daily_review.py --log "desc" # Loguj incydent
./scripts/view_incidents.sh                  # Pokaż incydenty
```

**Cron:** Uruchamia się codziennie o 8:00 automatycznie.

## Projekty

### 1. Finance Tracker (Gold Trading)
- Lokalizacja: `skills/finance-tracker/`
- Problemy naprawione:
  - GC=F wymaga dzielenia przez 1.8 aby uzyskać spot price
  - Cache TTL zwiększony do 60 minut
- Status: ✅ Działa poprawnie

### 2. Crypto Trading Bots (Paper)
- Lokalizacja: `skills/passivbot-micro/`
- Trzy boty: LOW, MEDIUM, HIGH risk
- Auto-restart: co 5 minut w cronie
- Status: ✅ Działają, otworzyły pierwszą pozycję

### 3. Unified Crypto Bot
- Lokalizacja: workspace root
- Repo: https://github.com/borek707/unified-crypto-bot.git
- Status: ⚠️ Wymaga monitoringu

## Ważne decyzje
- Boty mają działać 24/7 na paper trading
- Codzienne raporty są obowiązkowe
- Auto-restart dla wszystkich krytycznych usług

## Kontakty / Użytkownik
- Imię: Piotr
- Chce codzienne raporty o postępach
