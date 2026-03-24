"""
FLEXIBLE BOT - Dostosowuje się do dostępnych danych
==================================================
Dla różnych okresów używa różnych strategii:
- 1-7 dni: Price Action (support/resistance)
- 7-30 dni: EMA Cross (szybkie)
- 30-90 dni: RSI + EMA
- 90-200 dni: ADX + EMA
- 200+ dni: Pełny ADX
"""

from typing import List, Dict, Literal
import numpy as np

class FlexibleMarketClassifier:
    """Klasyfikator dostosowujący się do dostępnych danych"""
    
    def classify(self, prices: List[float]) -> Dict:
        """
        Wybiera strategię w zależności od ilości danych
        """
        n = len(prices)
        
        if n >= 200:
            # Pełny ADX dla długich okresów
            return self._classify_full(prices)
        elif n >= 90:
            # ADX uproszczony dla średnich
            return self._classify_medium(prices)
        elif n >= 30:
            # RSI + EMA dla krótkich
            return self._classify_short(prices)
        elif n >= 7:
            # Price action dla bardzo krótkich
            return self._classify_very_short(prices)
        else:
            # Za mało danych - neutralny
            return {'trend': 'sideways', 'confidence': 0.0}
    
    def _classify_full(self, prices: List[float]) -> Dict:
        """Pełny ADX + multi-EMA (200+ dni)"""
        # Tu wstaw obecną logikę ADX
        from technical_indicators import MarketClassifier
        mc = MarketClassifier(None)
        trend = mc.classify(prices)
        return {'trend': trend, 'confidence': 0.9, 'method': 'full_adx'}
    
    def _classify_medium(self, prices: List[float]) -> Dict:
        """Uproszczony ADX (90-200 dni)"""
        # Uproszczony ADX z mniejszym oknem
        ema_fast = np.mean(prices[-20:])
        ema_slow = np.mean(prices[-50:])
        
        if ema_fast > ema_slow * 1.02:
            trend = 'strong_uptrend'
        elif ema_fast < ema_slow * 0.98:
            trend = 'strong_downtrend'
        else:
            trend = 'sideways'
        
        return {'trend': trend, 'confidence': 0.7, 'method': 'simplified_adx'}
    
    def _classify_short(self, prices: List[float]) -> Dict:
        """RSI + EMA (30-90 dni)"""
        # EMA 10/20
        ema_10 = np.mean(prices[-10:])
        ema_20 = np.mean(prices[-20:])
        
        # RSI-like (zmiana ceny)
        gains = []
        losses = []
        for i in range(-14, 0):
            change = (prices[i] - prices[i-1]) / prices[i-1]
            if change > 0:
                gains.append(change)
            else:
                losses.append(abs(change))
        
        avg_gain = np.mean(gains) if gains else 0
        avg_loss = np.mean(losses) if losses else 0.001
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        # Decyzja
        if ema_10 > ema_20 and rsi > 50:
            trend = 'pullback_uptrend'
        elif ema_10 < ema_20 and rsi < 50:
            trend = 'bear_rally'
        else:
            trend = 'sideways'
        
        return {'trend': trend, 'confidence': 0.6, 'method': 'rsi_ema'}
    
    def _classify_very_short(self, prices: List[float]) -> Dict:
        """Price Action (7-30 dni)"""
        # Prosta analiza trendu
        recent = prices[-7:]
        first = np.mean(recent[:3])
        last = np.mean(recent[-3:])
        
        change = (last - first) / first
        
        if change > 0.03:  # +3%
            trend = 'strong_uptrend'
        elif change < -0.03:  # -3%
            trend = 'strong_downtrend'
        else:
            trend = 'sideways'
        
        return {'trend': trend, 'confidence': 0.5, 'method': 'price_action'}


# Strategie dla różnych okresów:
STRATEGIES = {
    7: {
        'name': 'Price Action',
        'entry': 'Breakout z 3-dniowego zakresu',
        'exit': 'Stop loss 2% / Target 4%',
        'max_positions': 2
    },
    30: {
        'name': 'EMA Cross',
        'entry': 'EMA 10 przecina EMA 20',
        'exit': 'EMA cross w drugą stronę',
        'max_positions': 3
    },
    90: {
        'name': 'RSI + EMA',
        'entry': 'RSI > 50 + EMA trend',
        'exit': 'RSI < 40 lub SL 3%',
        'max_positions': 4
    },
    200: {
        'name': 'ADX Trend Following',
        'entry': 'ADX > 25 + trend wzrostowy',
        'exit': 'ADX < 20 lub trailing stop',
        'max_positions': 5
    }
}

print("✅ FLEXIBLE BOT gotowy!")
print("\nDostępne strategie:")
for days, strat in STRATEGIES.items():
    print(f"  {days:3d}+ dni: {strat['name']}")
