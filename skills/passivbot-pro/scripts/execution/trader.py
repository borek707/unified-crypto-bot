"""
Execution Engine
================
Live trading execution with grid management.
Supports Hyperliquid, Bybit, and Binance via CCXT Pro.

Key Features:
- Async order placement and management
- Grid order logic with dynamic levels
- Position tracking and PnL calculation
- Risk management integration
- Real-time balance monitoring
"""

import asyncio
import ccxt.async_support as ccxt
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from loguru import logger
import json
import aiohttp

from ..config.settings import (
    GridConfig, RiskConfig, ExchangeType, OrderSide, 
    GridMode, config
)


# ============================================================
# ORDER & POSITION DATA STRUCTURES
# ============================================================
class OrderStatus(str, Enum):
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    CANCELLED = "cancelled"
    FAILED = "failed"


class OrderType(str, Enum):
    LIMIT = "limit"
    MARKET = "market"
    STOP_LIMIT = "stop_limit"
    STOP_MARKET = "stop_market"


@dataclass
class Order:
    """Order representation."""
    id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    price: float
    size: float
    status: OrderStatus = OrderStatus.PENDING
    filled_size: float = 0.0
    avg_fill_price: float = 0.0
    fee: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    grid_level: int = 0
    is_entry: bool = True
    
    @property
    def remaining(self) -> float:
        return self.size - self.filled_size
    
    @property
    def is_fully_filled(self) -> bool:
        return self.filled_size >= self.size * 0.99
    
    @property
    def notional(self) -> float:
        return self.price * self.size


@dataclass
class Position:
    """Active position tracking."""
    symbol: str
    side: OrderSide
    size: float
    entry_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    leverage: float = 1.0
    liquidation_price: float = 0.0
    margin_used: float = 0.0
    entry_time: datetime = field(default_factory=datetime.now)
    grid_entries: List[Order] = field(default_factory=list)
    
    @property
    def notional(self) -> float:
        return self.size * self.current_price
    
    @property
    def pnl_pct(self) -> float:
        if self.entry_price == 0:
            return 0.0
        return (self.current_price - self.entry_price) / self.entry_price * self.side.value


# ============================================================
# GRID MANAGER
# ============================================================
@dataclass
class GridLevel:
    """Single grid level configuration."""
    price: float
    size: float
    side: OrderSide
    level: int
    order_id: Optional[str] = None
    is_active: bool = True


