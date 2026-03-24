#!/usr/bin/env python3
"""
Unified Bot with RISK SCALING
==============================
Higher risk when capital is small ($100-150)
Medium risk when growing ($150-500)
Lower risk when substantial ($500+)

This helps overcome fixed fees at small capital while protecting gains.
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

# Setup logging
LOG_DIR = Path(os.getenv('BOT_LOG_DIR', Path.home() / '.crypto_bot' / 'logs'))
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'unified_bot_risk_scaling.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class RiskScaler:
    """
    Dynamically adjust risk based on current capital vs initial.
    
    Strategy:
    - $100-150: Aggressive (1.5x base risk) - overcome fees
    - $150-250: Moderate (1.2x base risk)
    - $250-500: Normal (1.0x base risk)
    - $500-1000: Conservative (0.8x base risk)
    - $1000+: Very conservative (0.6x base risk) - protect gains
    """
    
    def __init__(self, initial_capital: float, scaling_levels: List[Dict] = None):
        self.initial_capital = initial_capital
        self.current_multiplier = 1.0
        
        # Default scaling levels
        self.scaling_levels = scaling_levels or [
            {"capital_max": 150, "risk_multiplier": 1.5, "label": "AGGRESSIVE"},
            {"capital_max": 250, "risk_multiplier": 1.2, "label": "MODERATE"},
            {"capital_max": 500, "risk_multiplier": 1.0, "label": "NORMAL"},
            {"capital_max": 1000, "risk_multiplier": 0.8, "label": "CONSERVATIVE"},
            {"capital_max": 999999, "risk_multiplier": 0.6, "label": "CAPITAL PRESERVATION"}
        ]
        
        self.current_level = self.scaling_levels[0]
    
    def get_risk_multiplier(self, current_capital: float) -> float:
        """Get appropriate risk multiplier for current capital level."""
        for level in self.scaling_levels:
            if current_capital <= level["capital_max"]:
                if level != self.current_level:
                    self.current_level = level
                    logger.info(f"🎯 RISK LEVEL CHANGE: {level['label']} "
                               f"(${self.initial_capital:.0f} → ${current_capital:.0f}, "
                               f"multiplier: {level['risk_multiplier']:.1f}x)")
                return level["risk_multiplier"]
        return self.scaling_levels[-1]["risk_multiplier"]
    
    def get_position_size(self, base_pct: float, current_capital: float, 
                         trend_multiplier: float = 1.0) -> float:
        """Calculate final position size with both risk scaling and trend."""
        risk_mult = self.get_risk_multiplier(current_capital)
        final_size = base_pct * risk_mult * trend_multiplier
        
        # Cap single position at 50% of account (safety)
        return min(final_size, 0.50)
    
    def get_stats(self) -> str:
        """Return current risk level info."""
        return f"{self.current_level['label']} ({self.current_level['risk_multiplier']:.1f}x)"


@dataclass
class UnifiedConfig:
    """Configuration with risk scaling support."""
    
    initial_capital: float = 100.0
    
    circuit_breaker_enabled: bool = True
    max_daily_loss_pct: float = 0.10
    max_drawdown_pct: float = 0.25
    max_consecutive_losses: int = 3
    circuit_cooldown_minutes: int = 60
    
    risk_per_trade_pct: float = 0.05
    max_total_exposure_pct: float = 0.80
    
    trend_lookback: int = 24
    trend_threshold: float = 0.03
    use_market_classifier: bool = True
    
    # SHORT
    short_leverage: float = 3.0
    short_position_pct: float = 0.40
    short_max_positions: int = 2
    short_bounce_threshold: float = 0.015
    short_tp: float = 0.04
    short_sl: float = 0.025
    short_breakdown_enabled: bool = True
    short_breakdown_threshold: float = 0.015
    
    # LONG
    long_grid_spacing: float = 0.012
    long_markup: float = 0.008
    long_position_pct: float = 0.35
    long_entry_mult: float = 1.1
    max_grid_positions: int = 3
    
    # TREND FOLLOW
    trend_follow_position_pct: float = 0.40
    trend_follow_hard_stop_pct: float = 0.05
    trend_follow_activation_pct: float = 0.03
    trend_follow_trailing_stop_pct: float = 0.06
    trend_follow_partial_tp_enabled: bool = True
    trend_follow_partial_tp_pct: float = 0.06
    trend_follow_partial_tp_size: float = 0.50
    trend_follow_reentry_enabled: bool = True
    trend_follow_reentry_cooldown_hours: int = 24
    trend_follow_pyramiding_enabled: bool = False
    
    # DYNAMIC SIZING (by trend)
    dynamic_sizing_enabled: bool = False
    strong_uptrend_multiplier: float = 1.0
    strong_downtrend_multiplier: float = 1.0
    sideways_multiplier: float = 0.5
    
    # RISK SCALING (by capital growth)
    risk_scaling_enabled: bool = True
    risk_scaling_levels: List[Dict] = field(default_factory=lambda: [
        {"capital_max": 150, "risk_multiplier": 1.5},
        {"capital_max": 250, "risk_multiplier": 1.2},
        {"capital_max": 500, "risk_multiplier": 1.0},
        {"capital_max": 1000, "risk_multiplier": 0.8},
        {"capital_max": 999999, "risk_multiplier": 0.6}
    ])
    
    # SIDEWAYS
    sideways_grid_pct: float = 0.30
    sideways_dca_pct: float = 0.70
    sideways_spacing: float = 0.02
    sideways_markup: float = 0.015
    sideways_max_positions: int = 2
    stop_loss_multiplier: float = 1.5
    max_dca_per_position: int = 2
    
    # Guards
    long_guard_enabled: bool = True
    long_guard_ema_period: int = 200
    long_guard_min_24h_change: float = 0.0
    long_guard_min_72h_change: float = 0.01
    
    # Risk management
    turbulence_lookback: int = 30
    turbulence_threshold: float = 2.0
    turbulence_reduce_size: bool = True
    base_slippage_bps: float = 10.0
    
    # Optional modules
    sentiment_enabled: bool = False
    scalping_enabled: bool = False
    
    # Safety
    daily_loss_limit: float = 0.25
    liquidation_buffer: float = 0.20
    
    # Exchange
    exchange: str = 'hyperliquid'
    symbol: str = 'BTC/USDC:USDC'
    testnet: bool = True
    check_interval: int = 600
    
    def save(self, path: str):
        with open(path, 'w') as f:
            json.dump(asdict(self), f, indent=2)
    
    @classmethod
    def load(cls, path: str):
        with open(path, 'r') as f:
            return cls(**json.load(f))


class CircuitBreaker:
    """Circuit breaker with win rate tracking."""
    
    def __init__(self, max_daily_loss_pct: float = 0.10,
                 max_drawdown_pct: float = 0.25,
                 max_consecutive_losses: int = 3,
                 cooldown_minutes: int = 60):
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.max_consecutive_losses = max_consecutive_losses
        self.cooldown_minutes = cooldown_minutes
        
        self.active = False
        self.reason = ""
        self.cooldown_until: Optional[datetime] = None
        
        self.consecutive_losses = 0
        self.daily_pnl = 0.0
        self.peak_balance = 0.0
        self.initial_balance = 0.0
        self.trades_today = 0
        self.wins_today = 0
    
    def initialize(self, initial_balance: float):
        self.initial_balance = initial_balance
        self.peak_balance = initial_balance
    
    def check(self, current_balance: float) -> tuple:
        if self.cooldown_until and datetime.now() >= self.cooldown_until:
            self.reset()
        
        if self.cooldown_until and datetime.now() < self.cooldown_until:
            return True, f"Cooldown until {self.cooldown_until.strftime('%H:%M')}"
        
        if current_balance > self.peak_balance:
            self.peak_balance = current_balance
        
        drawdown = (self.peak_balance - current_balance) / self.peak_balance if self.peak_balance > 0 else 0
        daily_loss_pct = abs(self.daily_pnl) / self.initial_balance if self.initial_balance > 0 else 0
        
        # Win rate check after 5 trades
        if self.trades_today >= 5:
            win_rate = self.wins_today / self.trades_today
            if win_rate < 0.30:
                self.activate(f"Low win rate: {win_rate:.0%}")
                return True, self.reason
        
        if daily_loss_pct > self.max_daily_loss_pct:
            self.activate(f"Daily loss: {daily_loss_pct:.1%}")
            return True, self.reason
        
        if drawdown > self.max_drawdown_pct:
            self.activate(f"Drawdown: {drawdown:.1%}")
            return True, self.reason
        
        if self.consecutive_losses >= self.max_consecutive_losses:
            self.activate(f"Consecutive losses: {self.consecutive_losses}")
            return True, self.reason
        
        return False, ""
    
    def record_trade(self, pnl: float):
        self.daily_pnl += pnl
        self.trades_today += 1
        if pnl > 0:
            self.wins_today += 1
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
    
    def activate(self, reason: str):
        self.active = True
        self.reason = reason
        self.cooldown_until = datetime.now() + timedelta(minutes=self.cooldown_minutes)
        logger.warning(f"🔴 CIRCUIT BREAKER: {reason}")
    
    def reset(self):
        if self.active:
            logger.info("🟢 Circuit breaker reset")
        self.active = False
        self.reason = ""
        self.cooldown_until = None
        self.consecutive_losses = 0
    
    def reset_daily(self):
        self.daily_pnl = 0.0
        self.trades_today = 0
        self.wins_today = 0


class UnifiedBotRiskScaling:
    """Bot with risk scaling based on capital growth."""
    
    def __init__(self, config: UnifiedConfig):
        self.config = config
        self.exchange = None
        self.current_trend = 'sideways'
        
        self.positions_short: List[Dict] = []
        self.positions_long: List[Dict] = []
        
        self.current_balance = config.initial_capital
        self.peak_balance = config.initial_capital
        
        # Initialize risk scaler
        self.risk_scaler = RiskScaler(
            initial_capital=config.initial_capital,
            scaling_levels=config.risk_scaling_levels if config.risk_scaling_enabled else None
        )
        
        self.circuit_breaker = CircuitBreaker(
            max_daily_loss_pct=config.max_daily_loss_pct,
            max_drawdown_pct=config.max_drawdown_pct,
            max_consecutive_losses=config.max_consecutive_losses,
            cooldown_minutes=config.circuit_cooldown_minutes
        )
        
        self.stats = {
            'trades_total': 0,
            'trades_short': 0,
            'trades_long': 0,
            'profit_total': 0.0,
            'profit_short': 0.0,
            'profit_long': 0.0
        }
        
        logger.info("="*60)
        logger.info("🚀 UNIFIED BOT WITH RISK SCALING")
        logger.info("="*60)
        logger.info(f"Initial: ${config.initial_capital:.0f}")
        logger.info(f"Risk Strategy: AGGRESSIVE start → CONSERVATIVE growth")
        if config.risk_scaling_enabled:
            logger.info("Risk Levels:")
            for level in config.risk_scaling_levels[:4]:
                logger.info(f"  ${config.initial_capital:.0f}-${level['capital_max']:.0f}: "
                           f"{level['risk_multiplier']:.1f}x risk")
        logger.info("="*60)
    
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
            
            self.circuit_breaker.initialize(self.config.initial_capital)
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False
    
    def get_position_size(self, base_pct: float, trend_mult: float = 1.0) -> float:
        """Get position size with risk scaling."""
        if not self.config.risk_scaling_enabled:
            return base_pct * trend_mult
        
        return self.risk_scaler.get_position_size(base_pct, self.current_balance, trend_mult)
    
    def detect_trend(self, prices: List[float]) -> str:
        """Simple trend detection."""
        if len(prices) < 48:
            return 'sideways'
        
        change_24h = (prices[-1] / prices[-25]) - 1 if len(prices) >= 25 else 0
        change_48h = (prices[-1] / prices[-49]) - 1 if len(prices) >= 49 else change_24h
        
        if change_24h > 0.03 and change_48h > 0.05:
            return 'strong_uptrend'
        elif change_48h > 0.02:
            return 'uptrend'
        elif change_24h < -0.03 and change_48h < -0.05:
            return 'strong_downtrend'
        elif change_48h < -0.02:
            return 'downtrend'
        return 'sideways'
    
    def should_enter_short(self, price: float, price_history: List[float]) -> bool:
        if self.circuit_breaker.active:
            return False
        
        if len(self.positions_short) >= self.config.short_max_positions:
            return False
        
        # Breakdown entry
        if len(price_history) >= 6:
            change_6h = (price / price_history[-7]) - 1
            if change_6h < -self.config.short_breakdown_threshold:
                return True
        
        # Bounce entry
        if len(price_history) >= 24:
            recent_low = min(price_history[-24:])
            bounce = (price - recent_low) / recent_low
            if bounce >= self.config.short_bounce_threshold:
                return True
        
        return False
    
    def should_exit_short(self, position: Dict, current_price: float) -> Optional[str]:
        entry = position['entry_price']
        
        if current_price <= entry * (1 - self.config.short_tp):
            return 'tp'
        if current_price >= entry * (1 + self.config.short_sl):
            return 'sl'
        if self.current_trend == 'strong_uptrend':
            return 'trend_reversal'
        
        return None
    
    async def open_short(self, price: float) -> Optional[Dict]:
        position_pct = self.get_position_size(self.config.short_position_pct)
        position_size = self.current_balance * position_pct
        notional = position_size * self.config.short_leverage
        amount = notional / price
        
        logger.info(f"📉 SHORT: ${notional:.0f} ({position_pct:.0%} of ${self.current_balance:.0f}) "
                   f"[{self.risk_scaler.get_stats()}] @ ${price:.0f}")
        
        if self.config.testnet:
            return {
                'id': f"short_{int(time.time())}",
                'entry_price': price,
                'amount': amount,
                'notional': notional,
                'type': 'short'
            }
        return None
    
    async def close_short(self, position: Dict, price: float, reason: str) -> float:
        entry = position['entry_price']
        notional = position['notional']
        pnl = (entry - price) / entry * notional
        
        is_win = pnl > 0
        logger.info(f"📉 CLOSE SHORT ({reason}): PnL ${pnl:.2f}")
        
        self.circuit_breaker.record_trade(pnl)
        self.current_balance += pnl
        if self.current_balance > self.peak_balance:
            self.peak_balance = self.current_balance
        
        self.stats['trades_short'] += 1
        self.stats['profit_short'] += pnl
        self.stats['profit_total'] += pnl
        
        return pnl
    
    def should_enter_long(self, price: float, price_history: List[float]) -> bool:
        if self.circuit_breaker.active:
            return False
        
        long_positions = [p for p in self.positions_long if p['type'] == 'long_grid']
        if len(long_positions) >= self.config.max_grid_positions:
            return False
        
        if len(price_history) < 24:
            return False
        
        recent_high = max(price_history[-24:])
        dip = (recent_high - price) / recent_high
        
        return dip >= self.config.long_grid_spacing
    
    async def open_long(self, price: float) -> Optional[Dict]:
        position_pct = self.get_position_size(self.config.long_position_pct)
        position_size = self.current_balance * position_pct
        amount = position_size / price
        
        logger.info(f"📈 LONG: ${position_size:.0f} ({position_pct:.0%} of ${self.current_balance:.0f}) "
                   f"[{self.risk_scaler.get_stats()}] @ ${price:.0f}")
        
        if self.config.testnet:
            return {
                'id': f"long_{int(time.time())}",
                'entry_price': price,
                'amount': amount,
                'size': position_size,
                'tp_price': price * (1 + self.config.long_markup),
                'type': 'long_grid'
            }
        return None
    
    async def close_long(self, position: Dict, price: float, reason: str) -> float:
        entry = position['entry_price']
        size = position['size']
        pnl = (price - entry) / entry * size
        
        is_win = pnl > 0
        logger.info(f"📈 CLOSE LONG ({reason}): PnL ${pnl:.2f}")
        
        self.circuit_breaker.record_trade(pnl)
        self.current_balance += pnl
        if self.current_balance > self.peak_balance:
            self.peak_balance = self.current_balance
        
        self.stats['trades_long'] += 1
        self.stats['profit_long'] += pnl
        self.stats['profit_total'] += pnl
        
        return pnl
    
    async def run(self):
        if not await self.initialize():
            return
        
        price_history = []
        last_status_print = time.time()
        last_day = datetime.now().date()
        
        while True:
            try:
                # Daily reset
                current_day = datetime.now().date()
                if current_day != last_day:
                    self.circuit_breaker.reset_daily()
                    last_day = current_day
                    logger.info(f"📅 New day | Balance: ${self.current_balance:.2f} | "
                               f"Total PnL: ${self.stats['profit_total']:.2f}")
                
                # Circuit breaker
                should_stop, reason = self.circuit_breaker.check(self.current_balance)
                if should_stop:
                    logger.warning(f"⏸️  {reason}")
                    await asyncio.sleep(60)
                    continue
                
                # Get price
                try:
                    ticker = self.exchange.fetch_ticker(self.config.symbol)
                    price = ticker['last']
                except Exception as e:
                    logger.error(f"Price error: {e}")
                    await asyncio.sleep(self.config.check_interval)
                    continue
                
                price_history.append(price)
                if len(price_history) > 2000:
                    price_history = price_history[-1500:]
                
                # Detect trend
                self.current_trend = self.detect_trend(price_history)
                
                # Print status every hour
                if time.time() - last_status_print > 3600:
                    logger.info(f"📊 {self.current_trend.upper()} | "
                               f"Balance: ${self.current_balance:.2f} | "
                               f"Risk: {self.risk_scaler.get_stats()}")
                    last_status_print = time.time()
                
                # Execute strategy
                if self.current_trend in ('strong_downtrend', 'downtrend'):
                    # Manage shorts
                    for pos in self.positions_short[:]:
                        exit_reason = self.should_exit_short(pos, price)
                        if exit_reason:
                            await self.close_short(pos, price, exit_reason)
                            self.positions_short.remove(pos)
                    
                    # Enter short
                    if self.should_enter_short(price, price_history):
                        pos = await self.open_short(price)
                        if pos:
                            self.positions_short.append(pos)
                
                elif self.current_trend in ('strong_uptrend', 'uptrend'):
                    # Close shorts
                    for pos in self.positions_short[:]:
                        await self.close_short(pos, price, 'trend_change')
                        self.positions_short.remove(pos)
                    
                    # Manage longs
                    for pos in self.positions_long[:]:
                        if pos['type'] == 'long_grid' and price >= pos['tp_price']:
                            await self.close_long(pos, price, 'tp')
                            self.positions_long.remove(pos)
                    
                    # Enter long
                    if self.should_enter_long(price, price_history):
                        pos = await self.open_long(price)
                        if pos:
                            self.positions_long.append(pos)
                
                else:  # sideways
                    # Minimal activity
                    for pos in self.positions_short[:]:
                        await self.close_short(pos, price, 'sideways')
                        self.positions_short.remove(pos)
                
                await asyncio.sleep(self.config.check_interval)
                
            except KeyboardInterrupt:
                logger.info("Bot stopped")
                break
            except Exception as e:
                logger.error(f"Error: {e}")
                await asyncio.sleep(self.config.check_interval)
        
        self.print_final_stats()
    
    def print_final_stats(self):
        logger.info("="*60)
        logger.info("📊 FINAL RESULTS")
        logger.info("="*60)
        logger.info(f"Initial: ${self.config.initial_capital:.2f}")
        logger.info(f"Final:   ${self.current_balance:.2f}")
        logger.info(f"Return:  {(self.current_balance - self.config.initial_capital) / self.config.initial_capital:.2%}")
        logger.info(f"Peak:    ${self.peak_balance:.2f}")
        logger.info(f"Trades:  {self.stats['trades_total']} "
                   f"(Short: {self.stats['trades_short']}, Long: {self.stats['trades_long']})")
        logger.info(f"PnL:     ${self.stats['profit_total']:.2f}")
        logger.info("="*60)


def main():
    parser = argparse.ArgumentParser(description='Unified Bot with Risk Scaling')
    parser.add_argument('--config', default='config_100usd.json')
    parser.add_argument('--testnet', action='store_true')
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--create-config', action='store_true')
    
    args = parser.parse_args()
    
    if args.create_config:
        config = UnifiedConfig()
        config.save(args.config)
        print(f"Created: {args.config}")
        return
    
    if os.path.exists(args.config):
        config = UnifiedConfig.load(args.config)
    else:
        config = UnifiedConfig()
        config.save(args.config)
        print(f"Created default: {args.config}")
    
    if args.testnet:
        config.testnet = True
    elif args.live:
        config.testnet = False
    
    bot = UnifiedBotRiskScaling(config)
    
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("\n✋ Stopped")


if __name__ == '__main__':
    main()
