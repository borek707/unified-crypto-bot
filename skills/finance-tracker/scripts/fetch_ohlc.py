#!/usr/bin/env python3
"""
Fetch historical OHLC data for trading analysis.
Supports Yahoo Finance for stocks/indices.
"""
import sys
import json
import urllib.request
from datetime import datetime, timedelta

def fetch_ohlc_data(symbol, interval="15m", range_days=5):
    """
    Fetch OHLC candlestick data.
    
    Args:
        symbol: Stock/ETF symbol (e.g., ^IXIC for NASDAQ)
        interval: Candle interval (1m, 5m, 15m, 30m, 1h, 1d)
        range_days: How many days of data to fetch
    """
    # Map intervals to Yahoo Finance format
    interval_map = {
        "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
        "1h": "1h", "1d": "1d"
    }
    
    # Map range to Yahoo format
    if range_days <= 1:
        yahoo_range = "1d"
    elif range_days <= 5:
        yahoo_range = "5d"
    elif range_days <= 30:
        yahoo_range = "1mo"
    else:
        yahoo_range = "3mo"
    
    yahoo_interval = interval_map.get(interval, "15m")
    
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval={yahoo_interval}&range={yahoo_range}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
    except Exception as e:
        return {"error": f"Failed to fetch data: {e}"}
    
    result = data.get('chart', {}).get('result', [])
    if not result:
        error = data.get('chart', {}).get('error', {})
        return {"error": error.get('description', f"Symbol '{symbol}' not found")}
    
    stock_data = result[0]
    meta = stock_data.get('meta', {})
    timestamps = stock_data.get('timestamp', [])
    
    indicators = stock_data.get('indicators', {})
    quote = indicators.get('quote', [{}])[0]
    
    opens = quote.get('open', [])
    highs = quote.get('high', [])
    lows = quote.get('low', [])
    closes = quote.get('close', [])
    volumes = quote.get('volume', [])
    
    candles = []
    for i, ts in enumerate(timestamps):
        if opens[i] is not None:
            dt = datetime.fromtimestamp(ts)
            candles.append({
                "timestamp": ts,
                "datetime": dt.strftime('%Y-%m-%d %H:%M:%S'),
                "date": dt.strftime('%Y-%m-%d'),
                "time": dt.strftime('%H:%M'),
                "open": opens[i],
                "high": highs[i],
                "low": lows[i],
                "close": closes[i],
                "volume": volumes[i] if i < len(volumes) else None
            })
    
    return {
        "symbol": symbol.upper(),
        "name": meta.get('shortName', meta.get('longName', symbol.upper())),
        "currency": meta.get('currency', 'USD'),
        "interval": interval,
        "candles": candles
    }

def analyze_opening_range_breakout(symbol, days_to_analyze=20, session_open="15:30"):
    """
    Analyze "First 15min Candle Breakout" strategy.
    
    Strategy: Wait for first 15min candle after market open (9:30 ET / 15:30 CET),
    then enter on breakout of that candle's high/low.
    
    Returns statistics on how often the breakout continues.
    """
    data = fetch_ohlc_data(symbol, interval="15m", range_days=days_to_analyze + 5)
    
    if "error" in data:
        return data
    
    candles = data.get('candles', [])
    
    # Group candles by date
    daily_candles = {}
    for c in candles:
        date = c['date']
        if date not in daily_candles:
            daily_candles[date] = []
        daily_candles[date].append(c)
    
    # Analyze each trading day
    results = []
    
    for date, day_candles in sorted(daily_candles.items()):
        if len(day_candles) < 2:  # Need at least first candle + next candles
            continue
        
        # First 15min candle
        first_candle = day_candles[0]
        
        # Check if it's around market open (9:30 ET = 15:30 CET)
        # Yahoo data is in ET, so we look for 9:30-9:45
        candle_time = first_candle['time']
        if not (candle_time.startswith("09:") or candle_time.startswith("15:")):
            continue
        
        first_high = first_candle['high']
        first_low = first_candle['low']
        first_open = first_candle['open']
        first_close = first_candle['close']
        
        # Look for breakout in subsequent candles
        long_breakout = False
        short_breakout = False
        long_continuation = False
        short_continuation = False
        
        for i, candle in enumerate(day_candles[1:], 1):
            # Long breakout: price breaks above first candle high
            if not long_breakout and candle['high'] > first_high:
                long_breakout = True
                # Check if next candles continue up (at least +0.5% from breakout)
                if i + 1 < len(day_candles):
                    next_candles = day_candles[i+1:min(i+5, len(day_candles))]
                    max_high = max(c['high'] for c in next_candles) if next_candles else candle['high']
                    if max_high > first_high * 1.005:  # 0.5% continuation
                        long_continuation = True
            
            # Short breakout: price breaks below first candle low
            if not short_breakout and candle['low'] < first_low:
                short_breakout = True
                # Check if next candles continue down
                if i + 1 < len(day_candles):
                    next_candles = day_candles[i+1:min(i+5, len(day_candles))]
                    min_low = min(c['low'] for c in next_candles) if next_candles else candle['low']
                    if min_low < first_low * 0.995:  # 0.5% continuation
                        short_continuation = True
        
        results.append({
            "date": date,
            "first_candle": {
                "open": first_open,
                "high": first_high,
                "low": first_low,
                "close": first_close,
                "range": round(first_high - first_low, 2)
            },
            "long_breakout": long_breakout,
            "long_continuation": long_continuation,
            "short_breakout": short_breakout,
            "short_continuation": short_continuation
        })
    
    # Calculate statistics
    total_days = len(results)
    if total_days == 0:
        return {"error": "No valid trading days found for analysis"}
    
    long_breakouts = sum(1 for r in results if r['long_breakout'])
    long_continuations = sum(1 for r in results if r['long_continuation'])
    short_breakouts = sum(1 for r in results if r['short_breakout'])
    short_continuations = sum(1 for r in results if r['short_continuation'])
    
    return {
        "symbol": symbol.upper(),
        "strategy": "First 15min Candle Breakout",
        "session_open": "15:30 CET (09:30 ET)",
        "analysis_period_days": total_days,
        "statistics": {
            "long_breakout_rate": round(long_breakouts / total_days * 100, 1),
            "long_continuation_rate": round(long_continuations / total_days * 100, 1),
            "short_breakout_rate": round(short_breakouts / total_days * 100, 1),
            "short_continuation_rate": round(short_continuations / total_days * 100, 1),
            "any_breakout_rate": round((long_breakouts + short_breakouts) / total_days * 100, 1)
        },
        "daily_results": results[-10:]  # Last 10 days for reference
    }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: fetch_ohlc.py <symbol> [interval] [days] OR fetch_ohlc.py --analyze <symbol> [days]"}))
        sys.exit(1)
    
    if sys.argv[1] == "--analyze":
        if len(sys.argv) < 3:
            print(json.dumps({"error": "Usage: fetch_ohlc.py --analyze <symbol> [days]"}))
            sys.exit(1)
        symbol = sys.argv[2]
        days = int(sys.argv[3]) if len(sys.argv) > 3 else 20
        result = analyze_opening_range_breakout(symbol, days)
    else:
        symbol = sys.argv[1]
        interval = sys.argv[2] if len(sys.argv) > 2 else "15m"
        days = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        result = fetch_ohlc_data(symbol, interval, days)
    
    print(json.dumps(result, indent=2))
