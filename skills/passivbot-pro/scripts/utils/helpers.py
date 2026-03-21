"""
Utility Functions
=================
Helper functions for the trading bot.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Union
import json
from pathlib import Path


def format_usd(amount: float) -> str:
    """Format number as USD string."""
    if abs(amount) >= 1000:
        return f"${amount:,.2f}"
    elif abs(amount) >= 1:
        return f"${amount:.2f}"
    else:
        return f"${amount:.4f}"


def format_pct(value: float) -> str:
    """Format number as percentage string."""
    return f"{value * 100:.2f}%"


def calculate_sharpe_ratio(
    returns: np.ndarray,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 525600  # 1-minute data
) -> float:
    """
    Calculate annualized Sharpe ratio.
    
    Formula:
        sharpe = (mean_return - rf) / std_return * sqrt(periods_per_year)
    """
    if len(returns) == 0 or np.std(returns) == 0:
        return 0.0
    
    excess_returns = returns - risk_free_rate / periods_per_year
    return np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(periods_per_year)


def calculate_sortino_ratio(
    returns: np.ndarray,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 525600
) -> float:
    """
    Calculate Sortino ratio (downside deviation only).
    
    More relevant for trading strategies where we care about downside risk.
    """
    if len(returns) == 0:
        return 0.0
    
    excess_returns = returns - risk_free_rate / periods_per_year
    downside_returns = excess_returns[excess_returns < 0]
    
    if len(downside_returns) == 0:
        return float('inf')
    
    downside_std = np.std(downside_returns)
    if downside_std == 0:
        return 0.0
    
    return np.mean(excess_returns) / downside_std * np.sqrt(periods_per_year)


def calculate_max_drawdown(equity_curve: np.ndarray) -> Tuple[float, int]:
    """
    Calculate maximum drawdown and its duration.
    
    Returns:
        Tuple of (max_dd_pct, duration_in_periods)
    """
    if len(equity_curve) == 0:
        return 0.0, 0
    
    peak = equity_curve[0]
    max_dd = 0.0
    dd_start = 0
    max_duration = 0
    
    for i, equity in enumerate(equity_curve):
        if equity > peak:
            peak = equity
            dd_start = i
        else:
            dd = (peak - equity) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
            
            duration = i - dd_start
            if duration > max_duration:
                max_duration = duration
    
    return max_dd, max_duration


def calculate_calmar_ratio(
    annual_return: float,
    max_drawdown: float
) -> float:
    """
    Calculate Calmar ratio.
    
    Formula:
        calmar = annual_return / max_drawdown
    """
    if max_drawdown == 0:
        return float('inf')
    return annual_return / max_drawdown


def calculate_win_rate(trades: List[dict]) -> float:
    """Calculate win rate from trade list."""
    if not trades:
        return 0.0
    
    wins = sum(1 for t in trades if t.get('pnl', 0) > 0)
    return wins / len(trades)


def calculate_profit_factor(trades: List[dict]) -> float:
    """
    Calculate profit factor.
    
    Formula:
        pf = gross_profit / abs(gross_loss)
    """
    if not trades:
        return 1.0
    
    gross_profit = sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) > 0)
    gross_loss = abs(sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) < 0))
    
    if gross_loss == 0:
        return float('inf')
    
    return gross_profit / gross_loss


def calculate_expectancy(
    win_rate: float,
    avg_win: float,
    avg_loss: float
) -> float:
    """
    Calculate trade expectancy.
    
    Formula:
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * abs(avg_loss))
    """
    return (win_rate * avg_win) - ((1 - win_rate) * abs(avg_loss))


def calculate_kelly_fraction(
    win_rate: float,
    avg_win: float,
    avg_loss: float
) -> float:
    """
    Calculate Kelly fraction for position sizing.
    
    Formula:
        kelly = (p * b - q) / b
        
    where:
        p = win rate
        q = loss rate
        b = win/loss ratio
    """
    if avg_loss == 0:
        return 0.0
    
    b = avg_win / abs(avg_loss)
    p = win_rate
    q = 1 - win_rate
    
    kelly = (p * b - q) / b
    
    # Constrain to reasonable range
    return max(0.0, min(kelly, 0.25))  # Max 25% per Kelly


def time_to_timestamp(time: Union[datetime, str, int]) -> int:
    """Convert various time formats to millisecond timestamp."""
    if isinstance(time, int):
        return time
    elif isinstance(time, str):
        dt = pd.to_datetime(time)
        return int(dt.timestamp() * 1000)
    elif isinstance(time, datetime):
        return int(time.timestamp() * 1000)
    else:
        raise ValueError(f"Unknown time format: {type(time)}")


def timestamp_to_time(ts: int) -> datetime:
    """Convert millisecond timestamp to datetime."""
    return datetime.fromtimestamp(ts / 1000)


def resample_ohlcv(
    df: pd.DataFrame,
    target_timeframe: str
) -> pd.DataFrame:
    """
    Resample OHLCV data to different timeframe.
    
    Args:
        df: DataFrame with OHLCV columns and datetime index
        target_timeframe: Target timeframe ('5m', '15m', '1h', '4h', '1d')
    """
    agg_dict = {
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }
    
    return df.resample(target_timeframe).agg(agg_dict).dropna()


def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add common technical indicators to OHLCV DataFrame.
    
    Indicators added:
    - SMA (20, 50, 200)
    - EMA (12, 26)
    - RSI (14)
    - ATR (14)
    - Bollinger Bands
    - MACD
    """
    df = df.copy()
    
    # Simple Moving Averages
    df['sma_20'] = df['close'].rolling(20).mean()
    df['sma_50'] = df['close'].rolling(50).mean()
    df['sma_200'] = df['close'].rolling(200).mean()
    
    # Exponential Moving Averages
    df['ema_12'] = df['close'].ewm(span=12).mean()
    df['ema_26'] = df['close'].ewm(span=26).mean()
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # ATR
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = true_range.rolling(14).mean()
    
    # Bollinger Bands
    df['bb_middle'] = df['close'].rolling(20).mean()
    df['bb_std'] = df['close'].rolling(20).std()
    df['bb_upper'] = df['bb_middle'] + 2 * df['bb_std']
    df['bb_lower'] = df['bb_middle'] - 2 * df['bb_std']
    
    # MACD
    df['macd'] = df['ema_12'] - df['ema_26']
    df['macd_signal'] = df['macd'].ewm(span=9).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    
    return df


