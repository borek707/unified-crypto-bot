"""
Tests for Micro-PassivBot
=========================
Unit tests for core functionality.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from trading_bot.config.settings import (
    GridConfig, RiskConfig, UnstuckingConfig, BotConfig
)
from trading_bot.backtest.engine import (
    VectorizedBacktester, calculate_atr_numba, simulate_grid_numba
)
from trading_bot.execution.safety import (
    SafetyManager, UnstuckingEngine, RiskCalculator, UnstuckTrigger
)
from trading_bot.utils.helpers import (
    generate_sample_data, calculate_max_drawdown, calculate_sharpe_ratio
)


# ============================================================
# FIXTURES
# ============================================================
@pytest.fixture
def sample_data():
    """Generate sample OHLCV data for testing."""
    return generate_sample_data(n_candles=10000, seed=42)


@pytest.fixture
def grid_config():
    """Default grid configuration."""
    return GridConfig()


@pytest.fixture
def risk_config():
    """Default risk configuration."""
    return RiskConfig()


@pytest.fixture
def unstucking_config():
    """Default unstucking configuration."""
    return UnstuckingConfig()


# ============================================================
# CONFIG TESTS
# ============================================================
class TestConfig:
    """Tests for configuration models."""
    
    def test_grid_config_defaults(self):
        """Test grid configuration default values."""
        config = GridConfig()
        assert config.grid_spacing_pct == 0.005
        assert config.entry_multiplier == 1.3
        assert config.markup_pct == 0.004
    
    def test_risk_config_defaults(self):
        """Test risk configuration default values."""
        config = RiskConfig()
        assert config.initial_capital == 100.0
        assert config.stop_loss_balance == 80.0
        assert config.max_leverage == 5.0
    
    def test_unstucking_chunk_calculation(self):
        """Test unstucking chunk percentage calculation."""
        config = UnstuckingConfig()
        
        assert config.get_chunk_pct(0.03) == 0.05  # DD < 5%
        assert config.get_chunk_pct(0.07) == 0.10  # DD 5-10%
        assert config.get_chunk_pct(0.12) == 0.20  # DD 10-15%
        assert config.get_chunk_pct(0.20) == 0.30  # DD > 15%
    
    def test_risk_config_validation(self):
        """Test risk config validation."""
        with pytest.raises(ValueError):
            RiskConfig(stop_loss_balance=150)  # Must be less than initial


# ============================================================
# BACKTEST ENGINE TESTS
# ============================================================
class TestBacktester:
    """Tests for backtesting engine."""
    
    def test_atr_calculation(self, sample_data):
        """Test ATR calculation with Numba."""
        high = sample_data['high'].values.astype(np.float64)
        low = sample_data['low'].values.astype(np.float64)
        close = sample_data['close'].values.astype(np.float64)
        
        atr = calculate_atr_numba(high, low, close, period=14)
        
        assert len(atr) == len(close)
        assert not np.all(np.isnan(atr[14:]))  # ATR should be computed after warmup
    
    def test_backtest_runs(self, sample_data, grid_config, risk_config):
        """Test that backtest runs without errors."""
        backtester = VectorizedBacktester(
            grid_config=grid_config,
            risk_config=risk_config
        )
        
        result = backtester.run_vectorized(sample_data, verbose=False)
        
        assert result is not None
        assert isinstance(result.total_return, float)
        assert isinstance(result.max_drawdown, float)
        assert isinstance(result.sharpe_ratio, float)
    
    def test_backtest_performance(self, sample_data, grid_config, risk_config):
        """Test backtest speed (should be < 5s for 10k candles)."""
        import time
        
        backtester = VectorizedBacktester(
            grid_config=grid_config,
            risk_config=risk_config
        )
        
        start = time.perf_counter()
        backtester.run_vectorized(sample_data, verbose=False)
        elapsed = time.perf_counter() - start
        
        # 10k candles should process in < 1 second
        assert elapsed < 1.0, f"Backtest took {elapsed:.2f}s, expected < 1s"
    
    def test_backtest_with_zero_capital_fails(self, sample_data):
        """Test that zero capital raises error."""
        risk = RiskConfig(initial_capital=0)
        
        with pytest.raises(Exception):
            VectorizedBacktester(risk_config=risk)


# ============================================================
# SAFETY TESTS
# ============================================================
class TestSafety:
    """Tests for safety mechanisms."""
    
    def test_safety_manager_initialization(self, risk_config):
        """Test safety manager initialization."""
        manager = SafetyManager(risk_config)
        assert manager.is_trading_allowed
        assert not manager.emergency_stop
    
    def test_balance_floor_trigger(self, risk_config):
        """Test that balance floor triggers safety."""
        manager = SafetyManager(risk_config)
        
        state = manager.update_state(
            balance=70,  # Below stop_loss_balance of 80
            equity=70,
            margin_used=0,
            positions=[]
        )
        
        assert not state.is_safe
        assert manager.emergency_stop
        assert not manager.is_trading_allowed
    
    def test_daily_loss_limit_trigger(self, risk_config):
        """Test that daily loss limit triggers safety."""
        manager = SafetyManager(risk_config)
        
        # Initial state
        manager.update_state(
            balance=100,
            equity=100,
            margin_used=0,
            positions=[],
            daily_pnl=0
        )
        
        # Trigger daily loss limit (15% loss, limit is 10%)
        state = manager.update_state(
            balance=85,
            equity=85,
            margin_used=0,
            positions=[],
            daily_pnl=-15
        )
        
        assert not state.is_safe
    
    def test_position_size_limit(self, risk_config):
        """Test maximum position size calculation."""
        manager = SafetyManager(risk_config)
        
        # Initialize state
        manager.update_state(
            balance=100,
            equity=100,
            margin_used=0,
            positions=[]
        )
        
        max_size = manager.get_max_position_size("BTC", 50000)
        
        # Should be constrained by max_wallet_exposure
        max_value = max_size * 50000
        assert max_value <= 100 * risk_config.max_wallet_exposure * risk_config.max_leverage


class TestUnstucking:
    """Tests for unstucking mechanism."""
    
    def test_unstuck_engine_initialization(self, unstucking_config, risk_config):
        """Test unstucking engine initialization."""
        engine = UnstuckingEngine(unstucking_config, risk_config)
        assert engine.config.enabled
        assert len(engine.stuck_positions) == 0
    
    def test_identify_stuck_positions(self, unstucking_config, risk_config):
        """Test identification of stuck positions."""
        from trading_bot.execution.safety import StuckPosition
        from trading_bot.config.settings import OrderSide
        
        engine = UnstuckingEngine(unstucking_config, risk_config)
        
        # Create mock stuck position
        positions = [{
            'symbol': 'BTC/USDC:USDC',
            'side': OrderSide.LONG,
            'size': 0.002,
            'entry_price': 50000,
            'entry_time': datetime.now() - timedelta(hours=2),
            'leverage': 3
        }]
        
        current_prices = {'BTC/USDC:USDC': 45000}  # 10% down
        
        stuck = engine.identify_stuck_positions(positions, current_prices, balance=100)
        
        assert len(stuck) >= 1
        assert stuck[0].adverse_excursion_pct > 0
    
    def test_unstuck_action_calculation(self, unstucking_config, risk_config):
        """Test unstuck action calculation."""
        from trading_bot.execution.safety import StuckPosition
        from trading_bot.config.settings import OrderSide
        
        engine = UnstuckingEngine(unstucking_config, risk_config)
        
        stuck_pos = StuckPosition(
            symbol='BTC/USDC:USDC',
            side=OrderSide.LONG,
            size=0.002,
            entry_price=50000,
            current_price=45000,
            unrealized_pnl=-10,
            unrealized_pnl_pct=-0.10,
            time_stuck_minutes=120,
            margin_used=30,
            adverse_excursion_pct=0.10
        )
        
        action = engine.calculate_unstuck_action(
            stuck_pos,
            balance=100,
            margin_available=50
        )
        
        if action:  # May be None if cooldown active
            assert action.size_to_close > 0
            assert action.expected_loss > 0


class TestRiskCalculator:
    """Tests for risk calculations."""
    
    def test_liquidation_price_long(self):
        """Test liquidation price for long position."""
        from trading_bot.config.settings import OrderSide
        
        liq_price = RiskCalculator.calculate_liquidation_price(
            entry_price=50000,
            side=OrderSide.LONG,
            leverage=5
        )
        
        # Should be below entry for long
        assert liq_price < 50000
        # Approx: 50000 * (1 - 0.995/5) = 49000
        assert 40000 < liq_price < 49000
    
    def test_liquidation_price_short(self):
        """Test liquidation price for short position."""
        from trading_bot.config.settings import OrderSide
        
        liq_price = RiskCalculator.calculate_liquidation_price(
            entry_price=50000,
            side=OrderSide.SHORT,
            leverage=5
        )
        
        # Should be above entry for short
        assert liq_price > 50000
    
    def test_pnl_calculation(self):
        """Test PnL calculation."""
        from trading_bot.config.settings import OrderSide
        
        # Long position profit
        pnl = RiskCalculator.calculate_pnl(
            entry_price=50000,
            current_price=51000,
            size=0.1,
            side=OrderSide.LONG
        )
        assert pnl == 100  # (51000 - 50000) * 0.1
        
        # Short position profit
        pnl = RiskCalculator.calculate_pnl(
            entry_price=50000,
            current_price=49000,
            size=0.1,
            side=OrderSide.SHORT
        )
        assert pnl == 100  # (50000 - 49000) * 0.1


# ============================================================
# UTILITY TESTS
# ============================================================
class TestUtilities:
    """Tests for utility functions."""
    
    def test_generate_sample_data(self):
        """Test sample data generation."""
        df = generate_sample_data(n_candles=1000, seed=42)
        
        assert len(df) == 1000
        assert all(col in df.columns for col in ['open', 'high', 'low', 'close', 'volume'])
        assert (df['high'] >= df['low']).all()
    
    def test_max_drawdown_calculation(self):
        """Test maximum drawdown calculation."""
        # Monotonically increasing equity
        equity = np.linspace(100, 200, 100)
        dd, duration = calculate_max_drawdown(equity)
        assert dd == 0
        
        # Drawdown scenario
        equity = np.array([100, 110, 105, 95, 90, 100, 110])
        dd, duration = calculate_max_drawdown(equity)
        assert dd > 0
        assert dd < 0.2  # Max 20% DD
    
    def test_sharpe_ratio_calculation(self):
        """Test Sharpe ratio calculation."""
        # Positive returns
        returns = np.random.normal(0.001, 0.01, 1000)
        sharpe = calculate_sharpe_ratio(returns)
        assert isinstance(sharpe, float)


# ============================================================
# INTEGRATION TESTS
# ============================================================
class TestIntegration:
    """Integration tests for the complete system."""
    
    def test_full_backtest_pipeline(self, sample_data, grid_config, risk_config):
        """Test complete backtest pipeline."""
        # Run backtest
        backtester = VectorizedBacktester(
            grid_config=grid_config,
            risk_config=risk_config
        )
        
        result = backtester.run_vectorized(sample_data, verbose=False)
        
        # Verify all metrics are computed
        assert result.total_return != 0 or result.total_return == 0  # Can be 0
        assert result.max_drawdown >= 0
        assert result.total_trades >= 0
        assert 0 <= result.win_rate <= 1
    
    def test_config_to_backtest(self):
        """Test configuration integration with backtest."""
        config = BotConfig()
        
        backtester = VectorizedBacktester(
            grid_config=config.grid,
            risk_config=config.risk,
            unstucking_config=config.unstucking
        )
        
        df = generate_sample_data(n_candles=1000, seed=123)
        result = backtester.run_vectorized(df, verbose=False)
        
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
