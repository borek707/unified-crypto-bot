#!/usr/bin/env python3
"""Check Hyperliquid balance."""
import asyncio
import ccxt.async_support as ccxt

async def check():
    wallet = "0xb64995df52ea75ca8497d61e9e7e3ff185bf6787"
    secret = "0x839358e35f7155dfc8468a1d9d7d8c305b944b39db94ab9014cc11281ba65c7d"
    
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
