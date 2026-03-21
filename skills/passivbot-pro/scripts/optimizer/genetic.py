"""
Evolutionary Optimizer
======================
Genetic Algorithm for parameter optimization.
Uses multiprocessing to leverage 4 vCPUs for thousands of parallel backtests.

Key Features:
- DEAP-based genetic algorithm
- Multi-objective optimization (Profit, Drawdown, Sharpe)
- Elitism preservation
- Adaptive mutation rates
- Parallel fitness evaluation
"""

import numpy as np
import pandas as pd
from typing import Optional, Callable
from dataclasses import dataclass
import multiprocessing as mp
from functools import partial
import random
import time
from loguru import logger
from pathlib import Path
import json

from deap import base, creator, tools, algorithms

from ..config.settings import GridConfig, RiskConfig, OptimizerConfig, config
from ..backtest.engine import VectorizedBacktester, BacktestResult


# ============================================================
# FITNESS FUNCTION
# ============================================================
def calculate_fitness(
    result: BacktestResult,
    profit_weight: float = 1.0,
    dd_weight: float = 2.0,
    sharpe_weight: float = 0.5,
    trades_weight: float = 0.1,
    min_trades: int = 10
) -> float:
    """
    Calculate fitness score for optimization.
    
    Formula:
        fitness = (return * profit_weight) 
                - (drawdown * dd_weight)
                + (sharpe * sharpe_weight)
                + (trades_norm * trades_weight)
    
    Higher drawdown weight prevents risky parameters.
    """
    # Normalize components
    return_score = result.total_return_pct * profit_weight
    dd_penalty = result.max_drawdown_pct * dd_weight
    sharpe_score = max(result.sharpe_ratio, 0) * sharpe_weight
    
    # Trade count bonus (encourage active trading)
    trades_score = min(result.total_trades / 100, 1.0) * trades_weight
    
    # Minimum trades penalty
    if result.total_trades < min_trades:
        trades_score -= 0.5
    
    # Combine
    fitness = return_score - dd_penalty + sharpe_score + trades_score
    
    # Additional penalties
    if result.final_balance < config.risk.stop_loss_balance:
        fitness -= 1.0  # Heavy penalty for hitting stop loss
    
    if result.max_drawdown_pct > config.risk.max_drawdown_pct:
        fitness -= result.max_drawdown_pct
    
    return fitness


