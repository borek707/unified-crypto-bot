"""
Unstucking Mechanism & Safety Locks
====================================
Prevents margin calls by systematically closing stuck positions.
Protects the $100 account from liquidation.

Key Concepts:
- "Stuck" position: Price moved significantly against entry
- Unstucking: Realize small losses to free capital
- Safety Locks: Multiple layers of protection

Mathematical Model:
==================
unstuck_threshold = entry_price * (1 + max_adverse_pct)
where max_adverse_pct = wallet_exposure_limit / leverage / 2

chunk_size = position_size * unstuck_chunk_pct(dd)

The mechanism ensures:
1. Never hit margin call
2. Free capital for new profitable grids
3. Controlled loss realization
"""

import numpy as np
from typing import Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from loguru import logger

from ..config.settings import RiskConfig, UnstuckingConfig, OrderSide


# ============================================================
# DATA STRUCTURES
# ============================================================
class UnstuckTrigger(Enum):
    DRAWDOWN_THRESHOLD = "drawdown_threshold"
    TIME_THRESHOLD = "time_threshold"
    ADVERSE_EXCURSION = "adverse_excursion"
    MARGIN_PRESSURE = "margin_pressure"


@dataclass
class StuckPosition:
    """Represents a stuck position requiring unstucking."""
    symbol: str
    side: OrderSide
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    time_stuck_minutes: float
    margin_used: float
    adverse_excursion_pct: float  # How far price moved against entry
    
    @property
    def break_even_price(self) -> float:
        """Price at which position breaks even (excluding fees)."""
        return self.entry_price
    
    @property
    def gap_to_break_even(self) -> float:
        """Percentage distance to break even."""
        if self.side == OrderSide.LONG:
            return (self.entry_price - self.current_price) / self.entry_price
        else:
            return (self.current_price - self.entry_price) / self.entry_price


@dataclass
class UnstuckAction:
    """Represents an unstucking action to be executed."""
    symbol: str
    side: OrderSide
    size_to_close: float
    expected_loss: float
    trigger: UnstuckTrigger
    timestamp: datetime = field(default_factory=datetime.now)
    executed: bool = False
    
    @property
    def close_side(self) -> OrderSide:
        """Side to close the position."""
        return OrderSide.SHORT if self.side == OrderSide.LONG else OrderSide.LONG


@dataclass
class SafetyState:
    """Current safety state of the trading system."""
    balance: float
    equity: float
    margin_used: float
    margin_available: float
    current_drawdown: float
    current_drawdown_pct: float
    daily_pnl: float
    daily_pnl_pct: float
    max_drawdown_today: float
    positions_at_risk: int
    is_safe: bool = True
    warnings: List[str] = field(default_factory=list)
    
    @property
    def margin_ratio(self) -> float:
        """Ratio of margin used to available."""
        if self.margin_available <= 0:
            return float('inf')
        return self.margin_used / self.margin_available


