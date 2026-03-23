#!/usr/bin/env python3
"""
Micro-PassivBot UNIFIED - LONG & SHORT
======================================
Automatycznie przełącza między LONG i SHORT w zależności od trendu.

Strategie:
- DOWNTREND (📉): SHORT 3x leverage (zarabia na spadkach)
- UPTREND (📈): LONG Grid (zarabia na wzrostach)
- SIDEWAYS (➡️): Elastyczna Grid+DCA

Użycie:
    python unified_bot.py --testnet  # Test mode
    python unified_bot.py --live     # Live trading
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Literal, Tuple
import time

# Import technical indicators (optional enhancement)
try:
    from technical_indicators import MarketClassifier
    TECHNICAL_INDICATORS_AVAILABLE = True
except ImportError:
    TECHNICAL_INDICATORS_AVAILABLE = False
    MarketClassifier = None

# Setup logging - use environment variable or default to home directory
LOG_DIR = Path(os.getenv('BOT_LOG_DIR', Path.home() / '.crypto_bot' / 'logs'))
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'unified_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# CIRCUIT BREAKER - Protection against excessive losses
# ============================================================================

class CircuitBreaker:
    """Circuit breaker - stops trading when loss limits are exceeded."""
    
    def __init__(
        self,
        max_daily_loss_pct: float = 0.05,
        max_drawdown_pct: float = 0.15,
        max_consecutive_losses: int = 5,
        cooldown_minutes: int = 60
    ):
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.max_consecutive_losses = max_consecutive_losses
        self.cooldown_minutes = cooldown_minutes
        
        self.active = False
        self.reason = ""
        self.activated_at: Optional[datetime] = None
        self.cooldown_until: Optional[datetime] = None
        
        # Tracking
        self.consecutive_losses = 0
        self.max_consecutive_losses_seen = 0
        self.daily_pnl = 0.0
        self.peak_balance = 0.0
        self.initial_balance = 0.0
    
    def initialize(self, initial_balance: float):
        """Initialize with starting balance."""
        self.initial_balance = initial_balance
        self.peak_balance = initial_balance
    
    def check(self, current_balance: float) -> tuple:
        """Check if circuit breaker should activate. Returns: (should_stop, reason)"""
        # Check cooldown reset
        if self.cooldown_until and datetime.now() >= self.cooldown_until:
            self.reset()
        
        if self.cooldown_until and datetime.now() < self.cooldown_until:
            return True, f"Circuit breaker cooldown until {self.cooldown_until.strftime('%H:%M')}"
        
        # Calculate drawdown
        if current_balance > self.peak_balance:
            self.peak_balance = current_balance
        
        drawdown = (self.peak_balance - current_balance) / self.peak_balance if self.peak_balance > 0 else 0
        
        # Check daily loss
        daily_loss_pct = abs(self.daily_pnl) / self.initial_balance if self.initial_balance > 0 else 0
        if daily_loss_pct > self.max_daily_loss_pct:
            self.activate(f"Daily loss limit: {daily_loss_pct:.2%}")
            return True, self.reason
        
        # Check drawdown
        if drawdown > self.max_drawdown_pct:
            self.activate(f"Max drawdown: {drawdown:.2%}")
            return True, self.reason
        
        # Check consecutive losses
        if self.consecutive_losses >= self.max_consecutive_losses:
            self.activate(f"Consecutive losses: {self.consecutive_losses}")
            return True, self.reason
        
        return False, ""
    
    def record_trade(self, pnl: float):
        """Record trade result."""
        self.daily_pnl += pnl
        
        if pnl < 0:
            self.consecutive_losses += 1
            self.max_consecutive_losses_seen = max(
                self.max_consecutive_losses_seen,
                self.consecutive_losses
            )
        else:
            self.consecutive_losses = 0
    
    def activate(self, reason: str):
        """Activate circuit breaker."""
        self.active = True
        self.reason = reason
        self.activated_at = datetime.now()
        self.cooldown_until = datetime.now() + timedelta(minutes=self.cooldown_minutes)
        logger.warning(f"🔴 CIRCUIT BREAKER ACTIVATED: {reason}")
        logger.warning(f"⏸️  Trading suspended until {self.cooldown_until.strftime('%H:%M')}")
    
    def reset(self):
        """Reset circuit breaker."""
        if self.active:
            logger.info("🟢 Circuit breaker reset - trading resumed")
        self.active = False
        self.reason = ""
        self.activated_at = None
        self.cooldown_until = None
        self.consecutive_losses = 0
    
    def reset_daily(self):
        """Reset daily stats (call at midnight)."""
        self.daily_pnl = 0.0


@dataclass
class UnifiedConfig:
    """Configuration for unified bot with Circuit Breaker."""
    
    # Account
    initial_capital: float = 100.0
    
    # === CIRCUIT BREAKER ===
    circuit_breaker_enabled: bool = True
    max_daily_loss_pct: float = 0.05  # 5% daily loss
    max_drawdown_pct: float = 0.15    # 15% max drawdown
    max_consecutive_losses: int = 5   # 5 losses in a row
    circuit_cooldown_minutes: int = 60  # 1 hour cooldown
    
    # === RISK MANAGEMENT ===
    risk_per_trade_pct: float = 0.01   # 1% risk per trade
    max_total_exposure_pct: float = 0.50  # 50% max exposure
    
    # === TREND DETECTION ===
    trend_lookback: int = 48  # 48 hours
    trend_threshold: float = 0.05  # 5%
    
    # === DOWNTREND: SHORT 3x ===
    short_leverage: float = 3.0
    short_position_pct: float = 0.15  # 15% = $15
    short_max_positions: int = 2
    short_bounce_threshold: float = 0.015  # 1.5%
    short_tp: float = 0.04  # 4%
    short_sl: float = 0.025  # 2.5%
    
    # === UPTREND: LONG Grid ===
    long_grid_spacing: float = 0.008  # 0.8%
    long_markup: float = 0.006  # 0.6%
    long_position_pct: float = 0.10  # 10% = $10
    long_entry_mult: float = 1.5
    trend_follow_position_pct: float = 0.15
    trend_follow_hard_stop_pct: float = 0.03
    trend_follow_activation_pct: float = 0.02
    trend_follow_trailing_stop_pct: float = 0.04
    long_guard_enabled: bool = True
    long_guard_ema_period: int = 200
    long_guard_min_24h_change: float = 0.0
    long_guard_min_72h_change: float = 0.01
    
    # === SIDEWAYS: Grid + DCA ===
    sideways_grid_pct: float = 0.30  # 30% capital
    sideways_dca_pct: float = 0.70   # 70% capital
    sideways_spacing: float = 0.015   # 1.5%
    sideways_markup: float = 0.010    # 1%
    stop_loss_multiplier: float = 1.5  # SL = spacing * 1.5
    max_grid_positions: int = 4
    max_dca_per_position: int = 3
    
    # Safety
    daily_loss_limit: float = 0.15  # 15%
    liquidation_buffer: float = 0.10  # 10%
    
    # Exchange
    exchange: str = 'hyperliquid'
    symbol: str = 'BTC/USDC:USDC'
    testnet: bool = True
    check_interval: int = 60  # seconds
    
    def save(self, path: str):
        with open(path, 'w') as f:
            json.dump(asdict(self), f, indent=2)
    
    @classmethod
    def load(cls, path: str):
        with open(path, 'r') as f:
            return cls(**json.load(f))


class UnifiedBot:
    """
    Unified trading bot that adapts strategy based on market trend.
    """
    
    def __init__(self, config: UnifiedConfig):
        self.config = config
        self.exchange = None
        self.current_trend: Literal[
            'strong_uptrend',
            'pullback_uptrend',
            'sideways',
            'bear_rally',
            'strong_downtrend',
        ] = 'sideways'
        
        # Position tracking
        self.positions_short: List[Dict] = []
        self.positions_long: List[Dict] = []
        self.grid_orders: List[Dict] = []
        
        # Stats
        self.stats = {
            'trades_total': 0,
            'trades_short': 0,
            'trades_long': 0,
            'profit_total': 0.0,
            'profit_short': 0.0,
            'profit_long': 0.0,
            'daily_loss': 0.0,
            'last_reset': datetime.now().date()
        }
        
        # Circuit Breaker
        self.circuit_breaker = CircuitBreaker(
            max_daily_loss_pct=config.max_daily_loss_pct,
            max_drawdown_pct=config.max_drawdown_pct,
            max_consecutive_losses=config.max_consecutive_losses,
            cooldown_minutes=config.circuit_cooldown_minutes
        )
        
        # Balance tracking for CB
        self.current_balance = config.initial_capital
        self.peak_balance = config.initial_capital
        
        # Market Classifier (optional enhancement)
        if TECHNICAL_INDICATORS_AVAILABLE and MarketClassifier is not None:
            self.market_classifier = MarketClassifier(config)
            logger.info("📊 Market Classifier initialized (5-state)")
        else:
            self.market_classifier = None
            logger.info("⚠️ Market Classifier not available")
        
        logger.info("🤖 Unified Bot initialized (with Circuit Breaker v3.0)")
    
    async def initialize(self):
        """Initialize exchange connection."""
        try:
            import ccxt

            api_key = os.getenv('HYPERLIQUID_API_KEY', '').strip()
            secret = os.getenv('HYPERLIQUID_SECRET', '').strip()

            # Validate API keys before attempting connection
            if not self.config.testnet and (not api_key or not secret):
                logger.error("❌ API keys not configured. Set HYPERLIQUID_API_KEY and HYPERLIQUID_SECRET")
                return False

            if not self.config.testnet and len(api_key) < 10:
                logger.error("❌ API key appears invalid (too short)")
                return False

            self.exchange = ccxt.hyperliquid({
                'enableRateLimit': True,
                'apiKey': api_key,
                'secret': secret,
                'options': {
                    'defaultType': 'swap'
                }
            })
            
            # Load markets (sync in ccxt)
            self.exchange.load_markets()
            logger.info(f"✅ Connected to {self.config.exchange}")
            logger.info(f"Mode: {'PAPER (Testnet mode not available)' if self.config.testnet else 'LIVE'}")
            
            # Initialize Circuit Breaker
            self.circuit_breaker.initialize(self.config.initial_capital)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False
    
    def _ema(self, prices: List[float], period: int) -> float:
        """Compute EMA using the latest prices."""
        if not prices:
            return 0.0
        if len(prices) < period:
            return prices[-1]

        alpha = 2 / (period + 1)
        ema = prices[0]
        for p in prices[1:]:
            ema = alpha * p + (1 - alpha) * ema
        return ema

    def _pct_change(self, prices: List[float], lookback: int) -> Optional[float]:
        """Return percentage change for a given lookback if enough data is available."""
        if len(prices) <= lookback or prices[-lookback - 1] <= 0:
            return None
        return (prices[-1] / prices[-lookback - 1]) - 1

    def _to_hourly_prices(self, prices: List[float]) -> List[float]:
        """Collapse minute-level samples into hourly regime series."""
        samples_per_hour = max(1, int(3600 / max(self.config.check_interval, 1)))
        if len(prices) <= samples_per_hour:
            return prices
        return prices[::samples_per_hour]

    def detect_trend(
        self,
        prices: List[float]
    ) -> Literal['strong_uptrend', 'pullback_uptrend', 'sideways', 'bear_rally', 'strong_downtrend']:
        """Classify the market using 48h, 7d, 14d and 30d context on hourly data."""
        hourly_prices = self._to_hourly_prices(prices)
        if len(hourly_prices) < 48:
            return self.current_trend

        price = hourly_prices[-1]
        change_48h = self._pct_change(hourly_prices, 48)
        change_7d = self._pct_change(hourly_prices, 24 * 7)
        change_14d = self._pct_change(hourly_prices, 24 * 14)
        change_30d = self._pct_change(hourly_prices, 24 * 30)

        baseline_change = change_30d
        ema_period = 24 * 30
        if baseline_change is None:
            baseline_change = change_14d if change_14d is not None else change_7d
            ema_period = 24 * 14
        if baseline_change is None or change_48h is None or change_7d is None:
            return self.current_trend

        ema_baseline = self._ema(hourly_prices[-ema_period * 2:], ema_period)
        above_ema = price >= ema_baseline
        below_ema = price <= ema_baseline
        change_14d = change_14d if change_14d is not None else change_7d

        if baseline_change >= 0.12 and change_14d >= 0.05 and change_7d >= 0.02 and above_ema:
            if change_48h < 0:
                return 'pullback_uptrend'
            return 'strong_uptrend'

        if baseline_change >= 0.06 and change_14d >= 0.01 and price >= ema_baseline * 0.98:
            if -0.08 <= change_48h <= 0.01:
                return 'pullback_uptrend'

        if baseline_change <= -0.12 and change_14d <= -0.05 and change_7d <= -0.02 and below_ema:
            if change_48h > 0:
                return 'bear_rally'
            return 'strong_downtrend'

        if baseline_change <= -0.06 and change_14d <= -0.01 and price <= ema_baseline * 1.02:
            if change_48h > 0:
                return 'bear_rally'
            return 'strong_downtrend'

        return 'sideways'
    
    # ============ SHORT 3x STRATEGY ============
    
    def should_enter_short(self, price: float, price_history: List[float]) -> bool:
        """Check if we should enter SHORT position."""
        # Circuit breaker check
        if self.config.circuit_breaker_enabled and self.circuit_breaker.active:
            return False
        
        # Exposure check
        if not self._check_exposure_limit():
            return False
        
        if len(self.positions_short) >= self.config.short_max_positions:
            return False
        
        if len(price_history) < 10:
            return False
        
        # Find recent low
        recent_low = min(price_history[-24:])  # Last 24 hours

        # Safety: avoid division by zero
        if recent_low <= 0:
            return False

        # Bounce from low
        bounce = (price - recent_low) / recent_low

        return bounce >= self.config.short_bounce_threshold
    
    def should_exit_short(self, position: Dict, current_price: float) -> Optional[str]:
        """Check if we should exit SHORT position."""
        entry = position['entry_price']
        
        # Take profit: price dropped
        tp_price = entry * (1 - self.config.short_tp)
        if current_price <= tp_price:
            return 'tp'
        
        # Stop loss: price rose
        sl_price = entry * (1 + self.config.short_sl)
        if current_price >= sl_price:
            return 'sl'
        
        # Near liquidation
        liq_price = position.get('liq_price', entry * 1.33)
        if current_price >= liq_price * (1 - self.config.liquidation_buffer):
            return 'liq_protection'
        
        return None
    
    async def open_short(self, price: float) -> Optional[Dict]:
        """Open SHORT 3x position."""
        position_size = self.config.initial_capital * self.config.short_position_pct
        notional = position_size * self.config.short_leverage
        amount = notional / price
        
        logger.info(f"📉 OPEN SHORT 3x: ${notional:.2f} @ ${price:.2f}")
        
        if self.config.testnet:
            return {
                'id': f"short_{int(time.time())}",
                'entry_price': price,
                'amount': amount,
                'liq_price': price * 1.33,
                'type': 'short'
            }
        return None
    
    async def close_short(self, position: Dict, price: float, reason: str) -> float:
        """Close SHORT position."""
        entry = position['entry_price']
        amount = position['amount']
        
        # PnL for short: (entry - exit) / entry * notional
        pnl = (entry - price) / entry * (amount * entry)
        
        logger.info(f"📉 CLOSE SHORT ({reason}): PnL ${pnl:.2f}")
        
        # Record for circuit breaker
        if self.config.circuit_breaker_enabled:
            self.circuit_breaker.record_trade(pnl)
            self.current_balance += pnl
            if self.current_balance > self.peak_balance:
                self.peak_balance = self.current_balance
        
        self.stats['trades_short'] += 1
        self.stats['profit_short'] += pnl
        self.stats['profit_total'] += pnl
        
        if pnl < 0:
            self.stats['daily_loss'] += abs(pnl)
        
        return pnl
    
    # ============ LONG Grid STRATEGY ============
    
    def should_enter_long_grid(self, price: float, price_history: List[float]) -> bool:
        """Check if we should enter LONG grid position."""
        if len(price_history) < 10:
            return False

        if not self.is_long_allowed(price, price_history):
            return False
        
        # Circuit breaker check
        if self.config.circuit_breaker_enabled and self.circuit_breaker.active:
            return False
        
        # Exposure check
        if not self._check_exposure_limit():
            return False
        
        # Find recent high
        recent_high = max(price_history[-24:])
        
        # Dip from high
        dip = (recent_high - price) / recent_high
        
        return dip >= self.config.long_grid_spacing

    def _ema(self, prices: List[float], period: int) -> float:
        """Compute EMA using the latest prices."""
        if not prices:
            return 0.0
        if len(prices) < period:
            return prices[-1]

        alpha = 2 / (period + 1)
        ema = prices[0]
        for p in prices[1:]:
            ema = alpha * p + (1 - alpha) * ema
        return ema

    def is_long_allowed(self, price: float, price_history: List[float]) -> bool:
        """Global guard for opening NEW long positions in bearish conditions."""
        if not self.config.long_guard_enabled:
            return True

        ema_period = self.config.long_guard_ema_period
        min_lookback = max(ema_period, 72)
        if len(price_history) < min_lookback:
            return False

        recent = price_history[-(ema_period * 2):]
        ema_value = self._ema(recent, ema_period)

        price_24h_ago = price_history[-24]
        price_72h_ago = price_history[-72]
        ch_24h = (price / price_24h_ago) - 1 if price_24h_ago > 0 else -1
        ch_72h = (price / price_72h_ago) - 1 if price_72h_ago > 0 else -1

        return (
            price >= ema_value
            and ch_24h >= self.config.long_guard_min_24h_change
            and ch_72h >= self.config.long_guard_min_72h_change
        )
    
    def _check_exposure_limit(self, new_position_size: float = 0) -> bool:
        """Check if adding new position would exceed exposure limit."""
        current_exposure = sum(p.get('size', 0) for p in self.positions_long + self.positions_short)
        exposure_pct = (current_exposure + new_position_size) / self.current_balance if self.current_balance > 0 else 0
        return exposure_pct <= self.config.max_total_exposure_pct

    def _get_trend_follow_position(self) -> Optional[Dict]:
        """Return active trend-following long if present."""
        for pos in self.positions_long:
            if pos.get('type') == 'trend_follow':
                return pos
        return None

    def should_enter_trend_follow(self, price: float, price_history: List[float]) -> bool:
        """Open a carry long only when the market is in strong uptrend."""
        if self.config.circuit_breaker_enabled and self.circuit_breaker.active:
            return False
        if self._get_trend_follow_position() is not None:
            return False
        if not self.is_long_allowed(price, price_history):
            return False

        position_size = self.config.initial_capital * self.config.trend_follow_position_pct
        return self._check_exposure_limit(position_size)

    async def open_trend_follow(self, price: float) -> Optional[Dict]:
        """Open a trend-following long position."""
        position_size = self.config.initial_capital * self.config.trend_follow_position_pct
        amount = position_size / price

        logger.info(f"🚀 OPEN TREND LONG: ${position_size:.2f} @ ${price:.2f}")

        if self.config.testnet:
            return {
                'id': f"trend_{int(time.time())}",
                'entry_price': price,
                'amount': amount,
                'size': position_size,
                'highest_price': price,
                'hard_stop_price': price * (1 - self.config.trend_follow_hard_stop_pct),
                'trailing_stop_price': None,
                'type': 'trend_follow'
            }
        return None

    def should_exit_trend_follow(self, position: Dict, current_price: float) -> Optional[str]:
        """Update trailing stop and return exit reason if the carry long should close."""
        entry = position['entry_price']
        highest_price = max(position.get('highest_price', entry), current_price)
        position['highest_price'] = highest_price

        if current_price <= position['hard_stop_price']:
            return 'hard_stop'

        activation_price = entry * (1 + self.config.trend_follow_activation_pct)
        if highest_price >= activation_price:
            trailing_stop = highest_price * (1 - self.config.trend_follow_trailing_stop_pct)
            position['trailing_stop_price'] = max(
                position.get('trailing_stop_price') or trailing_stop,
                trailing_stop,
            )
            if current_price <= position['trailing_stop_price']:
                return 'trailing_stop'

        return None

    async def close_trend_follow(self, position: Dict, price: float, reason: str) -> float:
        """Close trend-following long position."""
        entry = position['entry_price']
        amount = position['amount']
        pnl = (price - entry) / entry * (amount * entry)

        logger.info(f"🚀 CLOSE TREND LONG ({reason}): PnL ${pnl:.2f}")

        if self.config.circuit_breaker_enabled:
            self.circuit_breaker.record_trade(pnl)
            self.current_balance += pnl
            if self.current_balance > self.peak_balance:
                self.peak_balance = self.current_balance

        self.stats['trades_long'] += 1
        self.stats['profit_long'] += pnl
        self.stats['profit_total'] += pnl

        return pnl
    
    async def open_long_grid(self, price: float) -> Optional[Dict]:
        """Open LONG grid position."""
        position_size = self.config.initial_capital * self.config.long_position_pct
        amount = position_size / price
        
        logger.info(f"📈 OPEN LONG Grid: ${position_size:.2f} @ ${price:.2f}")
        
        if self.config.testnet:
            return {
                'id': f"long_{int(time.time())}",
                'entry_price': price,
                'amount': amount,
                'tp_price': price * (1 + self.config.long_markup),
                'type': 'long_grid'
            }
        return None
    
    async def close_long_grid(self, position: Dict, price: float) -> float:
        """Close LONG grid position."""
        entry = position['entry_price']
        amount = position['amount']
        
        pnl = (price - entry) / entry * (amount * entry)
        
        logger.info(f"📈 CLOSE LONG Grid: PnL ${pnl:.2f}")
        
        # Record for circuit breaker
        if self.config.circuit_breaker_enabled:
            self.circuit_breaker.record_trade(pnl)
            self.current_balance += pnl
            if self.current_balance > self.peak_balance:
                self.peak_balance = self.current_balance
        
        self.stats['trades_long'] += 1
        self.stats['profit_long'] += pnl
        self.stats['profit_total'] += pnl
        
        return pnl
    
    # ============ SIDEWAYS Grid + DCA STRATEGY ============
    
    def calculate_sideways_levels(self, price_history: List[float]) -> Dict:
        """Calculate support and resistance levels for sideways trading."""
        if len(price_history) < 48:
            return {}
        
        # Use last 48 prices to determine range
        recent_prices = price_history[-48:]
        high = max(recent_prices)
        low = min(recent_prices)
        mid = (high + low) / 2
        
        # Grid levels
        grid_range = high - low
        if grid_range / mid < 0.005:  # Less than 0.5% range
            return {}  # Too tight, skip
        
        return {
            'high': high,
            'low': low,
            'mid': mid,
            'grid_range': grid_range,
            'support': low + grid_range * 0.2,
            'resistance': high - grid_range * 0.2
        }
    
    def should_enter_sideways_grid(self, price: float, levels: Dict) -> bool:
        """Check if we should enter sideways grid position."""
        # Circuit breaker check
        if self.config.circuit_breaker_enabled and self.circuit_breaker.active:
            return False
        
        # Max positions check
        sideways_positions = [p for p in self.positions_long if p.get('type') == 'sideways']
        if len(sideways_positions) >= self.config.max_grid_positions:
            return False
        
        # Exposure check
        if not self._check_exposure_limit():
            return False
        
        if not levels:
            return False
        
        # Buy near support
        support_zone = levels['support'] * (1 + self.config.sideways_spacing * 0.5)
        return price <= support_zone and price >= levels['low'] * 1.005
    
    def should_add_dca(self, price: float, position: Dict) -> bool:
        """Check if we should DCA (add to position at lower price)."""
        entry = position['entry_price']
        # DCA if price dropped by spacing amount
        return price <= entry * (1 - self.config.sideways_spacing)
    
    def should_exit_sideways_grid(self, price: float, position: Dict, levels: Dict) -> bool:
        """Check if we should exit sideways grid position."""
        entry = position['entry_price']
        markup_price = entry * (1 + self.config.sideways_markup)
        
        # Take profit at markup
        if price >= markup_price:
            return True
        
        # Stop loss below range low
        if levels and price <= levels['low'] * 0.995:
            return True
        
        return False
    
    async def open_sideways_position(self, price: float, is_dca: bool = False) -> Optional[Dict]:
        """Open sideways grid position."""
        # Grid uses sideways_grid_pct, DCA uses sideways_dca_pct
        if is_dca:
            position_size = self.config.initial_capital * self.config.sideways_dca_pct * 0.2  # 20% of DCA budget
            label = "DCA"
        else:
            position_size = self.config.initial_capital * self.config.sideways_grid_pct * 0.25  # 25% of grid budget
            label = "GRID"
        
        amount = position_size / price
        tp_price = price * (1 + self.config.sideways_markup)
        
        logger.info(f"📊 OPEN SIDEWAYS {label}: ${position_size:.2f} @ ${price:.2f} → TP @ ${tp_price:.2f}")
        
        if self.config.testnet:
            return {
                'id': f"sideways_{label}_{int(time.time())}",
                'entry_price': price,
                'amount': amount,
                'tp_price': tp_price,
                'type': 'sideways',
                'is_dca': is_dca
            }
        return None
    
    async def close_sideways_position(self, position: Dict, price: float, reason: str) -> float:
        """Close sideways grid position."""
        entry = position['entry_price']
        amount = position['amount']
        
        pnl = (price - entry) / entry * (amount * entry)
        pos_type = "DCA" if position.get('is_dca') else "GRID"
        
        logger.info(f"📊 CLOSE SIDEWAYS {pos_type} ({reason}): PnL ${pnl:.2f}")
        
        # Record for circuit breaker
        if self.config.circuit_breaker_enabled:
            self.circuit_breaker.record_trade(pnl)
            self.current_balance += pnl
            if self.current_balance > self.peak_balance:
                self.peak_balance = self.current_balance
        
        self.stats['trades_long'] += 1  # Count as long trade
        self.stats['profit_long'] += pnl
        self.stats['profit_total'] += pnl
        
        return pnl
    
    async def execute_sideways_strategy(self, price: float, price_history: List[float], allow_new_entries: bool = True):
        """Execute sideways grid + DCA strategy."""
        levels = self.calculate_sideways_levels(price_history)
        
        if not levels:
            return
        
        # Check exits first
        for pos in self.positions_long[:]:
            if pos.get('type') == 'sideways':
                if self.should_exit_sideways_grid(price, pos, levels):
                    await self.close_sideways_position(pos, price, 'TP' if price >= pos['tp_price'] else 'SL')
                    self.positions_long.remove(pos)
        
        # Count current sideways positions
        sideways_positions = [p for p in self.positions_long if p.get('type') == 'sideways']
        grid_positions = [p for p in sideways_positions if not p.get('is_dca')]
        dca_positions = [p for p in sideways_positions if p.get('is_dca')]

        if not allow_new_entries:
            return
        
        max_grid = 4  # Max 4 grid positions
        max_dca = 3   # Max 3 DCA adds per position
        
        # Enter grid positions
        if len(grid_positions) < max_grid:
            if self.should_enter_sideways_grid(price, levels):
                # Check we're not too close to existing position
                too_close = any(abs(p['entry_price'] - price) / price < self.config.sideways_spacing * 0.5 
                               for p in grid_positions)
                if not too_close:
                    pos = await self.open_sideways_position(price, is_dca=False)
                    if pos:
                        self.positions_long.append(pos)
        
        # DCA logic: add to lowest position if price dropped
        if dca_positions == 0 and grid_positions and len(sideways_positions) < max_grid + max_dca:
            lowest_pos = min(grid_positions, key=lambda p: p['entry_price'])
            if self.should_add_dca(price, lowest_pos):
                pos = await self.open_sideways_position(price, is_dca=True)
                if pos:
                    self.positions_long.append(pos)
    
    # ============ MAIN LOOP ============
    
    async def run(self):
        """Main bot loop."""
        logger.info("="*70)
        logger.info("🚀 UNIFIED BOT STARTED (v3.0 with Circuit Breaker)")
        logger.info("="*70)
        logger.info(f"Capital: ${self.config.initial_capital}")
        logger.info(f"Trend detection: {self.config.trend_lookback}h / {self.config.trend_threshold*100:.0f}%")
        if self.config.circuit_breaker_enabled:
            logger.info(f"Circuit Breaker: ENABLED")
            logger.info(f"  - Max daily loss: {self.config.max_daily_loss_pct:.1%}")
            logger.info(f"  - Max drawdown: {self.config.max_drawdown_pct:.1%}")
            logger.info(f"  - Max consecutive losses: {self.config.max_consecutive_losses}")
            logger.info(f"  - Cooldown: {self.config.circuit_cooldown_minutes} min")
        logger.info("="*70)
        
        # Initialize exchange connection
        if not await self.initialize():
            logger.error("❌ Failed to initialize exchange. Exiting.")
            return
        
        price_history = []
        last_trend_print = time.time()
        previous_trend = self.current_trend
        last_day = datetime.now().date()
        
        while True:
            try:
                # Check for new day (reset daily stats)
                current_day = datetime.now().date()
                if current_day != last_day:
                    if self.config.circuit_breaker_enabled:
                        self.circuit_breaker.reset_daily()
                    last_day = current_day
                    logger.info("📅 New day - daily stats reset")
                
                # Check circuit breaker
                if self.config.circuit_breaker_enabled:
                    should_stop, cb_reason = self.circuit_breaker.check(self.current_balance)
                    if should_stop:
                        logger.warning(f"⏸️  Trading suspended: {cb_reason}")
                        await asyncio.sleep(60)  # Check every minute during CB
                        continue
                
                # Get price with fallback
                price = None
                
                # Try 1: Hyperliquid exchange
                try:
                    logger.info(f"Fetching price from Hyperliquid...")
                    ticker = self.exchange.fetch_ticker(self.config.symbol)
                    price = ticker['last']
                    logger.info(f"✅ Hyperliquid price: ${price:.2f}")
                except Exception as e:
                    logger.warning(f"Hyperliquid failed: {e}")
                    
                    # Try 2: Local database
                    try:
                        import sqlite3
                        # Use environment variable or default to user home
                        data_dir = Path(os.getenv('BOT_DATA_DIR', Path.home() / '.crypto_bot' / 'data'))
                        db_path = data_dir / 'crypto_prices.db'
                        if db_path.exists():
                            conn = sqlite3.connect(db_path)
                            cursor = conn.cursor()
                            cursor.execute('SELECT price FROM crypto_prices WHERE coin="BTC" ORDER BY timestamp DESC LIMIT 1')
                            result = cursor.fetchone()
                            conn.close()
                            if result:
                                price = result[0]
                                logger.info(f"✅ Database price: ${price:.2f}")
                    except Exception as db_err:
                        logger.warning(f"Database failed: {db_err}")
                        
                        # Try 3: External API (Coinpaprika)
                        try:
                            # Try to find crypto_price_fetcher in common locations
                            script_dirs = [
                                Path(os.getenv('BOT_SCRIPTS_DIR', Path.home() / '.crypto_bot' / 'scripts')),
                                Path(__file__).parent.parent / 'finance-tracker' / 'scripts',
                            ]
                            for script_dir in script_dirs:
                                if script_dir.exists():
                                    sys.path.insert(0, str(script_dir))
                                    break
                            from crypto_price_fetcher import CryptoPriceFetcher
                            fetcher = CryptoPriceFetcher()
                            result = fetcher.get_price_with_fallback()
                            if result:
                                price = result['price']
                                logger.info(f"✅ API price ({result['source']}): ${price:.2f}")
                        except Exception as api_err:
                            logger.error(f"All price sources failed: {api_err}")
                            await asyncio.sleep(self.config.check_interval)
                            continue
                
                if price is None:
                    logger.error("Could not get price from any source")
                    await asyncio.sleep(self.config.check_interval)
                    continue
                
                price_history.append(price)
                if len(price_history) > 3000:  # Keep 50h of data (buffer above 48h requirement)
                    price_history = price_history[-2880:]
                
                # Detect trend
                new_trend = self.detect_trend(price_history)

                # Print trend every hour
                if time.time() - last_trend_print > 3600:
                    logger.info(f"📊 Current trend: {self.current_trend.upper()}")
                    last_trend_print = time.time()

                # === EXECUTE STRATEGY BASED ON TREND ===

                # FIX: Trend change detection - must check BEFORE updating current_trend
                if new_trend != previous_trend:
                    logger.info(f"🔄 TREND CHANGE: {previous_trend} → {new_trend}")

                    # Cancel all pending grid/DCA orders (don't close open positions!)
                    logger.info("📋 Canceling all pending orders (leaving open positions)")
                    self.grid_orders.clear()  # Clear pending grid orders

                    # Log open positions (they will hit SL/TP on their own)
                    if self.positions_long:
                        logger.info(f"📈 Leaving {len(self.positions_long)} LONG positions open (SL/TP active)")
                    if self.positions_short:
                        logger.info(f"📉 Leaving {len(self.positions_short)} SHORT positions open (SL/TP active)")

                    # Update trend tracking
                    self.current_trend = new_trend
                    previous_trend = new_trend
                
                if self.current_trend in ('strong_downtrend', 'bear_rally'):
                    # SHORT 3x STRATEGY
                    
                    # FIX 3: Don't close longs! Let them hit SL/TP
                    # Only check exits for shorts
                    for pos in self.positions_short[:]:
                        exit_reason = self.should_exit_short(pos, price)
                        if exit_reason:
                            await self.close_short(pos, price, exit_reason)
                            self.positions_short.remove(pos)
                    
                    # Check entry
                    if self.should_enter_short(price, price_history):
                        pos = await self.open_short(price)
                        if pos:
                            self.positions_short.append(pos)
                
                elif self.current_trend == 'pullback_uptrend':
                    # BUY THE DIP inside a broader bullish regime

                    for pos in self.positions_long[:]:
                        if pos.get('type') == 'trend_follow':
                            exit_reason = self.should_exit_trend_follow(pos, price)
                            if exit_reason:
                                await self.close_trend_follow(pos, price, exit_reason)
                                self.positions_long.remove(pos)

                    for pos in self.positions_long[:]:
                        if pos.get('type') == 'long_grid' and price >= pos['tp_price']:
                            await self.close_long_grid(pos, price)
                            self.positions_long.remove(pos)

                    if not any(p.get('type') == 'long_grid' for p in self.positions_long):
                        if self.should_enter_long_grid(price, price_history):
                            pos = await self.open_long_grid(price)
                            if pos:
                                self.positions_long.append(pos)

                elif self.current_trend == 'strong_uptrend':
                    # Strong trend: carry one long and protect it with trailing stop.
                    for pos in self.positions_short[:]:
                        await self.close_short(pos, price, 'strong_uptrend')
                        self.positions_short.remove(pos)

                    for pos in self.positions_long[:]:
                        if pos.get('type') == 'trend_follow':
                            exit_reason = self.should_exit_trend_follow(pos, price)
                            if exit_reason:
                                await self.close_trend_follow(pos, price, exit_reason)
                                self.positions_long.remove(pos)
                        elif pos.get('type') == 'long_grid' and price >= pos['tp_price']:
                            await self.close_long_grid(pos, price)
                            self.positions_long.remove(pos)

                    if self.should_enter_trend_follow(price, price_history):
                        pos = await self.open_trend_follow(price)
                        if pos:
                            self.positions_long.append(pos)
                
                else:  # sideways
                    for pos in self.positions_long[:]:
                        if pos.get('type') == 'trend_follow':
                            exit_reason = self.should_exit_trend_follow(pos, price)
                            if exit_reason:
                                await self.close_trend_follow(pos, price, exit_reason)
                                self.positions_long.remove(pos)

                    # Close all leveraged positions (keep grid positions)
                    for pos in self.positions_short[:]:
                        await self.close_short(pos, price, 'sideways')
                        self.positions_short.remove(pos)
                    
                    # === SIDEWAYS: Grid + DCA Strategy ===
                    allow_sideways_longs = self.is_long_allowed(price, price_history)
                    await self.execute_sideways_strategy(price, price_history, allow_new_entries=allow_sideways_longs)
                
                await asyncio.sleep(self.config.check_interval)
                
            except KeyboardInterrupt:
                logger.info("Bot stopped by user")
                break
            except Exception as e:
                logger.error(f"Error: {e}")
                await asyncio.sleep(self.config.check_interval)
        
        # Cleanup
        logger.info("Closing all positions...")
        for pos in self.positions_short + self.positions_long:
            logger.info(f"Position: {pos}")
        
        self.print_stats()
    
    def print_stats(self):
        """Print final statistics."""
        logger.info("="*70)
        logger.info("📊 FINAL STATISTICS")
        logger.info("="*70)
        if self.config.circuit_breaker_enabled:
            logger.info(f"Final Balance: ${self.current_balance:.2f} (Peak: ${self.peak_balance:.2f})")
            logger.info(f"Max Drawdown: {self.circuit_breaker.max_drawdown_pct:.2%}")
            logger.info(f"Consecutive Losses (max): {self.circuit_breaker.max_consecutive_losses_seen}")
        logger.info(f"Total Trades: {self.stats['trades_short'] + self.stats['trades_long']}")
        logger.info(f"  SHORT: {self.stats['trades_short']} | Profit: ${self.stats['profit_short']:.2f}")
        logger.info(f"  LONG:  {self.stats['trades_long']} | Profit: ${self.stats['profit_long']:.2f}")
        logger.info(f"Total PnL: ${self.stats['profit_total']:.2f}")
        logger.info("="*70)


def main():
    parser = argparse.ArgumentParser(description='Unified LONG/SHORT Bot')
    parser.add_argument('--config', default='unified_config.json')
    parser.add_argument('--testnet', action='store_true', help='Test mode')
    parser.add_argument('--live', action='store_true', help='Live trading')
    parser.add_argument('--create-config', action='store_true')
    
    args = parser.parse_args()
    
    if args.create_config:
        config = UnifiedConfig()
        config.save(args.config)
        print(f"Created config: {args.config}")
        return
    
    if os.path.exists(args.config):
        config = UnifiedConfig.load(args.config)
    else:
        config = UnifiedConfig()
        config.save(args.config)
        print(f"Created default config: {args.config}")
    
    if args.testnet:
        config.testnet = True
    elif args.live:
        config.testnet = False
    
    bot = UnifiedBot(config)
    
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("\n✋ Bot stopped")


if __name__ == '__main__':
    main()
