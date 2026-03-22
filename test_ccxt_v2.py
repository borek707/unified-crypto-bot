#!/usr/bin/env python3
"""
Hyperliquid test - trying different config options.
"""
import asyncio
import ccxt.async_support as ccxt

async def test_connection():
    import os
    wallet = os.environ.get('HYPERLIQUID_API_KEY') or os.environ.get('EXCHANGE_API_KEY')
    secret = os.environ.get('HYPERLIQUID_SECRET') or os.environ.get('EXCHANGE_API_SECRET')
    if not wallet or not secret:
        raise EnvironmentError('Set HYPERLIQUID_API_KEY and HYPERLIQUID_SECRET in your .env or environment.')
    
    print("=== Hyperliquid API Test (v2) ===")
    print(f"CCXT version: {ccxt.__version__}")
    print()
    
    try:
        # Try without sandbox first
        exchange = ccxt.hyperliquid({
            'apiKey': wallet,
            'secret': secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',
            }
        })
        
        print("1. Testing fetch_ticker (public)...")
        ticker = await exchange.fetch_ticker('BTC/USDC:USDC')
        print(f"   ✓ BTC Price: ${ticker['last']}")
        
        print("2. Testing fetch_balance...")
        balance = await exchange.fetch_balance({'user': wallet})
        print(f"   ✓ Balance: {balance}")
        
        await exchange.close()
        print("\n=== Success! ===")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    asyncio.run(test_connection())