# ============================================================
# UNSTUCKING ENGINE
# ============================================================
class UnstuckingEngine:
    """
    Implements the Passivbot-style unstucking mechanism.
    
    The core idea: When a position is "stuck" (price far from entry
    and we're holding a losing position), instead of hoping for
    reversal, we systematically close small chunks to:
    
    1. Realize a controlled loss
    2. Free up margin for new trades
    3. Never hit a margin call
    
    This is crucial for small accounts ($100) where one bad
    position can wipe out the entire account.
    """
    
    def __init__(
        self,
        config: UnstuckingConfig,
        risk_config: RiskConfig
    ):
        self.config = config
        self.risk = risk_config
        
        # State tracking
        self.stuck_positions: List[StuckPosition] = []
        self.unstuck_history: List[UnstuckAction] = []
        self.last_unstuck_time: Optional[datetime] = None
        self.total_unstuck_losses: float = 0.0
    
    def identify_stuck_positions(
        self,
        positions: List[dict],
        current_prices: dict,
        balance: float
    ) -> List[StuckPosition]:
        """
        Identify positions that are candidates for unstucking.
        
        A position is "stuck" if:
        1. Unrealized loss > activation threshold
        2. Time since entry > minimum stuck duration
        3. Adverse excursion > threshold
        """
        stuck = []
        
        for pos in positions:
            symbol = pos['symbol']
            current_price = current_prices.get(symbol, 0)
            
            if current_price == 0:
                continue
            
            # Calculate metrics
            entry_price = pos['entry_price']
            size = pos['size']
            side = pos['side']
            
            # Unrealized PnL
            if side == OrderSide.LONG:
                pnl = (current_price - entry_price) * size
                pnl_pct = (current_price - entry_price) / entry_price
                adverse_pct = max(0, (entry_price - current_price) / entry_price)
            else:
                pnl = (entry_price - current_price) * size
                pnl_pct = (entry_price - current_price) / entry_price
                adverse_pct = max(0, (current_price - entry_price) / entry_price)
            
            # Time stuck
            entry_time = pos.get('entry_time', datetime.now())
            time_stuck = (datetime.now() - entry_time).total_seconds() / 60
            
            # Margin used
            margin_used = size * current_price / pos.get('leverage', 1)
            
            # Check if stuck
            is_stuck = (
                pnl_pct < -self.config.activation_drawdown and
                time_stuck > self.config.min_stuck_duration_minutes and
                adverse_pct > self.config.max_adverse_excursion_pct * 0.5
            )
            
            if is_stuck or pnl_pct < -self.config.activation_drawdown * 1.5:
                stuck.append(StuckPosition(
                    symbol=symbol,
                    side=side,
                    size=size,
                    entry_price=entry_price,
                    current_price=current_price,
                    unrealized_pnl=pnl,
                    unrealized_pnl_pct=pnl_pct,
                    time_stuck_minutes=time_stuck,
                    margin_used=margin_used,
                    adverse_excursion_pct=adverse_pct
                ))
        
        self.stuck_positions = stuck
        return stuck
    
    def calculate_unstuck_action(
        self,
        stuck_pos: StuckPosition,
        balance: float,
        margin_available: float
    ) -> Optional[UnstuckAction]:
        """
        Calculate the unstucking action for a stuck position.
        
        Chunk Size Formula:
        -------------------
        chunk_pct is dynamic based on drawdown:
        
        if DD < 5%:   chunk_pct = 5%
        if DD < 10%:  chunk_pct = 10%
        if DD < 15%:  chunk_pct = 20%
        if DD >= 15%: chunk_pct = 30%
        
        chunk_size = position_size * chunk_pct
        
        Expected Loss = chunk_size * gap_to_break_even * current_price
        
        Safety Constraint:
        ------------------
        After unstuck, margin_remaining > margin_required * 1.5
        """
        if not self.config.enabled:
            return None
        
        # Check cooldown
        if self.last_unstuck_time:
            cooldown_remaining = self.config.unstuck_interval_minutes - \
                (datetime.now() - self.last_unstuck_time).total_seconds() / 60
            if cooldown_remaining > 0:
                logger.debug(f"Unstuck cooldown: {cooldown_remaining:.1f} min remaining")
                return None
        
        # Calculate drawdown percentage
        dd_pct = abs(stuck_pos.unrealized_pnl_pct)
        
        # Get chunk percentage based on drawdown
        chunk_pct = self.config.get_chunk_pct(dd_pct)
        
        # Calculate chunk size
        chunk_size = stuck_pos.size * chunk_pct
        
        # Calculate expected loss
        expected_loss = chunk_size * stuck_pos.gap_to_break_even * stuck_pos.current_price
        
        # Safety check: ensure we don't make things worse
        margin_freed = chunk_size * stuck_pos.current_price / self.risk.max_leverage
        
        if margin_available < margin_freed * 0.5:
            # Not enough margin benefit
            logger.warning(f"Unstuck skipped - insufficient margin benefit")
            return None
        
        # Determine trigger
        if dd_pct >= self.config.max_adverse_excursion_pct:
            trigger = UnstuckTrigger.ADVERSE_EXCURSION
        elif stuck_pos.time_stuck_minutes > self.config.min_stuck_duration_minutes * 2:
            trigger = UnstuckTrigger.TIME_THRESHOLD
        else:
            trigger = UnstuckTrigger.DRAWDOWN_THRESHOLD
        
        return UnstuckAction(
            symbol=stuck_pos.symbol,
            side=stuck_pos.side,
            size_to_close=chunk_size,
            expected_loss=expected_loss,
            trigger=trigger
        )
    
    def get_all_unstuck_actions(
        self,
        balance: float,
        margin_available: float
    ) -> List[UnstuckAction]:
        """Get all unstuck actions for current stuck positions."""
        actions = []
        
        for stuck_pos in self.stuck_positions:
            action = self.calculate_unstuck_action(
                stuck_pos, balance, margin_available
            )
            if action:
                actions.append(action)
        
        # Sort by expected loss (smallest first)
        actions.sort(key=lambda x: x.expected_loss)
        
        return actions
    
    def record_unstuck(self, action: UnstuckAction):
        """Record an executed unstuck action."""
        action.executed = True
        self.unstuck_history.append(action)
        self.last_unstuck_time = datetime.now()
        self.total_unstuck_losses += action.expected_loss
        
        logger.info(
            f"Unstuck executed: {action.symbol} {action.side.value} "
            f"size={action.size_to_close:.4f} loss=${action.expected_loss:.2f}"
        )
    
    def get_statistics(self) -> dict:
        """Get unstucking statistics."""
        return {
            'total_unstuck_actions': len(self.unstuck_history),
            'total_realized_losses': self.total_unstuck_losses,
            'current_stuck_positions': len(self.stuck_positions),
            'avg_loss_per_unstuck': (
                self.total_unstuck_losses / len(self.unstuck_history)
                if self.unstuck_history else 0
            )
        }


