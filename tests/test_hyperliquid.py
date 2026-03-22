#!/usr/bin/env python3
"""
Test Hyperliquid API connection.
Run after setting API keys.
"""

import os
import sys
import asyncio

# Add passivbot-pro to path
sys.path.insert(0, os.path.expanduser('~/.openclaw/workspace/skills/passivbot-pro/scripts'))

async def test_hyperliquid_connection():
    """Test connection to Hyperliquid."""
    
    api_key = os.getenv('EXCHANGE_API_KEY')
    api_secret = os.getenv('EXCHANGE_API_SECRET')
    
    if not api_key or api_key == 'your_api_key_here':
        print("❌ EXCHANGE_API_KEY not set!")
        print("   Run: source ~/.openclaw/workspace/setup_hyperliquid.sh")
        return False
    
    if not api_secret or api_secret == 'your_api_secret_here':
        print("❌ EXCHANGE_API_SECRET not set!")
        return False
    
    print("=== Hyperliquid API Test ===")
    print(f"API Key: {api_key[:8]}...{api_key[-4:]}")
    print(f"Testnet: {os.getenv('USE_TESTNET', 'true')}")
    print()
    
    try:
        import ccxt.async_support as ccxt
        
        exchange = ccxt.hyperliquid({
            'apiKey': api_key,
            'secret': api_secret,
            'sandbox': os.getenv('USE_TESTNET', 'true').lower() == 'true',
            'enableRateLimit': True,
        })
        
        print("Testing connection...")
        await exchange.load_markets()
        print(f"✅ Connected! Available pairs: {len(exchange.markets)}")
        
        # Test fetch balance
        print("Fetching balance...")
        balance = await exchange.fetch_balance()
        print(f"✅ Balance: {balance.get('total', {}).get('USDC', 0)} USDC")
        
        # Test fetch ticker
        print("Fetching BTC/USDC ticker...")
        ticker = await exchange.fetch_ticker('BTC/USDC:USDC')
        print(f"✅ BTC Price: ${ticker['last']}")
        
        await exchange.close()
        print()
        print("=== All tests passed! ===")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == '__main__':
    result = asyncio.run(test_hyperliquid_connection())
    sys.exit(0 if result else 1)