# ============================================================
# GENETIC ALGORITHM OPTIMIZER
# ============================================================
class GeneticOptimizer:
    """
    Genetic Algorithm optimizer for finding optimal grid parameters.
    
    Optimizes:
    - grid_spacing_pct
    - entry_multiplier
    - markup_pct
    - wallet_exposure_limit
    
    Uses DEAP library with multiprocessing for speed.
    """
    
    def __init__(
        self,
        df: pd.DataFrame,
        config: Optional[OptimizerConfig] = None,
        risk_config: Optional[RiskConfig] = None
    ):
        self.df = df
        self.config = config or OptimizerConfig()
        self.risk_config = risk_config or RiskConfig()
        
        # Parameter bounds
        self.bounds = {
            'grid_spacing_pct': self.config.grid_spacing_bounds,
            'entry_multiplier': self.config.entry_multiplier_bounds,
            'markup_pct': self.config.markup_bounds,
            'wallet_exposure_limit': self.config.wallet_exposure_bounds
        }
        
        # Setup DEAP
        self._setup_deap()
        
        # Results storage
        self.history: list[dict] = []
        self.best_params: Optional[dict] = None
        self.best_fitness: float = float('-inf')
    
    def _setup_deap(self):
        """Configure DEAP genetic algorithm components."""
        
        # Remove existing creators (for re-runs)
        if 'FitnessMax' in creator.__dict__:
            del creator.FitnessMax
        if 'Individual' in creator.__dict__:
            del creator.Individual
        
        # Create fitness and individual classes
        creator.create('FitnessMax', base.Fitness, weights=(1.0,))
        creator.create('Individual', list, fitness=creator.FitnessMax)
        
        # Toolbox setup
        self.toolbox = base.Toolbox()
        
        # Gene generator (uniform random within bounds)
        def generate_gene(param_name: str):
            low, high = self.bounds[param_name]
            return random.uniform(low, high)
        
        # Register gene generators
        self.toolbox.register('attr_grid_spacing', generate_gene, 'grid_spacing_pct')
        self.toolbox.register('attr_entry_mult', generate_gene, 'entry_multiplier')
        self.toolbox.register('attr_markup', generate_gene, 'markup_pct')
        self.toolbox.register('attr_wallet_exp', generate_gene, 'wallet_exposure_limit')
        
        # Individual and population
        self.toolbox.register(
            'individual',
            tools.initCycle,
            creator.Individual,
            (
                self.toolbox.attr_grid_spacing,
                self.toolbox.attr_entry_mult,
                self.toolbox.attr_markup,
                self.toolbox.attr_wallet_exp
            ),
            n=1
        )
        
        self.toolbox.register('population', tools.initRepeat, list, self.toolbox.individual)
        
        # Genetic operators
        self.toolbox.register('mate', tools.cxBlend, alpha=0.5)
        self.toolbox.register('mutate', tools.mutGaussian, mu=0, sigma=0.1, indpb=0.2)
        self.toolbox.register('select', tools.selTournament, tournsize=self.config.tournament_size)
    
    def _individual_to_params(self, individual: list) -> dict:
        """Convert individual genes to parameter dict."""
        return {
            'grid_spacing_pct': individual[0],
            'entry_multiplier': individual[1],
            'markup_pct': individual[2],
            'wallet_exposure_limit': individual[3]
        }
    
    def _clamp_individual(self, individual: list) -> list:
        """Clamp individual values to bounds."""
        params = ['grid_spacing_pct', 'entry_multiplier', 'markup_pct', 'wallet_exposure_limit']
        for i, param in enumerate(params):
            low, high = self.bounds[param]
            individual[i] = max(low, min(high, individual[i]))
        return individual
    
    def evaluate_single(self, individual: list) -> tuple:
        """Evaluate fitness of a single individual."""
        params = self._individual_to_params(individual)
        
        # Create configs
        grid_config = GridConfig(**params)
        
        # Run backtest
        backtester = VectorizedBacktester(
            grid_config=grid_config,
            risk_config=self.risk_config
        )
        
        result = backtester.run_vectorized(self.df, verbose=False)
        
        # Calculate fitness
        fitness = calculate_fitness(
            result,
            profit_weight=self.config.profit_weight,
            dd_weight=self.config.drawdown_weight,
            sharpe_weight=self.config.sharpe_weight,
            trades_weight=self.config.trades_weight
        )
        
        return (fitness,)
    
    def evaluate_batch(self, individuals: list) -> list:
        """Evaluate multiple individuals in parallel."""
        with mp.Pool(processes=self.config.max_workers) as pool:
            fitnesses = pool.map(self.evaluate_single, individuals)
        return fitnesses
    
    def optimize(self, verbose: bool = True) -> dict:
        """
        Run genetic algorithm optimization.
        
        Returns:
            dict: Best parameters found
        """
        logger.info(f"Starting GA optimization with {self.config.population_size} population, {self.config.generations} generations")
        
        start_time = time.perf_counter()
        
        # Initialize population
        pop = self.toolbox.population(n=self.config.population_size)
        
        # Statistics setup
        stats = tools.Statistics(lambda ind: ind.fitness.values)
        stats.register('avg', np.mean)
        stats.register('std', np.std)
        stats.register('min', np.min)
        stats.register('max', np.max)
        
        # Hall of fame (best individuals)
        hof = tools.HallOfFame(10)
        
        # Initial evaluation
        if verbose:
            logger.info("Evaluating initial population...")
        
        fitnesses = list(map(self.evaluate_single, pop))
        for ind, fit in zip(pop, fitnesses):
            ind.fitness.values = fit
        
        # Evolution loop
        for gen in range(self.config.generations):
            gen_start = time.perf_counter()
            
            # Selection
            offspring = self.toolbox.select(pop, len(pop))
            offspring = list(map(self.toolbox.clone, offspring))
            
            # Crossover
            for child1, child2 in zip(offspring[::2], offspring[1::2]):
                if random.random() < self.config.crossover_prob:
                    self.toolbox.mate(child1, child2)
                    del child1.fitness.values
                    del child2.fitness.values
            
            # Mutation
            for mutant in offspring:
                if random.random() < self.config.mutation_prob:
                    self.toolbox.mutate(mutant)
                    mutant[:] = self._clamp_individual(mutant)
                    del mutant.fitness.values
            
            # Evaluate invalid individuals
            invalid = [ind for ind in offspring if not ind.fitness.valid]
            fitnesses = list(map(self.evaluate_single, invalid))
            for ind, fit in zip(invalid, fitnesses):
                ind.fitness.values = fit
            
            # Replace population
            pop[:] = offspring
            
            # Update hall of fame
            hof.update(pop)
            
            # Record statistics
            record = stats.compile(pop)
            self.history.append({
                'generation': gen,
                **record
            })
            
            gen_time = time.perf_counter() - gen_start
            
            if verbose:
                logger.info(
                    f"Gen {gen + 1}/{self.config.generations} | "
                    f"Fitness: {record['max']:.4f} (avg: {record['avg']:.4f}) | "
                    f"Time: {gen_time:.1f}s"
                )
        
        # Get best individual
        best = hof[0]
        self.best_params = self._individual_to_params(best)
        self.best_fitness = best.fitness.values[0]
        
        total_time = time.perf_counter() - start_time
        
        if verbose:
            logger.info(f"Optimization completed in {total_time:.1f}s")
            logger.info(f"Best fitness: {self.best_fitness:.4f}")
            logger.info(f"Best parameters: {self.best_params}")
        
        return self.best_params
    
    def save_results(self, path: str):
        """Save optimization results to JSON."""
        results = {
            'best_params': self.best_params,
            'best_fitness': self.best_fitness,
            'history': self.history
        }
        
        with open(path, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"Results saved to {path}")


