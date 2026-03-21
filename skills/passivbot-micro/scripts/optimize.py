#!/usr/bin/env python3
"""
Parameter Optimizer Script
==========================
Find optimal trading parameters using genetic algorithm.

Usage:
    python optimize.py --candles 50000 --generations 30
    python optimize.py --quick  # Fast optimization with defaults
"""

import argparse
import sys
import os
import random
import time
from multiprocessing import Pool, cpu_count

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

# Import from backtest (now micro_backtest)
from backtest import (
    MicroBacktester, MicroGridConfig, MicroRiskConfig,
    generate_sample_data
)


# ============================================================
# GENETIC ALGORITHM
# ============================================================
class GeneticOptimizer:
    """
    Genetic Algorithm optimizer for grid trading parameters.
    
    Optimizes:
    - grid_spacing_pct
    - entry_multiplier
    - markup_pct
    - wallet_exposure_limit
    """
    
    def __init__(
        self,
        df: pd.DataFrame,
        population_size: int = 50,
        generations: int = 30,
        n_workers: int = None
    ):
        self.df = df
        self.population_size = population_size
        self.generations = generations
        self.n_workers = n_workers or min(cpu_count(), 4)
        
        # Parameter bounds
        self.bounds = {
            'grid_spacing_pct': (0.002, 0.015),
            'entry_multiplier': (1.1, 2.0),
            'markup_pct': (0.002, 0.015),
            'wallet_exposure_limit': (0.15, 0.40)
        }
        
        self.history = []
        self.best_params = None
        self.best_fitness = float('-inf')
    
    def random_individual(self) -> dict:
        """Generate random parameter set."""
        return {
            'grid_spacing_pct': random.uniform(*self.bounds['grid_spacing_pct']),
            'entry_multiplier': random.uniform(*self.bounds['entry_multiplier']),
            'markup_pct': random.uniform(*self.bounds['markup_pct']),
            'wallet_exposure_limit': random.uniform(*self.bounds['wallet_exposure_limit'])
        }
    
    def evaluate(self, params: dict) -> float:
        """
        Evaluate fitness of parameter set.
        
        Fitness formula:
            fitness = return - (drawdown * 2) + (sharpe * 0.5)
        """
        grid_config = MicroGridConfig(
            grid_spacing_pct=params['grid_spacing_pct'],
            entry_multiplier=params['entry_multiplier'],
            markup_pct=params['markup_pct']
        )
        
        risk_config = MicroRiskConfig(
            max_wallet_exposure=params['wallet_exposure_limit']
        )
        
        backtester = MicroBacktester(
            grid_config=grid_config,
            risk_config=risk_config
        )
        
        result = backtester.run(self.df, verbose=False)
        
        # Calculate fitness (result is now a dict)
        fitness = (
            result['total_return_pct'] * 1.0
            - result['max_drawdown_pct'] * 2.0
            + max(result['sharpe_ratio'], 0) * 0.5
        )
        
        # Penalize low trade counts
        if result['total_trades'] < 10:
            fitness -= 0.5
        
        # Penalize hitting stop loss
        if result['final_balance'] < 80:
            fitness -= 1.0
        
        return fitness
    
    def crossover(self, parent1: dict, parent2: dict) -> dict:
        """Create child from two parents."""
        child = {}
        for key in parent1:
            if random.random() < 0.5:
                child[key] = parent1[key]
            else:
                child[key] = parent2[key]
        return child
    
    def mutate(self, individual: dict, mutation_rate: float = 0.2) -> dict:
        """Mutate individual's parameters."""
        mutated = individual.copy()
        
        for key in mutated:
            if random.random() < mutation_rate:
                low, high = self.bounds[key]
                # Gaussian mutation centered on current value
                sigma = (high - low) * 0.2
                new_val = mutated[key] + random.gauss(0, sigma)
                mutated[key] = max(low, min(high, new_val))
        
        return mutated
    
    def optimize(self, verbose: bool = True) -> dict:
        """Run genetic algorithm optimization."""
        if verbose:
            print(f"\nStarting optimization:")
            print(f"  Population: {self.population_size}")
            print(f"  Generations: {self.generations}")
            print(f"  Workers: {self.n_workers}")
        
        start_time = time.perf_counter()
        
        # Initialize population
        population = [self.random_individual() for _ in range(self.population_size)]
        
        for gen in range(self.generations):
            gen_start = time.perf_counter()
            
            # Evaluate fitness (parallel)
            with Pool(self.n_workers) as pool:
                fitnesses = pool.map(self.evaluate, population)
            
            # Sort by fitness
            sorted_pop = sorted(zip(fitnesses, population), key=lambda x: x[0], reverse=True)
            
            # Update best
            if sorted_pop[0][0] > self.best_fitness:
                self.best_fitness = sorted_pop[0][0]
                self.best_params = sorted_pop[0][1]
            
            # Record history
            self.history.append({
                'generation': gen,
                'best_fitness': sorted_pop[0][0],
                'avg_fitness': np.mean(fitnesses),
                'worst_fitness': sorted_pop[-1][0]
            })
            
            gen_time = time.perf_counter() - gen_start
            
            if verbose:
                print(f"  Gen {gen + 1}/{self.generations} | "
                      f"Best: {sorted_pop[0][0]:.4f} | "
                      f"Avg: {np.mean(fitnesses):.4f} | "
                      f"Time: {gen_time:.1f}s")
            
            # Selection - keep top 20%
            elites = [ind for _, ind in sorted_pop[:self.population_size // 5]]
            
            # Create new population
            new_population = elites.copy()
            
            while len(new_population) < self.population_size:
                # Tournament selection
                p1 = max(random.sample(sorted_pop[:self.population_size // 2], 3), 
                        key=lambda x: x[0])[1]
                p2 = max(random.sample(sorted_pop[:self.population_size // 2], 3), 
                        key=lambda x: x[0])[1]
                
                # Crossover
                child = self.crossover(p1, p2)
                
                # Mutation
                child = self.mutate(child)
                
                new_population.append(child)
            
            population = new_population
        
        total_time = time.perf_counter() - start_time
        
        if verbose:
            print(f"\nOptimization completed in {total_time:.1f}s")
            print(f"Best fitness: {self.best_fitness:.4f}")
        
        return self.best_params
    
    def get_best_result(self) -> dict:
        """Get backtest result for best parameters."""
        if self.best_params is None:
            return None
        
        grid_config = MicroGridConfig(
            grid_spacing_pct=self.best_params['grid_spacing_pct'],
            entry_multiplier=self.best_params['entry_multiplier'],
            markup_pct=self.best_params['markup_pct']
        )
        risk_config = MicroRiskConfig(
            max_wallet_exposure=self.best_params['wallet_exposure_limit']
        )
        backtester = MicroBacktester(grid_config=grid_config, risk_config=risk_config)
        return backtester.run(self.df, verbose=False)


# ============================================================
# CLI ENTRY POINT
# ============================================================
def main():
    parser = argparse.ArgumentParser(description='Optimize trading parameters')
    parser.add_argument('--candles', type=int, default=50000, help='Number of candles')
    parser.add_argument('--population', type=int, default=50, help='Population size')
    parser.add_argument('--generations', type=int, default=30, help='Number of generations')
    parser.add_argument('--workers', type=int, default=None, help='Number of workers')
    parser.add_argument('--quick', action='store_true', help='Quick optimization')
    parser.add_argument('--seed', type=int, default=42, help='Random seed')
    
    args = parser.parse_args()
    
    # Set random seed
    random.seed(args.seed)
    np.random.seed(args.seed)
    
    print("=" * 60)
    print("MICRO-PASSIVBOT OPTIMIZER")
    print("=" * 60)
    
    # Quick mode
    if args.quick:
        args.candles = 10000
        args.population = 20
        args.generations = 10
    
    # Generate data
    print(f"\nGenerating {args.candles:,} candles of sample data...")
    df = generate_sample_data(n_candles=args.candles, seed=args.seed)
    
    # Run optimization
    optimizer = GeneticOptimizer(
        df=df,
        population_size=args.population,
        generations=args.generations,
        n_workers=args.workers
    )
    
    best_params = optimizer.optimize(verbose=True)
    
    # Print results
    print("\n" + "=" * 60)
    print("OPTIMIZED PARAMETERS")
    print("=" * 60)
    for key, value in best_params.items():
        if 'pct' in key:
            print(f"  {key}: {value:.4f} ({value * 100:.2f}%)")
        else:
            print(f"  {key}: {value:.4f}")
    
    # Get result with best params
    result = optimizer.get_best_result()
    print("\n" + "-" * 60)
    print("RESULT WITH OPTIMIZED PARAMETERS")
    print("-" * 60)
    print(f"  Total Return: {result['total_return_pct']:.2%}")
    print(f"  Max Drawdown: {result['max_drawdown_pct']:.2%}")
    print(f"  Sharpe Ratio: {result['sharpe_ratio']:.2f}")
    print(f"  Total Trades: {result['total_trades']}")
    print("=" * 60)


if __name__ == '__main__':
    main()
