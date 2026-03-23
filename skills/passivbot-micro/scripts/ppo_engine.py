"""
PPO TREND-FOLLOWING ENGINE
==========================
Proximal Policy Optimization for trend-following strategy.
Offline training to optimize entry/exit decisions.
"""

import numpy as np
import json
from typing import List, Tuple, Dict
from dataclasses import dataclass


@dataclass
class PPOConfig:
    """Configuration for PPO training"""
    learning_rate: float = 0.0003
    gamma: float = 0.99  # Discount factor
    gae_lambda: float = 0.95  # GAE parameter
    clip_epsilon: float = 0.2  # PPO clipping
    value_coef: float = 0.5
    entropy_coef: float = 0.01
    max_grad_norm: float = 0.5
    
    # Network architecture
    hidden_size: int = 64
    num_epochs: int = 10
    batch_size: int = 64
    
    # Training
    total_timesteps: int = 100000
    steps_per_update: int = 2048


class PPOModel:
    """
    Simple PPO implementation for trend-following.
    Uses actor-critic architecture.
    """
    
    def __init__(self, config: PPOConfig = None):
        self.config = config or PPOConfig()
        
        # State: [price_change_1h, price_change_4h, price_change_24h, 
        #         position_flag, entry_price_ratio]
        self.state_dim = 5
        
        # Actions: 0=hold, 1=enter_long, 2=exit
        self.action_dim = 3
        
        # Initialize network weights (simplified)
        self.actor_weights = np.random.randn(self.state_dim, self.action_dim) * 0.01
        self.critic_weights = np.random.randn(self.state_dim, 1) * 0.01
        
        # Experience buffer
        self.buffer = []
    
    def get_state(self, prices: List[float], position: Dict = None) -> np.ndarray:
        """Convert price history to state vector"""
        if len(prices) < 25:
            return np.zeros(self.state_dim)
        
        # Price changes
        change_1h = (prices[-1] - prices[-2]) / prices[-2] if len(prices) >= 2 else 0
        change_4h = (prices[-1] - prices[-5]) / prices[-5] if len(prices) >= 5 else 0
        change_24h = (prices[-1] - prices[-25]) / prices[-25] if len(prices) >= 25 else 0
        
        # Position info
        has_position = 1.0 if position else 0.0
        entry_ratio = 0.0
        if position:
            entry_ratio = (prices[-1] - position['entry_price']) / position['entry_price']
        
        return np.array([change_1h, change_4h, change_24h, has_position, entry_ratio])
    
    def select_action(self, state: np.ndarray) -> Tuple[int, float]:
        """Select action using current policy"""
        # Simple softmax policy
        logits = np.dot(state, self.actor_weights)
        exp_logits = np.exp(logits - np.max(logits))
        probs = exp_logits / exp_logits.sum()
        
        action = np.random.choice(self.action_dim, p=probs)
        return action, probs[action]
    
    def get_value(self, state: np.ndarray) -> float:
        """Estimate state value"""
        return np.dot(state, self.critic_weights)[0]
    
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
        Train PPO on historical price data.
        This is offline training - no real money at risk.
        """
        print(f"Training PPO on {len(prices)} prices for {epochs} epochs...")
        
        total_reward = 0
        position = None
        
        for epoch in range(epochs):
            epoch_reward = 0
            self.buffer = []
            
            for i in range(25, len(prices) - 1):
                state = self.get_state(prices[:i+1], position)
                action, log_prob = self.select_action(state)
                
                # Execute action
                reward = 0
                if action == 1 and position is None:  # Enter
                    position = {'entry_price': prices[i]}
                elif action == 2 and position:  # Exit
                    reward = (prices[i] - position['entry_price']) / position['entry_price']
                    position = None
                
                next_state = self.get_state(prices[:i+2], position)
                done = (i == len(prices) - 2)
                
                self.store_transition(state, action, reward, next_state, done, log_prob)
                epoch_reward += reward
            
            # Simple weight update (simplified PPO)
            if len(self.buffer) > 0:
                self._update_weights()
            
            total_reward += epoch_reward
            if epoch % 2 == 0:
                print(f"  Epoch {epoch}: Total Reward = {epoch_reward:.4f}")
        
        print(f"Training complete. Final avg reward: {total_reward/epochs:.4f}")
    
    def _update_weights(self):
        """Simple weight update (simplified gradient descent)"""
        if len(self.buffer) < self.config.batch_size:
            return
        
        # Sample batch
        batch = np.random.choice(self.buffer, 
                                min(self.config.batch_size, len(self.buffer)), 
                                replace=False)
        
        # Simple update (gradient approximation)
        for transition in batch:
            state = transition['state']
            action = transition['action']
            reward = transition['reward']
            
            # Update actor (simplified policy gradient)
            advantage = reward - self.get_value(state)
            self.actor_weights[:, action] += (self.config.learning_rate * 
                                              advantage * state)
            
            # Update critic
            value_error = reward - self.get_value(state)
            self.critic_weights[:, 0] += (self.config.learning_rate * 
                                          value_error * state)
    
    def predict(self, prices: List[float], position: Dict = None) -> int:
        """Predict best action for current state"""
        state = self.get_state(prices, position)
        action, _ = self.select_action(state)
        return action
    
    def save(self, path: str):
        """Save model weights"""
        np.savez(path, 
                 actor=self.actor_weights, 
                 critic=self.critic_weights)
        print(f"Model saved to {path}")
    
    def load(self, path: str):
        """Load model weights"""
        try:
            data = np.load(path)
            self.actor_weights = data['actor']
            self.critic_weights = data['critic']
            print(f"Model loaded from {path}")
        except:
            print(f"Could not load model from {path}, using fresh weights")


def train_trend_following_ppo(prices: List[float], save_path: str = None):
    """
    Train PPO model for trend-following on given price data.
    Returns trained model.
    """
    config = PPOConfig(
        learning_rate=0.0003,
        num_epochs=20,
        steps_per_update=1024
    )
    
    model = PPOModel(config)
    model.train(prices, epochs=config.num_epochs)
    
    if save_path:
        model.save(save_path)
    
    return model


if __name__ == "__main__":
    # Demo training
    import json
    
    # Load some price data
    try:
        with open('/tmp/hyperliquid_daily_big.json', 'r') as f:
            prices = json.load(f)
        
        print(f"Loaded {len(prices)} prices")
        print(f"Range: ${min(prices):.0f} - ${max(prices):.0f}")
        
        # Train model
        model = train_trend_following_ppo(prices, 
                                          save_path='/tmp/ppo_trend_model.npz')
        
        # Test predictions
        print("\nTesting predictions:")
        for i in [100, 500, 900]:
            action = model.predict(prices[:i])
            action_names = ['HOLD', 'ENTER_LONG', 'EXIT']
            print(f"  Step {i}: {action_names[action]}")
        
    except Exception as e:
        print(f"Error: {e}")
        print("Creating demo with synthetic data...")
        
        # Demo with synthetic data
        prices = [100 + i*0.1 + np.random.randn()*2 for i in range(1000)]
        model = train_trend_following_ppo(prices)