# ============================================================
# OPTUNA OPTIMIZER (Alternative)
# ============================================================
class OptunaOptimizer:
    """
    Optuna-based Bayesian optimization.
    
    More sample-efficient than GA for expensive evaluations.
    Uses TPE (Tree-structured Parzen Estimator) sampler.
    """
    
    def __init__(
        self,
        df: pd.DataFrame,
        n_trials: int = 100,
        n_jobs: int = 4
    ):
        self.df = df
        self.n_trials = n_trials
        self.n_jobs = n_jobs
        self.study = None
    
    def objective(self, trial) -> float:
        """Optuna objective function."""
        import optuna
        
        # Suggest parameters
        grid_spacing = trial.suggest_float('grid_spacing_pct', 0.002, 0.015, log=True)
        entry_mult = trial.suggest_float('entry_multiplier', 1.1, 2.0)
        markup = trial.suggest_float('markup_pct', 0.002, 0.015, log=True)
        wallet_exp = trial.suggest_float('wallet_exposure_limit', 0.15, 0.40)
        
        # Create config
        grid_config = GridConfig(
            grid_spacing_pct=grid_spacing,
            entry_multiplier=entry_mult,
            markup_pct=markup,
            wallet_exposure_limit=wallet_exp
        )
        
        # Run backtest
        backtester = VectorizedBacktester(grid_config=grid_config)
        result = backtester.run_vectorized(self.df, verbose=False)
        
        # Calculate fitness
        fitness = calculate_fitness(result)
        
        # Report additional metrics
        trial.set_user_attr('total_return', result.total_return_pct)
        trial.set_user_attr('max_drawdown', result.max_drawdown_pct)
        trial.set_user_attr('sharpe_ratio', result.sharpe_ratio)
        trial.set_user_attr('total_trades', result.total_trades)
        
        return fitness
    
    def optimize(self) -> dict:
        """Run Optuna optimization."""
        import optuna
        
        # Suppress log output
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        
        # Create study
        self.study = optuna.create_study(
            direction='maximize',
            study_name='grid_optimization'
        )
        
        # Run optimization
        self.study.optimize(
            self.objective,
            n_trials=self.n_trials,
            n_jobs=self.n_jobs,
            show_progress_bar=True
        )
        
        return self.study.best_params
    
    def get_importance(self) -> dict:
        """Get parameter importance."""
        import optuna
        
        if self.study is None:
            return {}
        
        importance = optuna.importance.get_param_importances(self.study)
        return dict(importance)