class GridManager:
    """
    Grid order management logic.
    
    Implements the Passivbot-style grid strategy:
    1. Place orders at fixed % intervals from current price
    2. Scale position size on re-entries (Martingale-ish)
    3. Take profit at markup distance
    4. Reset grid after TP hit
    """
    
    def __init__(
        self,
        symbol: str,
        grid_config: GridConfig,
        risk_config: RiskConfig
    ):
        self.symbol = symbol
        self.grid = grid_config
        self.risk = risk_config
        
        # Grid state
        self.long_grid: List[GridLevel] = []
        self.short_grid: List[GridLevel] = []
        self.position: Optional[Position] = None
        
        # Tracking
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl = 0.0
    
    def calculate_grid_levels(
        self,
        current_price: float,
        balance: float,
        position_side: Optional[OrderSide] = None
    ) -> tuple[List[GridLevel], List[GridLevel]]:
        """
        Calculate grid order levels based on current price.
        
        Formula:
            price_level = base_price * (1 ± grid_spacing_pct * level)
            size_level = base_size * (entry_multiplier ** level)
        
        Returns:
            tuple: (long_levels, short_levels)
        """
        # Base position size
        base_size = balance * self.grid.initial_entry_pct / current_price
        
        long_levels = []
        short_levels = []
        
        # Calculate max position value
        max_pos_value = balance * self.risk.max_wallet_exposure * self.risk.max_leverage
        
        # Generate long grid (buy orders below current price)
        if position_side is None or position_side == OrderSide.LONG:
            cumulative_size = 0.0
            
            for level in range(self.risk.max_grid_orders):
                price = current_price * (1 - self.grid.grid_spacing_pct * (level + 1))
                size = base_size * (self.grid.entry_multiplier ** level)
                
                # Check position limit
                if cumulative_size * price + size * price > max_pos_value:
                    break
                
                cumulative_size += size
                
                long_levels.append(GridLevel(
                    price=price,
                    size=size,
                    side=OrderSide.LONG,
                    level=level
                ))
        
        # Generate short grid (sell orders above current price)
        if position_side is None or position_side == OrderSide.SHORT:
            cumulative_size = 0.0
            
            for level in range(self.risk.max_grid_orders):
                price = current_price * (1 + self.grid.grid_spacing_pct * (level + 1))
                size = base_size * (self.grid.entry_multiplier ** level)
                
                # Check position limit
                if cumulative_size * price + size * price > max_pos_value:
                    break
                
                cumulative_size += size
                
                short_levels.append(GridLevel(
                    price=price,
                    size=size,
                    side=OrderSide.SHORT,
                    level=level
                ))
        
        return long_levels, short_levels
    
    def calculate_take_profit_price(self) -> Optional[float]:
        """
        Calculate take profit price for current position.
        
        Formula:
            tp_price = entry_price * (1 + markup_pct)  # for longs
            tp_price = entry_price * (1 - markup_pct)  # for shorts
        """
        if self.position is None:
            return None
        
        if self.position.side == OrderSide.LONG:
            return self.position.entry_price * (1 + self.grid.markup_pct)
        else:
            return self.position.entry_price * (1 - self.grid.markup_pct)
    
    def update_position_on_fill(self, order: Order):
        """Update position state after order fill."""
        if self.position is None:
            # New position
            self.position = Position(
                symbol=order.symbol,
                side=order.side,
                size=order.filled_size,
                entry_price=order.avg_fill_price,
                current_price=order.avg_fill_price
            )
        else:
            # Add to position
            if order.side == self.position.side:
                # Same direction - update average entry
                total_cost = (self.position.size * self.position.entry_price + 
                            order.filled_size * order.avg_fill_price)
                total_size = self.position.size + order.filled_size
                self.position.entry_price = total_cost / total_size
                self.position.size = total_size
            else:
                # Opposite direction - reduce or close
                if order.filled_size >= self.position.size:
                    # Position closed
                    pnl = self.position.size * (
                        self.position.entry_price - order.avg_fill_price
                    ) * (-1 if self.position.side == OrderSide.LONG else 1)
                    self.total_pnl += pnl
                    self.position = None
                else:
                    # Partial close
                    self.position.size -= order.filled_size
        
        self.position.grid_entries.append(order)
        self.total_trades += 1
    
    def get_grid_state(self) -> dict:
        """Get current grid state for logging/debugging."""
        return {
            'symbol': self.symbol,
            'position': {
                'side': self.position.side.value if self.position else None,
                'size': self.position.size if self.position else 0,
                'entry_price': self.position.entry_price if self.position else 0,
                'unrealized_pnl': self.position.unrealized_pnl if self.position else 0
            } if self.position else None,
            'long_grid_levels': len(self.long_grid),
            'short_grid_levels': len(self.short_grid),
            'total_trades': self.total_trades,
            'total_pnl': self.total_pnl
        }


