#!/usr/bin/env python3
"""
Setup Script
============
Install dependencies and verify setup.

Usage:
    python setup.py install
    python setup.py verify
"""

import subprocess
import sys
import os
from pathlib import Path


def install_dependencies():
    """Install required packages."""
    requirements_path = Path(__file__).parent.parent / "resources" / "requirements.txt"
    
    print("Installing dependencies...")
    print(f"Requirements file: {requirements_path}")
    
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", str(requirements_path)
        ])
        print("\n✅ Dependencies installed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Installation failed: {e}")
        return False
    
    return True


def verify_setup():
    """Verify that all components are working."""
    print("\nVerifying setup...\n")
    
    errors = []
    
    # Check Python version
    py_version = sys.version_info
    print(f"Python version: {py_version.major}.{py_version.minor}.{py_version.micro}")
    if py_version < (3, 10):
        errors.append("Python 3.10+ required")
    
    # Check imports
    modules = [
        ("numpy", "NumPy"),
        ("pandas", "Pandas"),
        ("numba", "Numba"),
        ("ccxt", "CCXT"),
        ("pydantic", "Pydantic"),
    ]
    
    for module, name in modules:
        try:
            __import__(module)
            print(f"  ✅ {name}")
        except ImportError:
            print(f"  ❌ {name} - not installed")
            errors.append(f"{name} not installed")
    
    # Test data generation
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from backtest import generate_sample_data
        df = generate_sample_data(n_candles=100, seed=42)
        assert len(df) == 100
        print(f"\n  ✅ Data generation works")
    except Exception as e:
        print(f"\n  ❌ Data generation failed: {e}")
        errors.append(f"Data generation error: {e}")
    
    # Test backtest
    try:
        from backtest import VectorizedBacktester, GridConfig
        config = GridConfig()
        backtester = VectorizedBacktester(grid_config=config)
        result = backtester.run(df, verbose=False)
        print(f"  ✅ Backtest works (return: {result.total_return_pct:.2%})")
    except Exception as e:
        print(f"  ❌ Backtest failed: {e}")
        errors.append(f"Backtest error: {e}")
    
    # Test risk calculator
    try:
        from risk_calc import RiskCalculator, OrderSide
        liq = RiskCalculator.calculate_liquidation_price(50000, OrderSide.LONG, 5)
        print(f"  ✅ Risk calculator works (liq price: ${liq:,.0f})")
    except Exception as e:
        print(f"  ❌ Risk calculator failed: {e}")
        errors.append(f"Risk calculator error: {e}")
    
    if errors:
        print(f"\n❌ Setup verification failed with {len(errors)} errors:")
        for error in errors:
            print(f"  - {error}")
        return False
    else:
        print("\n✅ All components verified successfully!")
        return True


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Setup Micro-PassivBot skill')
    parser.add_argument('command', choices=['install', 'verify', 'all'],
                       help='Command to run')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("MICRO-PASSIVBOT SETUP")
    print("=" * 60)
    
    if args.command == 'install':
        success = install_dependencies()
    elif args.command == 'verify':
        success = verify_setup()
    elif args.command == 'all':
        success = install_dependencies() and verify_setup()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
