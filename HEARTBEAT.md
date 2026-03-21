# Daily Tasks - HEARTBEAT

Sprawdź co godzinę czy wszystko działa.

## Codzienny raport (wieczorem ok 22:00)
- [ ] Utwórz raport dzienny: `./scripts/create_daily_report.sh`
- [ ] Wypełnij sekcje: co zrobiono, bugi, zmiany
- [ ] Zapisz w `memory/YYYY-MM-DD.md`

## Rano - Auto Review (8:00, automatycznie)
- [ ] Sprawdź wyniki: `cat memory/logs/daily_review.log | tail -50`
- [ ] Przejrzyj incydenty: `./scripts/view_incidents.sh`
- [ ] Napraw manualnie problemy oznaczone jako "manual_fix_needed"

## Monitoring botów
- [ ] Sprawdź czy boty działają: `./check_bots.sh`
- [ ] Sprawdź czy otworzyły pozycje: `grep "OPEN" memory/passivbot_logs/*/live.log`
- [ ] Sprawdź czy nie ma błędów: `grep -i "error\|exception" memory/passivbot_logs/*/live.log`

## Quick checks
- [ ] Boty działają (PID aktywne)
- [ ] Ceny złota poprawne (~$2,500)
- [ ] Brak krytycznych błędów w logach

## Logowanie problemów
Jeśli zauważysz problem, zaloguj go:
```bash
python3 scripts/daily_review.py --log "Krótki opis problemu"
```

Jeśli wszystko OK → HEARTBEAT_OK
Jeśli problemy → wyślij alert