# ============================================================
# EXCHANGE CONNECTOR
# ============================================================
class ExchangeConnector:
    """
    Exchange connection handler using CCXT Pro.
    
    Supports:
    - Hyperliquid (priority)
    - Bybit
    - Binance
    """
    
    def __init__(
        self,
        exchange_type: ExchangeType,
        api_key: str,
        api_secret: str,
        testnet: bool = True
    ):
        self.exchange_type = exchange_type
        self.testnet = testnet
        
        # Initialize exchange
        exchange_class = self._get_exchange_class()
        
        self.exchange = exchange_class({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',
                'adjustForTimeDifference': True,
            }
        })
        
        # Note: Hyperliquid doesn't have testnet, use small positions for testing
        self.testnet = testnet  # Store for reference but don't use sandbox
        if testnet:
            logger.warning("Hyperliquid doesn't support testnet - using MAINNET with minimal positions!")
        
        self._markets_loaded = False
    
    def _get_exchange_class(self):
        """Get CCXT exchange class."""
        exchange_map = {
            ExchangeType.HYPERLIQUID: ccxt.hyperliquid,
            ExchangeType.BYBIT: ccxt.bybit,
            ExchangeType.BINANCE: ccxt.binance
        }
        return exchange_map[self.exchange_type]
    
    def _set_testnet_urls(self):
        """Set testnet URLs for exchanges."""
        if self.exchange_type == ExchangeType.BYBIT:
            self.exchange.urls['api'] = {
                'futuresPublic': 'https://api-testnet.bybit.com',
                'futuresPrivate': 'https://api-testnet.bybit.com'
            }
        elif self.exchange_type == ExchangeType.BINANCE:
            self.exchange.urls['api'] = {
                'fapiPublic': 'https://testnet.binancefuture.com/fapi',
                'fapiPrivate': 'https://testnet.binancefuture.com/fapi'
            }
    
    async def initialize(self):
        """Load markets and validate connection."""
        await self.exchange.load_markets()
        self._markets_loaded = True
        logger.info(f"Connected to {self.exchange_type.value} (testnet={self.testnet})")
    
    async def fetch_balance(self) -> dict:
        """Fetch account balance."""
        # Hyperliquid requires wallet address as 'user' param
        params = {}
        if self.exchange_type == ExchangeType.HYPERLIQUID:
            params = {'user': self.exchange.apiKey}
        balance = await self.exchange.fetch_balance(params)
        return balance
    
    async def fetch_positions(self) -> List[dict]:
        """Fetch all open positions."""
        # Hyperliquid requires wallet address as 'user' param
        params = {}
        if self.exchange_type == ExchangeType.HYPERLIQUID:
            params = {'user': self.exchange.apiKey}
        positions = await self.exchange.fetch_positions(None, params)
        return [p for p in positions if float(p.get('contracts', 0)) > 0]
    
    async def fetch_open_orders(self, symbol: Optional[str] = None) -> List[dict]:
        """Fetch open orders."""
        if symbol:
            return await self.exchange.fetch_open_orders(symbol)
        return await self.exchange.fetch_open_orders()
    
    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        size: float,
        price: Optional[float] = None,
        params: Optional[dict] = None
    ) -> Order:
        """
        Place an order on the exchange.
        
        Args:
            symbol: Trading pair symbol
            side: Buy or Sell
            order_type: Limit, Market, etc.
            size: Position size in base currency
            price: Limit price (required for limit orders)
            params: Additional exchange-specific parameters
        
        Returns:
            Order object with exchange ID
        """
        if not self._markets_loaded:
            await self.initialize()
        
        # Normalize symbol for exchange
        market = self.exchange.market(symbol)
        
        # Convert side
        ccxt_side = 'buy' if side == OrderSide.LONG else 'sell'
        
        # Place order
        params = params or {}
        
        try:
            if order_type == OrderType.LIMIT:
                result = await self.exchange.create_limit_order(
                    symbol, ccxt_side, size, price, params
                )
            elif order_type == OrderType.MARKET:
                result = await self.exchange.create_market_order(
                    symbol, ccxt_side, size, None, params
                )
            else:
                raise ValueError(f"Unsupported order type: {order_type}")
            
            # Parse result
            order = Order(
                id=result['id'],
                symbol=symbol,
                side=side,
                order_type=order_type,
                price=float(result.get('price', price or 0)),
                size=float(result['amount']),
                status=OrderStatus.OPEN,
                timestamp=datetime.fromtimestamp(result['timestamp'] / 1000)
            )
            
            logger.info(f"Order placed: {order.id} {side.value} {size} @ {price}")
            return order
            
        except Exception as e:
            logger.error(f"Order failed: {e}")
            raise
    
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an open order."""
        try:
            await self.exchange.cancel_order(order_id, symbol)
            logger.info(f"Order cancelled: {order_id}")
            return True
        except Exception as e:
            logger.error(f"Cancel failed: {e}")
            return False
    
    async def cancel_all_orders(self, symbol: Optional[str] = None):
        """Cancel all open orders."""
        try:
            if symbol:
                await self.exchange.cancel_all_orders(symbol)
            else:
                await self.exchange.cancel_all_orders()
            logger.info("All orders cancelled")
        except Exception as e:
            logger.error(f"Cancel all failed: {e}")
    
    async def close_position(self, symbol: str, side: OrderSide, size: float):
        """Close a position with market order."""
        close_side = OrderSide.SHORT if side == OrderSide.LONG else OrderSide.LONG
        
        logger.info(f"Closing position: {symbol} {side.value} {size}")
        
        return await self.place_order(
            symbol=symbol,
            side=close_side,
            order_type=OrderType.MARKET,
            size=size
        )
    
    async def set_leverage(self, symbol: str, leverage: float):
        """Set leverage for a symbol."""
        try:
            if self.exchange_type == ExchangeType.BYBIT:
                await self.exchange.set_leverage(leverage, symbol, {'mode': 'cross'})
            elif self.exchange_type == ExchangeType.BINANCE:
                await self.exchange.fapiPrivatePostLeverage({
                    'symbol': self.exchange.market(symbol)['id'],
                    'leverage': int(leverage)
                })
            # Hyperliquid handles leverage differently
            logger.info(f"Leverage set to {leverage}x for {symbol}")
        except Exception as e:
            logger.warning(f"Set leverage failed: {e}")
    
    async def close(self):
        """Close exchange connection."""
        await self.exchange.close()


# ============================================================
# TRADING ENGINE
# ============================================================
class TradingEngine:
    """
    Main trading engine combining grid management and execution.
    """
    
    def __init__(
        self,
        exchange_connector: ExchangeConnector,
        grid_config: GridConfig,
        risk_config: RiskConfig,
        symbols: List[str]
    ):
        self.connector = exchange_connector
        self.grid_config = grid_config
        self.risk_config = risk_config
        self.symbols = symbols
        
        # Grid managers per symbol
        self.grid_managers: Dict[str, GridManager] = {}
        
        # Active orders
        self.open_orders: Dict[str, List[Order]] = {}
        
        # Account state
        self.balance: float = 0.0
        self.equity: float = 0.0
        self.available_margin: float = 0.0
        
        # Safety state
        self.trading_enabled = True
        self.daily_pnl = 0.0
        self.last_reset = datetime.now()
    
    async def initialize(self):
        """Initialize trading engine."""
        await self.connector.initialize()
        
        # Initialize grid managers
        for symbol in self.symbols:
            self.grid_managers[symbol] = GridManager(
                symbol=symbol,
                grid_config=self.grid_config,
                risk_config=self.risk_config
            )
            self.open_orders[symbol] = []
        
        # Fetch initial state
        await self.update_account_state()
        
        logger.info(f"Trading engine initialized for {len(self.symbols)} symbols")
    
    async def update_account_state(self):
        """Update balance and position information."""
        balance = await self.connector.fetch_balance()
        
        # Get USDC/USDT balance
        quote_currency = 'USDC' if 'USDC' in balance else 'USDT'
        self.balance = float(balance.get(quote_currency, {}).get('free', 0))
        self.equity = float(balance.get(quote_currency, {}).get('total', 0))
        self.available_margin = self.balance
        
        # Update daily reset
        if datetime.now().date() > self.last_reset.date():
            self.daily_pnl = 0.0
            self.last_reset = datetime.now()
    
    async def sync_positions(self):
        """Sync position state from exchange."""
        positions = await self.connector.fetch_positions()
        
        for pos in positions:
            symbol = pos['symbol']
            if symbol in self.grid_managers:
                gm = self.grid_managers[symbol]
                
                # Update or create position
                size = float(pos['contracts'])
                if size > 0:
                    gm.position = Position(
                        symbol=symbol,
                        side=OrderSide.LONG if pos['side'] == 'long' else OrderSide.SHORT,
                        size=size,
                        entry_price=float(pos['entryPrice']),
                        current_price=float(pos['markPrice']),
                        unrealized_pnl=float(pos['unrealizedPnl']),
                        leverage=float(pos['leverage'])
                    )
    
    async def sync_orders(self):
        """Sync open orders from exchange."""
        for symbol in self.symbols:
            orders = await self.connector.fetch_open_orders(symbol)
            
            # Update local order state
            self.open_orders[symbol] = [
                Order(
                    id=o['id'],
                    symbol=symbol,
                    side=OrderSide.LONG if o['side'] == 'buy' else OrderSide.SHORT,
                    order_type=OrderType.LIMIT,
                    price=float(o['price']),
                    size=float(o['remaining']),
                    status=OrderStatus.OPEN
                )
                for o in orders
            ]
    
    async def place_grid_orders(self, symbol: str, current_price: float):
        """Place grid orders for a symbol."""
        gm = self.grid_managers[symbol]
        
        # Calculate grid levels
        position_side = gm.position.side if gm.position else None
        long_levels, short_levels = gm.calculate_grid_levels(
            current_price=current_price,
            balance=self.balance,
            position_side=position_side
        )
        
        # Cancel existing orders first
        await self.connector.cancel_all_orders(symbol)
        
        # Place new grid orders
        for level in long_levels:
            try:
                order = await self.connector.place_order(
                    symbol=symbol,
                    side=OrderSide.LONG,
                    order_type=OrderType.LIMIT,
                    size=level.size,
                    price=level.price
                )
                level.order_id = order.id
            except Exception as e:
                logger.error(f"Failed to place long grid order: {e}")
        
        for level in short_levels:
            try:
                order = await self.connector.place_order(
                    symbol=symbol,
                    side=OrderSide.SHORT,
                    order_type=OrderType.LIMIT,
                    size=level.size,
                    price=level.price
                )
                level.order_id = order.id
            except Exception as e:
                logger.error(f"Failed to place short grid order: {e}")
        
        # Update grid state
        gm.long_grid = long_levels
        gm.short_grid = short_levels
        
        logger.debug(f"Placed {len(long_levels)} long + {len(short_levels)} short orders for {symbol}")
    
    async def check_take_profit(self, symbol: str, current_price: float):
        """Check and execute take profit."""
        gm = self.grid_managers[symbol]
        
        if gm.position is None:
            return
        
        tp_price = gm.calculate_take_profit_price()
        if tp_price is None:
            return
        
        should_close = False
        
        if gm.position.side == OrderSide.LONG and current_price >= tp_price:
            should_close = True
        elif gm.position.side == OrderSide.SHORT and current_price <= tp_price:
            should_close = True
        
        if should_close:
            logger.info(f"Take profit triggered for {symbol} at {current_price}")
            
            # Close position
            await self.connector.close_position(
                symbol=symbol,
                side=gm.position.side,
                size=gm.position.size
            )
            
            # Reset position
            gm.position = None
            
            # Place new grid
            await self.place_grid_orders(symbol, current_price)
    
    async def check_safety_limits(self) -> bool:
        """
        Check safety limits and return whether trading should continue.
        
        Checks:
        1. Balance > stop_loss_balance
        2. Daily loss < daily_loss_limit
        3. Max drawdown not exceeded
        """
        # Balance check
        if self.balance < self.risk_config.stop_loss_balance:
            logger.warning(f"Balance {self.balance} below stop loss {self.risk_config.stop_loss_balance}")
            self.trading_enabled = False
            return False
        
        # Daily loss check
        daily_loss_pct = abs(self.daily_pnl) / self.risk_config.initial_capital
        if self.daily_pnl < 0 and daily_loss_pct > self.risk_config.daily_loss_limit:
            logger.warning(f"Daily loss limit exceeded: {daily_loss_pct:.2%}")
            self.trading_enabled = False
            return False
        
        return True
    
    async def execute_cycle(self, price_data: Dict[str, float]):
        """
        Execute one trading cycle.
        
        Args:
            price_data: Current prices per symbol
        """
        if not self.trading_enabled:
            logger.warning("Trading disabled due to safety limits")
            return
        
        # Update state
        await self.update_account_state()
        
        # Process each symbol
        for symbol, price in price_data.items():
            if symbol not in self.grid_managers:
                continue
            
            # Check for filled orders and update position
            await self.sync_orders()
            
            # Check take profit
            await self.check_take_profit(symbol, price)
            
            # Refresh grid orders periodically
            gm = self.grid_managers[symbol]
            if len(self.open_orders.get(symbol, [])) < 3:
                await self.place_grid_orders(symbol, price)
        
        # Safety check
        await self.check_safety_limits()
    
    def get_status(self) -> dict:
        """Get current trading status."""
        return {
            'balance': self.balance,
            'equity': self.equity,
            'daily_pnl': self.daily_pnl,
            'trading_enabled': self.trading_enabled,
            'positions': {
                symbol: gm.get_grid_state()
                for symbol, gm in self.grid_managers.items()
            }
        }
