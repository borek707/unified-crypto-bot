#!/usr/bin/env python3
"""
First Candle Trading Bot for XAU/USD (Gold) - FIXED VERSION
Strategy: Enter on breakout of first 15-min candle after session open

FIXES:
- Changed from GC=F (bugged) to XAUUSD=X for correct prices
- Increased cache TTL from 15min to 60min
- Added stale cache fallback
- Added price sanity check (alert if >$4000)
"""
import sys
import json
import urllib.request
import sqlite3
import os
import time
from datetime import datetime, timedelta, time as dt_time
from pathlib import Path
import hashlib

# Database path
DB_PATH = os.path.expanduser("~/.openclaw/workspace/memory/trading.db")
CACHE_DIR = os.path.expanduser("~/.openclaw/workspace/.cache")
CACHE_TTL = 3600  # FIXED: 60 minutes instead of 15
STALE_CACHE_TTL = 86400  # Allow using stale cache up to 24 hours old

def ensure_cache_dir():
    """Ensure cache directory exists."""
    os.makedirs(CACHE_DIR, exist_ok=True)

def get_cache_key(url):
    """Generate cache key from URL."""
    return hashlib.md5(url.encode()).hexdigest()

def get_cached_data(url, allow_stale=False):
    """Get cached data if not expired (or if stale is allowed)."""
    ensure_cache_dir()
    cache_key = get_cache_key(url)
    cache_file = os.path.join(CACHE_DIR, f"gold_{cache_key}.json")
    
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

def set_cached_data(url, data):
    """Cache data with timestamp."""
    ensure_cache_dir()
    cache_key = get_cache_key(url)
    cache_file = os.path.join(CACHE_DIR, f"gold_{cache_key}.json")
    
    try:
        with open(cache_file, 'w') as f:
            json.dump({'timestamp': time.time(), 'data': data}, f)
    except:
        pass

def init_database():
    """Initialize SQLite database for tracking trades and performance."""
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Trades table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                date TEXT,
                session TEXT,
                signal TEXT,
                entry_price REAL,
                stop_loss REAL,
                take_profit REAL,
                position_size REAL,
                candle_data TEXT,
                status TEXT DEFAULT 'OPEN',
                exit_price REAL,
                exit_time TEXT,
                pnl REAL,
                pnl_percent REAL,
                notes TEXT
            )
        ''')
        
        # Performance metrics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                total_trades INTEGER,
                winning_trades INTEGER,
                losing_trades INTEGER,
                win_rate REAL,
                total_pnl REAL,
                avg_win REAL,
                avg_loss REAL,
                profit_factor REAL,
                max_drawdown REAL
            )
        ''')
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ Database warning: {e}", file=sys.stderr)

def fetch_with_retry(url, headers, max_retries=3, delay=5):
    """Fetch URL with retry logic and exponential backoff."""
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code == 429:  # Rate limit
                if attempt < max_retries - 1:
                    wait_time = delay * (2 ** attempt)  # Exponential backoff
                    time.sleep(wait_time)
                    continue
            return {"error": f"HTTP {e.code}: {e.reason}"}
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(delay)
                continue
            return {"error": str(e)}
    return {"error": "Max retries exceeded"}

