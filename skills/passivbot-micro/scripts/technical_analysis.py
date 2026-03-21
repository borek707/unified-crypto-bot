"""
TECHNICAL ANALYSIS MODULE
=========================
Modułowe wskaźniki TA dla strategii sideways.
Zoptymalizowane - bez heavy dependencies, używa numpy/pandas.
"""

import numpy as np
import pandas as pd
from typing import Tuple, List, Optional
from dataclasses import dataclass


@dataclass
class SignalResult:
    """Wynik sygnału tradingowego"""
    signal: str  # 'BUY', 'SELL', 'HOLD'
    strength: float  # 0.0 - 1.0
    reason: str
    indicators: dict


class TechnicalIndicators:
    """Wskaźniki techniczne bez pandas_ta - czysty numpy/pandas"""
    
    @staticmethod
    def ema(series: pd.Series, period: int) -> pd.Series:
        """Exponential Moving Average"""
        return series.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def sma(series: pd.Series, period: int) -> pd.Series:
        """Simple Moving Average"""
        return series.rolling(window=period).mean()
    
    @staticmethod
    def rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """Relative Strength Index"""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Average True Range"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        return tr.rolling(window=period).mean()
    
    @staticmethod
    def bollinger_bands(series: pd.Series, period: int = 20, std: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Bollinger Bands - zwraca (upper, middle, lower)"""
        middle = series.rolling(window=period).mean()
        std_dev = series.rolling(window=period).std()
        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)
        return upper, middle, lower
    
    @staticmethod
    def adx(df: pd.DataFrame, period: int = 14) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Average Directional Index - zwraca (adx, plus_di, minus_di)"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Directional Movement
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        plus_dm[plus_dm <= minus_dm] = 0
        minus_dm[minus_dm <= plus_dm] = 0
        
        # Smoothed
        atr = tr.rolling(window=period).mean()
        plus_di = 100 * plus_dm.rolling(window=period).mean() / atr
        minus_di = 100 * minus_dm.rolling(window=period).mean() / atr
        
        # ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()
        
        return adx, plus_di, minus_di
    
    @staticmethod
    def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """MACD - zwraca (macd, signal, histogram)"""
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram


class SidewaysIndicators:
    """Wskaźniki specjalnie dla strategii sideways"""
    
    @staticmethod
    def choppiness_index(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        Choppiness Index - wykrywa czy rynek jest w trendzie czy sideways.
        
        CI > 61.8 = Consolidation (sideways) - IDEALNE dla grid!
        CI < 38.2 = Trending - unikaj grid
        
        Wzór: CI = 100 * log10(n * sum(TR) / (HH - LL)) / log10(n)
        """
        high = df['high']
        low = df['low']
        close = df['close']
        
        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Sum TR over period
        sum_tr = tr.rolling(window=period).sum()
        
        # Highest high - Lowest low
        hh = high.rolling(window=period).max()
        ll = low.rolling(window=period).min()
        range_hl = hh - ll
        
        # Choppiness Index
        ci = 100 * np.log10(period * sum_tr / range_hl) / np.log10(period)
        
        return ci.fillna(50)  # Neutral default
    
    @staticmethod
    def keltner_channels(
        df: pd.DataFrame,
        ema_period: int = 20,
        atr_period: int = 10,
        atr_mult: float = 2.0
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Keltner Channels - świetne dla sideways trading.
        Cena w kanale = sideways (handluj)
        Przebicie kanału = trend (poczekaj)
        """
        ema = df['close'].ewm(span=ema_period, adjust=False).mean()
        atr = TechnicalIndicators.atr(df, atr_period)
        
        upper = ema + (atr * atr_mult)
        lower = ema - (atr * atr_mult)
        
        return upper, ema, lower
    
    @staticmethod
    def squeeze_momentum(
        df: pd.DataFrame,
        bb_period: int = 20,
        bb_std: float = 2.0,
        kc_mult: float = 1.5
    ) -> Tuple[pd.Series, pd.Series]:
        """
        TTM Squeeze - wykrywa okresy niskiej volatility przed breakout.
        
        Squeeze ON (True) = konsolidacja, niska volatility (handluj sideways)
        Squeeze OFF (False) = wysoka volatility, potencjalny breakout (czekaj)
        
        Zwraca: (squeeze_on, momentum)
        """
        close = df['close']
        high = df['high']
        low = df['low']
        
        # Bollinger Bands
        bb_mid = close.rolling(window=bb_period).mean()
        bb_std_dev = close.rolling(window=bb_period).std()
        bb_upper = bb_mid + bb_std_dev * bb_std
        bb_lower = bb_mid - bb_std_dev * bb_std
        
        # Keltner Channels (węższe)
        atr = TechnicalIndicators.atr(df, 14)
        kc_upper = bb_mid + atr * kc_mult
        kc_lower = bb_mid - atr * kc_mult
        
        # Squeeze condition - BB wewnątrz KC = low volatility
        squeeze_on = (bb_lower >= kc_lower) & (bb_upper <= kc_upper)
        
        # Momentum (simplified)
        highest = high.rolling(window=bb_period).max()
        lowest = low.rolling(window=bb_period).min()
        sma = close.rolling(window=bb_period).mean()
        
        # Linear regression approximation
        linreg_val = close - ((highest + lowest) / 2 + sma) / 2
        momentum = linreg_val.rolling(window=bb_period).mean()
        
        return squeeze_on, momentum
    
    @staticmethod
    def volume_profile(
        df: pd.DataFrame,
        bins: int = 20
    ) -> Tuple[np.ndarray, np.ndarray, float, List[float]]:
        """
        Volume Profile - identyfikuje poziomy z wysokim wolumenem.
        
        Zwraca:
        - prices: poziomy cenowe
        - volumes: wolumen na każdym poziomie
        - poc: Point of Control (najwyższy wolumen)
        - high_volume_levels: poziomy z wysokim wolumenem (S/R)
        """
        if 'volume' not in df.columns:
            return np.array([]), np.array([]), 0.0, []
        
        price_min = df['low'].min()
        price_max = df['high'].max()
        price_range = price_max - price_min
        
        if price_range == 0:
            return np.array([]), np.array([]), 0.0, []
        
        bin_size = price_range / bins
        volumes = np.zeros(bins)
        prices = np.linspace(price_min, price_max, bins)
        
        for idx, row in df.iterrows():
            low_bin = int((row['low'] - price_min) / bin_size)
            high_bin = int((row['high'] - price_min) / bin_size)
            
            low_bin = max(0, min(bins - 1, low_bin))
            high_bin = max(0, min(bins - 1, high_bin))
            
            if high_bin >= low_bin:
                vol_per_bin = row['volume'] / (high_bin - low_bin + 1)
                for i in range(low_bin, high_bin + 1):
                    volumes[i] += vol_per_bin
        
        # Point of Control
        poc_idx = np.argmax(volumes)
        poc = prices[poc_idx]
        
        # High volume levels (support/resistance)
        vol_threshold = volumes.mean() + volumes.std() * 0.5
        high_volume_levels = [
            prices[i] for i, vol in enumerate(volumes) 
            if vol > vol_threshold
        ]
        
        return prices, volumes, poc, high_volume_levels
    
    @staticmethod
    def vwap(df: pd.DataFrame) -> pd.Series:
        """
        VWAP (Volume Weighted Average Price).
        
        Cena powyżej VWAP = bullish bias
        Cena poniżej VWAP = bearish bias
        """
        if 'volume' not in df.columns:
            return df['close']
        
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        vwap = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
        return vwap
    
    @staticmethod
    def supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        SuperTrend - prosty wskaźnik trendu.
        Użyteczny do określenia kierunku w sideways.
        
        Zwraca: (supertrend, upper_band, lower_band)
        """
        atr = TechnicalIndicators.atr(df, period)
        hl2 = (df['high'] + df['low']) / 2
        
        upper_band = hl2 + multiplier * atr
        lower_band = hl2 - multiplier * atr
        
        supertrend = pd.Series(index=df.index, dtype=float)
        direction = pd.Series(index=df.index, dtype=int)
        
        for i in range(period, len(df)):
            if df['close'].iloc[i] > upper_band.iloc[i-1]:
                direction.iloc[i] = 1
                supertrend.iloc[i] = lower_band.iloc[i]
            elif df['close'].iloc[i] < lower_band.iloc[i-1]:
                direction.iloc[i] = -1
                supertrend.iloc[i] = upper_band.iloc[i]
            else:
                direction.iloc[i] = direction.iloc[i-1]
                if direction.iloc[i] == 1:
                    supertrend.iloc[i] = max(lower_band.iloc[i], supertrend.iloc[i-1])
                else:
                    supertrend.iloc[i] = min(upper_band.iloc[i], supertrend.iloc[i-1])
        
        return supertrend, upper_band, lower_band


class SidewaysAnalyzer:
    """Kompletna analiza dla strategii sideways"""
    
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.ti = TechnicalIndicators()
        self.si = SidewaysIndicators()
    
    def is_sideways_market(self, lookback: int = 50) -> Tuple[bool, float]:
        """
        Wielo-wskaźnikowa detekcja rynku sideways.
        Zwraca: (is_sideways, confidence)
        """
        if len(self.df) < lookback:
            return False, 0.0
        
        df = self.df.tail(lookback)
        scores = []
        
        # 1. Choppiness Index
        ci = self.si.choppiness_index(df)
        ci_val = ci.iloc[-1]
        if ci_val > 61.8:
            scores.append(1.0)
        elif ci_val > 50:
            scores.append(0.5)
        else:
            scores.append(0.0)
        
        # 2. ADX check (low ADX = sideways)
        adx, _, _ = self.ti.adx(df)
        adx_val = adx.iloc[-1]
        if adx_val < 20:
            scores.append(1.0)
        elif adx_val < 25:
            scores.append(0.5)
        else:
            scores.append(0.0)
        
        # 3. Bollinger Band Width (narrow = consolidation)
        upper, middle, lower = self.ti.bollinger_bands(df['close'])
        bbw = (upper - lower) / middle
        bbw_val = bbw.iloc[-1]
        bbw_mean = bbw.rolling(20).mean().iloc[-1]
        if bbw_val < bbw_mean * 0.7:
            scores.append(0.8)
        else:
            scores.append(0.3)
        
        # 4. Price range vs ATR
        atr = self.ti.atr(df)
        price_range = df['high'].max() - df['low'].min()
        atr_val = atr.iloc[-1]
        if atr_val > 0:
            range_atr_ratio = price_range / atr_val
            if range_atr_ratio < 5:
                scores.append(1.0)
            elif range_atr_ratio < 8:
                scores.append(0.5)
            else:
                scores.append(0.0)
        else:
            scores.append(0.5)
        
        # 5. EMA crossover count (few crosses = sideways)
        ema_9 = self.ti.ema(df['close'], 9)
        ema_21 = self.ti.ema(df['close'], 21)
        cross_diff = np.sign(ema_9 - ema_21).diff().fillna(0)
        crosses = (cross_diff != 0).sum()
        if crosses < 3:
            scores.append(1.0)
        elif crosses < 6:
            scores.append(0.5)
        else:
            scores.append(0.0)
        
        confidence = np.mean(scores)
        is_sideways = confidence > 0.6
        
        return is_sideways, confidence
    
    def get_optimal_grid_params(self) -> dict:
        """Oblicz optymalne parametry grid na podstawie warunków"""
        df = self.df
        
        # ATR dla spacing
        atr = self.ti.atr(df, 14).iloc[-1]
        price = df['close'].iloc[-1]
        atr_pct = atr / price if price > 0 else 0.01
        
        # Spacing = 0.8x ATR
        spacing = atr_pct * 0.8
        
        # Markup na podstawie volatility
        returns = df['close'].pct_change().dropna()
        volatility = returns.std() * np.sqrt(24)  # Daily vol
        
        if volatility > 0.05:  # High vol
            markup = atr_pct * 1.2
        elif volatility < 0.02:  # Low vol
            markup = atr_pct * 0.6
        else:
            markup = atr_pct * 0.9
        
        # Grid levels na podstawie range
        recent_range = df['high'].tail(48).max() - df['low'].tail(48).min()
        levels = int(recent_range / (atr * 2)) if atr > 0 else 3
        levels = max(3, min(6, levels))
        
        return {
            'spacing': round(spacing, 4),
            'markup': round(markup, 4),
            'grid_levels': levels,
            'atr': round(atr, 2),
            'volatility': round(volatility, 4)
        }
    
    def find_support_resistance(self, sensitivity: float = 0.02) -> Tuple[List[float], List[float]]:
        """Znajdź strefy support/resistance używając wielu metod"""
        df = self.df
        supports = []
        resistances = []
        
        # 1. Swing points
        for i in range(5, len(df) - 5):
            window_low = df['low'].iloc[i-5:i+6]
            window_high = df['high'].iloc[i-5:i+6]
            
            if df['low'].iloc[i] == window_low.min():
                supports.append(df['low'].iloc[i])
            if df['high'].iloc[i] == window_high.max():
                resistances.append(df['high'].iloc[i])
        
        # 2. Volume profile POC i high volume nodes
        if 'volume' in df.columns:
            _, _, poc, high_vol_levels = self.si.volume_profile(df.tail(100))
            for level in high_vol_levels:
                if level < df['close'].iloc[-1]:
                    supports.append(level)
                else:
                    resistances.append(level)
        
        # 3. Bollinger Band touches
        upper, _, lower = self.ti.bollinger_bands(df['close'])
        for i in range(20, len(df)):
            if df['low'].iloc[i] <= lower.iloc[i]:
                supports.append(df['low'].iloc[i])
            if df['high'].iloc[i] >= upper.iloc[i]:
                resistances.append(df['high'].iloc[i])
        
        # Cluster similar levels
        def cluster_levels(levels: List[float], tolerance: float = 0.01) -> List[float]:
            if not levels:
                return []
            levels = sorted(set([round(l, 2) for l in levels]))
            clusters = [[levels[0]]]
            
            for level in levels[1:]:
                if abs(level - clusters[-1][-1]) / clusters[-1][-1] < tolerance:
                    clusters[-1].append(level)
                else:
                    clusters.append([level])
            
            return [np.mean(cluster) for cluster in clusters]
        
        supports = cluster_levels(supports)
        resistances = cluster_levels(resistances)
        
        # Filter to nearest levels
        current_price = df['close'].iloc[-1]
        supports = [s for s in supports if s < current_price]
        resistances = [r for r in resistances if r > current_price]
        
        # Sort by proximity
        supports = sorted(supports, key=lambda x: current_price - x, reverse=True)[:5]
        resistances = sorted(resistances, key=lambda x: x - current_price)[:5]
        
        return supports, resistances
    
    def generate_signal(self) -> SignalResult:
        """Generuj sygnał wejścia z pełną analizą"""
        df = self.df
        
        # Check if sideways
        is_sideways, sideways_conf = self.is_sideways_market()
        
        if not is_sideways:
            return SignalResult(
                signal='HOLD',
                strength=0.0,
                reason=f"Not sideways (conf: {sideways_conf:.2f})",
                indicators={'sideways_confidence': sideways_conf}
            )
        
        # Get optimal params
        params = self.get_optimal_grid_params()
        
        # RSI
        rsi = self.ti.rsi(df['close']).iloc[-1]
        
        # Price position
        ema_20 = self.ti.ema(df['close'], 20).iloc[-1]
        price = df['close'].iloc[-1]
        
        # S/R levels
        supports, resistances = self.find_support_resistance()
        
        # Calculate signal
        signals = []
        reasons = []
        
        # RSI oversold (good for long)
        if rsi < 35:
            signals.append(0.8)
            reasons.append(f"RSI oversold ({rsi:.1f})")
        elif rsi > 65:
            signals.append(-0.3)
            reasons.append(f"RSI overbought ({rsi:.1f})")
        else:
            signals.append(0.5)
            reasons.append(f"RSI neutral ({rsi:.1f})")
        
        # Price near support
        if supports:
            nearest_support = supports[0]
            dist_to_support = (price - nearest_support) / price
            if dist_to_support < 0.01:
                signals.append(0.9)
                reasons.append(f"Near support ({nearest_support:.2f})")
            elif dist_to_support < 0.02:
                signals.append(0.7)
                reasons.append(f"Close to support ({nearest_support:.2f})")
        
        # Price near resistance
        if resistances:
            nearest_resistance = resistances[0]
            dist_to_resistance = (nearest_resistance - price) / price
            if dist_to_resistance < 0.01:
                signals.append(-0.5)
                reasons.append(f"Near resistance ({nearest_resistance:.2f})")
        
        # Price vs EMA
        if price < ema_20 * 0.99:
            signals.append(0.6)
            reasons.append("Below EMA20 (discount)")
        
        # Combine signals
        avg_signal = np.mean(signals) if signals else 0
        
        if avg_signal > 0.6:
            final_signal = 'BUY'
        elif avg_signal < -0.3:
            final_signal = 'SELL'
        else:
            final_signal = 'HOLD'
        
        return SignalResult(
            signal=final_signal,
            strength=min(1.0, abs(avg_signal)),
            reason=' | '.join(reasons),
            indicators={
                'rsi': rsi,
                'sideways_confidence': sideways_conf,
                'optimal_spacing': params['spacing'],
                'optimal_markup': params['markup'],
                'grid_levels': params['grid_levels'],
                'nearest_support': supports[0] if supports else None,
                'nearest_resistance': resistances[0] if resistances else None
            }
        )


def demo():
    """Demonstracja modułu TA"""
    import numpy as np
    
    # Generuj przykładowe dane sideways
    np.random.seed(42)
    n = 200
    base_price = 100
    
    # Symuluj rynek sideways
    prices = base_price + np.cumsum(np.random.randn(n) * 0.3)
    prices = prices - 0.03 * (prices - base_price)  # Mean reversion
    
    df = pd.DataFrame({
        'open': prices + np.random.rand(n) * 0.2,
        'high': prices + np.random.rand(n) * 0.5,
        'low': prices - np.random.rand(n) * 0.5,
        'close': prices,
        'volume': np.random.randint(1000, 5000, n)
    })
    
    # Analiza
    analyzer = SidewaysAnalyzer(df)
    
    print("=" * 50)
    print("SIDeways ANALYZER DEMO")
    print("=" * 50)
    
    # 1. Sideways detection
    is_sideways, conf = analyzer.is_sideways_market()
    print(f"\n1. Sideways Detection:")
    print(f"   Is Sideways: {is_sideways}")
    print(f"   Confidence: {conf:.2%}")
    
    # 2. Optimal params
    params = analyzer.get_optimal_grid_params()
    print(f"\n2. Optimal Grid Params:")
    print(f"   Spacing: {params['spacing']:.2%}")
    print(f"   Markup: {params['markup']:.2%}")
    print(f"   Levels: {params['grid_levels']}")
    print(f"   ATR: ${params['atr']:.2f}")
    
    # 3. Support/Resistance
    supports, resistances = analyzer.find_support_resistance()
    print(f"\n3. Support/Resistance:")
    print(f"   Supports: {[f'${s:.2f}' for s in supports[:3]]}")
    print(f"   Resistances: {[f'${r:.2f}' for r in resistances[:3]]}")
    
    # 4. Signal
    signal = analyzer.generate_signal()
    print(f"\n4. Trading Signal:")
    print(f"   Signal: {signal.signal}")
    print(f"   Strength: {signal.strength:.2f}")
    print(f"   Reason: {signal.reason}")
    print(f"\n   Indicators:")
    for k, v in signal.indicators.items():
        print(f"      {k}: {v}")
    
    print("\n" + "=" * 50)
    print("✅ Demo complete!")


if __name__ == "__main__":
    demo()
