"""
PPO CONTINUOUS ACTION SPACE ENGINE
====================================
Proximal Policy Optimization with continuous action space [-1, 1].
Based on research: continuous actions outperform discrete for trading.

Action space:
- [-1, -0.1]: SELL/EXIT (proportional to value)
- (-0.1, 0.1): HOLD (no action)
- [0.1, 1]: BUY/ENTER (proportional to position size)

Reward function includes:
- PnL from trades
- Slippage costs (estimated)
- Overtrading penalty
"""

import numpy as np
import json
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass

# Try to import slippage model
try:
    from risk_management import SlippageModel
    SLIPPAGE_AVAILABLE = True
except ImportError:
    SLIPPAGE_AVAILABLE = False
    SlippageModel = None


@dataclass
class PPOConfig:
    """Configuration for PPO training with continuous actions"""
    learning_rate: float = 0.0003
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_epsilon: float = 0.2
    value_coef: float = 0.5
    entropy_coef: float = 0.01
    max_grad_norm: float = 0.5
    
    # Network
    hidden_size: int = 64
    num_epochs: int = 10
    batch_size: int = 64
    
    # Trading costs (CRITICAL for realistic training)
    trading_fee_pct: float = 0.0006  # 0.06% (taker fee)
    slippage_bps: float = 5.0  # 5 basis points
    
    # Overtrading penalty
    overtrade_penalty: float = 0.001  # Penalty per trade
    
    # Action thresholds
    action_threshold: float = 0.1  # Min |action| to execute
    
    # Training
    total_timesteps: int = 100000
    steps_per_update: int = 2048