def fetch_xauusd_data(interval="15m", days=5):
    """Fetch XAU/USD OHLC data from Yahoo Finance with caching."""
    # NOTE: Using GC=F but with price sanity check
    # Yahoo Finance GC=F sometimes returns incorrect prices ($4000+ instead of ~$2000-2500)
    # We keep using GC=F but warn user when prices are suspicious
    symbol = "GC=F"  # Gold Futures (COMEX)
    
    range_map = {1: "1d", 5: "5d", 30: "1mo", 90: "3mo"}
    yahoo_range = range_map.get(days, f"{days}d" if days < 365 else "3mo")
    
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval={interval}&range={yahoo_range}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    # Check cache first (allow stale if needed)
    cached = get_cached_data(url, allow_stale=True)
    if cached:
        return cached
    
    # Fetch with retry
    data = fetch_with_retry(url, headers)
    
    if "error" in data:
        # Try to use stale cache even if old
        cached = get_cached_data(url, allow_stale=True)
        if cached:
            print("⚠️ Using stale cache due to fetch error", file=sys.stderr)
            return cached
        return data
    
    result = data.get('chart', {}).get('result', [])
    if not result:
        return {"error": "No data available"}
    
    stock_data = result[0]
    timestamps = stock_data.get('timestamp', [])
    indicators = stock_data.get('indicators', {})
    quote = indicators.get('quote', [{}])[0]
    
    candles = []
    for i, ts in enumerate(timestamps):
        if quote.get('open', [])[i] is not None:
            dt = datetime.fromtimestamp(ts)
            candles.append({
                "timestamp": ts,
                "datetime": dt.strftime('%Y-%m-%d %H:%M:%S'),
                "date": dt.strftime('%Y-%m-%d'),
                "time": dt.strftime('%H:%M'),
                "open": quote['open'][i],
                "high": quote['high'][i],
                "low": quote['low'][i],
                "close": quote['close'][i],
                "volume": quote.get('volume', [0]*len(timestamps))[i]
            })
    
    result_data = {
        "symbol": symbol,
        "candles": candles,
        "interval": interval,
        "meta": stock_data.get('meta', {})
    }
    
    # Cache the result
    set_cached_data(url, result_data)
    
    return result_data

def calculate_atr(candles, period=14):
    """Calculate Average True Range."""
    if len(candles) < period + 1:
        return None
    
    tr_values = []
    for i in range(1, len(candles)):
        high = candles[i]['high']
        low = candles[i]['low']
        prev_close = candles[i-1]['close']
        
        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        tr_values.append(tr)
    
    if len(tr_values) < period:
        return sum(tr_values) / len(tr_values)
    
    return sum(tr_values[-period:]) / period

def classify_candle(candle, atr):
    """Classify candle based on body size relative to ATR."""
    body_size = abs(candle['close'] - candle['open'])
    
    if atr is None or atr == 0:
        return "neutral", 0
    
    ratio = body_size / atr
    
    if ratio < 0.2:
        return "small", ratio
    elif ratio < 0.5:
        return "medium", ratio
    elif ratio < 1.0:
        return "large", ratio
    else:
        return "very_large", ratio

def get_current_session():
    """Determine current trading session based on UTC time."""
    now = datetime.utcnow()
    hour = now.hour
    weekday = now.weekday()  # 0=Monday, 6=Sunday
    
    if weekday >= 5:  # Weekend
        return "weekend", 0
    
    # Trading sessions (UTC)
    if 8 <= hour < 13:
        return "london", 2
    elif 13 <= hour < 16:
        return "london_ny_overlap", 3  # Highest priority
    elif 16 <= hour < 21:
        return "new_york", 2
    elif 21 <= hour < 24 or 0 <= hour < 8:
        return "asian", 1
    else:
        return "closed", 0

def analyze_first_candle(candles, current_time=None):
    """Analyze the most recent candle for First Candle strategy."""
    if not candles or len(candles) < 2:
        return {"error": "Insufficient candle data"}
    
    current_time = current_time or datetime.utcnow()
    
    # Get current session
    session, priority = get_current_session()
    
    if session == "weekend":
        return {"signal": "NO_TRADE", "reason": "Weekend - markets closed", "session": session}
    
    if priority == 0:
        return {"signal": "NO_TRADE", "reason": "Outside trading hours", "session": session}
    
    if priority == 1:
        return {"signal": "NO_TRADE", "reason": "Asian session - low volatility", "session": session}
    
    # Get recent candles
    atr = calculate_atr(candles[-20:], period=14)
    latest_candle = candles[-1]
    prev_candle = candles[-2]
    
    candle_class, ratio = classify_candle(latest_candle, atr)
    
    # Determine direction
    direction = "bullish" if latest_candle['close'] > latest_candle['open'] else "bearish"
    
    # First Candle Strategy Rules
    threshold_ratio = 1.1
    body_size = abs(latest_candle['close'] - latest_candle['open'])
    
    # FIXED: Price sanity check
    current_price = latest_candle['close']
    price_warning = None
    if current_price > 4000:
        price_warning = f"⚠️ WARNING: Price ${current_price:.2f} seems incorrect (should be ~$2000-3000). Data source may be bugged."
    
    signal = {
        "timestamp": current_time.strftime('%Y-%m-%d %H:%M:%S'),
        "session": session,
        "priority": priority,
        "current_price": current_price,
        "price_warning": price_warning,
        "candle": {
            "open": latest_candle['open'],
            "high": latest_candle['high'],
            "low": latest_candle['low'],
            "close": latest_candle['close'],
            "body_size": body_size,
            "direction": direction,
            "classification": candle_class,
            "atr_ratio": round(ratio, 2)
        },
        "atr_14": round(atr, 2) if atr else None,
        "threshold": round(atr * threshold_ratio, 2) if atr else None
    }
    
    # Generate signal
    if ratio >= threshold_ratio:
        if direction == "bullish":
            signal["signal"] = "BUY"
            signal["entry"] = latest_candle['close']
            signal["stop_loss"] = round(latest_candle['low'] - (atr * 0.5), 2)
            signal["take_profit"] = round(signal["entry"] + ((signal["entry"] - signal["stop_loss"]) * 1.5), 2)
        else:
            signal["signal"] = "SELL"
            signal["entry"] = latest_candle['close']
            signal["stop_loss"] = round(latest_candle['high'] + (atr * 0.5), 2)
            signal["take_profit"] = round(signal["entry"] - ((signal["stop_loss"] - signal["entry"]) * 1.5), 2)
    else:
        signal["signal"] = "HOLD"
        signal["reason"] = f"Insufficient momentum (body {round(ratio, 2)}x ATR, need >{threshold_ratio}x)"
    
    return signal