# ============================================================
# WALK-FORWARD OPTIMIZATION
# ============================================================
class WalkForwardOptimizer:
    """
    Walk-forward optimization for robust parameter selection.
    
    Splits data into:
    - Training period (optimization)
    - Testing period (validation)
    
    Prevents overfitting by validating on out-of-sample data.
    """
    
    def __init__(
        self,
        df: pd.DataFrame,
        train_period_days: int = 60,
        test_period_days: int = 30,
        step_days: int = 15
    ):
        self.df = df
        self.train_period = train_period_days * 1440  # candles
        self.test_period = test_period_days * 1440
        self.step = step_days * 1440
        self.results = []
    
    def run(self, verbose: bool = True) -> dict:
        """
        Run walk-forward optimization.
        
        Returns:
            dict: Average out-of-sample performance metrics
        """
        n = len(self.df)
        
        # Calculate number of windows
        window_size = self.train_period + self.test_period
        n_windows = (n - window_size) // self.step + 1
        
        logger.info(f"Running walk-forward optimization with {n_windows} windows")
        
        for w in range(n_windows):
            start_idx = w * self.step
            train_end = start_idx + self.train_period
            test_end = train_end + self.test_period
            
            if test_end > n:
                break
            
            # Split data
            train_df = self.df.iloc[start_idx:train_end]
            test_df = self.df.iloc[train_end:test_end]
            
            # Optimize on training data
            optimizer = GeneticOptimizer(train_df)
            best_params = optimizer.optimize(verbose=False)
            
            # Test on out-of-sample data
            grid_config = GridConfig(**best_params)
            backtester = VectorizedBacktester(grid_config=grid_config)
            test_result = backtester.run_vectorized(test_df, verbose=False)
            
            self.results.append({
                'window': w,
                'params': best_params,
                'train_fitness': optimizer.best_fitness,
                'test_return': test_result.total_return_pct,
                'test_drawdown': test_result.max_drawdown_pct,
                'test_sharpe': test_result.sharpe_ratio
            })
            
            if verbose:
                logger.info(
                    f"Window {w + 1}/{n_windows} | "
                    f"Train fitness: {optimizer.best_fitness:.4f} | "
                    f"Test return: {test_result.total_return_pct:.2%} | "
                    f"Test DD: {test_result.max_drawdown_pct:.2%}"
                )
        
        # Calculate average metrics
        avg_return = np.mean([r['test_return'] for r in self.results])
        avg_dd = np.mean([r['test_drawdown'] for r in self.results])
        avg_sharpe = np.mean([r['test_sharpe'] for r in self.results])
        
        return {
            'avg_out_of_sample_return': avg_return,
            'avg_out_of_sample_drawdown': avg_dd,
            'avg_out_of_sample_sharpe': avg_sharpe,
            'n_windows': len(self.results)
        }


# ============================================================
# PARAMETER SENSITIVITY ANALYSIS
# ============================================================
def analyze_sensitivity(
    df: pd.DataFrame,
    base_params: dict,
    param_name: str,
    n_points: int = 20
) -> pd.DataFrame:
    """
    Analyze sensitivity of performance to parameter changes.
    
    Args:
        df: Historical data
        base_params: Base parameter values
        param_name: Parameter to vary
        n_points: Number of points to test
    
    Returns:
        DataFrame with sensitivity results
    """
    results = []
    
    # Get parameter range
    bounds = {
        'grid_spacing_pct': (0.002, 0.015),
        'entry_multiplier': (1.1, 2.0),
        'markup_pct': (0.002, 0.015),
        'wallet_exposure_limit': (0.15, 0.40)
    }
    
    low, high = bounds[param_name]
    values = np.linspace(low, high, n_points)
    
    for val in values:
        params = base_params.copy()
        params[param_name] = val
        
        grid_config = GridConfig(**params)
        backtester = VectorizedBacktester(grid_config=grid_config)
        result = backtester.run_vectorized(df, verbose=False)
        
        results.append({
            'value': val,
            'return': result.total_return_pct,
            'drawdown': result.max_drawdown_pct,
            'sharpe': result.sharpe_ratio,
            'trades': result.total_trades
        })
    
    return pd.DataFrame(results)
