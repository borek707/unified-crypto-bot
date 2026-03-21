#!/usr/bin/env python3
"""
Wrapper for PassivBot Pro - runs original Piotr's code
Usage: python3 -m passivbot_pro [command] [args]
"""
import sys
import os

# Add scripts to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run original main
from scripts.main import main

if __name__ == "__main__":
    main()
