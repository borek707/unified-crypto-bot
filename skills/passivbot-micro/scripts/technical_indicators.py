"""
TECHNICAL INDICATORS MODULE - Phase 2
=====================================
ADX, Multi-EMA, and other technical indicators for market classification
"""

from typing import List, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class TechnicalIndicators:
    """Technical indicators for market analysis (ADX, EMA, etc.)"""
    
    @staticmethod
    def calculate_ema(prices: List[float], period: int) -> List[float]:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return prices[:]
        
        ema = [sum(prices[:period]) / period]  # SMA for first value
        multiplier = 2 / (period + 1)
        
        for price in prices[period:]:
            ema.append((price - ema[-1]) * multiplier + ema[-1])
        
        # Pad with first value to match input length
        return [ema[0]] * (period - 1) + ema
    
    @staticmethod
    def calculate_adx(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        """
        Calculate Average Directional Index (ADX)
        Returns value between 0-100 (higher = stronger trend)
        """
        if len(closes) < period + 1:
            return 25.0  # Neutral default
        
        # Calculate True Range (TR)
        tr_list = []
        for i in range(1, len(closes)):
            high = highs[i]
            low = lows[i]
            prev_close = closes[i-1]
            
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_list.append(tr)
        
        # Calculate +DM and -DM
        plus_dm = []
        minus_dm = []
        
        for i in range(1, len(closes)):
            high_diff = highs[i] - highs[i-1]
            low_diff = lows[i-1] - lows[i]
            
            if high_diff > low_diff and high_diff > 0:
                plus_dm.append(high_diff)
            else:
                plus_dm.append(0)
            
            if low_diff > high_diff and low_diff > 0:
                minus_dm.append(low_diff)
            else:
                minus_dm.append(0)
        
        # Calculate smoothed averages
        if len(tr_list) < period:
            return 25.0
        
        atr = sum(tr_list[:period]) / period
        plus_di_sum = sum(plus_dm[:period])
        minus_di_sum = sum(minus_dm[:period])
        
        if atr == 0:
            return 25.0
        
        plus_di = 100 * plus_di_sum / (period * atr)
        minus_di = 100 * minus_di_sum / (period * atr)
        
        # Calculate DX and ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di) > 0 else 0
        
        return dx  # Simplified - full ADX would smooth this further
    
    @staticmethod
    def calculate_multi_ema_context(prices: List[float]) -> Dict[str, float]:
        """
        Calculate EMAs for multiple timeframes
        Returns context for market classification
        """
        # Convert to different timeframes (assuming 1-min data)
        # 48h = 2880 candles, 7d = 10080, 30d = 43200
        
        context = {}
        
        # 48h EMA (2 days)
        if len(prices) >= 2880:
            ema_48h = TechnicalIndicators.calculate_ema(prices[-2880:], 288)
            context['ema_48h'] = ema_48h[-1] if ema_48h else prices[-1]
            context['price_vs_ema48h'] = (prices[-1] - context['ema_48h']) / context['ema_48h']
        
        # 7d EMA
        if len(prices) >= 10080:
            ema_7d = TechnicalIndicators.calculate_ema(prices[-10080:], 1008)
            context['ema_7d'] = ema_7d[-1] if ema_7d else prices[-1]
            context['price_vs_ema7d'] = (prices[-1] - context['ema_7d']) / context['ema_7d']
        
        # 30d EMA
        if len(prices) >= 43200:
            ema_30d = TechnicalIndicators.calculate_ema(prices[-43200:], 4320)
            context['ema_30d'] = ema_30d[-1] if ema_30d else prices[-1]
            context['price_vs_ema30d'] = (prices[-1] - context['ema_30d']) / context['ema_30d']
        
        # Fallback to available data
        if not context:
            # Use shorter EMAs if not enough data
            ema_short = TechnicalIndicators.calculate_ema(prices, min(len(prices) // 10, 200))
            context['ema_short'] = ema_short[-1] if ema_short else prices[-1]
            context['price_vs_ema'] = (prices[-1] - context['ema_short']) / context['ema_short']
        
        return context


class MarketClassifier:
    """
    5-state market classifier with ADX and multi-EMA context
    """
    
    def __init__(self, config=None):
        self.config = config
        self.indicators = TechnicalIndicators()
    
    def classify(self, prices: List[float], highs: List[float] = None, lows: List[float] = None) -> str:
        """
        Classify market into 5 states:
        - strong_uptrend
        - pullback_uptrend
        - sideways
        - bear_rally
        - strong_downtrend
        """
        if len(prices) < 100:
            return 'sideways'
        
        # Calculate multi-EMA context
        ema_context = self.indicators.calculate_multi_ema_context(prices)
        
        # Calculate ADX for trend strength
        if highs and lows and len(highs) == len(prices):
            adx = self.indicators.calculate_adx(highs, lows, prices)
        else:
            # Approximate ADX from price changes
            adx = self._approximate_adx(prices)
        
        # Get price changes for different periods
        change_48h = self._get_price_change(prices, 2880)  # 48h
        change_7d = self._get_price_change(prices, 10080) if len(prices) >= 10080 else change_48h
        
        # Classification logic with ADX and multi-timeframe context
        return self._classify_with_context(change_48h, change_7d, adx, ema_context)
    
    def _get_price_change(self, prices: List[float], lookback: int) -> float:
        """Get price change over lookback period"""
        if len(prices) < lookback:
            lookback = len(prices) // 2
        
        if lookback < 10:
            return 0.0
        
        old_price = prices[-lookback]
        new_price = prices[-1]
        return (new_price - old_price) / old_price
    
    def _approximate_adx(self, prices: List[float]) -> float:
        """Approximate ADX from price series when highs/lows not available"""
        if len(prices) < 28:
            return 25.0
        
        # Calculate directional movement
        plus_dm = 0
        minus_dm = 0
        
        for i in range(-28, 0):
            if i < -1:
                change = prices[i] - prices[i-1]
                if change > 0:
                    plus_dm += change
                else:
                    minus_dm += abs(change)
        
        total = plus_dm + minus_dm
        if total == 0:
            return 25.0
        
        # Approximate DX
        dx = 100 * abs(plus_dm - minus_dm) / total
        return min(100, max(0, dx))
    
    def _classify_with_context(self, change_48h: float, change_7d: float, adx: float, ema_context: Dict) -> str:
        """Classify market using all context"""
        
        # Strong trend thresholds
        strong_threshold = 0.05  # 5%
        moderate_threshold = 0.025  # 2.5%
        
        # High ADX = strong trend (> 30)
        # Low ADX = weak trend/no trend (< 20)
        is_strong_trend = adx > 30
        is_weak_trend = adx < 20
        
        # Multi-timeframe alignment
        if 'price_vs_ema48h' in ema_context and 'price_vs_ema7d' in ema_context:
            ema48 = ema_context['price_vs_ema48h']
            ema7d = ema_context['price_vs_ema7d']
            
            # Both timeframes aligned up
            if ema48 > 0.03 and ema7d > 0.03 and is_strong_trend:
                return 'strong_uptrend'
            
            # Both timeframes aligned down
            if ema48 < -0.03 and ema7d < -0.03 and is_strong_trend:
                return 'strong_downtrend'
        
        # 48h-based classification with ADX context
        if change_48h > strong_threshold:
            if is_strong_trend:
                return 'strong_uptrend'
            else:
                return 'pullback_uptrend'
        
        elif change_48h < -strong_threshold:
            if is_strong_trend:
                return 'strong_downtrend'
            else:
                return 'bear_rally'
        
        elif change_48h > moderate_threshold and change_48h <= strong_threshold:
            return 'pullback_uptrend'
        
        elif change_48h < -moderate_threshold and change_48h >= -strong_threshold:
            return 'bear_rally'
        
        else:
            # Weak movement - sideways or transition
            if is_weak_trend:
                return 'sideways'
            elif change_48h > 0:
                return 'pullback_uptrend'
            else:
                return 'bear_rally'


if __name__ == "__main__":
    # Test
    import random
    prices = [100 + random.gauss(0, 1) for _ in range(3000)]
    classifier = MarketClassifier()
    result = classifier.classify(prices)
    print(f"Market classification: {result}")
