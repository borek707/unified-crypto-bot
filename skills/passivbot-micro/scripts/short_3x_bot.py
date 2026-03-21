#!/usr/bin/env python3
"""
Micro-PassivBot SHORT 3x - Live Trading
======================================
Bot do automatycznego shortowania z lewarowaniem 3x na Hyperliquid.

Cel: 15-20% miesięcznie w trendzie spadkowym.
Ryzyko: Liquidation przy 33% wzroście BTC.

Użycie:
    python short_3x_bot.py --config config.json
    python short_3x_bot.py --testnet  # Test mode
"""

import argparse
import asyncio
import json
import logging
import sys
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('/home/ubuntu/.openclaw/workspace/memory/passivbot_logs/short_3x.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Ensure log directory exists
os.makedirs('/home/ubuntu/.openclaw/workspace/memory/passivbot_logs', exist_ok=True)


@dataclass
class BotConfig:
    """Configuration for SHORT 3x bot."""
    # Account
    initial_capital: float = 100.0
    
    # Leverage & Position
    leverage: float = 3.0
    position_size_pct: float = 0.15  # 15% of capital per trade = $15
    max_positions: int = 2
    
    # Entry conditions
    bounce_threshold: float = 0.015  # 1.5% bounce to enter
    trend_lookback: int = 48  # 48 hours
    
    # Exit conditions
    take_profit_pct: float = 0.04  # 4% below entry
    stop_loss_pct: float = 0.025   # 2.5% above entry
    
    # Safety
    liquidation_buffer: float = 0.10  # Close before 10% of liq distance
    daily_loss_limit: float = 0.15    # Stop after 15% daily loss
    
    # Exchange
    exchange: str = 'hyperliquid'
    symbol: str = 'BTC/USDC:USDC'
    testnet: bool = True
    
    # Timing
    check_interval: int = 60  # Check every 60 seconds
    
    def save(self, path: str):
        with open(path, 'w') as f:
            json.dump(asdict(self), f, indent=2)
    
    @classmethod
    def load(cls, path: str):
        with open(path, 'r') as f:
            return cls(**json.load(f))


class Short3xBot:
    """
    Automated SHORT trading bot with 3x leverage.
    
    Strategy:
    1. Wait for price bounce (1.5% up from recent low)
    2. Open SHORT position with 3x leverage
    3. Set TP at 4% below entry, SL at 2.5% above entry
    4. Monitor and close before liquidation
    """
    
    def __init__(self, config: BotConfig):
        self.config = config
        self.exchange = None
        self.positions: List[Dict] = []
        self.daily_stats = {
            'date': datetime.now().date(),
            'trades': 0,
            'profit': 0.0,
            'loss': 0.0
        }
        self.total_stats = {
            'trades': 0,
            'wins': 0,
            'losses': 0,
            'total_profit': 0.0,
            'max_drawdown': 0.0,
            'peak_balance': config.initial_capital
        }
        
    async def initialize(self):
        """Initialize exchange connection."""
        try:
            import ccxt
            
            # Load API keys from environment or config
            api_key = os.getenv('HYPERLIQUID_API_KEY', '')
            secret = os.getenv('HYPERLIQUID_SECRET', '')
            
            self.exchange = ccxt.hyperliquid({
                'enableRateLimit': True,
                'apiKey': api_key,
                'secret': secret,
                'options': {
                    'defaultType': 'swap',
                    'testnet': self.config.testnet
                }
            })
            
            # Test connection
            await self.exchange.load_markets()
            logger.info(f"Connected to {self.config.exchange}")
            logger.info(f"Testnet: {self.config.testnet}")
            logger.info(f"Symbol: {self.config.symbol}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize exchange: {e}")
            return False
    
    def calculate_liquidation_price(self, entry_price: float, side: str = 'short') -> float:
        """Calculate liquidation price for 3x short."""
        # For 3x short: liq_price = entry * (1 + 0.33) roughly
        # Exact calculation depends on margin and maintenance margin
        maintenance_margin = 0.005  # 0.5%
        liq_price = entry_price * (1 + (1 - maintenance_margin) / self.config.leverage)
        return liq_price
    
    def should_enter(self, price: float, price_history: List[float]) -> bool:
        """Check if we should enter SHORT position."""
        if len(price_history) < self.config.trend_lookback:
            return False
        
        # Find recent low
        recent_low = min(price_history[-self.config.trend_lookback:])
        
        # Check if we bounced from low
        bounce = (price - recent_low) / recent_low
        
        # Check if we have max positions
        if len(self.positions) >= self.config.max_positions:
            return False
        
        # Enter on 1.5% bounce
        if bounce >= self.config.bounce_threshold:
            logger.info(f"Bounce detected: {bounce*100:.2f}% from low ${recent_low:.2f}")
            return True
        
        return False
    
    def should_exit(self, position: Dict, current_price: float) -> Optional[str]:
        """Check if we should exit position. Returns 'tp', 'sl', or None."""
        entry = position['entry_price']
        
        # Take profit: price dropped 4%
        tp_price = entry * (1 - self.config.take_profit_pct)
        if current_price <= tp_price:
            return 'tp'
        
        # Stop loss: price rose 2.5%
        sl_price = entry * (1 + self.config.stop_loss_pct)
        if current_price >= sl_price:
            return 'sl'
        
        # Emergency: near liquidation
        liq_price = position.get('liquidation_price', self.calculate_liquidation_price(entry))
        if current_price >= liq_price * (1 - self.config.liquidation_buffer):
            logger.warning(f"Near liquidation! Closing position.")
            return 'sl'
        
        return None
    
    async def get_price(self) -> Optional[float]:
        """Get current price."""
        try:
            ticker = await self.exchange.fetch_ticker(self.config.symbol)
            return ticker['last']
        except Exception as e:
            logger.error(f"Failed to get price: {e}")
            return None
    
    async def open_short(self, price: float) -> Optional[Dict]:
        """Open SHORT position."""
        try:
            position_size = self.config.initial_capital * self.config.position_size_pct
            
            # Calculate amount with leverage
            notional = position_size * self.config.leverage
            amount = notional / price
            
            logger.info(f"Opening SHORT: ${notional:.2f} at ${price:.2f}")
            logger.info(f"Amount: {amount:.6f} BTC")
            logger.info(f"Liq price: ~${self.calculate_liquidation_price(price):.2f}")
            
            if self.config.testnet:
                # Simulate in testnet
                logger.info("TESTNET: Simulated order")
                return {
                    'id': f"sim_{int(time.time())}",
                    'entry_price': price,
                    'amount': amount,
                    'liquidation_price': self.calculate_liquidation_price(price),
                    'open_time': datetime.now()
                }
            else:
                # Real order
                order = await self.exchange.create_market_sell_order(
                    self.config.symbol,
                    amount
                )
                return {
                    'id': order['id'],
                    'entry_price': price,
                    'amount': amount,
                    'liquidation_price': self.calculate_liquidation_price(price),
                    'open_time': datetime.now()
                }
                
        except Exception as e:
            logger.error(f"Failed to open SHORT: {e}")
            return None
    
    async def close_short(self, position: Dict, price: float, reason: str) -> float:
        """Close SHORT position. Returns PnL."""
        try:
            entry = position['entry_price']
            amount = position['amount']
            
            # Calculate PnL for short
            pnl = (entry - price) / entry * (amount * entry)
            
            logger.info(f"Closing SHORT ({reason}): ${price:.2f}")
            logger.info(f"Entry: ${entry:.2f}, PnL: ${pnl:.2f}")
            
            if self.config.testnet:
                logger.info("TESTNET: Simulated close")
            else:
                await self.exchange.create_market_buy_order(
                    self.config.symbol,
                    amount
                )
            
            # Update stats
            self.total_stats['trades'] += 1
            if pnl > 0:
                self.total_stats['wins'] += 1
                self.total_stats['total_profit'] += pnl
            else:
                self.total_stats['losses'] += 1
                self.total_stats['total_profit'] += pnl
            
            # Daily stats
            self.daily_stats['trades'] += 1
            if pnl > 0:
                self.daily_stats['profit'] += pnl
            else:
                self.daily_stats['loss'] += abs(pnl)
            
            return pnl
            
        except Exception as e:
            logger.error(f"Failed to close SHORT: {e}")
            return 0.0
    
    def check_daily_limit(self) -> bool:
        """Check if we hit daily loss limit."""
        today = datetime.now().date()
        
        # Reset daily stats if new day
        if today != self.daily_stats['date']:
            self.daily_stats = {
                'date': today,
                'trades': 0,
                'profit': 0.0,
                'loss': 0.0
            }
        
        daily_loss_pct = self.daily_stats['loss'] / self.config.initial_capital
        
        if daily_loss_pct >= self.config.daily_loss_limit:
            logger.warning(f"Daily loss limit hit: {daily_loss_pct*100:.1f}%")
            return False
        
        return True
    
    def print_stats(self):
        """Print current statistics."""
        win_rate = self.total_stats['wins'] / max(self.total_stats['trades'], 1) * 100
        
        logger.info("="*60)
        logger.info("BOT STATISTICS")
        logger.info("="*60)
        logger.info(f"Total Trades: {self.total_stats['trades']}")
        logger.info(f"Wins: {self.total_stats['wins']} | Losses: {self.total_stats['losses']}")
        logger.info(f"Win Rate: {win_rate:.1f}%")
        logger.info(f"Total PnL: ${self.total_stats['total_profit']:.2f}")
        logger.info(f"Open Positions: {len(self.positions)}")
        logger.info(f"Daily Trades: {self.daily_stats['trades']}")
        logger.info("="*60)
    
    async def run(self):
        """Main bot loop."""
        logger.info("="*60)
        logger.info("STARTING SHORT 3x BOT")
        logger.info("="*60)
        logger.info(f"Capital: ${self.config.initial_capital}")
        logger.info(f"Leverage: {self.config.leverage}x")
        logger.info(f"Position Size: {self.config.position_size_pct*100:.0f}%")
        logger.info(f"TP: {self.config.take_profit_pct*100:.1f}% | SL: {self.config.stop_loss_pct*100:.1f}%")
        logger.info("="*60)
        
        # Price history for trend analysis
        price_history = []
        last_stats_print = time.time()
        
        while True:
            try:
                # Get current price
                price = await self.get_price()
                if price is None:
                    await asyncio.sleep(self.config.check_interval)
                    continue
                
                price_history.append(price)
                if len(price_history) > 100:
                    price_history.pop(0)
                
                # Check daily limit
                if not self.check_daily_limit():
                    logger.info("Daily limit hit, waiting for next day...")
                    await asyncio.sleep(3600)  # Sleep 1 hour
                    continue
                
                # Check existing positions
                for pos in self.positions[:]:
                    exit_reason = self.should_exit(pos, price)
                    if exit_reason:
                        pnl = await self.close_short(pos, price, exit_reason)
                        self.positions.remove(pos)
                        logger.info(f"Position closed. PnL: ${pnl:.2f}")
                
                # Check for new entry
                if self.should_enter(price, price_history):
                    position = await self.open_short(price)
                    if position:
                        self.positions.append(position)
                        logger.info(f"Position opened. ID: {position['id']}")
                
                # Print stats every hour
                if time.time() - last_stats_print > 3600:
                    self.print_stats()
                    last_stats_print = time.time()
                
                await asyncio.sleep(self.config.check_interval)
                
            except KeyboardInterrupt:
                logger.info("Bot stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(self.config.check_interval)
        
        # Close all positions on exit
        logger.info("Closing all positions...")
        price = await self.get_price()
        for pos in self.positions:
            await self.close_short(pos, price, 'shutdown')
        
        self.print_stats()


def main():
    parser = argparse.ArgumentParser(description='SHORT 3x Trading Bot')
    parser.add_argument('--config', type=str, default='short_3x_config.json',
                       help='Path to config file')
    parser.add_argument('--testnet', action='store_true',
                       help='Run in testnet mode (simulated trading)')
    parser.add_argument('--create-config', action='store_true',
                       help='Create default config file')
    
    args = parser.parse_args()
    
    if args.create_config:
        config = BotConfig()
        config.save(args.config)
        print(f"Created config: {args.config}")
        print("Edit the file and set your API keys")
        return
    
    # Load or create config
    if os.path.exists(args.config):
        config = BotConfig.load(args.config)
    else:
        config = BotConfig()
        if args.testnet:
            config.testnet = True
        config.save(args.config)
        print(f"Created default config: {args.config}")
    
    if args.testnet:
        config.testnet = True
    
    # Run bot
    bot = Short3xBot(config)
    
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("\nBot stopped")


if __name__ == '__main__':
    main()