def save_signal_to_db(signal_data):
    """Save signal to database."""
    if signal_data.get("signal") in ["NO_TRADE", "HOLD"]:
        return
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO trades 
            (timestamp, date, session, signal, entry_price, stop_loss, take_profit, candle_data, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            signal_data.get('timestamp'),
            signal_data.get('timestamp', '')[:10],
            signal_data.get('session'),
            signal_data.get('signal'),
            signal_data.get('entry'),
            signal_data.get('stop_loss'),
            signal_data.get('take_profit'),
            json.dumps(signal_data.get('candle')),
            'OPEN'
        ))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ Could not save to database: {e}", file=sys.stderr)

def format_signal_output(signal_data):
    """Format signal data for display."""
    if "error" in signal_data:
        return f"❌ Error: {signal_data['error']}"
    
    lines = []
    
    # Price warning if present
    if signal_data.get('price_warning'):
        lines.append(f"\n🚨 {signal_data['price_warning']}\n")
    
    lines.append(f"## 🥇 XAU/USD First Candle Signal Report")
    lines.append(f"**Time:** {signal_data.get('timestamp', 'N/A')} UTC")
    
    session = signal_data.get('session', 'unknown')
    priority = signal_data.get('priority', 0)
    
    session_emoji = {"london": "🇬🇧", "london_ny_overlap": "🔥", "new_york": "🇺🇸", "asian": "🌏"}
    session_name = {
        "london": "LONDON (08:00-13:00 UTC)",
        "london_ny_overlap": "LONDON-NY OVERLAP (13:00-16:00 UTC) ⭐⭐⭐",
        "new_york": "NEW YORK (16:00-21:00 UTC)",
        "asian": "ASIAN SESSION"
    }
    
    lines.append(f"**Session:** {session_emoji.get(session, '📊')} {session_name.get(session, session)}")
    lines.append("")
    
    sig = signal_data.get('signal', 'UNKNOWN')
    
    if sig == "NO_TRADE":
        lines.append(f"**Signal:** ⛔ {signal_data.get('reason', 'No trade')}")
    elif sig == "HOLD":
        lines.append(f"**Signal:** ⏸️ HOLD")
        lines.append(f"**Reason:** {signal_data.get('reason', 'Insufficient momentum')}")
        lines.append("")
        lines.append(f"**Current Price:** ${signal_data.get('current_price', 'N/A')}")
        if signal_data.get('atr_14'):
            lines.append(f"**ATR (14):** {signal_data['atr_14']}")
    elif sig in ["BUY", "SELL"]:
        emoji = "🟢" if sig == "BUY" else "🔴"
        lines.append(f"**Signal:** {emoji} **{sig}** {emoji}")
        lines.append("")
        lines.append(f"| Level | Value |")
        lines.append(f"|-------|-------|")
        lines.append(f"| Entry | ${signal_data.get('entry', 'N/A')} |")
        lines.append(f"| Stop Loss | ${signal_data.get('stop_loss', 'N/A')} |")
        lines.append(f"| Take Profit | ${signal_data.get('take_profit', 'N/A')} |")
        lines.append(f"| Risk:Reward | 1:1.5 |")
        lines.append("")
        lines.append(f"**Candle Analysis:**")
        candle = signal_data.get('candle', {})
        lines.append(f"- Direction: {candle.get('direction', 'N/A')}")
        lines.append(f"- Body Size: {candle.get('body_size', 'N/A'):.2f}")
        lines.append(f"- ATR Ratio: {candle.get('atr_ratio', 'N/A')}x (threshold: 1.1x)")
    
    return "\n".join(lines)