class ContinuousPPOModel:
    """
    PPO with continuous action space for trading.
    Action: scalar in [-1, 1] representing position change.
    """
    
    def __init__(self, config: PPOConfig = None):
        self.config = config or PPOConfig()
        
        # Extended state space
        self.state_dim = 8  # More features for better decisions
        
        # Single continuous action output
        self.action_dim = 1
        
        # Initialize weights (actor outputs mean, log_std)
        self.actor_mean_weights = np.random.randn(self.state_dim, 1) * 0.01
        self.actor_log_std = np.array([-1.0])  # Initial std
        self.critic_weights = np.random.randn(self.state_dim, 1) * 0.01
        
        # Slippage model for realistic training
        if SLIPPAGE_AVAILABLE and SlippageModel is not None:
            self.slippage_model = SlippageModel(
                base_slippage_bps=self.config.slippage_bps
            )
        else:
            self.slippage_model = None
        
        # Experience buffer
        self.buffer = []
        
        # Track trades for overtrading penalty
        self.trade_count = 0
    
    def get_state(self, prices: List[float], position: Dict = None) -> np.ndarray:
        """Enhanced state representation"""
        if len(prices) < 50:
            return np.zeros(self.state_dim)
        
        # Price changes at multiple timeframes
        change_1h = (prices[-1] - prices[-2]) / prices[-2] if len(prices) >= 2 else 0
        change_4h = (prices[-1] - prices[-5]) / prices[-5] if len(prices) >= 5 else 0
        change_24h = (prices[-1] - prices[-25]) / prices[-25] if len(prices) >= 25 else 0
        change_48h = (prices[-1] - prices[-49]) / prices[-49] if len(prices) >= 49 else 0
        
        # Volatility (rolling std)
        returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(-20, 0)]
        volatility = np.std(returns) if returns else 0
        
        # Position info
        has_position = 1.0 if position else 0.0
        position_pnl = 0.0
        if position:
            position_pnl = (prices[-1] - position['entry']) / position['entry']
        
        # Time since last trade (normalized)
        time_since_trade = min(self.trade_count / 100.0, 1.0)
        
        return np.array([
            change_1h, change_4h, change_24h, change_48h,
            volatility, has_position, position_pnl, time_since_trade
        ])
    
    def select_action(self, state: np.ndarray, deterministic: bool = False) -> Tuple[float, float]:
        """
        Select continuous action from policy.
        Returns: (action, log_prob)
        """
        # Get action mean from actor network
        action_mean = np.dot(state, self.actor_mean_weights)[0]
        
        # Add exploration noise during training
        if not deterministic:
            action_std = np.exp(self.actor_log_std[0])
            action = np.random.normal(action_mean, action_std)
        else:
            action = action_mean
        
        # Clip to valid range
        action = np.clip(action, -1.0, 1.0)
        
        # Calculate log probability
        action_std = np.exp(self.actor_log_std[0])
        log_prob = -0.5 * ((action - action_mean) / action_std) ** 2 - np.log(action_std * np.sqrt(2 * np.pi))
        
        return action, log_prob
    
    def get_value(self, state: np.ndarray) -> float:
        """Estimate state value"""
        return np.dot(state, self.critic_weights)[0]
    
    def calculate_reward(self, pnl: float, position_size: float, 
                        is_entry: bool = False, is_exit: bool = False) -> float:
        """
        Calculate reward with trading costs and overtrading penalty.
        
        Based on research: r_t = PnL - costs - penalty
        """
        reward = pnl
        
        # Subtract trading costs (CRITICAL for realistic training)
        # But don't make them too prohibitive - we want the model to learn
        if is_entry:
            fee = self.config.trading_fee_pct * position_size
            reward -= fee
        if is_exit:
            fee = self.config.trading_fee_pct * position_size
            reward -= fee
            # Overtrading penalty only on exit to avoid double counting
            reward -= self.config.overtrade_penalty
            self.trade_count += 1
        
        return reward
    
    def store_transition(self, state, action, reward, next_state, done, log_prob):
        """Store transition in buffer"""
        self.buffer.append({
            'state': state,
            'action': action,
            'reward': reward,
            'next_state': next_state,
            'done': done,
            'log_prob': log_prob
        })
    
    def train(self, prices: List[float], epochs: int = 10):
        """
        Train PPO with continuous actions on historical data.
        Includes realistic trading costs in reward function.
        """
        print(f"Training Continuous PPO on {len(prices)} prices for {epochs} epochs...")
        print(f"  Trading fee: {self.config.trading_fee_pct*100:.3f}%")
        print(f"  Slippage: {self.config.slippage_bps} bps")
        print(f"  Overtrade penalty: {self.config.overtrade_penalty}")
        
        total_reward = 0
        position = None
        position_size = 0.0
        self.trade_count = 0
        
        for epoch in range(epochs):
            epoch_reward = 0
            epoch_trades = 0
            self.buffer = []
            
            for i in range(50, len(prices) - 1):
                state = self.get_state(prices[:i+1], position)
                action, log_prob = self.select_action(state)
                
                # Execute action based on continuous value
                reward = 0
                is_entry = False
                is_exit = False
                
                if action > self.config.action_threshold and position is None:
                    # ENTER LONG (proportional to action strength)
                    position_size = abs(action) * 0.15  # Max 15% position
                    position = {'entry': prices[i], 'size': position_size}
                    is_entry = True
                    epoch_trades += 1
                    
                elif action < -self.config.action_threshold and position:
                    # EXIT (proportional to action strength)
                    pnl = (prices[i] - position['entry']) / position['entry']
                    pnl *= position['size']
                    is_exit = True
                    epoch_trades += 1
                    
                    # Calculate reward with costs
                    reward = self.calculate_reward(pnl, position['size'], is_entry=False, is_exit=True)
                    position = None
                    position_size = 0.0
                
                # Small penalty for holding (opportunity cost)
                elif position:
                    unrealized_pnl = (prices[i] - position['entry']) / position['entry']
                    reward = unrealized_pnl * position['size'] * 0.001  # Small carry reward
                
                next_state = self.get_state(prices[:i+2], position)
                done = (i == len(prices) - 2)
                
                self.store_transition(state, action, reward, next_state, done, log_prob)
                epoch_reward += reward
            
            # Update weights
            if len(self.buffer) > 0:
                self._update_weights()
            
            total_reward += epoch_reward
            if epoch % 2 == 0:
                print(f"  Epoch {epoch}: Reward={epoch_reward:.4f}, Trades={epoch_trades}")
        
        avg_reward = total_reward / epochs
        print(f"Training complete. Avg reward: {avg_reward:.4f}, Total trades: {self.trade_count}")
        return avg_reward
    
    def _update_weights(self):
        """Update actor and critic weights"""
        if len(self.buffer) < self.config.batch_size:
            return
        
        # Sample batch
        batch = np.random.choice(self.buffer, 
                                min(self.config.batch_size, len(self.buffer)), 
                                replace=False)
        
        for transition in batch:
            state = transition['state']
            action = transition['action']
            reward = transition['reward']
            
            # Critic update (value estimation)
            value = self.get_value(state)
            value_error = reward - value
            self.critic_weights[:, 0] += self.config.learning_rate * value_error * state
            
            # Actor update (policy gradient)
            advantage = reward - value
            
            # Update mean
            action_mean = np.dot(state, self.actor_mean_weights)[0]
            d_mean = (action - action_mean) / (np.exp(self.actor_log_std[0]) ** 2)
            self.actor_mean_weights[:, 0] += self.config.learning_rate * advantage * d_mean * state
            
            # Simplified std update
            self.actor_log_std += self.config.learning_rate * advantage * 0.01
    
    def predict(self, prices: List[float], position: Dict = None) -> float:
        """
        Predict action for current state.
        Returns continuous value in [-1, 1]:
        - Negative = sell/exit
        - Near zero = hold
        - Positive = buy
        """
        state = self.get_state(prices, position)
        action, _ = self.select_action(state, deterministic=True)
        return action
    
    def interpret_action(self, action: float, has_position: bool) -> Tuple[str, float]:
        """
        Interpret continuous action.
        Returns: (action_type, intensity)
        """
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
    
    def save(self, path: str):
        """Save model weights"""
        np.savez(path, 
                 actor_mean=self.actor_mean_weights,
                 actor_std=self.actor_log_std,
                 critic=self.critic_weights)
        print(f"Model saved to {path}")
    
    def load(self, path: str):
        """Load model weights"""
        try:
            data = np.load(path)
            self.actor_mean_weights = data['actor_mean']
            self.actor_log_std = data['actor_std']
            self.critic_weights = data['critic']
            print(f"Model loaded from {path}")
        except Exception as e:
            print(f"Could not load model: {e}")


def train_continuous_ppo(prices: List[float], save_path: str = None):
    """Train continuous PPO model"""
    config = PPOConfig(
        learning_rate=0.0003,
        num_epochs=20,
        trading_fee_pct=0.0006,
        slippage_bps=5.0,
        overtrade_penalty=0.001
    )
    
    model = ContinuousPPOModel(config)
    model.train(prices, epochs=config.num_epochs)
    
    if save_path:
        model.save(save_path)
    
    return model


if __name__ == "__main__":
    # Demo
    try:
        with open('/tmp/hyperliquid_daily_big.json', 'r') as f:
            prices = json.load(f)
        
        print(f"Loaded {len(prices)} prices")
        model = train_continuous_ppo(prices, save_path='/tmp/ppo_continuous.npz')
        
        # Test
        print("\nTesting continuous actions:")
        for i in [100, 500, 900]:
            action = model.predict(prices[:i])
            action_type, intensity = model.interpret_action(action, has_position=False)
            print(f"  Step {i}: action={action:+.3f} -> {action_type} (intensity={intensity:.2f})")
            
    except Exception as e:
        print(f"Error: {e}")
