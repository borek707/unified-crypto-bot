"""
Main Trading Bot Loop
=====================
Async entry point for live trading.
Coordinates all components: data, execution, safety, unstucking.

Usage:
    python -m trading_bot.main --config config.json
"""

import asyncio
import argparse
import signal
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List
import json
import os

from loguru import logger

from .config.settings import (
    BotConfig, ExchangeType, GridConfig, RiskConfig, 
    UnstuckingConfig, load_config
)
from .data.downloader import DataDownloader, BatchDataDownloader
from .backtest.engine import VectorizedBacktester, BacktestResult
from .optimizer.genetic import GeneticOptimizer
from .execution.trader import TradingEngine, ExchangeConnector, GridManager
from .execution.safety import SafetyManager, UnstuckingEngine, RiskCalculator


# ============================================================
# LOGGING CONFIGURATION
# ============================================================
def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None):
    """Configure loguru logging."""
    
    # Remove default handler
    logger.remove()
    
    # Console handler with colors
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        colorize=True
    )
    
    # File handler if specified
    if log_file:
        logger.add(
            log_file,
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
            rotation="10 MB",
            retention="7 days",
            compression="zip"
        )


# ============================================================
# BOT STATE
# ============================================================
class BotState:
    """Tracks the current state of the trading bot."""
    
    def __init__(self):
        self.start_time: datetime = datetime.now()
        self.is_running: bool = False
        self.is_paused: bool = False
        self.last_update: Optional[datetime] = None
        self.cycles_completed: int = 0
        self.errors_count: int = 0
        self.last_error: Optional[str] = None
        
        # Performance tracking
        self.total_pnl: float = 0.0
        self.total_trades: int = 0
        self.best_trade: float = 0.0
        self.worst_trade: float = 0.0
    
    def uptime(self) -> str:
        """Get human-readable uptime."""
        delta = datetime.now() - self.start_time
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for status display."""
        return {
            'uptime': self.uptime(),
            'is_running': self.is_running,
            'is_paused': self.is_paused,
            'cycles_completed': self.cycles_completed,
            'errors_count': self.errors_count,
            'total_pnl': self.total_pnl,
            'total_trades': self.total_trades
        }


# ============================================================
# MAIN BOT CLASS
# ============================================================
class MicroPassivBot:
    """
    Main trading bot class.
    
    Coordinates:
    - Data collection (DataDownloader)
    - Backtesting (VectorizedBacktester)
    - Optimization (GeneticOptimizer)
    - Execution (TradingEngine)
    - Safety (SafetyManager, UnstuckingEngine)
    """
    
    def __init__(self, config: BotConfig):
        self.config = config
        
        # Components (initialized later)
        self.data_downloader: Optional[DataDownloader] = None
        self.exchange: Optional[ExchangeConnector] = None
        self.trading_engine: Optional[TradingEngine] = None
        self.safety_manager: Optional[SafetyManager] = None
        self.unstucking_engine: Optional[UnstuckingEngine] = None
        
        # State
        self.state = BotState()
        
        # Shutdown signal
        self._shutdown_event = asyncio.Event()
        
        # Current prices
        self.current_prices: Dict[str, float] = {}
        
        # Optimized parameters
        self.optimized_params: Dict[str, dict] = {}
    
    async def initialize(self):
        """Initialize all bot components."""
        logger.info("Initializing Micro-PassivBot...")
        
        # Setup data directory
        Path(self.config.data_dir).mkdir(parents=True, exist_ok=True)
        
        # Initialize data downloader
        self.data_downloader = DataDownloader(
            exchange=self.config.exchange.exchange,
            testnet=self.config.exchange.testnet,
            cache_dir=self.config.data_dir
        )
        
        # Initialize exchange connector
        api_key = os.environ.get('EXCHANGE_API_KEY', '')
        api_secret = os.environ.get('EXCHANGE_API_SECRET', '')
        
        if not api_key or not api_secret:
            logger.warning("No API credentials found - running in simulation mode")
            self._simulation_mode = True
        else:
            self._simulation_mode = False
            self.exchange = ExchangeConnector(
                exchange_type=self.config.exchange.exchange,
                api_key=api_key,
                api_secret=api_secret,
                testnet=self.config.exchange.testnet
            )
            await self.exchange.initialize()
            
            # Initialize trading engine
            self.trading_engine = TradingEngine(
                exchange_connector=self.exchange,
                grid_config=self.config.grid,
                risk_config=self.config.risk,
                symbols=self.config.exchange.symbols
            )
            await self.trading_engine.initialize()
        
        # Initialize safety components
        self.safety_manager = SafetyManager(self.config.risk)
        self.unstucking_engine = UnstuckingEngine(
            self.config.unstucking,
            self.config.risk
        )
        
        logger.info("Initialization complete")
    
    async def run_optimization(self, symbol: str, days: int = 60) -> dict:
        """
        Run parameter optimization for a symbol.
        
        Uses Genetic Algorithm to find optimal grid parameters.
        """
        logger.info(f"Starting optimization for {symbol}...")
        
        # Download historical data
        df = await self.data_downloader.download_historical(
            symbol=symbol,
            timeframe="1m",
            days=days
        )
        
        if df.empty:
            logger.error(f"No data available for {symbol}")
            return {}
        
        # Run optimization
        optimizer = GeneticOptimizer(
            df=df,
            config=self.config.optimizer,
            risk_config=self.config.risk
        )
        
        best_params = optimizer.optimize(verbose=True)
        
        # Save results
        self.optimized_params[symbol] = best_params
        
        # Save to file
        results_path = Path(self.config.data_dir) / f"optimization_{symbol.replace('/', '_')}.json"
        optimizer.save_results(str(results_path))
        
        return best_params
    
    async def run_backtest(self, symbol: str, params: Optional[dict] = None) -> BacktestResult:
        """
        Run backtest with current or provided parameters.
        """
        # Download data if needed
        df = await self.data_downloader.download_historical(
            symbol=symbol,
            timeframe="1m",
            days=self.config.backtest.lookback_days
        )
        
        if df.empty:
            raise ValueError(f"No data for {symbol}")
        
        # Get parameters
        if params is None:
            params = self.optimized_params.get(symbol, {})
        
        grid_config = GridConfig(**params) if params else self.config.grid
        
        # Run backtest
        backtester = VectorizedBacktester(
            grid_config=grid_config,
            risk_config=self.config.risk,
            unstucking_config=self.config.unstucking
        )
        
        result = backtester.run_vectorized(df, verbose=True)
        
        logger.info(f"Backtest result: Return={result.total_return_pct:.2%}, "
                   f"DD={result.max_drawdown_pct:.2%}, Sharpe={result.sharpe_ratio:.2f}")
        
        return result
    
    async def _fetch_current_prices(self) -> Dict[str, float]:
        """Fetch current prices for all trading symbols."""
        prices = {}
        
        for symbol in self.config.exchange.symbols:
            try:
                orderbook = await self.data_downloader.download_orderbook_snapshot(symbol)
                if orderbook['bids'] and orderbook['asks']:
                    # Mid price
                    best_bid = orderbook['bids'][0][0]
                    best_ask = orderbook['asks'][0][0]
                    prices[symbol] = (best_bid + best_ask) / 2
            except Exception as e:
                logger.warning(f"Failed to fetch price for {symbol}: {e}")
                # Use last known price
                if symbol in self.current_prices:
                    prices[symbol] = self.current_prices[symbol]
        
        self.current_prices = prices
        return prices
    
    async def _execute_trading_cycle(self):
        """Execute one trading cycle."""
        
        # Fetch current prices
        prices = await self._fetch_current_prices()
        
        if not prices:
            logger.warning("No prices available - skipping cycle")
            return
        
        # Get account state
        if not self._simulation_mode:
            await self.trading_engine.update_account_state()
            balance = self.trading_engine.balance
            equity = self.trading_engine.equity
        else:
            balance = self.config.risk.initial_capital
            equity = balance
        
        # Update safety state
        positions = [] if self._simulation_mode else []
        safety_state = self.safety_manager.update_state(
            balance=balance,
            equity=equity,
            margin_used=0,  # TODO: calculate from positions
            positions=positions
        )
        
        if not safety_state.is_safe:
            logger.warning(f"Safety warning: {safety_state.warnings}")
        
        # Check unstucking
        if not self._simulation_mode:
            stuck_positions = self.unstucking_engine.identify_stuck_positions(
                positions=positions,
                current_prices=prices,
                balance=balance
            )
            
            if stuck_positions:
                unstuck_actions = self.unstucking_engine.get_all_unstuck_actions(
                    balance=balance,
                    margin_available=safety_state.margin_available
                )
                
                for action in unstuck_actions[:1]:  # Execute one at a time
                    # Execute unstuck order
                    logger.info(f"Executing unstuck: {action.symbol} {action.size_to_close}")
                    # TODO: Execute the close order
                    self.unstucking_engine.record_unstuck(action)
        
        # Execute trading logic
        if safety_state.is_safe and not self._simulation_mode:
            await self.trading_engine.execute_cycle(prices)
        
        self.state.cycles_completed += 1
        self.state.last_update = datetime.now()
    
    async def run_live(self, interval_seconds: int = 10):
        """
        Run live trading loop.
        
        Args:
            interval_seconds: Time between trading cycles
        """
        logger.info("Starting live trading...")
        self.state.is_running = True
        
        # Setup signal handlers
        loop = asyncio.get_event_loop()
        
        def signal_handler():
            logger.info("Shutdown signal received")
            self._shutdown_event.set()
        
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)
        
        try:
            while not self._shutdown_event.is_set():
                try:
                    await self._execute_trading_cycle()
                    
                    # Log status periodically
                    if self.state.cycles_completed % 10 == 0:
                        self._log_status()
                    
                except Exception as e:
                    logger.error(f"Error in trading cycle: {e}")
                    self.state.errors_count += 1
                    self.state.last_error = str(e)
                    
                    if self.state.errors_count > 10:
                        logger.critical("Too many errors - stopping")
                        self._shutdown_event.set()
                
                # Wait for next cycle
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=interval_seconds
                    )
                except asyncio.TimeoutError:
                    pass  # Normal timeout, continue loop
        
        finally:
            self.state.is_running = False
            logger.info("Trading stopped")
            
            # Cleanup
            if self.exchange:
                await self.exchange.close()
            if self.data_downloader:
                await self.data_downloader.close()
    
    def _log_status(self):
        """Log current bot status."""
        status = {
            **self.state.to_dict(),
            'prices': self.current_prices,
            'safety': {
                'is_safe': self.safety_manager.state.is_safe if self.safety_manager.state else None,
                'trading_allowed': self.safety_manager.is_trading_allowed
            }
        }
        
        logger.info(f"Status: {json.dumps(status, indent=2, default=str)}")
    
    async def run_simulation(self, duration_minutes: int = 60):
        """
        Run paper trading simulation.
        
        Uses historical data to simulate live trading.
        """
        logger.info(f"Running {duration_minutes} minute simulation...")
        
        # Download recent data
        for symbol in self.config.exchange.symbols:
            df = await self.data_downloader.download_historical(
                symbol=symbol,
                timeframe="1m",
                days=1
            )
            
            if df.empty:
                logger.warning(f"No data for simulation: {symbol}")
                continue
            
            # Run simulation
            backtester = VectorizedBacktester(
                grid_config=self.config.grid,
                risk_config=self.config.risk
            )
            
            # Use recent data only
            recent_df = df.tail(duration_minutes)
            result = backtester.run_vectorized(recent_df, verbose=True)
            
            logger.info(
                f"Simulation {symbol}: Return={result.total_return_pct:.2%}, "
                f"DD={result.max_drawdown_pct:.2%}, Trades={result.total_trades}"
            )
    
    def get_status(self) -> dict:
        """Get comprehensive bot status."""
        return {
            'bot_state': self.state.to_dict(),
            'config': {
                'exchange': self.config.exchange.exchange.value,
                'symbols': self.config.exchange.symbols,
                'initial_capital': self.config.risk.initial_capital,
                'testnet': self.config.exchange.testnet
            },
            'current_prices': self.current_prices,
            'optimized_params': self.optimized_params,
            'safety': self.safety_manager.get_status_report() if self.safety_manager else None,
            'unstucking': self.unstucking_engine.get_statistics() if self.unstucking_engine else None
        }


# ============================================================
# CLI ENTRY POINT
# ============================================================
async def main_async():
    """Main async entry point."""
    
    parser = argparse.ArgumentParser(description='Micro-PassivBot Trading System')
    parser.add_argument('--config', type=str, help='Path to config file')
    parser.add_argument('--mode', type=str, choices=['live', 'backtest', 'optimize', 'simulate'],
                       default='backtest', help='Running mode')
    parser.add_argument('--symbol', type=str, help='Trading symbol (for backtest/optimize)')
    parser.add_argument('--days', type=int, default=60, help='Days of historical data')
    parser.add_argument('--log-level', type=str, default='INFO', help='Log level')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level, log_file="trading_bot.log")
    
    # Load configuration
    config = load_config(args.config)
    
    # Create bot
    bot = MicroPassivBot(config)
    
    try:
        await bot.initialize()
        
        if args.mode == 'live':
            await bot.run_live()
        
        elif args.mode == 'backtest':
            symbol = args.symbol or config.exchange.symbols[0]
            result = await bot.run_backtest(symbol)
            print(f"\nBacktest Results for {symbol}:")
            print(f"  Total Return: {result.total_return_pct:.2%}")
            print(f"  Max Drawdown: {result.max_drawdown_pct:.2%}")
            print(f"  Sharpe Ratio: {result.sharpe_ratio:.2f}")
            print(f"  Profit Factor: {result.profit_factor:.2f}")
            print(f"  Total Trades: {result.total_trades}")
            print(f"  Win Rate: {result.win_rate:.1%}")
            print(f"  Days to Liquidation: {result.days_to_liquidation:.1f}")
        
        elif args.mode == 'optimize':
            symbol = args.symbol or config.exchange.symbols[0]
            params = await bot.run_optimization(symbol, args.days)
            print(f"\nOptimized Parameters for {symbol}:")
            for key, value in params.items():
                print(f"  {key}: {value}")
        
        elif args.mode == 'simulate':
            await bot.run_simulation(args.days)
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
    finally:
        # Cleanup
        if bot.data_downloader:
            await bot.data_downloader.close()
        if bot.exchange:
            await bot.exchange.close()


def main():
    """CLI entry point."""
    asyncio.run(main_async())


if __name__ == '__main__':
    main()
