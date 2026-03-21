#!/bin/bash
# Daily report helper - tworzy szablon raportu na dzisiejszy dzień

cd ~/.openclaw/workspace

TODAY=$(date +%Y-%m-%d)
REPORT_FILE="memory/${TODAY}.md"

if [ -f "$REPORT_FILE" ]; then
    echo "📄 Raport na dziś już istnieje: $REPORT_FILE"
    echo "Edytuj go ręcznie lub użyj: nano $REPORT_FILE"
else
    # Utwórz raport z dzisiejszą datą
    cat > "$REPORT_FILE" << EOF
# Raport Dzienny - ${TODAY}

## Co zrobiliśmy dzisiaj
- 

## Bugi / Problemy napotkane
| Problem | Status | Rozwiązanie |
|---------|--------|-------------|
| | | |

## Co nie działało (i dlaczego)
- 

## Zmiany / Nowe funkcje
- 

## Decyzje podjęte
- 

## Do zrobienia jutro
- [ ] 
- [ ] 

## Wnioski / Lekcje
- 

---
*Raport wygenerowany: $(date "+%Y-%m-%d %H:%M UTC")*
EOF
    echo "✅ Utworzono raport: $REPORT_FILE"
fi

# Pokaż ostatnie 3 raporty
echo ""
echo "📁 Ostatnie raporty:"
ls -lt memory/20*.md 2>/dev/null | head -5
