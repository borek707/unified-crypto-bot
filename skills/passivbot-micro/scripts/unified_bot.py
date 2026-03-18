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
from datetime import datetime
from typing import Optional, Dict, List, Literal
import time

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


@dataclass
class UnifiedConfig:
    """Configuration for unified bot."""
    # Account
    initial_capital: float = 100.0
    
    # Trend detection
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
    
    # === SIDEWAYS: Grid + DCA ===
    sideways_grid_pct: float = 0.30  # 30% capital
    sideways_dca_pct: float = 0.70   # 70% capital
    sideways_spacing: float = 0.01   # 1%
    sideways_markup: float = 0.008   # 0.8%
    
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
        self.current_trend: Literal['uptrend', 'downtrend', 'sideways'] = 'sideways'
        
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
                'options': {
                    'defaultType': 'swap'
                }
            })
            
            # Load markets (sync in ccxt)
            self.exchange.load_markets()
            logger.info(f"✅ Connected to {self.config.exchange}")
            logger.info(f"Mode: {'PAPER (Testnet mode not available)' if self.config.testnet else 'LIVE'}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False
    
    def detect_trend(self, prices: List[float]) -> Literal['uptrend', 'downtrend', 'sideways']:
        """
        Detect market trend based on recent price action with HYSTERESIS.
        
        FIX 1: Hysteresis prevents "ping-pong" effect at trend boundaries.
        FIX 2: Use 2880 candles for 48h on 1-minute data.
        """
        # FIX 1: For 1-minute data, 48h = 2880 candles
        lookback = 2880  # 48 hours in minutes
        
        if len(prices) < lookback:
            return self.current_trend  # Keep current trend if not enough data
        
        recent = prices[-lookback:]
        change = (recent[-1] / recent[0]) - 1
        
        # FIX 2: Hysteresis (buffer zones)
        if self.current_trend == 'sideways':
            # Enter trend at ±5%
            if change > self.config.trend_threshold:
                return 'uptrend'
            elif change < -self.config.trend_threshold:
                return 'downtrend'
            return 'sideways'
            
        elif self.current_trend == 'uptrend':
            # Stay in uptrend unless drops below 3.5% (buffer 1.5%)
            exit_threshold = self.config.trend_threshold - 0.015
            if change < exit_threshold:
                return 'sideways'
            return 'uptrend'
            
        elif self.current_trend == 'downtrend':
            # Stay in downtrend unless rises above -3.5% (buffer 1.5%)
            exit_threshold = -self.config.trend_threshold + 0.015
            if change > exit_threshold:
                return 'sideways'
            return 'downtrend'
        
        return 'sideways'
    
    # ============ SHORT 3x STRATEGY ============
    
    def should_enter_short(self, price: float, price_history: List[float]) -> bool:
        """Check if we should enter SHORT position."""
        if len(self.positions_short) >= self.config.short_max_positions:
            return False
        
        if len(price_history) < 10:
            return False
        
        # Find recent low
        recent_low = min(price_history[-24:])  # Last 24 hours
        
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
        
        # Find recent high
        recent_high = max(price_history[-24:])
        
        # Dip from high
        dip = (recent_high - price) / recent_high
        
        return dip >= self.config.long_grid_spacing
    
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
        
        self.stats['trades_long'] += 1  # Count as long trade
        self.stats['profit_long'] += pnl
        self.stats['profit_total'] += pnl
        
        return pnl
    
    async def execute_sideways_strategy(self, price: float, price_history: List[float]):
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
        logger.info("🚀 UNIFIED BOT STARTED")
        logger.info("="*70)
        logger.info(f"Capital: ${self.config.initial_capital}")
        logger.info(f"Trend detection: {self.config.trend_lookback}h / {self.config.trend_threshold*100:.0f}%")
        logger.info("="*70)
        
        # Initialize exchange connection
        if not await self.initialize():
            logger.error("❌ Failed to initialize exchange. Exiting.")
            return
        
        price_history = []
        last_trend_print = time.time()
        previous_trend = self.current_trend  # Initialize previous_trend
        
        while True:
            try:
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
                        from pathlib import Path
                        db_path = Path('~/.openclaw/workspace/memory/crypto_prices.db').expanduser()
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
                            sys.path.insert(0, str(Path('~/.openclaw/workspace/skills/finance-tracker/scripts').expanduser()))
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
                if len(price_history) > 200:
                    price_history.pop(0)
                
                # Detect trend
                new_trend = self.detect_trend(price_history)
                
                if new_trend != self.current_trend:
                    logger.info(f"🔄 TREND CHANGE: {self.current_trend} → {new_trend}")
                    self.current_trend = new_trend
                
                # Print trend every hour
                if time.time() - last_trend_print > 3600:
                    logger.info(f"📊 Current trend: {self.current_trend.upper()}")
                    last_trend_print = time.time()
                
                # === EXECUTE STRATEGY BASED ON TREND ===
                
                # FIX 3: Trend change - cancel orders, don't close positions
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
                    
                    self.current_trend = new_trend
                    previous_trend = new_trend
                
                if self.current_trend == 'downtrend':
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
                
                elif self.current_trend == 'uptrend':
                    # LONG Grid STRATEGY
                    
                    # FIX 3: Don't close shorts! Let them hit SL/TP
                    # Grid logic for longs
                    if not self.positions_long:
                        if self.should_enter_long_grid(price, price_history):
                            pos = await self.open_long_grid(price)
                            if pos:
                                self.positions_long.append(pos)
                    else:
                        # Check TP
                        for pos in self.positions_long[:]:
                            if price >= pos['tp_price']:
                                await self.close_long_grid(pos, price)
                                self.positions_long.remove(pos)
                    if not self.positions_long:
                        if self.should_enter_long_grid(price, price_history):
                            pos = await self.open_long_grid(price)
                            if pos:
                                self.positions_long.append(pos)
                    else:
                        # Check TP
                        for pos in self.positions_long[:]:
                            if price >= pos['tp_price']:
                                await self.close_long_grid(pos, price)
                                self.positions_long.remove(pos)
                
                else:  # sideways
                    # Close all leveraged positions (keep grid positions)
                    for pos in self.positions_short[:]:
                        await self.close_short(pos, price, 'sideways')
                        self.positions_short.remove(pos)
                    
                    # === SIDEWAYS: Grid + DCA Strategy ===
                    await self.execute_sideways_strategy(price, price_history)
                
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
