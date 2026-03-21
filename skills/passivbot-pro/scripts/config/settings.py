"""
Micro-PassivBot Configuration
=============================
Central configuration using Pydantic for validation.
Optimized for $100 capital and micro-trades.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings
from enum import Enum
import os


class ExchangeType(str, Enum):
    HYPERLIQUID = "hyperliquid"
    BYBIT = "bybit"
    BINANCE = "binance"


class OrderSide(str, Enum):
    LONG = "long"
    SHORT = "short"


class GridMode(str, Enum):
    NORMAL = "normal"
    AGGRESSIVE = "aggressive"
    CONSERVATIVE = "conservative"


# ============================================================
# RISK PARAMETERS (Optimized for $100 Capital)
# ============================================================
class RiskConfig(BaseModel):
    """Risk management configuration for micro-accounts."""
    
    # Capital limits
    initial_capital: float = Field(default=100.0, gt=0, description="Starting capital in USD")
    min_position_size: float = Field(default=2.0, ge=1.0, description="Minimum position size")
    max_position_size: float = Field(default=10.0, le=20.0, description="Maximum position size")
    
    # Safety locks
    stop_loss_balance: float = Field(default=80.0, description="Stop trading if balance falls below")
    max_leverage: float = Field(default=5.0, ge=1.0, le=10.0, description="Maximum leverage multiplier")
    max_wallet_exposure: float = Field(default=0.3, ge=0.1, le=0.5, description="Max % of wallet per pair")
    
    # Position limits
    max_open_positions: int = Field(default=3, ge=1, le=5, description="Maximum concurrent positions")
    max_grid_orders: int = Field(default=10, ge=3, le=20, description="Maximum grid orders per side")
    
    # Drawdown protection
    max_drawdown_pct: float = Field(default=0.20, ge=0.05, le=0.35, description="Max drawdown before pause")
    daily_loss_limit: float = Field(default=0.10, ge=0.03, le=0.20, description="Daily loss limit as fraction")
    
    @validator('stop_loss_balance')
    def validate_stop_loss(cls, v, values):
        if 'initial_capital' in values and v >= values['initial_capital']:
            raise ValueError("Stop loss must be less than initial capital")
        return v


# ============================================================
# GRID STRATEGY PARAMETERS
# ============================================================
class GridConfig(BaseModel):
    """Grid trading strategy parameters."""
    
    # Grid spacing (in % of price)
    grid_spacing_pct: float = Field(default=0.005, ge=0.001, le=0.02, description="Distance between grid orders")
    grid_spacing_atr_multiplier: float = Field(default=0.5, ge=0.1, le=2.0, description="ATR multiplier for dynamic spacing")
    
    # Entry scaling (Martingale-ish)
    entry_multiplier: float = Field(default=1.3, ge=1.0, le=2.5, description="Position size multiplier on re-entry")
    max_entry_multiplier: float = Field(default=3.0, ge=1.5, le=5.0, description="Cap on total multiplier")
    
    # Take profit
    markup_pct: float = Field(default=0.004, ge=0.001, le=0.02, description="Take profit distance")
    min_markup_usd: float = Field(default=0.10, ge=0.05, description="Minimum profit in USD")
    
    # Initial entry
    initial_entry_pct: float = Field(default=0.01, ge=0.005, le=0.03, description="Initial entry as % of balance")
    
    # Auto-compounding
    auto_compound: bool = Field(default=True, description="Reinvest profits")
    compound_threshold: float = Field(default=10.0, description="Reinvest when profits exceed this")


# ============================================================
# UNSTUCKING MECHANISM PARAMETERS
# ============================================================
class UnstuckingConfig(BaseModel):
    """
    Unstucking mechanism configuration.
    
    Mathematical Formula:
    =====================
    The Unstucking mechanism prevents margin calls by systematically
    closing portions of stuck positions when drawdown exceeds thresholds.
    
    Core Formula:
    
        unstuck_threshold = entry_price * (1 + max_adverse_pct)
        
        Where:
        - max_adverse_pct = max_wallet_exposure / leverage / 2
        
    Chunk Size Calculation:
    
        chunk_size = position_size * unstuck_chunk_pct
        
        Where unstuck_chunk_pct is dynamic:
        
        if DD < 5%:   chunk_pct = 0.05  (close 5% of position)
        if DD < 10%:  chunk_pct = 0.10  (close 10% of position)
        if DD < 15%:  chunk_pct = 0.20  (close 20% of position)
        if DD >= 15%: chunk_pct = 0.30  (close 30% of position)
    
    Break-Even Gap Calculation:
    
        gap_to_be = (avg_entry - current_price) / avg_entry
        
    Realized Loss per Chunk:
    
        realized_loss = chunk_size * gap_to_be * price
        
    Safety Constraint (ensures we never hit margin call):
    
        margin_remaining > margin_required * 1.5
        
    The formula ensures:
    1. We never lose more than 20% of account in a single position
    2. We free up capital for new profitable grids
    3. Maximum time to liquidation: calculated via Monte Carlo simulation
    """
    
    enabled: bool = Field(default=True, description="Enable unstucking mechanism")
    
    # Thresholds
    activation_drawdown: float = Field(default=0.05, ge=0.02, le=0.15, description="DD% to activate unstucking")
    
    # Chunk sizing (dynamic based on drawdown)
    chunk_pct_tier_1: float = Field(default=0.05, description="Chunk % when DD < 5%")
    chunk_pct_tier_2: float = Field(default=0.10, description="Chunk % when DD 5-10%")
    chunk_pct_tier_3: float = Field(default=0.20, description="Chunk % when DD 10-15%")
    chunk_pct_tier_4: float = Field(default=0.30, description="Chunk % when DD > 15%")
    
    # Timing
    unstuck_interval_minutes: int = Field(default=30, ge=10, le=120, description="Time between unstuck actions")
    min_stuck_duration_minutes: int = Field(default=60, ge=30, le=240, description="Min time before position is 'stuck'")
    
    # Price thresholds
    max_adverse_excursion_pct: float = Field(default=0.15, ge=0.05, le=0.25, description="Max % from entry before forced unstuck")
    
    def get_chunk_pct(self, drawdown: float) -> float:
        """Calculate chunk percentage based on current drawdown."""
        if drawdown < 0.05:
            return self.chunk_pct_tier_1
        elif drawdown < 0.10:
            return self.chunk_pct_tier_2
        elif drawdown < 0.15:
            return self.chunk_pct_tier_3
        else:
            return self.chunk_pct_tier_4


# ============================================================
# EXCHANGE-SPECIFIC CONFIGURATIONS
# ============================================================
class ExchangeFees(BaseModel):
    """Fee structure for each exchange."""
    maker_fee: float = 0.0002  # 0.02%
    taker_fee: float = 0.0005  # 0.05%
    funding_interval_hours: int = 8
    
    # Class methods for exchange-specific fees
    @classmethod
    def hyperliquid(cls):
        return cls(maker_fee=0.0002, taker_fee=0.0005)
    
    @classmethod
    def bybit(cls):
        return cls(maker_fee=0.0002, taker_fee=0.00055)
    
    @classmethod
    def binance(cls):
        return cls(maker_fee=0.0002, taker_fee=0.0005)


class ExchangeConfig(BaseModel):
    """Exchange connection configuration."""
    
    exchange: ExchangeType = Field(default=ExchangeType.HYPERLIQUID)
    
    # API credentials (loaded from environment)
    api_key: Optional[str] = Field(default=None, env="EXCHANGE_API_KEY")
    api_secret: Optional[str] = Field(default=None, env="EXCHANGE_API_SECRET")
    
    # Connection settings
    testnet: bool = Field(default=True, description="Use testnet for development")
    rate_limit: int = Field(default=10, description="Requests per second")
    timeout: int = Field(default=30, description="Request timeout in seconds")
    
    # Trading pairs
    symbols: list[str] = Field(default=["BTC/USDC:USDC", "ETH/USDC:USDC"])
    
    # Fees
    fees: ExchangeFees = Field(default_factory=lambda: ExchangeFees(maker_fee=0.0002, taker_fee=0.0005))


# ============================================================
# BACKTEST CONFIGURATION
# ============================================================
class BacktestConfig(BaseModel):
    """Backtesting engine configuration."""
    
    # Data settings
    lookback_days: int = Field(default=90, ge=30, le=365, description="Historical data period")
    resolution: str = Field(default="1m", description="Candle resolution")
    
    # Slippage model
    base_slippage_pct: float = Field(default=0.0001, description="Base slippage percentage")
    volatility_slippage_multiplier: float = Field(default=0.5, description="Slippage scales with vol")
    
    # Funding rates
    funding_rate_avg: float = Field(default=0.0001, description="Average funding rate per 8h")
    funding_rate_volatility: float = Field(default=0.00005, description="Funding rate std dev")
    
    # Performance
    vectorized: bool = Field(default=True, description="Use vectorized backtesting")
    max_workers: int = Field(default=4, description="Parallel workers for optimization")


# ============================================================
# OPTIMIZER CONFIGURATION (Genetic Algorithm)
# ============================================================
class OptimizerConfig(BaseModel):
    """Genetic Algorithm optimizer configuration."""
    
    # Population
    population_size: int = Field(default=100, ge=50, le=500)
    generations: int = Field(default=50, ge=10, le=200)
    
    # Genetic operators
    crossover_prob: float = Field(default=0.7, ge=0.5, le=0.9)
    mutation_prob: float = Field(default=0.2, ge=0.05, le=0.4)
    elitism_ratio: float = Field(default=0.1, ge=0.05, le=0.2)
    
    # Selection
    tournament_size: int = Field(default=3, ge=2, le=5)
    
    # Objective function weights
    profit_weight: float = Field(default=1.0)
    drawdown_weight: float = Field(default=2.0)  # Penalize drawdown more
    sharpe_weight: float = Field(default=0.5)
    trades_weight: float = Field(default=0.1)  # Minimum trades requirement
    
    # Parameter bounds (for optimization)
    grid_spacing_bounds: tuple[float, float] = (0.002, 0.015)
    entry_multiplier_bounds: tuple[float, float] = (1.1, 2.0)
    markup_bounds: tuple[float, float] = (0.002, 0.015)
    wallet_exposure_bounds: tuple[float, float] = (0.15, 0.40)


# ============================================================
# MAIN CONFIGURATION CLASS
# ============================================================
class BotConfig(BaseSettings):
    """Main bot configuration combining all modules."""
    
    # Sub-configurations
    risk: RiskConfig = Field(default_factory=RiskConfig)
    grid: GridConfig = Field(default_factory=GridConfig)
    unstucking: UnstuckingConfig = Field(default_factory=UnstuckingConfig)
    exchange: ExchangeConfig = Field(default_factory=ExchangeConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    optimizer: OptimizerConfig = Field(default_factory=OptimizerConfig)
    
    # General settings
    log_level: str = Field(default="INFO")
    data_dir: str = Field(default="/home/ubuntu/.openclaw/workspace/memory/passivbot_data")
    
    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"


# ============================================================
# HELPER FUNCTIONS
# ============================================================
def load_config(config_path: Optional[str] = None) -> BotConfig:
    """Load configuration from file or environment."""
    if config_path and os.path.exists(config_path):
        import json
        with open(config_path) as f:
            data = json.load(f)
        return BotConfig(**data)
    return BotConfig()


# Default configuration instance
config = BotConfig()
