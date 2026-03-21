#!/usr/bin/env python3
"""
Simple test for Hyperliquid connection.
"""
import os
import sys

api_key = os.getenv('EXCHANGE_API_KEY')
api_secret = os.getenv('EXCHANGE_API_SECRET')

print("=== Hyperliquid Configuration ===")
print(f"API Key (Wallet): {api_key[:10]}...{api_key[-6:] if api_key else 'None'}")
print(f"API Secret (Private): {api_secret[:10]}...{api_secret[-6:] if api_secret else 'None'}")
print(f"Testnet: {os.getenv('USE_TESTNET', 'not set')}")

if not api_key or api_key == 'your_api_key_here':
    print("\n❌ EXCHANGE_API_KEY not set properly!")
    sys.exit(1)

if not api_secret or api_secret == 'your_api_secret_here':
    print("\n❌ EXCHANGE_API_SECRET not set properly!")
    sys.exit(1)

print("\n✅ Credentials configured!")
print("\nNext steps:")
print("1. Download data: python3 -m passivbot_pro.scripts.main --mode download --symbol BTC/USDC:USDC")
print("2. Run backtest: python3 -m passivbot_pro.scripts.main --mode backtest --symbol BTC/USDC:USDC")
print("3. Start paper trading: python3 -m passivbot_pro.scripts.main --mode live --testnet")
