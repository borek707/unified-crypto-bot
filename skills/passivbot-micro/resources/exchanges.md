# Exchange Setup Guide

This guide covers setting up API access for supported exchanges.

## Supported Exchanges

| Exchange | Priority | Maker Fee | Taker Fee | Min Trade | Notes |
|----------|----------|-----------|-----------|-----------|-------|
| Hyperliquid | #1 | 0.02% | 0.05% | ~$1 | Lowest fees, best for micro-accounts |
| Bybit | #2 | 0.02% | 0.055% | ~$2 | Good liquidity, testnet available |
| Binance | #3 | 0.02% | 0.05% | ~$5 | Largest exchange, higher minimums |

## Why Hyperliquid First?

For a $100 account with $2-$10 trades:

- **Hyperliquid**: $2 trade = $0.004 fee (0.4% of profit target)
- **Binance**: $2 trade = $0.01 fee (1% of profit target)
- **Bybit**: $2 trade = $0.01 fee (1% of profit target)

Hyperliquid's 0.02% maker fee is the lowest in the industry.

---

## Hyperliquid Setup

### 1. Create Account
1. Go to [hyperliquid.xyz](https://hyperliquid.xyz)
2. Connect your wallet (MetaMask, Phantom, etc.)
3. Deposit USDC (minimum $50 recommended)

### 2. Get API Credentials

Hyperliquid uses wallet-based authentication:

```bash
# Your wallet address is your "API key"
# Your private key is your "API secret"
```

**⚠️ SECURITY WARNING:**
- Never share your private key
- Create a dedicated trading wallet
- Use hardware wallet for large amounts

### 3. Testnet Access

1. Go to [testnet.hyperliquid.xyz](https://testnet.hyperliquid.xyz)
2. Connect wallet and request testnet USDC
3. Use testnet for all development

### 4. Environment Variables

```bash
export EXCHANGE_API_KEY="0xYourWalletAddress"
export EXCHANGE_API_SECRET="YourPrivateKey"
export EXCHANGE_TESTNET="true"
```

---

## Bybit Setup

### 1. Create Account
1. Go to [bybit.com](https://bybit.com)
2. Complete KYC (required for API)
3. Deposit USDT

### 2. Create API Key
1. Go to Profile → API
2. Create new API key
3. Enable: "Futures Trading" only
4. Set IP whitelist (recommended)

### 3. Testnet Access
1. Go to [testnet.bybit.com](https://testnet.bybit.com)
2. Create testnet account
3. Get testnet API keys

### 4. Environment Variables

```bash
export BYBIT_API_KEY="your_api_key"
export BYBIT_API_SECRET="your_api_secret"
export EXCHANGE_TESTNET="true"
```

---

## Binance Setup

### 1. Create Account
1. Go to [binance.com](https://binance.com)
2. Complete KYC
3. Deposit USDT

### 2. Create API Key
1. Go to Profile → API Management
2. Create new API key
3. Enable: "Futures" only
4. Set IP whitelist (recommended)

### 3. Testnet Access
1. Go to [testnet.binancefuture.com](https://testnet.binancefuture.com)
2. Login with GitHub
3. Get testnet API keys

### 4. Environment Variables

```bash
export BINANCE_API_KEY="your_api_key"
export BINANCE_API_SECRET="your_api_secret"
export EXCHANGE_TESTNET="true"
```

---

## Rate Limits

| Exchange | REST Limit | WebSocket Limit | Notes |
|----------|-----------|-----------------|-------|
| Hyperliquid | 1200/min | 10 sub/s | Very generous |
| Bybit | 50/s | 10 sub/s | Standard |
| Binance | 1200/min | 5 sub/s | Strict enforcement |

---

## Testing Connection

Use this Python snippet to test your setup:

```python
import ccxt.async_support as ccxt
import asyncio

async def test_connection():
    exchange = ccxt.hyperliquid({
        'apiKey': 'your_wallet_address',
        'secret': 'your_private_key',
    })
    
    try:
        balance = await exchange.fetch_balance()
        print(f"Connected! Balance: {balance['USDC']}")
    except Exception as e:
        print(f"Connection failed: {e}")
    finally:
        await exchange.close()

asyncio.run(test_connection())
```

---

## Security Best Practices

1. **Never commit API keys** to git
2. **Use environment variables** or `.env` files
3. **Enable IP whitelist** on exchanges
4. **Use testnet first** for all development
5. **Create dedicated trading wallets**
6. **Withdraw profits** regularly
7. **Monitor positions** actively

---

## Troubleshooting

### "Invalid API Key"
- Check key/secret are correct
- Verify testnet vs mainnet
- Check IP whitelist

### "Insufficient Margin"
- Check available balance
- Verify leverage settings
- Check position limits

### "Rate Limit Exceeded"
- Reduce request frequency
- Implement exponential backoff
- Check for infinite loops

### "Market Closed"
- Some markets have trading hours
- Check exchange status page
- Try alternative pairs
