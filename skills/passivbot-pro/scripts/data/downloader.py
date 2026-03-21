"""
Data Downloader Module
======================
Async data collection from Hyperliquid, Bybit, and Binance.
Supports historical OHLCV, L2 Order Book, and Trade streams.
"""

import asyncio
import aiohttp
import pandas as pd
import numpy as np
from typing import Optional, AsyncIterator
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger
import pyarrow as pa
import pyarrow.parquet as pq
from abc import ABC, abstractmethod
import json
import time

from ..config.settings import ExchangeType, config


# ============================================================
# BASE DATA PROVIDER
# ============================================================
class DataProvider(ABC):
    """Abstract base class for exchange data providers."""
    
    @abstractmethod
    async def fetch_ohlcv(
        self, 
        symbol: str, 
        timeframe: str = "1m",
        since: Optional[int] = None,
        limit: int = 1000
    ) -> pd.DataFrame:
        """Fetch OHLCV candlestick data."""
        pass
    
    @abstractmethod
    async def fetch_orderbook(self, symbol: str, depth: int = 20) -> dict:
        """Fetch L2 order book."""
        pass
    
    @abstractmethod
    async def fetch_trades(
        self, 
        symbol: str, 
        since: Optional[int] = None,
        limit: int = 1000
    ) -> pd.DataFrame:
        """Fetch recent trades."""
        pass
    
    @abstractmethod
    async def subscribe_trades(self, symbol: str) -> AsyncIterator[dict]:
        """Subscribe to real-time trade stream."""
        pass
    
    @abstractmethod
    async def subscribe_orderbook(self, symbol: str) -> AsyncIterator[dict]:
        """Subscribe to real-time order book updates."""
        pass


