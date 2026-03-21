#!/usr/bin/env python3
"""
Fetch stock data from Yahoo Finance.
Uses Yahoo Finance API (no key required for basic data).
"""
import sys
import json
import urllib.request
import urllib.parse

def fetch_stock_data(symbol):
    """Fetch current stock data for a given ticker symbol."""
    # Yahoo Finance API endpoint
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
    except Exception as e:
        return {"error": f"Failed to fetch data: {e}"}
    
    result = data.get('chart', {}).get('result', [])
    if not result:
        error = data.get('chart', {}).get('error', {})
        return {"error": error.get('description', f"Stock '{symbol}' not found")}
    
    stock_data = result[0]
    meta = stock_data.get('meta', {})
    timestamps = stock_data.get('timestamp', [])
    
    # Get price data
    indicators = stock_data.get('indicators', {})
    quote = indicators.get('quote', [{}])[0]
    
    closes = quote.get('close', [])
    volumes = quote.get('volume', [])
    highs = quote.get('high', [])
    lows = quote.get('low', [])
    opens = quote.get('open', [])
    
    if not closes or closes[-1] is None:
        return {"error": f"No price data available for '{symbol}'"}
    
    current_price = closes[-1]
    prev_close = meta.get('chartPreviousClose', closes[0] if closes else current_price)
    
    # Calculate change
    change = current_price - prev_close
    change_percent = (change / prev_close * 100) if prev_close else 0
    
    return {
        "symbol": symbol.upper(),
        "name": meta.get('shortName', meta.get('longName', symbol.upper())),
        "currency": meta.get('currency', 'USD'),
        "current_price": current_price,
        "previous_close": prev_close,
        "change": change,
        "change_percent": change_percent,
        "volume_24h": volumes[-1] if volumes else None,
        "high_24h": max(h for h in highs if h is not None) if highs else None,
        "low_24h": min(l for l in lows if l is not None) if lows else None,
        "open_price": opens[0] if opens else None,
        "market_state": meta.get('marketState', 'UNKNOWN'),
        "exchange": meta.get('exchangeName', 'Unknown')
    }

def fetch_stock_chart(symbol, days=7):
    """Fetch historical chart data for a stock."""
    # Map days to Yahoo range
    range_map = {1: "1d", 7: "5d", 30: "1mo", 90: "3mo", 180: "6mo", 365: "1y"}
    yahoo_range = range_map.get(days, f"{days}d" if days < 365 else "1y")
    
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range={yahoo_range}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
    except Exception as e:
        return {"error": f"Failed to fetch chart data: {e}"}
    
    result = data.get('chart', {}).get('result', [])
    if not result:
        return {"error": f"No chart data available for '{symbol}'"}
    
    stock_data = result[0]
    timestamps = stock_data.get('timestamp', [])
    indicators = stock_data.get('indicators', {})
    quote = indicators.get('quote', [{}])[0]
    closes = quote.get('close', [])
    
    # Format data points
    from datetime import datetime
    formatted_prices = []
    for i, (ts, price) in enumerate(zip(timestamps, closes)):
        if price is not None:
            date = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
            formatted_prices.append({"date": date, "price": price})
    
    return {
        "symbol": symbol.upper(),
        "days": days,
        "prices": formatted_prices
    }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: fetch_stock.py <symbol> [chart_days]"}))
        sys.exit(1)
    
    symbol = sys.argv[1]
    chart_days = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    if chart_days:
        result = fetch_stock_chart(symbol, chart_days)
    else:
        result = fetch_stock_data(symbol)
    
    print(json.dumps(result, indent=2))
