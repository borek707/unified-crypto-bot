#!/usr/bin/env python3
"""Check Hyperliquid balance."""
import asyncio
import ccxt.async_support as ccxt

async def check():
    import os
    wallet = os.environ.get('HYPERLIQUID_API_KEY') or os.environ.get('EXCHANGE_API_KEY')
    secret = os.environ.get('HYPERLIQUID_SECRET') or os.environ.get('EXCHANGE_API_SECRET')
    if not wallet or not secret:
        raise EnvironmentError('Set HYPERLIQUID_API_KEY and HYPERLIQUID_SECRET in your .env or environment.')
    
    ex = ccxt.hyperliquid({
        'apiKey': wallet,
        'secret': secret,
        'enableRateLimit': True,
    })
    
    bal = await ex.fetch_balance({'user': wallet})
    usdc = bal.get('USDC', {}).get('free', 0)
    print(f'USDC Balance: {usdc}')
    await ex.close()

asyncio.run(check())
