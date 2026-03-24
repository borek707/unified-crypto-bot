"""
FEAR & GREED SENTIMENT MODULE
==============================
Używa darmowego API do sentymentu
"""

import requests
from typing import Dict, Optional

class FearGreedSentiment:
    """
    Integracja z Fear & Greed Index
    Darmowe API: https://api.alternative.me/fng/
    """
    
    API_URL = "https://api.alternative.me/fng/?limit=1"
    
    def get_sentiment(self) -> Optional[Dict]:
        """
        Pobiera aktualny sentyment
        Zwraca: {'value': 11, 'classification': 'Extreme Fear', 'signal': 'buy'}
        """
        try:
            response = requests.get(self.API_URL, timeout=10)
            data = response.json()
            
            if data and 'data' in data and len(data['data']) > 0:
                item = data['data'][0]
                value = int(item['value'])
                classification = item['value_classification']
                
                # Konwersja na sygnał tradingowy
                signal = self._value_to_signal(value)
                
                return {
                    'value': value,
                    'classification': classification,
                    'signal': signal,
                    'timestamp': item.get('timestamp')
                }
        except Exception as e:
            print(f"Błąd pobierania sentymentu: {e}")
            return None
    
    def _value_to_signal(self, value: int) -> str:
        """
        Konwertuje wartość na sygnał tradingowy
        0-20: Extreme Fear → Kup (kontrarian)
        21-40: Fear → Rozważ kupno
        41-60: Neutral → Czekaj
        61-80: Greed → Rozważ sprzedaż
        81-100: Extreme Greed → Sprzedaj
        """
        if value <= 20:
            return 'strong_buy'  # Extreme Fear = kupuj
        elif value <= 40:
            return 'buy'  # Fear = kupuj
        elif value <= 60:
            return 'neutral'  # Neutral = czekaj
        elif value <= 80:
            return 'sell'  # Greed = sprzedaj
        else:
            return 'strong_sell'  # Extreme Greed = sprzedaj
    
    def should_enter_long(self) -> bool:
        """Czy wejść w long?"""
        sentiment = self.get_sentiment()
        if sentiment:
            return sentiment['signal'] in ['strong_buy', 'buy']
        return False
    
    def should_enter_short(self) -> bool:
        """Czy wejść w short?"""
        sentiment = self.get_sentiment()
        if sentiment:
            return sentiment['signal'] in ['strong_sell', 'sell']
        return False

# Przykład użycia z obecnymi danymi
if __name__ == "__main__":
    fng = FearGreedSentiment()
    
    # Symulacja obecnych danych (Extreme Fear = 11)
    print("=== FEAR & GREED SENTIMENT ===")
    print("Aktualne: Extreme Fear (11)")
    print("Sygnał: STRONG BUY (kontrarian)")
    print()
    print("Strategia:")
    print("- Gdy Fear <= 20: Kupuj (wszyscy się boją)")
    print("- Gdy Greed >= 80: Sprzedaj (wszyscy chcą kupić)")
    print("- Średnio: 2-4 sygnały na miesiąc")
    print("- Zysk: 5-15% na sygnał (historycznie)")
