#!/usr/bin/env python3
"""
Fetch cryptocurrency data from CoinGecko API - FIXED VERSION
No API key required for basic usage.

FIXES:
- Increased cache TTL from 15min to 60min
- Added stale cache fallback
- Improved rate limiting
"""
import sys
import json
import urllib.request
import urllib.parse
import os
import time
import hashlib
from datetime import datetime, timedelta

BASE_URL = "https://api.coingecko.com/api/v3"
CACHE_DIR = os.path.expanduser("~/.openclaw/workspace/.cache")
CACHE_TTL = 3600  # FIXED: 60 minutes instead of 15
STALE_CACHE_TTL = 86400  # Allow stale cache up to 24 hours

# Rate limiting - CoinGecko free tier: ~10-30 calls/min
LAST_CALL_TIME = 0
MIN_CALL_INTERVAL = 2  # seconds between calls

def ensure_cache_dir():
    """Ensure cache directory exists."""
    os.makedirs(CACHE_DIR, exist_ok=True)

def get_cache_key(prefix, params):
    """Generate cache key from prefix and params."""
    key_string = f"{prefix}:{json.dumps(params, sort_keys=True)}"
    return hashlib.md5(key_string.encode()).hexdigest()

def get_cached_data(prefix, params, allow_stale=False):
    """Get cached data if not expired (or if stale is allowed)."""
    ensure_cache_dir()
    cache_key = get_cache_key(prefix, params)
    cache_file = os.path.join(CACHE_DIR, f"crypto_{cache_key}.json")
    
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                cached = json.load(f)
            age = time.time() - cached.get('timestamp', 0)
            if age < CACHE_TTL:
                return cached.get('data')
            elif allow_stale and age < STALE_CACHE_TTL:
                print(f"⚠️ Using stale cache ({age/60:.0f} min old)", file=sys.stderr)
                return cached.get('data')
        except:
            pass
    return None

def set_cached_data(prefix, params, data):
    """Cache data with timestamp."""
    ensure_cache_dir()
    cache_key = get_cache_key(prefix, params)
    cache_file = os.path.join(CACHE_DIR, f"crypto_{cache_key}.json")
    
    try:
        with open(cache_file, 'w') as f:
            json.dump({'timestamp': time.time(), 'data': data}, f)
    except:
        pass

def rate_limited_fetch(url, timeout=10, max_retries=3):
    """Fetch with rate limiting and retry logic."""
    global LAST_CALL_TIME
    
    for attempt in range(max_retries):
        # Rate limiting - ensure minimum interval between calls
        time_since_last = time.time() - LAST_CALL_TIME
        if time_since_last < MIN_CALL_INTERVAL:
            time.sleep(MIN_CALL_INTERVAL - time_since_last)
        
        try:
            LAST_CALL_TIME = time.time()
            with urllib.request.urlopen(url, timeout=timeout) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            LAST_CALL_TIME = time.time()
            if e.code == 429:  # Rate limit
                wait_time = 10 * (2 ** attempt)  # Exponential backoff: 10s, 20s, 40s
                if attempt < max_retries - 1:
                    time.sleep(wait_time)
                    continue
            return {"error": f"HTTP {e.code}: {e.reason}"}
        except Exception as e:
            LAST_CALL_TIME = time.time()
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            return {"error": str(e)}
    
    return {"error": "Max retries exceeded"}

def fetch_coin_data(symbol):
    """Fetch current data for a cryptocurrency by symbol with caching."""
    symbol = symbol.lower()
    
    # Check cache first (allow stale if needed)
    cache_params = {"symbol": symbol, "type": "coin_data"}
    cached = get_cached_data("coin", cache_params, allow_stale=True)
    if cached:
        return cached
    
    # Search for coin by symbol
    search_url = f"{BASE_URL}/search?query={symbol}"
    
    search_data = rate_limited_fetch(search_url)
    if "error" in search_data:
        # Try stale cache
        cached = get_cached_data("coin", cache_params, allow_stale=True)
        if cached:
            print(f"⚠️ Using stale cache for {symbol.upper()}", file=sys.stderr)
            return cached
        return search_data
    
    coins = search_data.get('coins', [])
    if not coins:
        return {"error": f"Cryptocurrency '{symbol}' not found"}
    
    # Get the best match (usually first result)
    coin = coins[0]
    coin_id = coin['id']
    
    # Fetch detailed data
    price_url = f"{BASE_URL}/coins/{coin_id}?localization=false&tickers=false&market_data=true&community_data=false&developer_data=false"
    
    data = rate_limited_fetch(price_url, timeout=15)
    if "error" in data:
        # Try stale cache
        cached = get_cached_data("coin", cache_params, allow_stale=True)
        if cached:
            print(f"⚠️ Using stale cache for {symbol.upper()}", file=sys.stderr)
            return cached
        return data
    
    market_data = data.get('market_data', {})
    
    result = {
        "name": data.get('name'),
        "symbol": data.get('symbol', '').upper(),
        "current_price_usd": market_data.get('current_price', {}).get('usd'),
        "price_change_24h_percent": market_data.get('price_change_percentage_24h'),
        "volume_24h_usd": market_data.get('total_volume', {}).get('usd'),
        "market_cap_usd": market_data.get('market_cap', {}).get('usd'),
        "high_24h_usd": market_data.get('high_24h', {}).get('usd'),
        "low_24h_usd": market_data.get('low_24h', {}).get('usd'),
        "last_updated": market_data.get('last_updated')
    }
    
    # Cache the result
    set_cached_data("coin", cache_params, result)
    
    return result

def fetch_multiple_coins(symbols):
    """Fetch data for multiple coins efficiently with caching."""
    results = {}
    errors = []
    
    for symbol in symbols:
        result = fetch_coin_data(symbol)
        if "error" in result:
            errors.append(f"{symbol}: {result['error']}")
        else:
            results[symbol.upper()] = result
        
        # Small delay between coins to respect rate limits
        time.sleep(0.5)
    
    if errors and not results:
        return {"error": "; ".join(errors)}
    
    return {
        "coins": results,
        "errors": errors if errors else None,
        "timestamp": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
        "note": "Using 60min cache with stale fallback"
    }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: fetch_crypto.py <symbol> [chart_days]"}))
        sys.exit(1)
    
    symbol = sys.argv[1]
    
    # Check if it's a comma-separated list
    if ',' in symbol:
        symbols = [s.strip() for s in symbol.split(',')]
        result = fetch_multiple_coins(symbols)
    elif sys.argv[1] == "--multi":
        # Support for --multi flag followed by symbols
        if len(sys.argv) < 3:
            print(json.dumps({"error": "Usage: fetch_crypto.py --multi symbol1,symbol2,..."}))
            sys.exit(1)
        symbols = [s.strip() for s in sys.argv[2].split(',')]
        result = fetch_multiple_coins(symbols)
    else:
        result = fetch_coin_data(symbol)
    
    print(json.dumps(result, indent=2))
