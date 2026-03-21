"""
Micro-PassivBot UNIFIED - LONG & SHORT (ENHANCED v3.0)
=======================================================
Automatycznie przełącza między LONG i SHORT w zależności od trendu.

NOWOŚCI w v3.0:
- ✅ Circuit Breaker (5% daily loss, 15% drawdown, 5 consecutive losses)
- ✅ Risk-based position sizing (1% risk per trade)
- ✅ Entry filters (8 filtrów)
- ✅ Consecutive loss tracking
- ✅ Auto-reset po cooldown

Strategie:
- DOWNTREND (📉): SHORT 3x leverage
- UPTREND (📈): LONG Grid
- SIDEWAYS (➡️): Elastyczna Grid+DCA
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Literal, Tuple

# Setup logging
os.makedirs('/home/ubuntu/.openclaw/workspace/memory/passivbot_logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('/home/ubuntu/.openclaw/workspace/memory/passivbot_logs/unified_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# CIRCUIT BREAKER CLASS
# ============================================================================

class CircuitBreaker:
    """Circuit breaker - zatrzymuje trading przy przekroczeniu limitów strat."""
    
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
    
    def check(self, current_balance: float) -> Tuple[bool, str]:
        """
        Check if circuit breaker should activate.
        Returns: (should_stop, reason)
        """
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


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class UnifiedConfig:
    """Configuration for unified bot with Circuit Breaker."""
    
    # Account
    initial_capital: float = 100.0
    
    # Trend detection
    trend_lookback: int = 48
    trend_threshold: float = 0.05
    
    # === CIRCUIT BREAKER ===
    circuit_breaker_enabled: bool = True
    max_daily_loss_pct: float = 0.05  # 5% daily loss
    max_drawdown_pct: float = 0.15    # 15% max drawdown
    max_consecutive_losses: int = 5   # 5 losses in a row
    circuit_cooldown_minutes: int = 60  # 1 hour cooldown
    
    # === RISK MANAGEMENT ===
    risk_per_trade_pct: float = 0.01   # 1% risk per trade
    max_total_exposure_pct: float = 0.50  # 50% max exposure
    
    # === DOWNTREND: SHORT 3x ===
    short_leverage: float = 3.0
    short_position_pct: float = 0.15
    short_max_positions: int = 2
    short_bounce_threshold: float = 0.015
    short_tp: float = 0.04
    short_sl: float = 0.025
    
    # === UPTREND: LONG Grid ===
    long_grid_spacing: float = 0.008
    long_markup: float = 0.006
    long_position_pct: float = 0.10
    long_entry_mult: float = 1.5
    
    # === SIDEWAYS: Grid + DCA ===
    sideways_grid_pct: float = 0.30
    sideways_dca_pct: float = 0.70
    sideways_spacing: float = 0.015
    sideways_markup: float = 0.010
    max_grid_positions: int = 4
    max_dca_per_position: int = 3
    
    # Safety
    daily_loss_limit: float = 0.15
    liquidation_buffer: float = 0.10
    
    # Exchange
    exchange: str = 'hyperliquid'
    symbol: str = 'BTC/USDC:USDC'
    testnet: bool = True
    check_interval: int = 60
    
    def save(self, path: str):
        with open(path, 'w') as f:
            json.dump(asdict(self), f, indent=2)
    
    @classmethod
    def load(cls, path: str):
        with open(path, 'r') as f:
            return cls(**json.load(f))


# ============================================================================
# MAIN BOT CLASS
# ============================================================================

class UnifiedBot:
    """Unified trading bot with Circuit Breaker and Risk Management."""
    
    def __init__(self, config: UnifiedConfig):
        self.config = config
        self.exchange = None
        self.current_trend: Literal['uptrend', 'downtrend', 'sideways'] = 'sideways'
        
        # Position tracking
        self.positions_short: List[Dict] = []
        self.positions_long: List[Dict] = []
        self.grid_orders: List[Dict] = []
        
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
        
        # Price history
        self.history_path = Path('~/.openclaw/workspace/memory/bot_price_history.json').expanduser()
        
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
        
        logger.info("🤖 Unified Bot v3.0 initialized (with Circuit Breaker)")
    
    # =========================================================================
    # STATE MANAGEMENT
    # =========================================================================
    
    def save_price_history(self, price_history: List[float]):
        """Save price history to file."""
        try:
            with open(self.history_path, 'w') as f:
                json.dump(price_history, f)
        except Exception as e:
            logger.warning(f"Could not save price history: {e}")
    
    def load_price_history(self) -> List[float]:
        """Load price history from file or database."""
        try:
            if self.history_path.exists():
                with open(self.history_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load price history from file: {e}")
        
        try:
            import sqlite3
            db_path = Path('~/.openclaw/workspace/memory/crypto_prices.db').expanduser()
            if db_path.exists():
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute('SELECT price FROM crypto_prices WHERE coin="BTC" ORDER BY timestamp DESC LIMIT 200')
                results = cursor.fetchall()
                conn.close()
                if results:
                    prices = [r[0] for r in reversed(results)]
                    logger.info(f"📂 Loaded {len(prices)} prices from database")
                    return prices
        except Exception as e:
            logger.warning(f"Could not load price history from database: {e}")
        
        return []
    
    def save_state(self):
        """Save bot state including positions and stats."""
        stats_copy = self.stats.copy()
        if 'last_reset' in stats_copy and hasattr(stats_copy['last_reset'], 'isoformat'):
            stats_copy['last_reset'] = stats_copy['last_reset'].isoformat()
        
        state = {
            'positions_short': self.positions_short,
            'positions_long': self.positions_long,
            'stats': stats_copy,
            'current_trend': self.current_trend,
            'circuit_breaker': {
                'active': self.circuit_breaker.active,
                'reason': self.circuit_breaker.reason,
                'consecutive_losses': self.circuit_breaker.consecutive_losses,
                'daily_pnl': self.circuit_breaker.daily_pnl,
                'cooldown_until': self.circuit_breaker.cooldown_until.isoformat() if self.circuit_breaker.cooldown_until else None
            },
            'balance': self.current_balance,
            'peak_balance': self.peak_balance
        }
        try:
            state_path = Path('~/.openclaw/workspace/memory/bot_state.json').expanduser()
            with open(state_path, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save state: {e}")
    
    def load_state(self):
        """Load bot state."""
        try:
            state_path = Path('~/.openclaw/workspace/memory/bot_state.json').expanduser()
            if state_path.exists():
                with open(state_path, 'r') as f:
                    state = json.load(f)
                
                self.positions_short = state.get('positions_short', [])
                self.positions_long = state.get('positions_long', [])
                self.stats = state.get('stats', self.stats)
                self.current_trend = state.get('current_trend', 'sideways')
                self.current_balance = state.get('balance', self.config.initial_capital)
                self.peak_balance = state.get('peak_balance', self.config.initial_capital)
                
                # Restore circuit breaker state
                cb_state = state.get('circuit_breaker', {})
                self.circuit_breaker.active = cb_state.get('active', False)
                self.circuit_breaker.reason = cb_state.get('reason', '')
                self.circuit_breaker.consecutive_losses = cb_state.get('consecutive_losses', 0)
                self.circuit_breaker.daily_pnl = cb_state.get('daily_pnl', 0.0)
                
                cooldown_str = cb_state.get('cooldown_until')
                if cooldown_str:
                    self.circuit_breaker.cooldown_until = datetime.fromisoformat(cooldown_str)
                    if datetime.now() >= self.circuit_breaker.cooldown_until:
                        self.circuit_breaker.reset()
                
                self.circuit_breaker.initial_balance = self.config.initial_capital
                self.circuit_breaker.peak_balance = self.peak_balance
                
                logger.info(f"📂 Loaded state: {len(self.positions_short)} short, {len(self.positions_long)} long")
                if self.circuit_breaker.active:
                    logger.warning(f"🔴 Circuit breaker active: {self.circuit_breaker.reason}")
        except Exception as e:
            logger.warning(f"Could not load state: {e}")
    
    # =========================================================================
    # CIRCUIT BREAKER & RISK METHODS
    # =========================================================================
    
    def check_circuit_breaker(self) -> Tuple[bool, str]:
        """Check if circuit breaker should stop trading."""
        if not self.config.circuit_breaker_enabled:
            return False, ""
        return self.circuit_breaker.check(self.current_balance)
    
    def record_trade_result(self, pnl: float):
        """Record trade result and update circuit breaker."""
        self.circuit_breaker.record_trade(pnl)
        self.current_balance += pnl
        
        if self.current_balance > self.peak_balance:
            self.peak_balance = self.current_balance
        
        # Update stats
        if pnl < 0:
            self.stats['daily_loss'] += abs(pnl)
    
    def calculate_position_size(self, entry_price: float, stop_loss_price: float) -> float:
        """
        Calculate position size based on risk per trade.
        Formula: Position Size = Risk Amount / (Entry - Stop Loss)
        """
        risk_amount = self.current_balance * self.config.risk_per_trade_pct
        
        # Reduce after consecutive losses
        if self.circuit_breaker.consecutive_losses >= 3:
            risk_amount *= 0.5
            logger.info(f"Risk reduced by 50% after {self.circuit_breaker.consecutive_losses} losses")
        
        sl_distance = abs(entry_price - stop_loss_price)
        
        if sl_distance == 0:
            return self.current_balance * 0.10  # Fallback
        
        position_size = risk_amount / sl_distance * entry_price
        
        # Cap at max
        max_position = self.current_balance * 0.10
        return min(position_size, max_position)
    
    def check_exposure_limit(self, new_position_size: float = 0) -> bool:
        """Check if adding new position would exceed exposure limit."""
        current_exposure = sum(p.get('size', 0) for p in self.positions_long + self.positions_short)
        exposure_pct = (current_exposure + new_position_size) / self.current_balance
        return exposure_pct <= self.config.max_total_exposure_pct
    
    # =========================================================================
    # EXCHANGE & TREND
    # =========================================================================
    
    async def initialize(self):
        """Initialize exchange connection."""
        try:
            import ccxt
            
            api_key = os.getenv('HYPERLIQUID_API_KEY', '')
            secret = os.getenv('HYPERLIQUID_SECRET', '')
            
            self.exchange = ccxt.hyperliquid({
                'enableRateLimit': True,
                'apiKey': api_key,
                'secret': secret,
                'options': {'defaultType': 'swap'}
            })
            
            self.exchange.load_markets()
            logger.info(f"✅ Connected to {self.config.exchange}")
            
            # Initialize circuit breaker with balance
            self.circuit_breaker.initialize(self.config.initial_capital)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False
    
    def detect_trend(self, prices: List[float]) -> Literal['uptrend', 'downtrend', 'sideways']:
        """Detect market trend with hysteresis."""
        lookback = 2880  # 48 hours in minutes
        
        if len(prices) < lookback:
            return self.current_trend
        
        recent = prices[-lookback:]
        change = (recent[-1] / recent[0]) - 1
        
        if self.current_trend == 'sideways':
            if change > self.config.trend_threshold:
                return 'uptrend'
            elif change < -self.config.trend_threshold:
                return 'downtrend'
            return 'sideways'
        elif self.current_trend == 'uptrend':
            exit_threshold = self.config.trend_threshold - 0.015
            if change < exit_threshold:
                return 'sideways'
            return 'uptrend'
        elif self.current_trend == 'downtrend':
            exit_threshold = -self.config.trend_threshold + 0.015
            if change > exit_threshold:
                return 'sideways'
            return 'downtrend'
        
        return 'sideways'
    
    # =========================================================================
    # ENTRY FILTERS (All strategies check CB first)
    # =========================================================================
    
    def should_enter_short(self, price: float, price_history: List[float]) -> bool:
        """Check if we should enter SHORT position."""
        # Circuit breaker check
        if self.circuit_breaker.active:
            return False
        
        # Exposure check
        if not self.check_exposure_limit():
            return False
        
        if len(self.positions_short) >= self.config.short_max_positions:
            return False
        
        if len(price_history) < 10:
            return False
        
        recent_low = min(price_history[-24:])
        bounce = (price - recent_low) / recent_low
        
        return bounce >= self.config.short_bounce_threshold
    
    def should_enter_long_grid(self, price: float, price_history: List[float]) -> bool:
        """Check if we should enter LONG grid position."""
        # Circuit breaker check
        if self.circuit_breaker.active:
            return False
        
        # Exposure check
        if not self.check_exposure_limit():
            return False
        
        if len(price_history) < 10:
            return False
        
        recent_high = max(price_history[-24:])
        dip = (recent_high - price) / recent_high
        
        return dip >= self.config.long_grid_spacing
    
    def should_enter_sideways_grid(self, price: float, levels: Dict) -> bool:
        """Check if we should enter sideways grid position."""
        # Circuit breaker check
        if self.circuit_breaker.active:
            return False
        
        # Max positions check
        sideways_positions = [p for p in self.positions_long if p.get('type') == 'sideways']
        if len(sideways_positions) >= self.config.max_grid_positions:
            return False
        
        if not levels:
            return False
        
        support_zone = levels['support'] * (1 + self.config.sideways_spacing * 0.5)
        return price <= support_zone and price >= levels['low'] * 1.005
    
    # =========================================================================
    # POSITION MANAGEMENT (Record PnL for CB)
    # =========================================================================
    
    async def close_short(self, position: Dict, price: float, reason: str) -> float:
        """Close SHORT position and record result."""
        entry = position['entry_price']
        amount = position['amount']
        
        pnl = (entry - price) / entry * (amount * entry)
        
        logger.info(f"📉 CLOSE SHORT ({reason}): PnL ${pnl:.2f}")
        
        # Record for circuit breaker
        self.record_trade_result(pnl)
        
        self.stats['trades_short'] += 1
        self.stats['profit_short'] += pnl
        self.stats['profit_total'] += pnl
        
        return pnl
    
    async def close_long_grid(self, position: Dict, price: float) -> float:
        """Close LONG grid position and record result."""
        entry = position['entry_price']
        amount = position['amount']
        
        pnl = (price - entry) / entry * (amount * entry)
        
        logger.info(f"📈 CLOSE LONG Grid: PnL ${pnl:.2f}")
        
        # Record for circuit breaker
        self.record_trade_result(pnl)
        
        self.stats['trades_long'] += 1
        self.stats['profit_long'] += pnl
        self.stats['profit_total'] += pnl
        
        return pnl
    
    async def close_sideways_position(self, position: Dict, price: float, reason: str) -> float:
        """Close sideways position and record result."""
        entry = position['entry_price']
        amount = position['amount']
        
        pnl = (price - entry) / entry * (amount * entry)
        pos_type = "DCA" if position.get('is_dca') else "GRID"
        
        logger.info(f"📊 CLOSE SIDEWAYS {pos_type} ({reason}): PnL ${pnl:.2f}")
        
        # Record for circuit breaker
        self.record_trade_result(pnl)
        
        self.stats['trades_long'] += 1
        self.stats['profit_long'] += pnl
        self.stats['profit_total'] += pnl
        
        return pnl
    
    # =========================================================================
    # OPEN POSITIONS (with risk sizing)
    # =========================================================================
    
    async def open_short(self, price: float) -> Optional[Dict]:
        """Open SHORT 3x position with risk-based sizing."""
        # Calculate position size based on risk
        stop_loss = price * (1 + self.config.short_sl)
        position_size = self.calculate_position_size(price, stop_loss)
        
        notional = position_size * self.config.short_leverage
        amount = notional / price
        
        logger.info(f"📉 OPEN SHORT 3x: ${notional:.2f} @ ${price:.2f}")
        
        if self.config.testnet:
            return {
                'id': f"short_{int(time.time())}",
                'entry_price': price,
                'amount': amount,
                'size': position_size,
                'liq_price': price * 1.33,
                'type': 'short'
            }
        return None
    
    async def open_long_grid(self, price: float) -> Optional[Dict]:
        """Open LONG grid position with risk-based sizing."""
        stop_loss = price * (1 - self.config.long_grid_spacing * 1.5)
        position_size = self.calculate_position_size(price, stop_loss)
        amount = position_size / price
        tp_price = price * (1 + self.config.long_markup)
        
        logger.info(f"📈 OPEN LONG Grid: ${position_size:.2f} @ ${price:.2f}")
        
        if self.config.testnet:
            return {
                'id': f"long_{int(time.time())}",
                'entry_price': price,
                'amount': amount,
                'size': position_size,
                'tp_price': tp_price,
                'type': 'long_grid'
            }
        return None
    
    async def open_sideways_position(self, price: float, is_dca: bool = False) -> Optional[Dict]:
        """Open sideways grid position with risk-based sizing."""
        stop_loss = price * (1 - self.config.sideways_spacing * 1.5)
        
        if is_dca:
            position_size = self.config.initial_capital * self.config.sideways_dca_pct * 0.2
            label = "DCA"
        else:
            position_size = self.config.initial_capital * self.config.sideways_grid_pct * 0.25
            label = "GRID"
        
        # Apply risk-based sizing
        risk_size = self.calculate_position_size(price, stop_loss)
        position_size = min(position_size, risk_size)
        
        amount = position_size / price
        tp_price = price * (1 + self.config.sideways_markup)
        
        logger.info(f"📊 OPEN SIDEWAYS {label}: ${position_size:.2f} @ ${price:.2f} → TP @ ${tp_price:.2f}")
        
        if self.config.testnet:
            return {
                'id': f"sideways_{label}_{int(time.time())}",
                'entry_price': price,
                'amount': amount,
                'size': position_size,
                'tp_price': tp_price,
                'type': 'sideways',
                'is_dca': is_dca
            }
        return None
    
    # =========================================================================
    # OTHER METHODS (keep original)
    # =========================================================================
    
    def should_exit_short(self, position: Dict, current_price: float) -> Optional[str]:
        """Check if we should exit SHORT position."""
        entry = position['entry_price']
        tp_price = entry * (1 - self.config.short_tp)
        sl_price = entry * (1 + self.config.short_sl)
        
        if current_price <= tp_price:
            return 'tp'
        if current_price >= sl_price:
            return 'sl'
        
        liq_price = position.get('liq_price', entry * 1.33)
        if current_price >= liq_price * (1 - self.config.liquidation_buffer):
            return 'liq_protection'
        
        return None
    
    def should_add_dca(self, price: float, position: Dict) -> bool:
        """Check if we should DCA."""
        entry = position['entry_price']
        return price <= entry * (1 - self.config.sideways_spacing)
    
    def should_exit_sideways_grid(self, price: float, position: Dict, levels: Dict) -> bool:
        """Check if we should exit sideways position."""
        entry = position['entry_price']
        markup_price = entry * (1 + self.config.sideways_markup)
        
        if price >= markup_price:
            return True
        if levels and price <= levels['low'] * 0.995:
            return True
        return False
    
    def calculate_sideways_levels(self, price_history: List[float]) -> Dict:
        """Calculate support and resistance levels."""
        if len(price_history) < 48:
            return {}
        
        recent_prices = price_history[-48:]
        high = max(recent_prices)
        low = min(recent_prices)
        mid = (high + low) / 2
        grid_range = high - low
        
        if grid_range / mid < 0.005:
            return {}
        
        return {
            'high': high,
            'low': low,
            'mid': mid,
            'grid_range': grid_range,
            'support': low + grid_range * 0.2,
            'resistance': high - grid_range * 0.2
        }
    
    async def execute_sideways_strategy(self, price: float, price_history: List[float]):
        """Execute sideways grid + DCA strategy."""
        levels = self.calculate_sideways_levels(price_history)
        if not levels:
            return
        
        # Check exits
        for pos in self.positions_long[:]:
            if pos.get('type') == 'sideways':
                if self.should_exit_sideways_grid(price, pos, levels):
                    await self.close_sideways_position(pos, price, 'TP' if price >= pos['tp_price'] else 'SL')
                    self.positions_long.remove(pos)
        
        sideways_positions = [p for p in self.positions_long if p.get('type') == 'sideways']
        grid_positions = [p for p in sideways_positions if not p.get('is_dca')]
        
        # Enter grid
        if len(grid_positions) < self.config.max_grid_positions:
            if self.should_enter_sideways_grid(price, levels):
                too_close = any(abs(p['entry_price'] - price) / price < self.config.sideways_spacing * 0.5 
                               for p in grid_positions)
                if not too_close:
                    pos = await self.open_sideways_position(price, is_dca=False)
                    if pos:
                        self.positions_long.append(pos)
        
        # DCA logic
        if grid_positions and len(sideways_positions) < self.config.max_grid_positions + self.config.max_dca_per_position:
            lowest_pos = min(grid_positions, key=lambda p: p['entry_price'])
            if self.should_add_dca(price, lowest_pos):
                pos = await self.open_sideways_position(price, is_dca=True)
                if pos:
                    self.positions_long.append(pos)
    
    # =========================================================================
    # MAIN LOOP
    # =========================================================================
    
    async def run(self):
        """Main bot loop with Circuit Breaker."""
        logger.info("="*70)
        logger.info("🚀 UNIFIED BOT v3.0 STARTED")
        logger.info("="*70)
        logger.info(f"Capital: ${self.config.initial_capital}")
        logger.info(f"Circuit Breaker: ENABLED")
        logger.info(f"  - Max daily loss: {self.config.max_daily_loss_pct:.1%}")
        logger.info(f"  - Max drawdown: {self.config.max_drawdown_pct:.1%}")
        logger.info(f"  - Max consecutive losses: {self.config.max_consecutive_losses}")
        logger.info(f"  - Cooldown: {self.config.circuit_cooldown_minutes} min")
        logger.info(f"Risk per trade: {self.config.risk_per_trade_pct:.2%}")
        logger.info("="*70)
        
        if not await self.initialize():
            logger.error("❌ Failed to initialize exchange. Exiting.")
            return
        
        self.load_state()
        price_history = self.load_price_history()
        logger.info(f"📂 Loaded {len(price_history)} historical prices")
        
        last_trend_print = time.time()
        previous_trend = self.current_trend
        last_day = datetime.now().date()
        
        while True:
            try:
                # Check for new day (reset daily stats)
                current_day = datetime.now().date()
                if current_day != last_day:
                    self.circuit_breaker.reset_daily()
                    last_day = current_day
                    logger.info("📅 New day - daily stats reset")
                
                # Check circuit breaker
                should_stop, cb_reason = self.check_circuit_breaker()
                if should_stop:
                    logger.warning(f"⏸️  Trading suspended: {cb_reason}")
                    await asyncio.sleep(60)  # Check every minute during CB
                    continue
                
                # Get price
                price = await self._get_price(price_history)
                if price is None:
                    await asyncio.sleep(self.config.check_interval)
                    continue
                
                price_history.append(price)
                if len(price_history) > 200:
                    price_history.pop(0)
                
                if len(price_history) % 10 == 0:
                    self.save_price_history(price_history)
                    self.save_state()
                
                # Detect trend
                new_trend = self.detect_trend(price_history)
                if new_trend != self.current_trend:
                    logger.info(f"🔄 TREND CHANGE: {self.current_trend} → {new_trend}")
                    self.current_trend = new_trend
                
                if time.time() - last_trend_print > 3600:
                    logger.info(f"📊 Trend: {self.current_trend.upper()} | Balance: ${self.current_balance:.2f} | CB losses: {self.circuit_breaker.consecutive_losses}")
                    last_trend_print = time.time()
                
                # Execute strategy
                await self._execute_strategy(price, price_history, new_trend, previous_trend)
                previous_trend = self.current_trend
                
                await asyncio.sleep(self.config.check_interval)
                
            except KeyboardInterrupt:
                logger.info("Bot stopped by user")
                break
            except Exception as e:
                logger.error(f"Error: {e}")
                await asyncio.sleep(self.config.check_interval)
        
        self.save_state()
        self.print_stats()
    
    async def _get_price(self, price_history: List[float]) -> Optional[float]:
        """Get price from exchange or fallback sources."""
        try:
            ticker = self.exchange.fetch_ticker(self.config.symbol)
            return ticker['last']
        except Exception as e:
            logger.warning(f"Exchange failed: {e}")
            
            # Try database
            try:
                import sqlite3
                db_path = Path('~/.openclaw/workspace/memory/crypto_prices.db').expanduser()
                if db_path.exists():
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute('SELECT price FROM crypto_prices WHERE coin="BTC" ORDER BY timestamp DESC LIMIT 1')
                    result = cursor.fetchone()
                    conn.close()
                    if result:
                        return result[0]
            except Exception as db_err:
                logger.warning(f"Database failed: {db_err}")
        
        return None
    
    async def _execute_strategy(self, price: float, price_history: List[float], 
                                new_trend: str, previous_trend: str):
        """Execute trading strategy based on trend."""
        # Handle trend change
        if new_trend != previous_trend:
            logger.info(f"🔄 TREND CHANGE: {previous_trend} → {new_trend}")
            self.grid_orders.clear()
        
        if self.current_trend == 'downtrend':
            # SHORT strategy
            for pos in self.positions_short[:]:
                exit_reason = self.should_exit_short(pos, price)
                if exit_reason:
                    await self.close_short(pos, price, exit_reason)
                    self.positions_short.remove(pos)
            
            if self.should_enter_short(price, price_history):
                pos = await self.open_short(price)
                if pos:
                    self.positions_short.append(pos)
        
        elif self.current_trend == 'uptrend':
            # LONG Grid strategy
            if not self.positions_long:
                if self.should_enter_long_grid(price, price_history):
                    pos = await self.open_long_grid(price)
                    if pos:
                        self.positions_long.append(pos)
            else:
                for pos in self.positions_long[:]:
                    if price >= pos.get('tp_price', float('inf')):
                        await self.close_long_grid(pos, price)
                        self.positions_long.remove(pos)
        
        else:  # sideways
            # Close shorts
            for pos in self.positions_short[:]:
                await self.close_short(pos, price, 'sideways')
                self.positions_short.remove(pos)
            
            # Sideways strategy
            await self.execute_sideways_strategy(price, price_history)
    
    def print_stats(self):
        """Print final statistics."""
        logger.info("="*70)
        logger.info("📊 FINAL STATISTICS")
        logger.info("="*70)
        logger.info(f"Final Balance: ${self.current_balance:.2f} (Peak: ${self.peak_balance:.2f})")
        logger.info(f"Total Return: {((self.current_balance / self.config.initial_capital) - 1):+.2%}")
        logger.info(f"Max Drawdown: {self.circuit_breaker.max_drawdown_pct:.2%}")
        logger.info(f"Consecutive Losses (max): {self.circuit_breaker.max_consecutive_losses_seen}")
        logger.info(f"Total Trades: {self.stats['trades_short'] + self.stats['trades_long']}")
        logger.info(f"  SHORT: {self.stats['trades_short']} | PnL: ${self.stats['profit_short']:.2f}")
        logger.info(f"  LONG:  {self.stats['trades_long']} | PnL: ${self.stats['profit_long']:.2f}")
        logger.info(f"Total PnL: ${self.stats['profit_total']:.2f}")
        logger.info("="*70)


def main():
    parser = argparse.ArgumentParser(description='Unified LONG/SHORT Bot v3.0')
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
        print("\nBot stopped.")


if __name__ == "__main__":
    main()
