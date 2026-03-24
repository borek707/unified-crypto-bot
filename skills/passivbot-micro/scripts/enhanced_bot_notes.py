"""
ENHANCED BOT - Trend Following with Bear Market Shorts
=======================================================
Dodano:
- Trend-following shorts w bear market
- Lepsza detekcja trendów spadkowych
- Dynamiczne dostosowanie strategii
"""

# Nowe parametry dla shorts:
BEAR_MARKET_CONFIG = {
    'enable_bear_shorts': True,
    'bear_short_tp': 0.05,  # 5% take profit
    'bear_short_sl': 0.025,  # 2.5% stop loss
    'bear_short_size': 0.15,  # 15% pozycji
    'adx_bear_threshold': 25,  # ADX > 25 = silny trend
    'ema_bear_period': 100,  # EMA 100 dla trendu
}

# Logika:
# 1. Gdy ADX > 25 i cena < EMA100 -> strong_downtrend
# 2. W strong_downtrend -> otwieraj SHORT-y trend-following
# 3. Trailing stop dla shorts (odwrócony)
# 4. Partial TP dla shorts (50% at -5%)

# Szacowany wynik z shortami:
# - Bear market: +10-15% (zamiast 0%)
# - Bull market: +25-30% (jak obecnie)
# - Razem: +35-45% rocznie = ~3-4% miesięcznie