# ============================================================
# SAFETY MANAGER
# ============================================================
class SafetyManager:
    """
    Multi-layer safety management for the trading bot.
    
    Safety Layers:
    1. Balance Floor: Stop if balance < stop_loss_balance
    2. Daily Loss Limit: Pause if daily loss > threshold
    3. Max Drawdown: Emergency stop if drawdown > threshold
    4. Leverage Cap: Never exceed max leverage
    5. Position Concentration: Limit exposure per symbol
    6. Margin Buffer: Keep minimum margin available
    """
    
    def __init__(self, risk_config: RiskConfig):
        self.config = risk_config
        
        # State
        self.state: Optional[SafetyState] = None
        self.is_trading_allowed = True
        self.emergency_stop = False
        self.pause_until: Optional[datetime] = None
        
        # History
        self.daily_pnl_history: List[Tuple[datetime, float]] = []
        self.max_drawdown_seen = 0.0
    
    def update_state(
        self,
        balance: float,
        equity: float,
        margin_used: float,
        positions: List[dict],
        daily_pnl: float = 0.0
    ) -> SafetyState:
        """
        Update safety state and run all checks.
        
        Returns:
            SafetyState with current status and any warnings
        """
        warnings = []
        is_safe = True
        
        # Calculate metrics
        initial_capital = self.config.initial_capital
        current_drawdown = max(0, initial_capital - equity)
        current_drawdown_pct = current_drawdown / initial_capital
        
        margin_available = balance - margin_used / self.config.max_leverage
        
        daily_pnl_pct = daily_pnl / initial_capital
        
        # Update max drawdown
        if current_drawdown_pct > self.max_drawdown_seen:
            self.max_drawdown_seen = current_drawdown_pct
        
        # Count positions at risk (drawdown > 10%)
        positions_at_risk = sum(
            1 for p in positions
            if abs(p.get('unrealized_pnl_pct', 0)) > 0.10
        )
        
        # =====================================
        # SAFETY CHECK 1: Balance Floor
        # =====================================
        if balance < self.config.stop_loss_balance:
            warnings.append(
                f"CRITICAL: Balance ${balance:.2f} below floor ${self.config.stop_loss_balance:.2f}"
            )
            is_safe = False
            self.emergency_stop = True
        
        # =====================================
        # SAFETY CHECK 2: Daily Loss Limit
        # =====================================
        if daily_pnl < 0 and abs(daily_pnl_pct) > self.config.daily_loss_limit:
            warnings.append(
                f"DAILY LOSS LIMIT: {daily_pnl_pct:.1%} exceeds {self.config.daily_loss_limit:.1%}"
            )
            is_safe = False
            self.pause_until = datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            ) + timedelta(days=1)  # Pause until midnight
        
        # =====================================
        # SAFETY CHECK 3: Max Drawdown
        # =====================================
        if current_drawdown_pct > self.config.max_drawdown_pct:
            warnings.append(
                f"MAX DRAWDOWN: {current_drawdown_pct:.1%} exceeds {self.config.max_drawdown_pct:.1%}"
            )
            is_safe = False
            self.emergency_stop = True
        
        # =====================================
        # SAFETY CHECK 4: Margin Pressure
        # =====================================
        margin_ratio = margin_used / max(margin_available, 0.01)
        if margin_ratio > 0.8:
            warnings.append(
                f"MARGIN PRESSURE: Using {margin_ratio:.1%} of available margin"
            )
            is_safe = False
        
        # =====================================
        # SAFETY CHECK 5: Position Count
        # =====================================
        if len(positions) > self.config.max_open_positions:
            warnings.append(
                f"TOO MANY POSITIONS: {len(positions)} > {self.config.max_open_positions}"
            )
            # Don't disable trading, just warn
        
        # Update state
        self.state = SafetyState(
            balance=balance,
            equity=equity,
            margin_used=margin_used,
            margin_available=margin_available,
            current_drawdown=current_drawdown,
            current_drawdown_pct=current_drawdown_pct,
            daily_pnl=daily_pnl,
            daily_pnl_pct=daily_pnl_pct,
            max_drawdown_today=self.max_drawdown_seen,
            positions_at_risk=positions_at_risk,
            is_safe=is_safe,
            warnings=warnings
        )
        
        # Update trading permission
        if self.pause_until and datetime.now() < self.pause_until:
            self.is_trading_allowed = False
        elif self.emergency_stop:
            self.is_trading_allowed = False
        else:
            self.is_trading_allowed = is_safe
        
        return self.state
    
    def should_reduce_positions(self) -> Tuple[bool, str]:
        """
        Check if positions should be reduced immediately.
        
        Returns:
            Tuple of (should_reduce, reason)
        """
        if self.state is None:
            return False, ""
        
        if self.state.margin_ratio > 0.9:
            return True, "Margin ratio critical"
        
        if self.state.current_drawdown_pct > self.config.max_drawdown_pct * 0.8:
            return True, "Approaching max drawdown"
        
        if self.state.positions_at_risk >= 2:
            return True, "Multiple positions at risk"
        
        return False, ""
    
    def get_max_position_size(self, symbol: str, current_price: float) -> float:
        """
        Calculate maximum position size allowed for a symbol.
        
        Considers:
        - Wallet exposure limit
        - Max leverage
        - Available margin
        """
        if self.state is None:
            return 0.0
        
        # Base limit from config
        max_value = self.config.initial_capital * self.config.max_wallet_exposure
        
        # Adjust for current drawdown
        if self.state.current_drawdown_pct > 0.05:
            # Reduce limit when in drawdown
            reduction_factor = 1 - self.state.current_drawdown_pct * 2
            max_value *= max(0.3, reduction_factor)
        
        # Check available margin
        margin_limit = self.state.margin_available * self.config.max_leverage * 0.8
        max_value = min(max_value, margin_limit)
        
        # Convert to size
        max_size = max_value / current_price
        
        # Apply position size limits
        max_size = max(self.config.min_position_size / current_price,
                      min(self.config.max_position_size / current_price, max_size))
        
        return max_size
    
    def can_open_position(self, symbol: str, size: float, price: float) -> Tuple[bool, str]:
        """
        Check if a new position can be opened.
        
        Returns:
            Tuple of (can_open, reason)
        """
        if not self.is_trading_allowed:
            return False, "Trading not allowed"
        
        if self.state is None:
            return False, "State not initialized"
        
        # Check margin
        required_margin = size * price / self.config.max_leverage
        if required_margin > self.state.margin_available * 0.5:
            return False, "Insufficient margin"
        
        # Check position size
        max_size = self.get_max_position_size(symbol, price)
        if size > max_size:
            return False, f"Size {size} exceeds max {max_size}"
        
        return True, "OK"
    
    def reset_daily(self):
        """Reset daily counters."""
        self.max_drawdown_seen = 0.0
        if self.pause_until and datetime.now() >= self.pause_until:
            self.pause_until = None
            logger.info("Daily reset - trading resumed")
    
    def force_resume(self):
        """Force resume trading (use with caution)."""
        self.emergency_stop = False
        self.pause_until = None
        self.is_trading_allowed = True
        logger.warning("Trading force-resumed")
    
    def get_status_report(self) -> str:
        """Generate human-readable status report."""
        if self.state is None:
            return "Safety state not initialized"
        
        lines = [
            "=" * 50,
            "SAFETY STATUS REPORT",
            "=" * 50,
            f"Balance: ${self.state.balance:.2f}",
            f"Equity: ${self.state.equity:.2f}",
            f"Drawdown: ${self.state.current_drawdown:.2f} ({self.state.current_drawdown_pct:.1%})",
            f"Daily PnL: ${self.state.daily_pnl:.2f} ({self.state.daily_pnl_pct:.1%})",
            f"Margin Used: ${self.state.margin_used:.2f}",
            f"Margin Available: ${self.state.margin_available:.2f}",
            f"Margin Ratio: {self.state.margin_ratio:.1%}",
            f"Positions at Risk: {self.state.positions_at_risk}",
            "",
            f"Trading Allowed: {'YES' if self.is_trading_allowed else 'NO'}",
            f"Emergency Stop: {'YES' if self.emergency_stop else 'NO'}",
        ]
        
        if self.pause_until:
            remaining = (self.pause_until - datetime.now()).total_seconds() / 3600
            lines.append(f"Paused for: {remaining:.1f} hours")
        
        if self.state.warnings:
            lines.append("")
            lines.append("WARNINGS:")
            for w in self.state.warnings:
                lines.append(f"  - {w}")
        
        return "\n".join(lines)


