#!/usr/bin/env python3
"""
Simple Hyperliquid connection test using CCXT directly.
"""
import asyncio
import ccxt.async_support as ccxt
import os

async def test_connection():
    import os
    wallet = os.environ.get('HYPERLIQUID_API_KEY') or os.environ.get('EXCHANGE_API_KEY')
    secret = os.environ.get('HYPERLIQUID_SECRET') or os.environ.get('EXCHANGE_API_SECRET')
    if not wallet or not secret:
        raise EnvironmentError('Set HYPERLIQUID_API_KEY and HYPERLIQUID_SECRET in your .env or environment.')
    
    print("=== Hyperliquid API Test ===")
    print(f"Wallet: {wallet[:10]}...{wallet[-6:]}")
    print()
    
    try:
        # Initialize exchange
        exchange = ccxt.hyperliquid({
            'apiKey': wallet,
            'secret': secret,
            'enableRateLimit': True,
            'sandbox': True,
        })
        
        print("1. Loading markets...")
        markets = await exchange.load_markets()
        print(f"   ✓ Loaded {len(markets)} markets")
        
        print("2. Fetching BTC/USDC ticker...")
        ticker = await exchange.fetch_ticker('BTC/USDC:USDC')
        print(f"   ✓ BTC Price: ${ticker['last']}")
        
        print("3. Fetching balance...")
        # Hyperliquid requires wallet address for public balance fetch
        balance = await exchange.fetch_balance({'user': wallet})
        usdc = balance.get('USDC', {}).get('free', 0)
        print(f"   ✓ USDC Balance: {usdc}")
        
        print("\n=== Connection successful! ===")
        await exchange.close()
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        return False

if __name__ == '__main__':
    result = asyncio.run(test_connection())
    exit(0 if result else 1)
