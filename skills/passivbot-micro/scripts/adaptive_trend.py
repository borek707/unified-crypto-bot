#!/usr/bin/env python3
"""
ADAPTIVE TREND MODULE - Phase 2 Enhanced
========================================
Porównuje trendy na wielu timeframe (3, 6, 7, 10, 14, 30 dni)
Dostosowuje się do dostępnych danych
"""

import numpy as np
from typing import List, Dict, Tuple
from dataclasses import dataclass

@dataclass
class TrendAnalysis:
    timeframe: str
    days: int
    trend: str
    strength: float
    ema_fast: float
    ema_slow: float
    price_change: float
    confidence: float

class AdaptiveTrendDetector:
    """
    Wykrywa trendy porównując multiple timeframes
    """
    
    TIMEFRAMES = [
        (3, "3d"),
        (6, "6d"), 
        (7, "1w"),
        (10, "10d"),
        (14, "2w"),
        (30, "1m"),
    ]
    
    def analyze(self, prices: List[float]) -> Dict:
        """
        Analizuje wszystkie dostępne timeframe
        """
        analyses = []
        
        for days, label in self.TIMEFRAMES:
            if len(prices) >= days:
                analysis = self._analyze_single(prices, days, label)
                analyses.append(analysis)
        
        if not analyses:
            return {
                'primary_trend': 'insufficient_data',
                'trend_strength': 0.0,
                'timeframes_analyzed': 0,
                'analyses': []
            }
        
        # Konsensus z wszystkich timeframe
        consensus = self._calculate_consensus(analyses)
        
        return {
            'primary_trend': consensus['trend'],
            'trend_strength': consensus['strength'],
            'timeframes_analyzed': len(analyses),
            'analyses': analyses,
            'consensus_score': consensus['score'],
            'recommendation': consensus['recommendation']
        }
    
    def _analyze_single(self, prices: List[float], days: int, label: str) -> TrendAnalysis:
        """Analizuje pojedynczy timeframe"""
        period = prices[-days:]
        
        # EMAs
        ema_3 = np.mean(period[-3:]) if len(period) >= 3 else period[-1]
        ema_full = np.mean(period)
        
        # Price change
        price_change = (period[-1] - period[0]) / period[0]
        
        # Trend
        if ema_3 > ema_full * 1.01 and price_change > 0.02:
            trend = 'strong_uptrend'
            strength = min(abs(price_change) * 100, 1.0)
        elif ema_3 > ema_full * 1.005 and price_change > 0:
            trend = 'uptrend'
            strength = min(abs(price_change) * 100, 0.7)
        elif ema_3 < ema_full * 0.99 and price_change < -0.02:
            trend = 'strong_downtrend'
            strength = min(abs(price_change) * 100, 1.0)
        elif ema_3 < ema_full * 0.995 and price_change < 0:
            trend = 'downtrend'
            strength = min(abs(price_change) * 100, 0.7)
        else:
            trend = 'sideways'
            strength = 0.3
        
        # Confidence based on data length
        confidence = min(len(period) / days, 1.0)
        
        return TrendAnalysis(
            timeframe=label,
            days=days,
            trend=trend,
            strength=strength,
            ema_fast=ema_3,
            ema_slow=ema_full,
            price_change=price_change,
            confidence=confidence
        )
    
    def _calculate_consensus(self, analyses: List[TrendAnalysis]) -> Dict:
        """Oblicza konsensus ze wszystkich timeframe"""
        
        trends = [a.trend for a in analyses]
        strengths = [a.strength for a in analyses]
        
        # Zlicz trendy
        trend_counts = {}
        for t in trends:
            trend_counts[t] = trend_counts.get(t, 0) + 1
        
        # Najczęstszy trend
        primary_trend = max(trend_counts, key=trend_counts.get)
        consensus_score = trend_counts[primary_trend] / len(trends)
        
        # Średnia siła
        avg_strength = np.mean(strengths)
        
        # Rekomendacja
        if consensus_score >= 0.7 and avg_strength > 0.5:
            recommendation = 'enter'
        elif consensus_score >= 0.5 and primary_trend in ['uptrend', 'strong_uptrend']:
            recommendation = 'consider'
        else:
            recommendation = 'wait'
        
        return {
            'trend': primary_trend,
            'strength': avg_strength,
            'score': consensus_score,
            'recommendation': recommendation
        }


def test_bear_market():
    """Testuje na danych bear market"""
    import json
    
    with open('/tmp/hyperliquid_daily_big.json', 'r') as f:
        prices = json.load(f)
    
    # Znajdź okresy bear market (spadki)
    bear_periods = []
    for i in range(200, len(prices), 100):
        change = (prices[i] - prices[i-100]) / prices[i-100]
        if change < -0.20:  # Spadek > 20%
            bear_periods.append((i-100, i, prices[i-100:i+1]))
    
    detector = AdaptiveTrendDetector()
    
    print(f"=== TEST NA BEAR MARKET ===\n")
    print(f"Znaleziono {len(bear_periods)} okresów bear market\n")
    
    for idx, (start, end, period_prices) in enumerate(bear_periods[:5]):
        result = detector.analyze(period_prices)
        btc_change = ((period_prices[-1]/period_prices[0])-1)*100
        
        print(f"Bear #{idx+1}: Dni {start}-{end} ({len(period_prices)} dni)")
        print(f"  BTC zmiana: {btc_change:+.1f}%")
        print(f"  Trend wykryty: {result['primary_trend']}")
        print(f"  Siła trendu: {result['trend_strength']:.2f}")
        print(f"  Timeframe: {result['timeframes_analyzed']}")
        print(f"  Konsensus: {result['consensus_score']:.0%}")
        print(f"  Rekomendacja: {result['recommendation']}")
        print()
        
        # Pokaż wszystkie timeframe
        for analysis in result['analyses']:
            print(f"    {analysis.timeframe:4s}: {analysis.trend:20s} (siła: {analysis.strength:.2f})")
        print()

if __name__ == "__main__":
    test_bear_market()
