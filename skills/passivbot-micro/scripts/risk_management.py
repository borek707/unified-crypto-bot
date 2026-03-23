"""
TURBULENCE INDEX + SLIPPAGE MODEL
=================================
Phase 4: Risk Management and Execution Quality
"""

import numpy as np
from typing import List, Dict, Tuple
from dataclasses import dataclass


@dataclass
class TurbulenceResult:
    """Result of turbulence calculation"""
    turbulence_index: float
    is_turbulent: bool
    volatility_regime: str  # 'low', 'normal', 'high', 'extreme'
    adjusted_size_factor: float  # 0.0-1.0, reduce position size in turbulence


class TurbulenceIndex:
    """
    Detects market stress periods based on volatility and correlation breakdown.
    Reduces position sizes during high turbulence.
    """
    
    def __init__(self, 
                 lookback: int = 30,
                 turbulence_threshold: float = 1.5,
                 extreme_threshold: float = 2.5):
        self.lookback = lookback
        self.turbulence_threshold = turbulence_threshold
        self.extreme_threshold = extreme_threshold
        
        # Historical statistics
        self.mean_returns = None
        self.cov_matrix = None
        self.history = []
    
    def calculate(self, prices: List[float]) -> TurbulenceResult:
        """
        Calculate turbulence index based on price deviations.
        Higher = more turbulent = reduce positions.
        """
        if len(prices) < self.lookback + 10:
            return TurbulenceResult(
                turbulence_index=0.0,
                is_turbulent=False,
                volatility_regime='normal',
                adjusted_size_factor=1.0
            )
        
        # Calculate returns
        returns = [(prices[i] - prices[i-1]) / prices[i-1] 
                   for i in range(1, len(prices))]
        
        # Use recent lookback period
        recent_returns = returns[-self.lookback:]
        
        # Calculate volatility (standard deviation of returns)
        volatility = np.std(recent_returns) * np.sqrt(365)  # Annualized
        
        # Calculate turbulence as deviation from historical norm
        if len(returns) > self.lookback * 2:
            historical_returns = returns[:-self.lookback]
            historical_vol = np.std(historical_returns) * np.sqrt(365)
            
            if historical_vol > 0:
                turbulence = volatility / historical_vol
            else:
                turbulence = 1.0
        else:
            # Not enough history - use absolute volatility
            turbulence = volatility * 10  # Scale for comparison
        
        # Determine regime
        if turbulence > self.extreme_threshold:
            regime = 'extreme'
            is_turbulent = True
            size_factor = 0.0  # No trading
        elif turbulence > self.turbulence_threshold:
            regime = 'high'
            is_turbulent = True
            size_factor = 0.5  # 50% size
        elif turbulence > 0.8:
            regime = 'normal'
            is_turbulent = False
            size_factor = 1.0
        else:
            regime = 'low'
            is_turbulent = False
            size_factor = 1.0
        
        return TurbulenceResult(
            turbulence_index=turbulence,
            is_turbulent=is_turbulent,
            volatility_regime=regime,
            adjusted_size_factor=size_factor
        )


class SlippageModel:
    """
    Models execution slippage based on market conditions.
    Estimates real fill prices vs expected prices.
    """
    
    def __init__(self,
                 base_slippage_bps: float = 5.0,  # 5 basis points base
                 volatility_multiplier: float = 2.0,
                 size_multiplier: float = 1.0):
        self.base_slippage = base_slippage_bps / 10000  # Convert to %
        self.volatility_multiplier = volatility_multiplier
        self.size_multiplier = size_multiplier
    
    def estimate_slippage(self, 
                         price: float,
                         position_size: float,
                         volatility: float,
                         is_entry: bool = True) -> float:
        """
        Estimate slippage percentage.
        
        Args:
            price: Expected execution price
            position_size: Size of position (as % of account)
            volatility: Current volatility (daily %)
            is_entry: True for entry, False for exit
            
        Returns:
            Slippage percentage (positive = worse price)
        """
        # Base slippage
        slippage = self.base_slippage
        
        # Volatility adjustment (higher vol = more slippage)
        vol_adjustment = volatility * self.volatility_multiplier * 0.01
        slippage += vol_adjustment
        
        # Size adjustment (larger positions = more market impact)
        if position_size > 0.1:  # >10% of account
            size_impact = (position_size - 0.1) * self.size_multiplier * 0.01
            slippage += size_impact
        
        # Entry vs exit (exits usually have more slippage in fast markets)
        if not is_entry:
            slippage *= 1.2
        
        return slippage
    
    def apply_slippage(self,
                      price: float,
                      position_size: float,
                      volatility: float,
                      is_entry: bool = True,
                      is_long: bool = True) -> float:
        """
        Apply estimated slippage to price.
        
        Returns:
            Adjusted price (worse than expected)
        """
        slippage = self.estimate_slippage(price, position_size, volatility, is_entry)
        
        if is_long:
            if is_entry:
                # Long entry: pay higher
                return price * (1 + slippage)
            else:
                # Long exit: receive lower
                return price * (1 - slippage)
        else:
            # Short positions
            if is_entry:
                # Short entry: receive lower
                return price * (1 - slippage)
            else:
                # Short exit: pay higher
                return price * (1 + slippage)