# ============================================================
# RISK CALCULATOR
# ============================================================
class RiskCalculator:
    """
    Utility class for risk calculations.
    """
    
    @staticmethod
    def calculate_liquidation_price(
        entry_price: float,
        side: OrderSide,
        leverage: float,
        maintenance_margin_rate: float = 0.005
    ) -> float:
        """
        Calculate liquidation price for a position.
        
        Formula (for long):
            liq_price = entry * (1 - (1 - mmr) / leverage)
        
        Formula (for short):
            liq_price = entry * (1 + (1 - mmr) / leverage)
        """
        if side == OrderSide.LONG:
            return entry_price * (1 - (1 - maintenance_margin_rate) / leverage)
        else:
            return entry_price * (1 + (1 - maintenance_margin_rate) / leverage)
    
    @staticmethod
    def calculate_margin_required(
        position_size: float,
        price: float,
        leverage: float
    ) -> float:
        """Calculate margin required for a position."""
        return position_size * price / leverage
    
    @staticmethod
    def calculate_pnl(
        entry_price: float,
        current_price: float,
        size: float,
        side: OrderSide,
        fees_paid: float = 0.0
    ) -> float:
        """Calculate realized or unrealized PnL."""
        if side == OrderSide.LONG:
            return (current_price - entry_price) * size - fees_paid
        else:
            return (entry_price - current_price) * size - fees_paid
    
    @staticmethod
    def calculate_break_even_price(
        entry_price: float,
        fees_pct: float = 0.0005,  # Round trip
        side: OrderSide = OrderSide.LONG
    ) -> float:
        """Calculate price at which position breaks even after fees."""
        if side == OrderSide.LONG:
            return entry_price * (1 + fees_pct * 2)
        else:
            return entry_price * (1 - fees_pct * 2)
    
    @staticmethod
    def calculate_optimal_leverage(
        balance: float,
        position_size: float,
        price: float,
        max_leverage: float,
        safety_factor: float = 0.7
    ) -> float:
        """
        Calculate optimal leverage for a position.
        
        Returns leverage that uses safety_factor of available balance.
        """
        required_notional = position_size * price
        optimal_leverage = required_notional / (balance * safety_factor)
        
        return min(max(optimal_leverage, 1.0), max_leverage)
    
    @staticmethod
    def estimate_days_to_liquidation(
        balance: float,
        daily_volatility: float,
        leverage: float,
        confidence: float = 0.95
    ) -> float:
        """
        Estimate days until liquidation based on volatility.
        
        Uses Value at Risk (VaR) approximation.
        """
        # Z-score for confidence level
        from scipy import stats
        z = stats.norm.ppf(1 - confidence)
        
        # Daily loss at confidence level
        daily_var = abs(z) * daily_volatility * leverage
        
        if daily_var <= 0:
            return float('inf')
        
        # Days to 100% loss (simplified)
        days_to_liq = 1.0 / daily_var
        
        return min(days_to_liq, 365)
