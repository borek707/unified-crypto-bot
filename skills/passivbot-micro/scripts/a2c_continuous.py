"""
A2C CONTINUOUS ACTION SPACE
============================
Advantage Actor-Critic for bearish/sideways markets.
Lower drawdown than PPO, better for risk management.

Based on research: A2C has lowest drawdown (-10.2%) vs PPO (-15.0%)
"""

import numpy as np
from typing import List, Tuple, Dict
from dataclasses import dataclass

# Import PPO config (shared settings)
from ppo_continuous import PPOConfig


@dataclass
class A2CConfig:
    """Configuration for A2C"""
    learning_rate: float = 0.001
    gamma: float = 0.99
    value_coef: float = 0.5
    entropy_coef: float = 0.01
    
    num_epochs: int = 10
    batch_size: int = 64
    
    # Trading costs
    trading_fee_pct: float = 0.0009  # 0.09% (Hyperliquid taker)
    slippage_bps: float = 2.0
    overtrade_penalty: float = 0.0001
    action_threshold: float = 0.05


class ContinuousA2CModel:
    """
    A2C with continuous action space.
    Optimized for lower drawdown in bearish/sideways markets.
    """
    
    def __init__(self, config: A2CConfig = None):
        self.config = config or A2CConfig()
        
        # State space (same as PPO)
        self.state_dim = 8
        self.action_dim = 1
        
        # Actor weights (mean only, A2C doesn't use std like PPO)
        self.actor_weights = np.random.randn(self.state_dim, 1) * 0.01
        self.critic_weights = np.random.randn(self.state_dim, 1) * 0.01
        
        self.trade_count = 0
    
    def get_state(self, prices: List[float], position: Dict = None) -> np.ndarray:
        """Same state representation as PPO"""
        if len(prices) < 50:
            return np.zeros(self.state_dim)
        
        change_1h = (prices[-1] - prices[-2]) / prices[-2] if len(prices) >= 2 else 0
        change_4h = (prices[-1] - prices[-5]) / prices[-5] if len(prices) >= 5 else 0
        change_24h = (prices[-1] - prices[-25]) / prices[-25] if len(prices) >= 25 else 0
        change_48h = (prices[-1] - prices[-49]) / prices[-49] if len(prices) >= 49 else 0
        
        returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(-20, 0)]
        volatility = np.std(returns) if returns else 0
        
        has_position = 1.0 if position else 0.0
        position_pnl = 0.0
        if position:
            position_pnl = (prices[-1] - position['entry']) / position['entry']
        
        time_since_trade = min(self.trade_count / 100.0, 1.0)
        
        return np.array([
            change_1h, change_4h, change_24h, change_48h,
            volatility, has_position, position_pnl, time_since_trade
        ])
    
    def select_action(self, state: np.ndarray, deterministic: bool = False) -> Tuple[float, float]:
        """Select action using actor"""
        action_mean = np.dot(state, self.actor_weights)[0]
        
        if not deterministic:
            # Add small noise for exploration
            action = np.random.normal(action_mean, 0.1)
        else:
            action = action_mean
        
        action = np.clip(action, -1.0, 1.0)
        
        return action, 0.0  # No log_prob needed for A2C
    
    def get_value(self, state: np.ndarray) -> float:
        """Estimate state value"""
        return np.dot(state, self.critic_weights)[0]
    
    def calculate_reward(self, pnl: float, position_size: float, 
                        is_entry: bool = False, is_exit: bool = False) -> float:
        """Calculate reward with costs"""
        reward = pnl
        
        if is_entry:
            fee = self.config.trading_fee_pct * position_size
            reward -= fee
        if is_exit:
            fee = self.config.trading_fee_pct * position_size
            reward -= fee
            reward -= self.config.overtrade_penalty
            self.trade_count += 1
        
        return reward
    
    def train(self, prices: List[float], epochs: int = 10):
        """Train A2C on historical data"""
        print(f"Training A2C on {len(prices)} prices for {epochs} epochs...")
        print(f"  Trading fee: {self.config.trading_fee_pct*100:.3f}%")
        
        total_reward = 0
        position = None
        self.trade_count = 0
        
        for epoch in range(epochs):
            epoch_reward = 0
            epoch_trades = 0
            
            for i in range(50, len(prices) - 1):
                state = self.get_state(prices[:i+1], position)
                action, _ = self.select_action(state)
                
                # Execute action
                reward = 0
                is_entry = False
                is_exit = False
                
                if action > self.config.action_threshold and position is None:
                    position_size = abs(action) * 0.15
                    position = {'entry': prices[i], 'size': position_size}
                    is_entry = True
                    epoch_trades += 1
                    
                elif action < -self.config.action_threshold and position:
                    pnl = (prices[i] - position['entry']) / position['entry']
                    pnl *= position['size']
                    is_exit = True
                    epoch_trades += 1
                    
                    reward = self.calculate_reward(pnl, position['size'], is_entry=False, is_exit=True)
                    position = None
                
                elif position:
                    unrealized = (prices[i] - position['entry']) / position['entry']
                    reward = unrealized * position['size'] * 0.001
                
                # A2C update
                value = self.get_value(state)
                advantage = reward - value
                
                # Actor update (policy gradient)
                self.actor_weights[:, 0] += self.config.learning_rate * advantage * state
                
                # Critic update
                value_error = reward - value
                self.critic_weights[:, 0] += self.config.learning_rate * value_error * state
                
                epoch_reward += reward
            
            total_reward += epoch_reward
            if epoch % 2 == 0:
                print(f"  Epoch {epoch}: Reward={epoch_reward:.4f}, Trades={epoch_trades}")
        
        avg_reward = total_reward / epochs
        print(f"Training complete. Avg reward: {avg_reward:.4f}")
        return avg_reward
    
    def predict(self, prices: List[float], position: Dict = None) -> float:
        """Predict action"""
        state = self.get_state(prices, position)
        action, _ = self.select_action(state, deterministic=True)
        return action
    
    def interpret_action(self, action: float, has_position: bool) -> Tuple[str, float]:
        """Interpret continuous action"""
        if action > self.config.action_threshold:
            if has_position:
                return 'HOLD', 0.0
            else:
                return 'BUY', action
        elif action < -self.config.action_threshold:
            if has_position:
                return 'SELL', abs(action)
            else:
                return 'HOLD', 0.0
        else:
            return 'HOLD', 0.0