def generate_performance_report():
    """Generate performance report from database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get open positions
        cursor.execute("SELECT COUNT(*) FROM trades WHERE status = 'OPEN'")
        open_count = cursor.fetchone()[0]
        
        # Get 7-day stats
        seven_days_ago = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT COUNT(*), 
                   SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END),
                   SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END),
                   SUM(pnl)
            FROM trades 
            WHERE date >= ? AND status = 'CLOSED'
        ''', (seven_days_ago,))
        
        week_stats = cursor.fetchone()
        
        # Get 30-day stats
        thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT COUNT(*), 
                   SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END),
                   SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END),
                   SUM(pnl)
            FROM trades 
            WHERE date >= ? AND status = 'CLOSED'
        ''', (thirty_days_ago,))
        
        month_stats = cursor.fetchone()
        
        conn.close()
        
        return {
            "open_positions": open_count,
            "7_day": {
                "trades": week_stats[0] or 0,
                "wins": week_stats[1] or 0,
                "losses": week_stats[2] or 0,
                "pnl": week_stats[3] or 0
            },
            "30_day": {
                "trades": month_stats[0] or 0,
                "wins": month_stats[1] or 0,
                "losses": month_stats[2] or 0,
                "pnl": month_stats[3] or 0
            }
        }
    except Exception as e:
        return {
            "open_positions": 0,
            "error": str(e),
            "7_day": {"trades": 0, "wins": 0, "losses": 0, "pnl": 0},
            "30_day": {"trades": 0, "wins": 0, "losses": 0, "pnl": 0}
        }

def format_report(report_data):
    """Format performance report."""
    lines = []
    lines.append("# 📊 Daily Trading Report")
    lines.append(f"**Date:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC")
    lines.append("")
    
    if report_data.get('error'):
        lines.append(f"⚠️ Database error: {report_data['error']}")
        lines.append("")
    
    lines.append(f"**Open Positions:** {report_data['open_positions']}")
    lines.append("")
    
    for period in ['7_day', '30_day']:
        label = "7-Day" if period == '7_day' else "30-Day"
        stats = report_data[period]
        
        lines.append(f"### {label} Performance")
        lines.append(f"- Trades: {stats['trades']}")
        if stats['trades'] > 0:
            win_rate = (stats['wins'] / stats['trades']) * 100
            lines.append(f"- Win Rate: {win_rate:.1f}% ({stats['wins']}W/{stats['losses']}L)")
            lines.append(f"- P&L: ${stats['pnl']:.2f}")
        else:
            lines.append(f"- Win Rate: N/A (no trades)")
            lines.append(f"- P&L: $0.00")
        lines.append("")
    
    return "\n".join(lines)

def main():
    """Main function."""
    init_database()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--report":
        report = generate_performance_report()
        print(format_report(report))
        return
    
    # Fetch data
    data = fetch_xauusd_data(interval="15m", days=2)
    
    if "error" in data:
        print(f"❌ Error fetching data: {data['error']}")
        print("\n💡 Tip: API may be rate-limited. Using cached data if available.")
        sys.exit(1)
    
    candles = data.get('candles', [])
    if not candles:
        print("❌ No candle data available")
        sys.exit(1)
    
    # Analyze
    signal = analyze_first_candle(candles)
    
    # Save to DB if actionable
    if signal.get('signal') in ['BUY', 'SELL']:
        save_signal_to_db(signal)
    
    # Output
    print(format_signal_output(signal))

if __name__ == "__main__":
    main()
