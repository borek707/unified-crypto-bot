"""
Micro-PassivBot Trading Skill
==============================
Autonomous crypto trading bot optimized for $100 accounts.

Usage:
    from skills.passivbot_micro.scripts.backtest import VectorizedBacktester, GridConfig
    from skills.passivbot_micro.scripts.risk_calc import RiskCalculator
"""

__version__ = "1.0.0"

# Lazy imports to avoid circular dependencies
def __getattr__(name):
    if name == 'VectorizedBacktester':
        from .scripts.backtest import VectorizedBacktester
        return VectorizedBacktester
    elif name == 'GridConfig':
        from .scripts.backtest import GridConfig
        return GridConfig
    elif name == 'RiskConfig':
        from .scripts.backtest import RiskConfig
        return RiskConfig
    elif name == 'RiskCalculator':
        from .scripts.risk_calc import RiskCalculator
        return RiskCalculator
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
