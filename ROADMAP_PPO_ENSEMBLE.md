# PPO + Ensemble Strategy Roadmap

## Overview
Implementation of research-based RL trading system with PPO/A2C ensemble, continuous action space, and Hyperliquid integration.

## Phase 1: Core Architecture ✅ COMPLETED
- [x] Continuous PPO action space [-1, 1] (`ppo_continuous.py`)
- [x] Slippage integrated in reward function
- [x] Turbulence Kill Switch (liquidate all when triggered)
- [x] Overtrading penalty in training

## Phase 2: Hyperliquid Integration ✅ COMPLETED
- [x] Fee structure identified: Taker 0.045%, Maker 0.015%
- [x] Market orders (taker) selected for speed: 0.09% round-trip
- [x] Fee configuration updated in PPO config

## Phase 3: Ensemble Strategy (PPO + A2C) 🔄 IN PROGRESS
### 3.1 A2C Implementation
- [ ] Create `a2c_continuous.py` with same interface as PPO
- [ ] Short position support (negative h_t values)
- [ ] A2C reward function optimized for bearish markets

### 3.2 Rolling Window Methodology
- [ ] 1 year training window (In-sample)
- [ ] 3 months validation window (Sharpe comparison)
- [ ] 3 months out-of-sample trading
- [ ] Quarterly retraining and model selection

### 3.3 Model Selection
- [ ] Train PPO, A2C, DDPG concurrently
- [ ] Calculate Sharpe ratio for each on validation window
- [ ] Route trading to best performing model

## Phase 4: Micro-Portfolio Optimization 🔄 PENDING
### 4.1 Position Sizing
- [ ] Map continuous action [-1, 1] to discrete "10 USD chunks"
- [ ] Max 10 chunks (100 USD) total position
- [ ] Hard balance constraint (no negative balance)

### 4.2 Fee Optimization
- [ ] Target: Maker fees 0.015% via limit orders
- [ ] Fallback: Taker 0.045% when speed critical
- [ ] Dynamic fee estimation in reward function

## Phase 5: Testing & Validation
### 5.1 Parameter Optimization
- [x] 5000 test runs with different parameters
- [ ] Analysis of optimal learning rates, fees, thresholds
- [ ] Best parameters: LR=0.001, Fee=0.09%, Threshold=0.048

### 5.2 Walk-Forward Testing
- [ ] 3 years of BTC data (28k prices)
- [ ] Quarterly rolling windows
- [ ] Sharpe-based model selection validation

### 5.3 Live Testing
- [ ] Paper trading on Hyperliquid testnet
- [ ] 3-month validation period
- [ ] Comparison with current SIDEWAYS GRID strategy

## Phase 6: Production Deployment
### 6.1 Bot Migration
- [ ] Stop current SIDEWAYS GRID bots
- [ ] Deploy Ensemble Strategy bots (LOW/MEDIUM/HIGH risk)
- [ ] Monitor for 1 week

### 6.2 Monitoring
- [ ] Daily PnL tracking
- [ ] Model selection logging (which model active)
- [ ] Kill switch activation alerts
- [ ] Fee impact analysis

## Research References
- PPO/A2C comparison for trading (FinRL, 2024)
- Turbulence Index as kill switch (Mahalanobis distance)
- Rolling window walk-forward methodology
- Continuous action space for position sizing

## Current Status
- Bots running: 3 (SIDEWAYS GRID strategy)
- Active positions: 3 (all under water, waiting for TP)
- Test mode: Paper trading (testnet)
- Next step: Implement A2C + Ensemble Strategy

## Files Created
- `ppo_continuous.py` - Continuous action PPO
- `optimize_ultra.py` - Fast parameter optimization
- `test_ppo_comprehensive.py` - Walk-forward testing
- `test_ppo_research.py` - Research-based validation

## Next Actions
1. Implement A2C agent
2. Create ensemble router
3. Add short position support
4. Run full walk-forward test
5. Deploy to production
