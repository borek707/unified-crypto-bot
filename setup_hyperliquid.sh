#!/bin/bash
# Setup API keys dla passivbot-pro (Hyperliquid)
# Uruchom: source ~/.openclaw/workspace/setup_hyperliquid.sh

echo "=== Hyperliquid API Setup ==="
echo ""
echo "Podaj swoje API credentials:"
echo ""

read -s -p "Hyperliquid API Key: " API_KEY
echo ""
read -s -p "Hyperliquid API Secret: " API_SECRET
echo ""

# Dodaj do .bashrc jeśli nie ma
if ! grep -q "EXCHANGE_API_KEY" ~/.bashrc; then
    echo "" >> ~/.bashrc
    echo "# PassivBot Pro - Hyperliquid API" >> ~/.bashrc
    echo "export EXCHANGE_API_KEY=\"$API_KEY\"" >> ~/.bashrc
    echo "export EXCHANGE_API_SECRET=\"$API_SECRET\"" >> ~/.bashrc
    echo "export EXCHANGE_TYPE=\"hyperliquid\"" >> ~/.bashrc
    echo "✓ Dodano do ~/.bashrc"
else
    # Zaktualizuj istniejące
    sed -i "s|export EXCHANGE_API_KEY=.*|export EXCHANGE_API_KEY=\"$API_KEY\"|" ~/.bashrc
    sed -i "s|export EXCHANGE_API_SECRET=.*|export EXCHANGE_API_SECRET=\"$API_SECRET\"|" ~/.bashrc
    echo "✓ Zaktualizowano ~/.bashrc"
fi

# Ustaw dla aktualnej sesji
export EXCHANGE_API_KEY="$API_KEY"
export EXCHANGE_API_SECRET="$API_SECRET"
export EXCHANGE_TYPE="hyperliquid"

echo ""
echo "=== Konfiguracja zapisana ==="
echo ""
echo "Wymagane restarty:"
echo "1. Uruchom: source ~/.bashrc"
echo "2. Zrestartuj OpenClaw (lub poczekaj na nową sesję)"
echo ""
echo "Testowanie połączenia..."
