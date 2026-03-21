"""
ENHANCED UNIFIED TRADING BOT - ETAP 1
=====================================
Dodano:
- Circuit breaker (daily loss, consecutive losses, drawdown)
- Risk-based position sizing  
- Entry filters (8 filtrów)
- Risk metrics tracking
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Literal
import numpy as np

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


class MarketRegime(Enum):
    """Reżimy rynku dla filtrów wejścia"""
    STRONG_UPTREND = "strong_uptrend"
    UPTREND = "uptrend"
    SIDEWAYS_BULLISH = "sideways_bullish"
    SIDEWAYS = "sideways"
    SIDEWAYS_BEARISH = "sideways_bearish"
    DOWNTREND = "downtrend"
    STRONG_DOWNTREND = "strong_downtrend"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"


@dataclass
class RiskMetrics:
    """Metryki ryzyka z circuit breaker"""
    total_exposure: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    daily_pnl: float = 0.0
    consecutive_losses: int = 0
    max_consecutive_losses: int = 0
    peak_balance: float = 0.0
    initial_balance: float = 0.0
    
    def update_after_trade(self, pnl: float):
        """Aktualizuj metryki po zamknięciu pozycji"""
        self.daily_pnl += pnl
        
        if pnl >= 0:
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            self.max_consecutive_losses = max(
                self.max_consecutive_losses,
                self.consecutive_losses
            )


@dataclass
class EnhancedConfig:
    """Rozszerzona konfiguracja z risk management"""
    # === ACCOUNT ===
    initial_capital: float = 100.0
    
    # === CIRCUIT BREAKER ===
    circuit_breaker_enabled: bool = True
    max_daily_loss_pct: float = 0.05  # 5% daily loss
    max_drawdown_pct: float = 0.15    # 15% max drawdown
    max_consecutive_losses: int = 5   # Stop after 5 losses
    circuit_cooldown_minutes: int = 60  # Cooldown period
    
    # === RISK PER TRADE ===
    risk_per_trade_pct: float = 0.01   # 1% risk per trade
    max_total_exposure_pct: float = 0.50  # 50% max exposure
    position_size_multiplier: float = 1.0
    
    # === FILTRY WEJŚCIA ===
    # Trend filter
    trend_filter_enabled: bool = True
    adx_threshold: float = 25.0       # ADX > 25 = trend
    adx_strong_trend: float = 40.0    # ADX > 40 = strong trend
    
    # Volatility filter
    volatility_filter_enabled: bool = True
    min_volatility_pct: float = 0.005  # 0.5% min
    max_volatility_pct: float = 0.05   # 5% max
    
    # Volume filter
    volume_filter_enabled: bool = True
    min_volume_ratio: float = 0.7      # 70% of avg volume
    
    # RSI filter
    rsi_enabled: bool = True
    rsi_period: int = 14
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0
    
    # Price position filter
    price_filter_enabled: bool = True
    max_distance_from_support: float = 0.03  # 3% max from support
    
    # === GRID SETTINGS ===
    max_grid_positions: int = 4
    max_dca_per_position: int = 3
    
    # === SIDEWAYS PARAMS ===
    sideways_grid_pct: float = 0.30
    sideways_dca_pct: float = 0.70
    sideways_spacing: float = 0.015   # 1.5%
    sideways_markup: float = 0.010    # 1%
    
    # === STOP LOSS ===
    stop_loss_multiplier: float = 1.5  # SL = entry * (1 - spacing * multiplier)
    
    # === EXCHANGE ===
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


class CircuitBreaker:
    """Circuit breaker - zatrzymuje trading przy przekroczeniu limitów"""
    
    def __init__(self, config: EnhancedConfig):
        self.config = config
        self.active = False
        self.reason = ""
        self.activated_at: Optional[datetime] = None
        self.cooldown_until: Optional[datetime] = None
    
    def check(self, risk_metrics: RiskMetrics) -> Tuple[bool, str]:
        """
        Sprawdź czy circuit breaker powinien być aktywny.
        Zwraca (should_stop, reason)
        """
        # Check cooldown
        if self.cooldown_until and datetime.now() < self.cooldown_until:
            return True, f"Circuit breaker cooldown until {self.cooldown_until}"
        
        # Reset if cooldown passed
        if self.cooldown_until and datetime.now() >= self.cooldown_until:
            self.reset()
        
        # Check daily loss
        daily_loss_pct = abs(risk_metrics.daily_pnl) / risk_metrics.initial_balance
        if daily_loss_pct > self.config.max_daily_loss_pct:
            self.activate(f"Daily loss exceeded: {daily_loss_pct:.2%}")
            return True, self.reason
        
        # Check drawdown
        if risk_metrics.max_drawdown > self.config.max_drawdown_pct:
            self.activate(f"Max drawdown exceeded: {risk_metrics.max_drawdown:.2%}")
            return True, self.reason
        
        # Check consecutive losses
        if risk_metrics.consecutive_losses >= self.config.max_consecutive_losses:
            self.activate(f"Too many consecutive losses: {risk_metrics.consecutive_losses}")
            return True, self.reason
        
        return False, ""
    
    def activate(self, reason: str):
        """Aktywuj circuit breaker"""
        self.active = True
        self.reason = reason
        self.activated_at = datetime.now()
        self.cooldown_until = datetime.now() + timedelta(
            minutes=self.config.circuit_cooldown_minutes
        )
        logger.warning(f"🔴 CIRCUIT BREAKER ACTIVATED: {reason}")
    
    def reset(self):
        """Reset circuit breaker"""
        if self.active:
            logger.info("🟢 Circuit breaker reset")
        self.active = False
        self.reason = ""
        self.activated_at = None
        self.cooldown_until = None


class EntryFilters:
    """8 filtrów wejścia dla pozycji"""
    
    def __init__(self, config: EnhancedConfig):
        self.config = config
    
    def check_all(
        self,
        current_price: float,
        support: float,
        resistance: float,
        positions_count: int,
        current_exposure: float,
        circuit_breaker: CircuitBreaker,
        risk_metrics: RiskMetrics,
        market_data: Dict
    ) -> Tuple[bool, str]:
        """
        Sprawdź wszystkie filtry wejścia.
        Zwraca (should_enter, reason)
        """
        # 1. Circuit breaker
        if circuit_breaker.active:
            return False, f"Circuit breaker active: {circuit_breaker.reason}"
        
        # 2. Max positions
        if positions_count >= self.config.max_grid_positions:
            return False, f"Max grid positions reached: {positions_count}"
        
        # 3. Exposure limit
        exposure_pct = current_exposure / risk_metrics.initial_balance
        if exposure_pct >= self.config.max_total_exposure_pct:
            return False, f"Max exposure reached: {exposure_pct:.2%}"
        
        # 4. Trend filter (jeśli strong trend - nie wchodź w sideways)
        if self.config.trend_filter_enabled:
            adx = market_data.get('adx', 0)
            trend_strength = market_data.get('trend_strength', 0)
            
            if adx > self.config.adx_strong_trend:
                if abs(trend_strength) > 0.5:
                    return False, f"Strong trend detected: ADX={adx:.1f}, strength={trend_strength:.2f}"
        
        # 5. Volatility filter
        if self.config.volatility_filter_enabled:
            volatility = market_data.get('volatility', 0)
            if volatility < self.config.min_volatility_pct:
                return False, f"Volatility too low: {volatility:.4f}"
            if volatility > self.config.max_volatility_pct:
                return False, f"Volatility too high: {volatility:.4f}"
        
        # 6. Volume filter
        if self.config.volume_filter_enabled:
            volume_ratio = market_data.get('volume_ratio', 1.0)
            if volume_ratio < self.config.min_volume_ratio:
                return False, f"Low volume: {volume_ratio:.2f}"
        
        # 7. RSI filter
        if self.config.rsi_enabled:
            rsi = market_data.get('rsi', 50)
            if rsi > self.config.rsi_overbought:
                return False, f"RSI overbought: {rsi:.1f}"
        
        # 8. Price position (distance from support)
        if self.config.price_filter_enabled and support > 0:
            distance = (current_price - support) / support
            if distance > self.config.max_distance_from_support:
                return False, f"Too far from support: {distance:.2%} > {self.config.max_distance_from_support:.2%}"
            if current_price < support * 0.99:
                return False, f"Price below support: {current_price:.2f} < {support:.2f}"
        
        return True, "All filters passed"


class RiskBasedSizing:
    """Risk-based position sizing"""
    
    def __init__(self, config: EnhancedConfig):
        self.config = config
    
    def calculate_size(
        self,
        account_balance: float,
        entry_price: float,
        stop_loss_price: float,
        risk_metrics: RiskMetrics
    ) -> float:
        """
        Oblicz wielkość pozycji na podstawie ryzyka.
        Formula: Position Size = Risk Amount / (Entry - Stop Loss)
        """
        # Base risk amount (1% of capital)
        risk_amount = account_balance * self.config.risk_per_trade_pct
        
        # Reduce after consecutive losses
        if risk_metrics.consecutive_losses >= 3:
            risk_amount *= 0.5
            logger.info(f"Risk reduced by 50% after {risk_metrics.consecutive_losses} losses")
        
        # Calculate position size
        sl_distance = abs(entry_price - stop_loss_price)
        
        if sl_distance == 0:
            # Fallback to percentage sizing
            return account_balance * 0.10 * self.config.position_size_multiplier
        
        position_size = risk_amount / sl_distance * entry_price
        
        # Apply multiplier
        position_size *= self.config.position_size_multiplier
        
        # Cap at max position (10% of account)
        max_position = account_balance * 0.10
        position_size = min(position_size, max_position)
        
        return position_size


class EnhancedUnifiedBot:
    """
    Rozszerzony bot z circuit breaker, filtrami wejścia i risk-based sizing.
    """
    
    def __init__(self, config: EnhancedConfig):
        self.config = config
        
        # Stan bota
        self.positions: List[Dict] = []
        self.current_trend: Literal['uptrend', 'downtrend', 'sideways'] = 'sideways'
        
        # Risk management
        self.risk_metrics = RiskMetrics(initial_balance=config.initial_capital)
        self.risk_metrics.peak_balance = config.initial_capital
        self.circuit_breaker = CircuitBreaker(config)
        self.entry_filters = EntryFilters(config)
        self.sizing = RiskBasedSizing(config)
        
        # Market state
        self.support = 0.0
        self.resistance = 0.0
        self.market_data = {}
        
        # Paths
        self.history_path = Path('~/.openclaw/workspace/memory/bot_price_history.json').expanduser()
        self.state_path = Path('~/.openclaw/workspace/memory/bot_state.json').expanduser()
        
        logger.info("🤖 Enhanced Unified Bot initialized (Etap 1)")
    
    def calculate_support_resistance(self, prices: List[float]) -> Tuple[float, float]:
        """Oblicz dynamiczne poziomy support/resistance"""
        if len(prices) < 20:
            return prices[-1] * 0.98, prices[-1] * 1.02
        
        recent = prices[-48:] if len(prices) >= 48 else prices
        
        # Swing lows/highs
        lows = []
        highs = []
        
        for i in range(2, len(recent) - 2):
            if recent[i] == min(recent[i-2:i+3]):
                lows.append(recent[i])
            if recent[i] == max(recent[i-2:i+3]):
                highs.append(recent[i])
        
        support = min(lows) if lows else min(recent)
        resistance = max(highs) if highs else max(recent)
        
        return support, resistance
    
    def calculate_simple_indicators(self, prices: List[float]) -> Dict:
        """Oblicz uproszczone wskaźniki techniczne"""
        if len(prices) < 20:
            return {'adx': 20, 'trend_strength': 0, 'volatility': 0.02, 'rsi': 50, 'volume_ratio': 1.0}
        
        # Simple volatility (ATR-like)
        returns = np.diff(prices) / prices[:-1]
        volatility = np.std(returns) * np.sqrt(24)  # Daily vol
        
        # Simple trend strength (EMA-like)
        if len(prices) >= 20:
            ema_short = np.mean(prices[-10:])
            ema_long = np.mean(prices[-20:])
            trend_strength = (ema_short - ema_long) / ema_long
        else:
            trend_strength = 0
        
        # Simple RSI approximation
        gains = [r for r in returns if r > 0]
        losses = [abs(r) for r in returns if r < 0]
        avg_gain = np.mean(gains) if gains else 0
        avg_loss = np.mean(losses) if losses else 0.001
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        rsi = np.clip(rsi, 0, 100)
        
        # ADX approximation (trend strength)
        adx = min(50, abs(trend_strength) * 1000)
        
        return {
            'adx': adx,
            'trend_strength': trend_strength,
            'volatility': volatility,
            'rsi': rsi,
            'volume_ratio': 1.0  # Would need volume data
        }
    
    def should_enter_position(
        self,
        current_price: float,
        account_balance: float
    ) -> Tuple[bool, str, Optional[float]]:
        """
        Sprawdź czy wejść w pozycję z filtrami i sizing.
        Zwraca (should_enter, reason, position_size)
        """
        # Calculate market data
        prices = self.load_price_history()
        if len(prices) >= 20:
            self.support, self.resistance = self.calculate_support_resistance(prices)
            self.market_data = self.calculate_simple_indicators(prices)
        
        # Check circuit breaker
        should_stop, cb_reason = self.circuit_breaker.check(self.risk_metrics)
        if should_stop:
            return False, cb_reason, None
        
        # Check entry filters
        current_exposure = sum(p.get('size', 0) for p in self.positions)
        
        should_enter, reason = self.entry_filters.check_all(
            current_price=current_price,
            support=self.support,
            resistance=self.resistance,
            positions_count=len(self.positions),
            current_exposure=current_exposure,
            circuit_breaker=self.circuit_breaker,
            risk_metrics=self.risk_metrics,
            market_data=self.market_data
        )
        
        if not should_enter:
            return False, reason, None
        
        # Calculate position size
        stop_loss = current_price * (1 - self.config.sideways_spacing * self.config.stop_loss_multiplier)
        position_size = self.sizing.calculate_size(
            account_balance=account_balance,
            entry_price=current_price,
            stop_loss_price=stop_loss,
            risk_metrics=self.risk_metrics
        )
        
        return True, "Entry approved", position_size
    
    def load_price_history(self) -> List[float]:
        """Załaduj historię cen"""
        try:
            if self.history_path.exists():
                with open(self.history_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load price history: {e}")
        return []
    
    def save_state(self):
        """Zapisz stan bota"""
        state = {
            'positions': self.positions,
            'risk_metrics': {
                'daily_pnl': self.risk_metrics.daily_pnl,
                'consecutive_losses': self.risk_metrics.consecutive_losses,
                'max_consecutive_losses': self.risk_metrics.max_consecutive_losses,
                'peak_balance': self.risk_metrics.peak_balance,
            },
            'circuit_breaker': {
                'active': self.circuit_breaker.active,
                'reason': self.circuit_breaker.reason,
                'cooldown_until': self.circuit_breaker.cooldown_until.isoformat() if self.circuit_breaker.cooldown_until else None
            },
            'current_trend': self.current_trend,
            'timestamp': datetime.now().isoformat()
        }
        try:
            with open(self.state_path, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save state: {e}")
    
    def load_state(self):
        """Załaduj stan bota"""
        try:
            if self.state_path.exists():
                with open(self.state_path, 'r') as f:
                    state = json.load(f)
                
                self.positions = state.get('positions', [])
                self.current_trend = state.get('current_trend', 'sideways')
                
                # Restore risk metrics
                rm = state.get('risk_metrics', {})
                self.risk_metrics.daily_pnl = rm.get('daily_pnl', 0)
                self.risk_metrics.consecutive_losses = rm.get('consecutive_losses', 0)
                self.risk_metrics.max_consecutive_losses = rm.get('max_consecutive_losses', 0)
                self.risk_metrics.peak_balance = rm.get('peak_balance', self.config.initial_capital)
                
                # Restore circuit breaker
                cb = state.get('circuit_breaker', {})
                if cb.get('active'):
                    self.circuit_breaker.active = True
                    self.circuit_breaker.reason = cb.get('reason', '')
                    cooldown_str = cb.get('cooldown_until')
                    if cooldown_str:
                        self.circuit_breaker.cooldown_until = datetime.fromisoformat(cooldown_str)
                
                logger.info(f"📂 Loaded state: {len(self.positions)} positions, CB active: {self.circuit_breaker.active}")
        except Exception as e:
            logger.warning(f"Could not load state: {e}")
    
    def get_status_report(self) -> Dict:
        """Generuj raport statusu"""
        return {
            'timestamp': datetime.now().isoformat(),
            'positions': {
                'count': len(self.positions),
                'total_exposure': sum(p.get('size', 0) for p in self.positions)
            },
            'risk_metrics': {
                'daily_pnl': self.risk_metrics.daily_pnl,
                'consecutive_losses': self.risk_metrics.consecutive_losses,
                'max_drawdown': self.risk_metrics.max_drawdown,
                'win_rate': self.risk_metrics.win_rate,
            },
            'circuit_breaker': {
                'active': self.circuit_breaker.active,
                'reason': self.circuit_breaker.reason,
                'cooldown_until': self.circuit_breaker.cooldown_until.isoformat() if self.circuit_breaker.cooldown_until else None
            },
            'market': {
                'trend': self.current_trend,
                'support': self.support,
                'resistance': self.resistance,
                'adx': self.market_data.get('adx', 0),
                'rsi': self.market_data.get('rsi', 50),
                'volatility': self.market_data.get('volatility', 0)
            }
        }


# ============================================================================
# BACKWARD COMPATIBILITY - Wrap old UnifiedBot calls
# ============================================================================

class UnifiedBot(EnhancedUnifiedBot):
    """Wrapper dla backward compatibility"""
    pass


if __name__ == "__main__":
    # Test
    config = EnhancedConfig()
    bot = EnhancedUnifiedBot(config)
    print(json.dumps(bot.get_status_report(), indent=2))