class WalkForwardRobustness:
    """
    Tests strategy robustness using walk-forward analysis.
    Ensures strategy works across different market regimes.
    """
    
    def __init__(self, 
                 train_size: int = 180,  # 6 months training
                 test_size: int = 60):    # 2 months testing
        self.train_size = train_size
        self.test_size = test_size
    
    def split_data(self, prices: List[float]) -> List[Tuple[List[float], List[float]]]:
        """
        Split data into train/test sets for walk-forward analysis.
        
        Returns:
            List of (train_data, test_data) tuples
        """
        splits = []
        total_size = len(prices)
        
        # Walk forward
        start = 0
        while start + self.train_size + self.test_size <= total_size:
            train = prices[start:start + self.train_size]
            test = prices[start + self.train_size:start + self.train_size + self.test_size]
            splits.append((train, test))
            start += self.test_size  # Move forward by test size
        
        return splits
    
    def calculate_robustness_score(self, 
                                   results: List[Dict]) -> float:
        """
        Calculate robustness score from walk-forward results.
        
        Args:
            results: List of result dicts with 'pnl' key
            
        Returns:
            Score 0.0-1.0 (higher = more robust)
        """
        if not results:
            return 0.0
        
        pnls = [r['pnl'] for r in results]
        
        # Calculate metrics
        profitable_ratio = len([p for p in pnls if p > 0]) / len(pnls)
        avg_pnl = np.mean(pnls)
        pnl_std = np.std(pnls)
        
        # Sharpe-like ratio
        sharpe = avg_pnl / pnl_std if pnl_std > 0 else 0
        
        # Robustness score
        score = (profitable_ratio * 0.4 + 
                min(avg_pnl / 10, 0.3) +  # Normalize PnL
                min(sharpe / 2, 0.3))     # Normalize Sharpe
        
        return min(score, 1.0)


def calculate_execution_quality(expected_price: float,
                               actual_price: float,
                               is_entry: bool,
                               is_long: bool) -> float:
    """
    Calculate execution quality score.
    
    Returns:
        Score 0.0-1.0 (1.0 = perfect execution)
    """
    if expected_price == 0:
        return 0.0
    
    slippage = abs(actual_price - expected_price) / expected_price
    
    if is_long:
        if is_entry:
            # Long entry: paid more = bad
            return max(0, 1 - slippage * 100)
        else:
            # Long exit: received less = bad
            return max(0, 1 - slippage * 100)
    else:
        # Short positions
        if is_entry:
            # Short entry: received less = bad
            return max(0, 1 - slippage * 100)
        else:
            # Short exit: paid more = bad
            return max(0, 1 - slippage * 100)


if __name__ == "__main__":
    # Demo
    import random
    
    # Generate sample prices
    prices = [100 + i*0.05 + random.gauss(0, 1) for i in range(365)]
    
    # Turbulence index
    turb = TurbulenceIndex()
    result = turb.calculate(prices)
    print(f"Turbulence Index: {result.turbulence_index:.2f}")
    print(f"Is Turbulent: {result.is_turbulent}")
    print(f"Regime: {result.volatility_regime}")
    print(f"Size Factor: {result.adjusted_size_factor:.0%}")
    
    # Slippage model
    slippage = SlippageModel()
    slip = slippage.estimate_slippage(100, 0.15, 2.5, True)
    print(f"\nEstimated Slippage: {slip*100:.3f}%")
    
    adjusted = slippage.apply_slippage(100, 0.15, 2.5, True, True)
    print(f"Adjusted Price: ${adjusted:.2f}")