# ============================================================
# HYPERLIQUID DATA PROVIDER
# ============================================================
class HyperliquidProvider(DataProvider):
    """
    Hyperliquid-specific data provider.
    
    Hyperliquid API endpoints:
    - REST: https://api.hyperliquid.xyz
    - WebSocket: wss://api.hyperliquid.xyz/ws
    
    Advantages for micro-accounts:
    - Lowest maker fees in the industry (0.02%)
    - No gas fees for trading
    - HLP (Hyperliquid Points) rewards
    - Excellent liquidity for major pairs
    """
    
    API_URL = "https://api.hyperliquid.xyz"
    WS_URL = "wss://api.hyperliquid.xyz/ws"
    
    def __init__(self, testnet: bool = False):
        self.testnet = testnet
        if testnet:
            self.API_URL = "https://api.hyperliquid-testnet.xyz"
            self.WS_URL = "wss://api.hyperliquid-testnet.xyz/ws"
        
        self.session: Optional[aiohttp.ClientSession] = None
        self._request_count = 0
        self._last_request_time = 0.0
        
    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure aiohttp session is active."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={"Content-Type": "application/json"}
            )
        return self.session
    
    async def _rate_limit(self, requests_per_second: int = 10):
        """Simple rate limiting."""
        min_interval = 1.0 / requests_per_second
        elapsed = time.time() - self._last_request_time
        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)
        self._last_request_time = time.time()
    
    async def _post(self, endpoint: str, payload: dict) -> dict:
        """Make POST request to Hyperliquid API."""
        await self._rate_limit()
        session = await self._ensure_session()
        
        url = f"{self.API_URL}{endpoint}"
        async with session.post(url, json=payload) as response:
            response.raise_for_status()
            return await response.json()
    
    def _normalize_symbol(self, symbol: str) -> str:
        """Convert CCXT symbol format to Hyperliquid format.
        
        Examples:
            BTC/USDC:USDC -> BTC
            ETH/USDC:USDC -> ETH
        """
        # Hyperliquid uses just the base asset for perps
        base = symbol.split("/")[0]
        return base
    
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1m",
        since: Optional[int] = None,
        limit: int = 1000
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV data from Hyperliquid.
        
        Hyperliquid returns data in format:
        {
            "t": timestamp_ms,
            "o": open,
            "h": high,
            "l": low,
            "c": close,
            "v": volume
        }
        """
        coin = self._normalize_symbol(symbol)
        
        # Map timeframe to interval
        interval_map = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "1h": "1h",
            "4h": "4h",
            "1d": "1d"
        }
        interval = interval_map.get(timeframe, "1m")
        
        # Calculate start time if not provided
        if since is None:
            # Default to lookback_days from config
            since = int((datetime.now() - timedelta(days=config.backtest.lookback_days)).timestamp() * 1000)
        
        payload = {
            "type": "candleSnapshot",
            "req": {
                "coin": coin,
                "interval": interval,
                "startTime": since,
                "endTime": int(datetime.now().timestamp() * 1000)
            }
        }
        
        try:
            data = await self._post("/info", payload)
            
            if not data or "error" in data:
                logger.error(f"Hyperliquid API error: {data}")
                return pd.DataFrame()
            
            # Parse response
            candles = []
            for candle in data:
                candles.append({
                    "timestamp": pd.to_datetime(candle["t"], unit="ms"),
                    "open": float(candle["o"]),
                    "high": float(candle["h"]),
                    "low": float(candle["l"]),
                    "close": float(candle["c"]),
                    "volume": float(candle["v"])
                })
            
            df = pd.DataFrame(candles)
            if not df.empty:
                df.set_index("timestamp", inplace=True)
                df.sort_index(inplace=True)
            
            logger.info(f"Fetched {len(df)} candles for {coin}")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching OHLCV: {e}")
            return pd.DataFrame()
    
    async def fetch_orderbook(self, symbol: str, depth: int = 20) -> dict:
        """Fetch L2 order book snapshot."""
        coin = self._normalize_symbol(symbol)
        
        payload = {
            "type": "l2Book",
            "coin": coin
        }
        
        try:
            data = await self._post("/info", payload)
            
            if not data or "levels" not in data:
                logger.error(f"Order book error: {data}")
                return {"bids": [], "asks": []}
            
            # Parse bids and asks
            bids = [[float(level["px"]), float(level["sz"])] for level in data["levels"][0][:depth]]
            asks = [[float(level["px"]), float(level["sz"])] for level in data["levels"][1][:depth]]
            
            return {
                "bids": bids,
                "asks": asks,
                "timestamp": datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Error fetching order book: {e}")
            return {"bids": [], "asks": []}
    
    async def fetch_trades(
        self,
        symbol: str,
        since: Optional[int] = None,
        limit: int = 1000
    ) -> pd.DataFrame:
        """Fetch recent public trades."""
        coin = self._normalize_symbol(symbol)
        
        payload = {
            "type": "recentTrades",
            "coin": coin,
            "limit": limit
        }
        
        try:
            data = await self._post("/info", payload)
            
            if not data:
                return pd.DataFrame()
            
            trades = []
            for trade in data:
                trades.append({
                    "timestamp": pd.to_datetime(trade["time"], unit="ms"),
                    "price": float(trade["px"]),
                    "size": float(trade["sz"]),
                    "side": "buy" if trade["side"] == "B" else "sell",
                    "hash": trade.get("hash", "")
                })
            
            df = pd.DataFrame(trades)
            if not df.empty:
                df.set_index("timestamp", inplace=True)
                df.sort_index(inplace=True)
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching trades: {e}")
            return pd.DataFrame()
    
    async def fetch_funding_rate(self, symbol: str) -> dict:
        """Fetch current funding rate."""
        coin = self._normalize_symbol(symbol)
        
        payload = {
            "type": "meta"
        }
        
        try:
            data = await self._post("/info", payload)
            
            if not data or "universe" not in data:
                return {"funding_rate": 0.0, "next_funding_time": None}
            
            # Find the coin in universe
            for asset in data["universe"]:
                if asset["name"] == coin:
                    return {
                        "funding_rate": float(asset.get("funding", 0)),
                        "next_funding_time": datetime.now() + timedelta(hours=8)
                    }
            
            return {"funding_rate": 0.0, "next_funding_time": None}
            
        except Exception as e:
            logger.error(f"Error fetching funding rate: {e}")
            return {"funding_rate": 0.0, "next_funding_time": None}
    
    async def subscribe_trades(self, symbol: str) -> AsyncIterator[dict]:
        """Subscribe to real-time trade stream via WebSocket."""
        coin = self._normalize_symbol(symbol)
        
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(self.WS_URL) as ws:
                # Subscribe to trades
                subscribe_msg = {
                    "method": "subscribe",
                    "subscription": {
                        "type": "trades",
                        "coin": coin
                    }
                }
                await ws.send_json(subscribe_msg)
                
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        if "channel" in data and data["channel"] == "trades":
                            for trade in data.get("data", []):
                                yield {
                                    "timestamp": datetime.now(),
                                    "price": float(trade["px"]),
                                    "size": float(trade["sz"]),
                                    "side": "buy" if trade["side"] == "B" else "sell"
                                }
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        logger.error(f"WebSocket error: {ws.exception()}")
                        break
    
    async def subscribe_orderbook(self, symbol: str) -> AsyncIterator[dict]:
        """Subscribe to real-time L2 order book updates."""
        coin = self._normalize_symbol(symbol)
        
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(self.WS_URL) as ws:
                subscribe_msg = {
                    "method": "subscribe",
                    "subscription": {
                        "type": "l2Book",
                        "coin": coin
                    }
                }
                await ws.send_json(subscribe_msg)
                
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        if "channel" in data and data["channel"] == "l2Book":
                            book = data.get("data", {})
                            yield {
                                "bids": [[float(l["px"]), float(l["sz"])] for l in book.get("levels", [[], []])[0]],
                                "asks": [[float(l["px"]), float(l["sz"])] for l in book.get("levels", [[], []])[1]],
                                "timestamp": datetime.now()
                            }
    
    async def close(self):
        """Close the session."""
        if self.session and not self.session.closed:
            await self.session.close()


# ============================================================
# BYBIT DATA PROVIDER
# ============================================================
class BybitProvider(DataProvider):
    """
    Bybit V5 API data provider.
    
    Bybit API endpoints:
    - REST: https://api.bybit.com
    - WebSocket: wss://stream.bybit.com/v5/public/linear
    """
    
    API_URL = "https://api.bybit.com"
    WS_URL = "wss://stream.bybit.com/v5/public/linear"
    
    def __init__(self, testnet: bool = False):
        self.testnet = testnet
        if testnet:
            self.API_URL = "https://api-testnet.bybit.com"
            self.WS_URL = "wss://stream-testnet.bybit.com/v5/public/linear"
        
        self.session: Optional[aiohttp.ClientSession] = None
        self._last_request_time = 0.0
    
    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def _rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < 0.1:
            await asyncio.sleep(0.1 - elapsed)
        self._last_request_time = time.time()
    
    def _normalize_symbol(self, symbol: str) -> str:
        """Convert CCXT symbol format to Bybit format."""
        # BTC/USDC:USDC -> BTCUSDT
        base, quote = symbol.split("/")
        quote = quote.split(":")[0]
        return f"{base}{quote}"
    
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1m",
        since: Optional[int] = None,
        limit: int = 1000
    ) -> pd.DataFrame:
        """Fetch historical OHLCV from Bybit."""
        await self._rate_limit()
        session = await self._ensure_session()
        
        sym = self._normalize_symbol(symbol)
        url = f"{self.API_URL}/v5/market/kline"
        
        params = {
            "category": "linear",
            "symbol": sym,
            "interval": timeframe,
            "limit": limit
        }
        
        if since:
            params["start"] = since
        
        try:
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()
            
            if data.get("retCode") != 0:
                logger.error(f"Bybit API error: {data}")
                return pd.DataFrame()
            
            # Bybit returns: [startTime, openPrice, highPrice, lowPrice, closePrice, volume, turnover]
            candles = []
            for candle in data["result"]["list"]:
                candles.append({
                    "timestamp": pd.to_datetime(int(candle[0]), unit="ms"),
                    "open": float(candle[1]),
                    "high": float(candle[2]),
                    "low": float(candle[3]),
                    "close": float(candle[4]),
                    "volume": float(candle[5])
                })
            
            df = pd.DataFrame(candles)
            if not df.empty:
                df.set_index("timestamp", inplace=True)
                df.sort_index(inplace=True)
            
            logger.info(f"Fetched {len(df)} candles from Bybit for {sym}")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching Bybit OHLCV: {e}")
            return pd.DataFrame()
    
    async def fetch_orderbook(self, symbol: str, depth: int = 20) -> dict:
        """Fetch order book from Bybit."""
        await self._rate_limit()
        session = await self._ensure_session()
        
        sym = self._normalize_symbol(symbol)
        url = f"{self.API_URL}/v5/market/orderbook"
        
        params = {
            "category": "linear",
            "symbol": sym,
            "limit": depth
        }
        
        try:
            async with session.get(url, params=params) as response:
                data = await response.json()
            
            if data.get("retCode") != 0:
                return {"bids": [], "asks": []}
            
            return {
                "bids": [[float(b[0]), float(b[1])] for b in data["result"]["b"]],
                "asks": [[float(a[0]), float(a[1])] for a in data["result"]["a"]],
                "timestamp": datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Error fetching Bybit orderbook: {e}")
            return {"bids": [], "asks": []}
    
    async def fetch_trades(
        self,
        symbol: str,
        since: Optional[int] = None,
        limit: int = 1000
    ) -> pd.DataFrame:
        """Fetch recent trades from Bybit."""
        await self._rate_limit()
        session = await self._ensure_session()
        
        sym = self._normalize_symbol(symbol)
        url = f"{self.API_URL}/v5/market/recent-trade"
        
        params = {
            "category": "linear",
            "symbol": sym,
            "limit": limit
        }
        
        try:
            async with session.get(url, params=params) as response:
                data = await response.json()
            
            if data.get("retCode") != 0:
                return pd.DataFrame()
            
            trades = []
            for t in data["result"]["list"]:
                trades.append({
                    "timestamp": pd.to_datetime(int(t["time"]), unit="ms"),
                    "price": float(t["price"]),
                    "size": float(t["size"]),
                    "side": t["side"].lower()
                })
            
            df = pd.DataFrame(trades)
            if not df.empty:
                df.set_index("timestamp", inplace=True)
                df.sort_index(inplace=True)
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching Bybit trades: {e}")
            return pd.DataFrame()
    
    async def subscribe_trades(self, symbol: str) -> AsyncIterator[dict]:
        """Subscribe to Bybit trade stream."""
        sym = self._normalize_symbol(symbol)
        
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(self.WS_URL) as ws:
                subscribe_msg = {
                    "op": "subscribe",
                    "args": [f"publicTrade.{sym}"]
                }
                await ws.send_json(subscribe_msg)
                
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        if "topic" in data and "publicTrade" in data["topic"]:
                            for trade in data.get("data", []):
                                yield {
                                    "timestamp": datetime.now(),
                                    "price": float(trade["p"]),
                                    "size": float(trade["v"]),
                                    "side": trade["S"].lower()
                                }
    
    async def subscribe_orderbook(self, symbol: str) -> AsyncIterator[dict]:
        """Subscribe to Bybit order book stream."""
        sym = self._normalize_symbol(symbol)
        
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(self.WS_URL) as ws:
                subscribe_msg = {
                    "op": "subscribe",
                    "args": [f"orderbook.50.{sym}"]
                }
                await ws.send_json(subscribe_msg)
                
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        if "topic" in data and "orderbook" in data["topic"]:
                            book = data.get("data", {})
                            yield {
                                "bids": [[float(b[0]), float(b[1])] for b in book.get("b", [])],
                                "asks": [[float(a[0]), float(a[1])] for a in book.get("a", [])],
                                "timestamp": datetime.now()
                            }
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()


# ============================================================
# DATA DOWNLOADER (MAIN CLASS)
# ============================================================
class DataDownloader:
    """
    Main Data Downloader class.
    
    Coordinates data fetching from multiple exchanges.
    Implements caching with Parquet for fast optimization access.
    """
    
    def __init__(
        self,
        exchange: ExchangeType = ExchangeType.HYPERLIQUID,
        testnet: bool = False,
        cache_dir: str = "/home/z/my-project/trading_bot/data/cache"
    ):
        self.exchange = exchange
        self.testnet = testnet
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize provider
        self.provider: DataProvider
        if exchange == ExchangeType.HYPERLIQUID:
            self.provider = HyperliquidProvider(testnet=testnet)
        elif exchange == ExchangeType.BYBIT:
            self.provider = BybitProvider(testnet=testnet)
        else:
            raise ValueError(f"Unsupported exchange: {exchange}")
    
    def _cache_path(self, symbol: str, data_type: str, timeframe: str = "1m") -> Path:
        """Generate cache file path."""
        safe_symbol = symbol.replace("/", "_").replace(":", "_")
        return self.cache_dir / f"{safe_symbol}_{data_type}_{timeframe}.parquet"
    
    def _save_to_parquet(self, df: pd.DataFrame, path: Path):
        """Save DataFrame to Parquet with compression."""
        if df.empty:
            return
        
        # Reset index for proper storage
        df_to_save = df.reset_index()
        
        # Use snappy compression for speed
        table = pa.Table.from_pandas(df_to_save)
        pq.write_table(table, path, compression='snappy')
        logger.debug(f"Saved {len(df)} rows to {path}")
    
    def _load_from_parquet(self, path: Path) -> Optional[pd.DataFrame]:
        """Load DataFrame from Parquet cache."""
        if not path.exists():
            return None
        
        try:
            table = pq.read_table(path)
            df = table.to_pandas()
            
            if 'timestamp' in df.columns:
                df.set_index('timestamp', inplace=True)
            
            logger.debug(f"Loaded {len(df)} rows from cache")
            return df
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
            return None
    
    async def download_historical(
        self,
        symbol: str,
        timeframe: str = "1m",
        days: int = 90,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Download historical OHLCV data.
        
        For 90 days of 1m data:
        - Approximately 129,600 candles
        - Cache size: ~5-10MB per symbol
        """
        cache_path = self._cache_path(symbol, "ohlcv", timeframe)
        
        # Check cache first
        if use_cache:
            cached = self._load_from_parquet(cache_path)
            if cached is not None and not cached.empty:
                # Check if cache is recent enough
                cache_age = datetime.now() - cached.index[-1].to_pydatetime()
                if cache_age < timedelta(hours=1):
                    logger.info(f"Using cached data for {symbol}")
                    return cached
        
        # Download in chunks (exchanges typically limit to ~1000 candles per request)
        all_candles = []
        since = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
        
        logger.info(f"Downloading {days} days of {timeframe} data for {symbol}...")
        
        total_candles = 0
        batch_size = 1000
        
        while total_candles < days * 24 * 60:  # Max candles for 1m data
            df = await self.provider.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                since=since,
                limit=batch_size
            )
            
            if df.empty:
                break
            
            all_candles.append(df)
            total_candles += len(df)
            
            # Update since for next batch
            since = int(df.index[-1].timestamp() * 1000) + 60000  # +1 minute
            
            # Rate limiting
            await asyncio.sleep(0.2)
            
            if len(df) < batch_size:
                break
        
        if not all_candles:
            return pd.DataFrame()
        
        # Combine all candles
        combined = pd.concat(all_candles)
        combined = combined[~combined.index.duplicated(keep='first')]
        combined.sort_index(inplace=True)
        
        # Save to cache
        self._save_to_parquet(combined, cache_path)
        
        logger.info(f"Downloaded {len(combined)} candles for {symbol}")
        return combined
    
    async def download_orderbook_snapshot(self, symbol: str) -> dict:
        """Download current order book state."""
        return await self.provider.fetch_orderbook(symbol, depth=50)
    
    async def stream_trades(self, symbol: str):
        """Stream real-time trades."""
        async for trade in self.provider.subscribe_trades(symbol):
            yield trade
    
    async def stream_orderbook(self, symbol: str):
        """Stream real-time order book updates."""
        async for update in self.provider.subscribe_orderbook(symbol):
            yield update
    
    async def close(self):
        """Cleanup resources."""
        await self.provider.close()


