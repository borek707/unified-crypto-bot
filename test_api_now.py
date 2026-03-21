#!/usr/bin/env python3
"""
Test Hyperliquid API connection.
"""
import asyncio
import ccxt.async_support as ccxt
import os

async def test():
    wallet = os.getenv('HYPERLIQUID_API_KEY', '0xb64995df52ea75ca8497d61e9e7e3ff185bf6787')
    secret = os.getenv('HYPERLIQUID_SECRET', '0x839358e35f7155dfc8468a1d9d7d8c305b944b39db94ab9014cc11281ba65c7d')
    
    print("Testing Hyperliquid API...")
    print(f"Wallet: {wallet[:10]}...{wallet[-6:]}")
    
    try:
        exchange = ccxt.hyperliquid({
            'enableRateLimit': True,
            'apiKey': wallet,
            'secret': secret,
        })
        
        print("Loading markets...")
        await exchange.load_markets()
        print(f"✅ Markets loaded: {len(exchange.markets)} pairs")
        
        print("Fetching BTC price...")
        ticker = await exchange.fetch_ticker('BTC/USDC:USDC')
        print(f"✅ BTC Price: ${ticker['last']}")
        
        print("Fetching balance...")
        balance = await exchange.fetch_balance({'user': wallet})
        usdc = balance.get('USDC', {}).get('free', 0)
        print(f"✅ USDC Balance: {usdc}")
        
        await exchange.close()
        print("\n✅ API TEST PASSED!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    result = asyncio.run(test())
    exit(0 if result else 1)
