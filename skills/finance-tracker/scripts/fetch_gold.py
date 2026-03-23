#!/usr/bin/env python3
"""
Gold price fetcher with multiple data sources fallback
Uses: Yahoo Finance (primary) → Alpha Vantage (fallback) → Stale cache (last resort)
"""
import sys
import json
import urllib.request
import os
import time
from datetime import datetime

CACHE_DIR = os.path.expanduser("~/.openclaw/workspace/.cache")

def fetch_from_yahoo():
    """Try Yahoo Finance GC=F"""
    url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=15m&range=2d"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode())
        
        result = data.get('chart', {}).get('result', [])
        if not result:
            return None
        
        meta = result[0].get('meta', {})
        price = meta.get('regularMarketPrice')
        
        # Sanity check
        if price and 2000 < price < 3500:
            return {"source": "yahoo", "price": price, "data": result[0]}
        else:
            print(f"⚠️ Yahoo returned suspicious price: ${price}", file=sys.stderr)
            return None
    except Exception as e:
        print(f"⚠️ Yahoo error: {e}", file=sys.stderr)
        return None

def check_alphavantage_limit():
    """Check if we haven't exceeded 25 requests/day limit"""
    limit_file = os.path.expanduser("~/.openclaw/workspace/.cache/alphavantage_limit.json")
    today = datetime.now().strftime('%Y-%m-%d')
    
    try:
        with open(limit_file, 'r') as f:
            data = json.load(f)
        if data.get('date') == today:
            count = data.get('count', 0)
            remaining = 25 - count
            if remaining <= 5:
                print(f"⚠️ Alpha Vantage: {remaining}/25 requests remaining today", file=sys.stderr)
            if count >= 25:
                return False  # Limit reached
    except:
        pass
    return True  # OK to proceed

def increment_alphavantage_counter():
    """Increment daily request counter"""
    limit_file = os.path.expanduser("~/.openclaw/workspace/.cache/alphavantage_limit.json")
    today = datetime.now().strftime('%Y-%m-%d')
    
    try:
        with open(limit_file, 'r') as f:
            data = json.load(f)
    except:
        data = {}
    
    if data.get('date') != today:
        data = {'date': today, 'count': 0}
    
    data['count'] = data.get('count', 0) + 1
    
    os.makedirs(os.path.dirname(limit_file), exist_ok=True)
    with open(limit_file, 'w') as f:
        json.dump(data, f)

def fetch_from_alphavantage():
    """Try Alpha Vantage (requires API key) - with rate limiting"""
    # Check rate limit first
    if not check_alphavantage_limit():
        print(f"⚠️ Alpha Vantage daily limit (25) reached", file=sys.stderr)
        return None
    
    # Check for API key in environment or file
    api_key = os.environ.get('ALPHAVANTAGE_API_KEY')
    
    if not api_key:
        # Try to read from config
        try:
            with open(os.path.expanduser("~/.alphavantage_key"), 'r') as f:
                api_key = f.read().strip()
        except:
            pass
    
    if not api_key:
        return None
    
    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol=XAUUSD&interval=15min&apikey={api_key}"
    
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode())
        
        ts = data.get('Time Series (15min)', {})
        if not ts:
            return None
        
        # Get latest candle
        latest_time = sorted(ts.keys())[-1]
        latest = ts[latest_time]
        
        price = float(latest['4. close'])
        
        # Increment counter (successful request)
        increment_alphavantage_counter()
        
        # Build candles format similar to Yahoo
        candles = []
        for t in sorted(ts.keys()):
            candle = ts[t]
            dt = datetime.strptime(t, '%Y-%m-%d %H:%M:%S')
            candles.append({
                "timestamp": int(dt.timestamp()),
                "datetime": dt.strftime('%Y-%m-%d %H:%M:%S'),
                "date": dt.strftime('%Y-%m-%d'),
                "time": dt.strftime('%H:%M'),
                "open": float(candle['1. open']),
                "high": float(candle['2. high']),
                "low": float(candle['3. low']),
                "close": float(candle['4. close']),
                "volume": int(candle['5. volume'])
            })
        
        return {
            "source": "alphavantage", 
            "price": price, 
            "candles": candles,
            "meta": {"symbol": "XAUUSD", "regularMarketPrice": price}
        }
    except Exception as e:
        print(f"⚠️ Alpha Vantage error: {e}", file=sys.stderr)
        return None

def fetch_gold_data():
    """Fetch gold data with fallback chain"""
    
    # Try Yahoo first
    result = fetch_from_yahoo()
    if result:
        return result
    
    # Try Alpha Vantage
    result = fetch_from_alphavantage()
    if result:
        return result
    
    # Fallback: return error with instructions
    return {
        "error": "All data sources failed",
        "yahoo_issue": "Yahoo Finance GC=F returning incorrect prices (~$4000 instead of ~$2500)",
        "solution": "Set ALPHAVANTAGE_API_KEY environment variable or create ~/.alphavantage_key file",
        "register": "Get free API key at: https://www.alphavantage.co/support/#api-key"
    }

if __name__ == "__main__":
    result = fetch_gold_data()
    print(json.dumps(result, indent=2))
