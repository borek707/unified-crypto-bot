#!/usr/bin/env python3
"""
Micro-PassivBot UNIFIED ENHANCED v4.1
=====================================
Higher risk/reward version with:
- Dynamic position sizing based on trend strength
- Aggressive short strategy with breakdown entries
- Pyramiding in strong uptrends
- Enhanced circuit breaker for higher volatility

Target: 5% in bear markets, 10% in bull markets
WARNING: Max drawdown increased to 20% (from 15%)

Usage:
    python unified_bot_enhanced.py --config config_enhanced.json --testnet
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Literal, Tuple
import time

# Import technical indicators
try:
    from technical_indicators import MarketClassifier
    TECHNICAL_INDICATORS_AVAILABLE = True
except ImportError:
    TECHNICAL_INDICATORS_AVAILABLE = False
    MarketClassifier = None

# Import risk management
try:
    from risk_management import TurbulenceIndex, SlippageModel, WalkForwardRobustness
    RISK_MGMT_AVAILABLE = True
except ImportError:
    RISK_MGMT_AVAILABLE = False
    TurbulenceIndex = None
    SlippageModel = None

# Setup logging
LOG_DIR = Path(os.getenv('BOT_LOG_DIR', Path.home() / '.crypto_bot' / 'logs'))
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'unified_bot_enhanced.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# ENHANCED CIRCUIT BREAKER v4.0 - Higher limits for aggressive strategy
# ============================================================================

class CircuitBreaker:
    """Enhanced circuit breaker for higher risk/reward strategy."""
    
    def __init__(
        self,
        max_daily_loss_pct: float = 0.08,      # Increased from 5% to 8%
        max_drawdown_pct: float = 0.20,        # Increased from 15% to 20%
        max_consecutive_losses: int = 4,       # Tighter (was 5)
        cooldown_minutes: int = 30             # Shorter (was 60)
    ):
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.max_consecutive_losses = max_consecutive_losses
        self.cooldown_minutes = cooldown_minutes
        
        self.active = False
        self.reason = ""
        self.activated_at: Optional[datetime] = None
        self.cooldown_until: Optional[datetime] = None
        
        self.consecutive_losses = 0
        self.max_consecutive_losses_seen = 0
        self.daily_pnl = 0.0
        self.peak_balance = 0.0
        self.initial_balance = 0.0
        self.total_trades_today = 0
        self.winning_trades_today = 0
    
    def initialize(self, initial_balance: float):
        self.initial_balance = initial_balance
        self.peak_balance = initial_balance
    
    def check(self, current_balance: float) -> tuple:
        if self.cooldown_until and datetime.now() >= self.cooldown_until:
            self.reset()
        
        if self.cooldown_until and datetime.now() < self.cooldown_until:
            return True, f"Circuit breaker cooldown until {self.cooldown_until.strftime('%H:%M')}"
        
        if current_balance > self.peak_balance:
            self.peak_balance = current_balance
        
        drawdown = (self.peak_balance - current_balance) / self.peak_balance if self.peak_balance > 0 else 0
        daily_loss_pct = abs(self.daily_pnl) / self.initial_balance if self.initial_balance > 0 else 0
        
        # Check win rate - if below 30% after 10 trades, pause
        if self.total_trades_today >= 10:
            win_rate = self.winning_trades_today / self.total_trades_today
            if win_rate < 0.30:
                self.activate(f"Low win rate: {win_rate:.1%} ({self.winning_trades_today}/{self.total_trades_today})")
                return True, self.reason
        
        if daily_loss_pct > self.max_daily_loss_pct:
            self.activate(f"Daily loss limit: {daily_loss_pct:.2%}")
            return True, self.reason
        
        if drawdown > self.max_drawdown_pct:
            self.activate(f"Max drawdown: {drawdown:.2%}")
            return True, self.reason
        
        if self.consecutive_losses >= self.max_consecutive_losses:
            self.activate(f"Consecutive losses: {self.consecutive_losses}")
            return True, self.reason
        
        return False, ""
    
    def record_trade(self, pnl: float, is_win: bool = False):
        self.daily_pnl += pnl
        self.total_trades_today += 1
        if is_win:
            self.winning_trades_today += 1
        
        if pnl < 0:
            self.consecutive_losses += 1
            self.max_consecutive_losses_seen = max(
                self.max_consecutive_losses_seen,
                self.consecutive_losses
            )
        else:
            self.consecutive_losses = 0
    
    def activate(self, reason: str):
        self.active = True
        self.reason = reason
        self.activated_at = datetime.now()
        self.cooldown_until = datetime.now() + timedelta(minutes=self.cooldown_minutes)
        logger.warning(f"🔴 CIRCUIT BREAKER: {reason}")
        logger.warning(f"⏸️  Trading suspended until {self.cooldown_until.strftime('%H:%M')}")
    
    def reset(self):
        if self.active:
            logger.info("🟢 Circuit breaker reset - trading resumed")
        self.active = False
        self.reason = ""
        self.activated_at = None
        self.cooldown_until = None
        self.consecutive_losses = 0
    
    def reset_daily(self):
        self.daily_pnl = 0.0
        self.total_trades_today = 0
        self.winning_trades_today = 0


@dataclass
class UnifiedConfig:
    """Enhanced configuration for unified bot."""
    
    initial_capital: float = 100.0
    
    circuit_breaker_enabled: bool = True
    max_daily_loss_pct: float = 0.08
    max_drawdown_pct: float = 0.20
    max_consecutive_losses: int = 4
    circuit_cooldown_minutes: int = 30
    
    risk_per_trade_pct: float = 0.02
    max_total_exposure_pct: float = 0.75
    
    trend_lookback: int = 24
    trend_threshold: float = 0.03
    use_market_classifier: bool = True
    
    # SHORT - Enhanced for bear markets
    short_leverage: float = 3.0
    short_position_pct: float = 0.25
    short_max_positions: int = 3
    short_bounce_threshold: float = 0.008
    short_tp: float = 0.025
    short_sl: float = 0.018
    short_breakdown_enabled: bool = True
    short_breakdown_threshold: float = 0.01
    
    # LONG - Tighter grids for bull
    long_grid_spacing: float = 0.005
    long_markup: float = 0.004
    long_position_pct: float = 0.20
    long_entry_mult: float = 1.1
    max_grid_positions: int = 6
    
    # TREND FOLLOW - Enhanced with pyramiding
    trend_follow_position_pct: float = 0.25
    trend_follow_hard_stop_pct: float = 0.03
    trend_follow_activation_pct: float = 0.02
    trend_follow_trailing_stop_pct: float = 0.04
    trend_follow_partial_tp_enabled: bool = True
    trend_follow_partial_tp_pct: float = 0.03
    trend_follow_partial_tp_size: float = 0.30
    trend_follow_reentry_enabled: bool = True
    trend_follow_reentry_cooldown_hours: int = 12
    trend_follow_pyramiding_enabled: bool = True
    trend_follow_pyramiding_threshold: float = 0.01
    trend_follow_max_pyramids: int = 2
    
    # DYNAMIC SIZING - New feature
    dynamic_sizing_enabled: bool = True
    strong_uptrend_multiplier: float = 1.5
    strong_downtrend_multiplier: float = 1.3
    sideways_multiplier: float = 0.5
    
    # SIDEWAYS - Reduced activity
    sideways_grid_pct: float = 0.20
    sideways_dca_pct: float = 0.80
    sideways_spacing: float = 0.015
    sideways_markup: float = 0.010
    sideways_max_positions: int = 2
    stop_loss_multiplier: float = 1.5
    max_dca_per_position: int = 2
    
    # Risk Management
    long_guard_enabled: bool = True
    long_guard_ema_period: int = 200
    long_guard_min_24h_change: float = 0.0
    long_guard_min_72h_change: float = 0.005
    
    turbulence_lookback: int = 30
    turbulence_threshold: float = 1.5
    turbulence_reduce_size: bool = True
    base_slippage_bps: float = 5.0
    
    # Sentiment (optional integration)
    sentiment_enabled: bool = False
    sentiment_extreme_fear_threshold: float = 20
    sentiment_extreme_greed_threshold: float = 80
    sentiment_block_trading_hours: int = 6
    
    # Safety
    daily_loss_limit: float = 0.20
    liquidation_buffer: float = 0.15
    
    exchange: str = 'hyperliquid'
    symbol: str = 'BTC/USDC:USDC'
    testnet: bool = True
    check_interval: int = 300
    
    def save(self, path: str):
        with open(path, 'w') as f:
            json.dump(asdict(self), f, indent=2)
    
    @classmethod
    def load(cls, path: str):
        with open(path, 'r') as f:
            return cls(**json.load(f))


class UnifiedBotEnhanced:
    """Enhanced unified trading bot with higher risk/reward profile."""
    
    def __init__(self, config: UnifiedConfig):
        self.config = config
        self.exchange = None
        self.current_trend: Literal[
            'strong_uptrend', 'pullback_uptrend', 'sideways', 
            'bear_rally', 'strong_downtrend'
        ] = 'sideways'
        
        self.positions_short: List[Dict] = []
        self.positions_long: List[Dict] = []
        self.positions_pyramid: List[Dict] = []  # Additional trend-follow positions
        self.grid_orders: List[Dict] = []
        
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
        
        self.circuit_breaker = CircuitBreaker(
            max_daily_loss_pct=config.max_daily_loss_pct,
            max_drawdown_pct=config.max_drawdown_pct,
            max_consecutive_losses=config.max_consecutive_losses,
            cooldown_minutes=config.circuit_cooldown_minutes
        )
        
        self.current_balance = config.initial_capital
        self.peak_balance = config.initial_capital
        
        if TECHNICAL_INDICATORS_AVAILABLE and MarketClassifier is not None:
            self.market_classifier = MarketClassifier(config)
            logger.info("📊 Market Classifier initialized")
        else:
            self.market_classifier = None
        
        if RISK_MGMT_AVAILABLE and TurbulenceIndex is not None:
            self.turbulence_index = TurbulenceIndex(
                lookback=config.turbulence_lookback,
                turbulence_threshold=config.turbulence_threshold
            )
            self.slippage_model = SlippageModel(
                base_slippage_bps=config.base_slippage_bps
            )
            logger.info("🛡️ Risk Management initialized")
        else:
            self.turbulence_index = None
            self.slippage_model = None
        
        logger.info("🚀 Unified Bot ENHANCED v4.1 initialized")
        logger.info(f"Target: 5% bear / 10% bull | Max DD: {config.max_drawdown_pct:.0%}")
    
    async def initialize(self):
        try:
            import ccxt
            
            api_key = os.getenv('HYPERLIQUID_API_KEY', '').strip()
            secret = os.getenv('HYPERLIQUID_SECRET', '').strip()
            
            if not self.config.testnet and (not api_key or not secret):
                logger.error("❌ API keys not configured")
                return False
            
            self.exchange = ccxt.hyperliquid({
                'enableRateLimit': True,
                'apiKey': api_key,
                'secret': secret,
                'options': {'defaultType': 'swap'}
            })
            
            self.exchange.load_markets()
            logger.info(f"✅ Connected to {self.config.exchange}")
            logger.info(f"Mode: {'PAPER' if self.config.testnet else 'LIVE'}")
            
            self.circuit_breaker.initialize(self.config.initial_capital)
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False
    
    # =========================================================================
    # DYNAMIC POSITION SIZING - NEW FEATURE
    # =========================================================================
    
    def get_position_size(self, base_pct: float) -> float:
        """Calculate position size with trend-based multiplier."""
        if not self.config.dynamic_sizing_enabled:
            return base_pct
        
        multiplier = 1.0
        
        if self.current_trend == 'strong_uptrend':
            multiplier = self.config.strong_uptrend_multiplier
        elif self.current_trend == 'strong_downtrend':
            multiplier = self.config.strong_downtrend_multiplier
        elif self.current_trend == 'sideways':
            multiplier = self.config.sideways_multiplier
        
        # Check turbulence
        if self.turbulence_index and self.config.turbulence_reduce_size:
            # Turbulence check would need price history - simplified here
            pass
        
        final_size = base_pct * multiplier
        
        # Cap at max exposure
        max_single_position = self.config.max_total_exposure_pct / 2
        return min(final_size, max_single_position)
    
    # =========================================================================
    # TREND DETECTION - Enhanced with 24h lookback
    # =========================================================================
    
    def _ema(self, prices: List[float], period: int) -> float:
        if not prices or len(prices) < period:
            return prices[-1] if prices else 0.0
        
        alpha = 2 / (period + 1)
        ema = prices[0]
        for p in prices[1:]:
            ema = alpha * p + (1 - alpha) * ema
        return ema
    
    def _pct_change(self, prices: List[float], lookback: int) -> Optional[float]:
        if len(prices) <= lookback or prices[-lookback - 1] <= 0:
            return None
        return (prices[-1] / prices[-lookback - 1]) - 1
    
    def detect_trend(self, prices: List[float]) -> Literal[
        'strong_uptrend', 'pullback_uptrend', 'sideways', 
        'bear_rally', 'strong_downtrend'
    ]:
        """Enhanced trend detection with 24h and 48h context."""
        
        if self.config.use_market_classifier and self.market_classifier is not None and len(prices) >= 100:
            classification = self.market_classifier.classify(prices)
            return classification
        
        # Fallback to enhanced EMA-based detection
        if len(prices) < 48:
            return self.current_trend
        
        # Use hourly aggregation
        hourly_prices = prices[::max(1, int(3600 / self.config.check_interval))]
        if len(hourly_prices) < 24:
            hourly_prices = prices
        
        price = hourly_prices[-1]
        
        # Multiple timeframe changes
        change_24h = self._pct_change(hourly_prices, 24)
        change_48h = self._pct_change(hourly_prices, 48)
        change_7d = self._pct_change(hourly_prices, 24 * 7) if len(hourly_prices) >= 168 else change_48h
        change_14d = self._pct_change(hourly_prices, 24 * 14) if len(hourly_prices) >= 336 else change_7d
        
        # EMAs
        ema_24 = self._ema(hourly_prices[-48:], 24) if len(hourly_prices) >= 24 else price
        ema_48 = self._ema(hourly_prices[-96:], 48) if len(hourly_prices) >= 48 else ema_24
        
        above_ema24 = price >= ema_24
        above_ema48 = price >= ema_48
        
        # Strong uptrend: price above both EMAs, positive momentum
        if change_24h and change_24h > 0.03 and change_48h and change_48h > 0.05:
            if above_ema24 and above_ema48:
                return 'strong_uptrend'
        
        # Pullback in uptrend: longer term bullish, short term dip
        if change_7d and change_7d > 0.02 and change_24h and change_24h < 0:
            if change_24h > -0.05:  # Not a crash
                return 'pullback_uptrend'
        
        # Strong downtrend: price below EMAs, negative momentum
        if change_24h and change_24h < -0.03 and change_48h and change_48h < -0.05:
            if not above_ema24 and not above_ema48:
                return 'strong_downtrend'
        
        # Bear rally: longer term bearish, short term bounce
        if change_7d and change_7d < -0.02 and change_24h and change_24h > 0:
            if change_24h < 0.05:  # Not a full reversal
                return 'bear_rally'
        
        return 'sideways'
    
    # =========================================================================
    # SHORT STRATEGY - Enhanced with breakdown entries
    # =========================================================================
    
    def should_enter_short(self, price: float, price_history: List[float]) -> bool:
        if self.config.circuit_breaker_enabled and self.circuit_breaker.active:
            return False
        
        if not self._check_exposure_limit():
            return False
        
        if len(self.positions_short) >= self.config.short_max_positions:
            return False
        
        if len(price_history) < 10:
            return False
        
        # ENHANCED: Breakdown entry in strong downtrend
        if self.config.short_breakdown_enabled and self.current_trend == 'strong_downtrend':
            change_6h = self._pct_change(price_history, 6)
            if change_6h and change_6h < -self.config.short_breakdown_threshold:
                logger.info(f"📉 SHORT BREAKDOWN: -{abs(change_6h):.2%} in 6h")
                return True
        
        # Original bounce entry
        recent_low = min(price_history[-24:]) if len(price_history) >= 24 else min(price_history)
        if recent_low <= 0:
            return False
        
        bounce = (price - recent_low) / recent_low
        return bounce >= self.config.short_bounce_threshold
    
    def should_exit_short(self, position: Dict, current_price: float) -> Optional[str]:
        entry = position['entry_price']
        
        tp_price = entry * (1 - self.config.short_tp)
        if current_price <= tp_price:
            return 'tp'
        
        sl_price = entry * (1 + self.config.short_sl)
        if current_price >= sl_price:
            return 'sl'
        
        liq_price = position.get('liq_price', entry * 1.33)
        if current_price >= liq_price * (1 - self.config.liquidation_buffer):
            return 'liq_protection'
        
        # ENHANCED: Exit if trend reverses to strong uptrend
        if self.current_trend == 'strong_uptrend':
            return 'trend_reversal'
        
        return None
    
    async def open_short(self, price: float) -> Optional[Dict]:
        position_pct = self.get_position_size(self.config.short_position_pct)
        position_size = self.config.initial_capital * position_pct
        notional = position_size * self.config.short_leverage
        amount = notional / price
        
        logger.info(f"📉 OPEN SHORT 3x: ${notional:.2f} ({position_pct:.1%} size) @ ${price:.2f}")
        
        if self.config.testnet:
            return {
                'id': f"short_{int(time.time())}",
                'entry_price': price,
                'amount': amount,
                'liq_price': price * 1.33,
                'type': 'short',
                'position_pct': position_pct
            }
        return None
    
    async def close_short(self, position: Dict, price: float, reason: str) -> float:
        entry = position['entry_price']
        amount = position['amount']
        
        pnl = (entry - price) / entry * (amount * entry)
        is_win = pnl > 0
        
        logger.info(f"📉 CLOSE SHORT ({reason}): PnL ${pnl:.2f}")
        
        if self.config.circuit_breaker_enabled:
            self.circuit_breaker.record_trade(pnl, is_win)
            self.current_balance += pnl
            if self.current_balance > self.peak_balance:
                self.peak_balance = self.current_balance
        
        self.stats['trades_short'] += 1
        self.stats['profit_short'] += pnl
        self.stats['profit_total'] += pnl
        
        return pnl
    
    # =========================================================================
    # LONG STRATEGY - Enhanced with tighter grids and pyramiding
    # =========================================================================
    
    def is_long_allowed(self, price: float, price_history: List[float]) -> bool:
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
            price >= ema_value and
            ch_24h >= self.config.long_guard_min_24h_change and
            ch_72h >= self.config.long_guard_min_72h_change
        )
    
    def should_enter_long_grid(self, price: float, price_history: List[float]) -> bool:
        if len(price_history) < 10:
            return False
        
        if not self.is_long_allowed(price, price_history):
            return False
        
        if self.config.circuit_breaker_enabled and self.circuit_breaker.active:
            return False
        
        if not self._check_exposure_limit():
            return False
        
        grid_positions = [p for p in self.positions_long if p.get('type') == 'long_grid']
        if len(grid_positions) >= self.config.max_grid_positions:
            return False
        
        recent_high = max(price_history[-24:]) if len(price_history) >= 24 else max(price_history)
        if recent_high <= 0:
            return False
        
        dip = (recent_high - price) / recent_high
        return dip >= self.config.long_grid_spacing
    
    # =========================================================================
    # TREND FOLLOW - Enhanced with pyramiding
    # =========================================================================
    
    def _get_trend_follow_positions(self) -> List[Dict]:
        return [p for p in self.positions_long if p.get('type') == 'trend_follow']
    
    def _can_reenter_trend_follow(self) -> bool:
        if not self.config.trend_follow_reentry_enabled:
            return False
        
        last_exit_time = getattr(self, '_last_trend_follow_exit', None)
        if last_exit_time is None:
            return True
        
        hours_since_exit = (datetime.now() - last_exit_time).total_seconds() / 3600
        return hours_since_exit >= self.config.trend_follow_reentry_cooldown_hours
    
    def should_enter_trend_follow(self, price: float, price_history: List[float]) -> bool:
        if self.config.circuit_breaker_enabled and self.circuit_breaker.active:
            return False
        
        positions = self._get_trend_follow_positions()
        if len(positions) >= 1 + self.config.trend_follow_max_pyramids:
            return False
        
        if not self._can_reenter_trend_follow():
            return False
        
        if not self.is_long_allowed(price, price_history):
            return False
        
        position_pct = self.get_position_size(self.config.trend_follow_position_pct)
        position_size = self.config.initial_capital * position_pct
        return self._check_exposure_limit(position_size)
    
    def should_add_pyramid(self, price: float, main_position: Dict) -> bool:
        """Add to winning position on dip (pyramiding)."""
        if not self.config.trend_follow_pyramiding_enabled:
            return False
        
        if self.current_trend != 'strong_uptrend':
            return False
        
        pyramid_count = len([p for p in self.positions_pyramid 
                            if p.get('parent_id') == main_position.get('id')])
        if pyramid_count >= self.config.trend_follow_max_pyramids:
            return False
        
        highest = main_position.get('highest_price', main_position['entry_price'])
        dip = (highest - price) / highest
        
        return dip >= self.config.trend_follow_pyramiding_threshold
    
    async def open_trend_follow(self, price: float, is_pyramid: bool = False) -> Optional[Dict]:
        position_pct = self.get_position_size(self.config.trend_follow_position_pct)
        position_size = self.config.initial_capital * position_pct
        amount = position_size / price
        
        pos_type = "PYRAMID" if is_pyramid else "TREND LONG"
        logger.info(f"🚀 OPEN {pos_type}: ${position_size:.2f} ({position_pct:.1%} size) @ ${price:.2f}")
        
        if self.config.testnet:
            pos_id = f"trend_{int(time.time())}"
            return {
                'id': pos_id,
                'entry_price': price,
                'amount': amount,
                'size': position_size,
                'highest_price': price,
                'hard_stop_price': price * (1 - self.config.trend_follow_hard_stop_pct),
                'trailing_stop_price': None,
                'type': 'trend_follow',
                'is_pyramid': is_pyramid,
                'partial_tp_done': False
            }
        return None
    
    def should_exit_trend_follow(self, position: Dict, current_price: float) -> Optional[str]:
        entry = position['entry_price']
        highest_price = max(position.get('highest_price', entry), current_price)
        position['highest_price'] = highest_price
        
        if self.config.trend_follow_partial_tp_enabled and not position.get('partial_tp_done'):
            partial_tp_price = entry * (1 + self.config.trend_follow_partial_tp_pct)
            if current_price >= partial_tp_price:
                return 'partial_tp'
        
        if current_price <= position['hard_stop_price']:
            return 'hard_stop'
        
        activation_price = entry * (1 + self.config.trend_follow_activation_pct)
        if highest_price >= activation_price:
            trailing_stop = highest_price * (1 - self.config.trend_follow_trailing_stop_pct)
            position['trailing_stop_price'] = max(
                position.get('trailing_stop_price') or trailing_stop,
                trailing_stop
            )
            if current_price <= position['trailing_stop_price']:
                return 'trailing_stop'
        
        return None
    
    async def partial_close_trend_follow(self, position: Dict, price: float) -> float:
        entry = position['entry_price']
        close_size = position['amount'] * self.config.trend_follow_partial_tp_size
        
        pnl = (price - entry) / entry * (close_size * entry)
        
        position['amount'] *= (1 - self.config.trend_follow_partial_tp_size)
        position['partial_tp_done'] = True
        
        logger.info(f"🚀 PARTIAL CLOSE (+{self.config.trend_follow_partial_tp_pct:.0%}): "
                   f"Closed {self.config.trend_follow_partial_tp_size:.0%}, PnL ${pnl:.2f}")
        
        if self.config.circuit_breaker_enabled:
            self.circuit_breaker.record_trade(pnl, is_win=True)
            self.current_balance += pnl
            if self.current_balance > self.peak_balance:
                self.peak_balance = self.current_balance
        
        self.stats['trades_long'] += 1
        self.stats['profit_long'] += pnl
        self.stats['profit_total'] += pnl
        
        return pnl
    
    async def close_trend_follow(self, position: Dict, price: float, reason: str) -> float:
        entry = position['entry_price']
        amount = position['amount']
        pnl = (price - entry) / entry * (amount * entry)
        is_win = pnl > 0
        
        logger.info(f"🚀 CLOSE TREND LONG ({reason}): PnL ${pnl:.2f}")
        
        if self.config.trend_follow_reentry_enabled:
            self._last_trend_follow_exit = datetime.now()
        
        if self.config.circuit_breaker_enabled:
            self.circuit_breaker.record_trade(pnl, is_win)
            self.current_balance += pnl
            if self.current_balance > self.peak_balance:
                self.peak_balance = self.current_balance
        
        self.stats['trades_long'] += 1
        self.stats['profit_long'] += pnl
        self.stats['profit_total'] += pnl
        
        return pnl
    
    async def open_long_grid(self, price: float) -> Optional[Dict]:
        position_pct = self.get_position_size(self.config.long_position_pct)
        position_size = self.config.initial_capital * position_pct
        amount = position_size / price
        
        logger.info(f"📈 OPEN LONG Grid: ${position_size:.2f} ({position_pct:.1%} size) @ ${price:.2f}")
        
        if self.config.testnet:
            return {
                'id': f"long_{int(time.time())}",
                'entry_price': price,
                'amount': amount,
                'tp_price': price * (1 + self.config.long_markup),
                'type': 'long_grid',
                'position_pct': position_pct
            }
        return None
    
    async def close_long_grid(self, position: Dict, price: float) -> float:
        entry = position['entry_price']
        amount = position['amount']
        pnl = (price - entry) / entry * (amount * entry)
        is_win = pnl > 0
        
        logger.info(f"📈 CLOSE LONG Grid: PnL ${pnl:.2f}")
        
        if self.config.circuit_breaker_enabled:
            self.circuit_breaker.record_trade(pnl, is_win)
            self.current_balance += pnl
            if self.current_balance > self.peak_balance:
                self.peak_balance = self.current_balance
        
        self.stats['trades_long'] += 1
        self.stats['profit_long'] += pnl
        self.stats['profit_total'] += pnl
        
        return pnl
    
    def _check_exposure_limit(self, new_position_size: float = 0) -> bool:
        current_exposure = sum(p.get('size', 0) for p in self.positions_long + self.positions_short)
        current_exposure += sum(p.get('size', 0) for p in self.positions_pyramid)
        exposure_pct = (current_exposure + new_position_size) / self.current_balance if self.current_balance > 0 else 0
        return exposure_pct <= self.config.max_total_exposure_pct
    
    # =========================================================================
    # SIDEWAYS - Reduced activity
    # =========================================================================
    
    async def execute_sideways_strategy(self, price: float, price_history: List[float], allow_new_entries: bool = True):
        """Minimal activity in sideways - just preserve capital."""
        if not allow_new_entries:
            return
        
        # In sideways, only allow 2 positions max
        sideways_positions = [p for p in self.positions_long if p.get('type') == 'sideways']
        if len(sideways_positions) >= self.config.sideways_max_positions:
            return
        
        # Check exits
        for pos in self.positions_long[:]:
            if pos.get('type') == 'sideways':
                entry = pos['entry_price']
                tp_price = entry * (1 + self.config.sideways_markup)
                if price >= tp_price:
                    await self.close_sideways_position(pos, price, 'TP')
                    self.positions_long.remove(pos)
        
        # Minimal entries - only clear setups
        if allow_new_entries and len(sideways_positions) < self.config.sideways_max_positions:
            if len(price_history) >= 48:
                recent_prices = price_history[-48:]
                high = max(recent_prices)
                low = min(recent_prices)
                mid = (high + low) / 2
                
                # Only buy near low with markup potential
                if price <= low * 1.02 and price >= low * 1.005:
                    pos = await self.open_sideways_position(price)
                    if pos:
                        self.positions_long.append(pos)
    
    async def open_sideways_position(self, price: float) -> Optional[Dict]:
        position_pct = self.config.sideways_grid_pct * 0.25  # Small position
        position_size = self.config.initial_capital * position_pct
        amount = position_size / price
        
        logger.info(f"📊 OPEN SIDEWAYS (minimal): ${position_size:.2f} @ ${price:.2f}")
        
        if self.config.testnet:
            return {
                'id': f"sideways_{int(time.time())}",
                'entry_price': price,
                'amount': amount,
                'tp_price': price * (1 + self.config.sideways_markup),
                'type': 'sideways'
            }
        return None
    
    async def close_sideways_position(self, position: Dict, price: float, reason: str) -> float:
        entry = position['entry_price']
        amount = position['amount']
        pnl = (price - entry) / entry * (amount * entry)
        is_win = pnl > 0
        
        logger.info(f"📊 CLOSE SIDEWAYS ({reason}): PnL ${pnl:.2f}")
        
        if self.config.circuit_breaker_enabled:
            self.circuit_breaker.record_trade(pnl, is_win)
            self.current_balance += pnl
            if self.current_balance > self.peak_balance:
                self.peak_balance = self.current_balance
        
        self.stats['profit_long'] += pnl
        self.stats['profit_total'] += pnl
        
        return pnl
    
    # =========================================================================
    # MAIN LOOP
    # =========================================================================
    
    async def run(self):
        logger.info("="*70)
        logger.info("🚀 UNIFIED BOT ENHANCED v4.1 STARTED")
        logger.info("="*70)
        logger.info(f"Capital: ${self.config.initial_capital}")
        logger.info(f"Target: 5% bear / 10% bull | Max DD: {self.config.max_drawdown_pct:.0%}")
        logger.info(f"Dynamic sizing: {self.config.dynamic_sizing_enabled}")
        logger.info(f"Circuit Breaker: {self.config.max_daily_loss_pct:.0%} daily / {self.config.max_drawdown_pct:.0%} DD")
        logger.info("="*70)
        
        if not await self.initialize():
            logger.error("❌ Failed to initialize. Exiting.")
            return
        
        price_history = []
        last_trend_print = time.time()
        previous_trend = self.current_trend
        last_day = datetime.now().date()
        
        while True:
            try:
                current_day = datetime.now().date()
                if current_day != last_day:
                    if self.config.circuit_breaker_enabled:
                        self.circuit_breaker.reset_daily()
                    last_day = current_day
                    logger.info("📅 New day - daily stats reset")
                    logger.info(f"📊 Balance: ${self.current_balance:.2f} | PnL today: ${self.circuit_breaker.daily_pnl:.2f}")
                
                # Circuit breaker check
                if self.config.circuit_breaker_enabled:
                    should_stop, cb_reason = self.circuit_breaker.check(self.current_balance)
                    if should_stop:
                        logger.warning(f"⏸️  Trading suspended: {cb_reason}")
                        await asyncio.sleep(60)
                        continue
                
                # Get price (simplified)
                try:
                    ticker = self.exchange.fetch_ticker(self.config.symbol)
                    price = ticker['last']
                except Exception as e:
                    logger.error(f"Price fetch failed: {e}")
                    await asyncio.sleep(self.config.check_interval)
                    continue
                
                price_history.append(price)
                if len(price_history) > 3000:
                    price_history = price_history[-2880:]
                
                # Detect trend
                new_trend = self.detect_trend(price_history)
                
                if time.time() - last_trend_print > 3600:
                    logger.info(f"📊 Trend: {self.current_trend.upper()} | Balance: ${self.current_balance:.2f}")
                    last_trend_print = time.time()
                
                # Trend change handling
                if new_trend != previous_trend:
                    logger.info(f"🔄 TREND CHANGE: {previous_trend} → {new_trend}")
                    self.current_trend = new_trend
                    previous_trend = new_trend
                
                # Execute strategy based on trend
                if self.current_trend in ('strong_downtrend', 'bear_rally'):
                    # SHORT STRATEGY
                    for pos in self.positions_short[:]:
                        exit_reason = self.should_exit_short(pos, price)
                        if exit_reason:
                            await self.close_short(pos, price, exit_reason)
                            self.positions_short.remove(pos)
                    
                    if self.should_enter_short(price, price_history):
                        pos = await self.open_short(price)
                        if pos:
                            self.positions_short.append(pos)
                
                elif self.current_trend == 'strong_uptrend':
                    # STRONG UPTREND: Trend follow + pyramiding
                    for pos in self.positions_short[:]:
                        await self.close_short(pos, price, 'trend_change')
                        self.positions_short.remove(pos)
                    
                    # Manage existing trend positions
                    for pos in self.positions_long[:]:
                        if pos.get('type') == 'trend_follow':
                            exit_reason = self.should_exit_trend_follow(pos, price)
                            if exit_reason == 'partial_tp':
                                await self.partial_close_trend_follow(pos, price)
                            elif exit_reason:
                                await self.close_trend_follow(pos, price, exit_reason)
                                self.positions_long.remove(pos)
                            else:
                                # Check for pyramiding
                                if self.should_add_pyramid(price, pos):
                                    pyramid_pos = await self.open_trend_follow(price, is_pyramid=True)
                                    if pyramid_pos:
                                        pyramid_pos['parent_id'] = pos.get('id')
                                        self.positions_pyramid.append(pyramid_pos)
                    
                    # Enter new trend follow
                    if self.should_enter_trend_follow(price, price_history):
                        pos = await self.open_trend_follow(price)
                        if pos:
                            self.positions_long.append(pos)
                
                elif self.current_trend == 'pullback_uptrend':
                    # PULLBACK: Grid buying
                    for pos in self.positions_long[:]:
                        if pos.get('type') == 'long_grid' and price >= pos['tp_price']:
                            await self.close_long_grid(pos, price)
                            self.positions_long.remove(pos)
                    
                    if not any(p.get('type') == 'long_grid' for p in self.positions_long):
                        if self.should_enter_long_grid(price, price_history):
                            pos = await self.open_long_grid(price)
                            if pos:
                                self.positions_long.append(pos)
                
                else:  # sideways
                    # SIDEWAYS: Minimal activity
                    for pos in self.positions_short[:]:
                        await self.close_short(pos, price, 'sideways')
                        self.positions_short.remove(pos)
                    
                    allow_sideways = self.is_long_allowed(price, price_history)
                    await self.execute_sideways_strategy(price, price_history, allow_sideways)
                
                await asyncio.sleep(self.config.check_interval)
                
            except KeyboardInterrupt:
                logger.info("Bot stopped by user")
                break
            except Exception as e:
                logger.error(f"Error: {e}")
                await asyncio.sleep(self.config.check_interval)
        
        self.print_stats()
    
    def print_stats(self):
        logger.info("="*70)
        logger.info("📊 FINAL STATISTICS")
        logger.info("="*70)
        logger.info(f"Final Balance: ${self.current_balance:.2f} (Peak: ${self.peak_balance:.2f})")
        if self.peak_balance > self.config.initial_capital:
            max_dd = (self.peak_balance - min(self.current_balance, self.config.initial_capital)) / self.peak_balance
            logger.info(f"Max Drawdown: {max_dd:.2%}")
        logger.info(f"Total Return: {(self.current_balance - self.config.initial_capital) / self.config.initial_capital:.2%}")
        logger.info(f"Trades: {self.stats['trades_short'] + self.stats['trades_long']} "
                   f"(Short: {self.stats['trades_short']}, Long: {self.stats['trades_long']})")
        logger.info(f"PnL: Short ${self.stats['profit_short']:.2f}, Long ${self.stats['profit_long']:.2f}")
        logger.info(f"Total PnL: ${self.stats['profit_total']:.2f}")
        logger.info("="*70)


def main():
    parser = argparse.ArgumentParser(description='Unified Bot ENHANCED v4.1')
    parser.add_argument('--config', default='config_enhanced.json')
    parser.add_argument('--testnet', action='store_true')
    parser.add_argument('--live', action='store_true')
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
    
    bot = UnifiedBotEnhanced(config)
    
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("\n✋ Bot stopped")


if __name__ == '__main__':
    main()