def generate_sample_data(
    n_candles: int = 10000,
    start_price: float = 50000.0,
    volatility: float = 0.02,
    drift: float = 0.0001,
    seed: Optional[int] = None
) -> pd.DataFrame:
    """
    Generate sample OHLCV data for testing.
    
    Uses geometric Brownian motion model.
    """
    if seed is not None:
        np.random.seed(seed)
    
    # Generate timestamps
    start_time = datetime.now() - timedelta(minutes=n_candles)
    timestamps = pd.date_range(start=start_time, periods=n_candles, freq='1min')
    
    # Generate price path (GBM)
    returns = np.random.normal(drift, volatility, n_candles)
    prices = start_price * np.exp(np.cumsum(returns))
    
    # Generate OHLCV
    df = pd.DataFrame(index=timestamps)
    df['close'] = prices
    
    # Generate realistic OHLC
    intra_candle_range = volatility * prices * 0.3
    df['high'] = df['close'] + np.abs(np.random.normal(0, intra_candle_range))
    df['low'] = df['close'] - np.abs(np.random.normal(0, intra_candle_range))
    df['open'] = df['close'].shift(1).fillna(start_price)
    
    # Ensure OHLC consistency
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)
    
    # Volume
    df['volume'] = np.random.exponential(100, n_candles) * (1 + volatility * 10)
    
    return df


def save_backtest_results(
    results: dict,
    output_path: str
):
    """Save backtest results to JSON file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, 'w') as f:
        json.dump(results, f, indent=2, default=str)


def load_backtest_results(input_path: str) -> dict:
    """Load backtest results from JSON file."""
    with open(input_path) as f:
        return json.load(f)