# ============================================================
# BATCH DOWNLOADER FOR MULTIPLE SYMBOLS
# ============================================================
class BatchDataDownloader:
    """
    Batch download data for multiple symbols concurrently.
    Utilizes the 26GB RAM for parallel downloads.
    """
    
    def __init__(self, exchange: ExchangeType = ExchangeType.HYPERLIQUID):
        self.exchange = exchange
    
    async def download_all(
        self,
        symbols: list[str],
        timeframe: str = "1m",
        days: int = 90
    ) -> dict[str, pd.DataFrame]:
        """Download data for all symbols concurrently."""
        
        results = {}
        
        async def download_one(symbol: str) -> tuple[str, pd.DataFrame]:
            downloader = DataDownloader(exchange=self.exchange)
            try:
                df = await downloader.download_historical(symbol, timeframe, days)
                return symbol, df
            finally:
                await downloader.close()
        
        # Use semaphore to limit concurrent connections
        semaphore = asyncio.Semaphore(3)  # Max 3 concurrent downloads
        
        async def limited_download(symbol: str):
            async with semaphore:
                return await download_one(symbol)
        
        # Run all downloads
        tasks = [limited_download(s) for s in symbols]
        completed = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in completed:
            if isinstance(result, Exception):
                logger.error(f"Download failed: {result}")
            else:
                symbol, df = result
                if not df.empty:
                    results[symbol] = df
        
        logger.info(f"Downloaded data for {len(results)}/{len(symbols)} symbols")
        return results


# ============================================================
# UTILITY FUNCTIONS
# ============================================================
def estimate_cache_size(symbols: int, days: int = 90) -> str:
    """Estimate RAM/disk usage for cached data."""
    # Each 1m candle: ~48 bytes (OHLCV as float64)
    candles_per_day = 1440
    bytes_per_candle = 48
    
    total_bytes = symbols * days * candles_per_day * bytes_per_candle
    
    # With Parquet compression (roughly 3:1 ratio)
    compressed = total_bytes / 3
    
    if compressed < 1024:
        return f"{compressed:.0f} bytes"
    elif compressed < 1024 * 1024:
        return f"{compressed / 1024:.1f} KB"
    elif compressed < 1024 * 1024 * 1024:
        return f"{compressed / (1024 * 1024):.1f} MB"
    else:
        return f"{compressed / (1024 * 1024 * 1024):.1f} GB"
