#!/usr/bin/env python3
"""
Rate-limited API wrapper dla finance-tracker.
Zarządza limitami:
- CoinGecko: 10-30 calls/min (2s delay)
- Yahoo Finance: 100/h (5s delay + cache)
- Gold bot: co 15 min w sesjach
"""

import json
import time
import os
import sys
from datetime import datetime
from pathlib import Path

# Rate limit tracker
RATE_LIMITS = {
    'coingecko': {'calls': 0, 'last_reset': time.time(), 'max_per_min': 25, 'delay': 2},
    'yahoo': {'calls': 0, 'last_reset': time.time(), 'max_per_hour': 80, 'delay': 5},
    'gold': {'calls': 0, 'last_reset': time.time(), 'max_per_min': 4, 'delay': 3}  # co 15 min
}

STATE_FILE = os.path.expanduser('~/.openclaw/workspace/.api_rate_state.json')
LOG_FILE = os.path.expanduser('~/.openclaw/workspace/memory/logs/api_calls.log')

def load_state():
    """Load rate limit state from file."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return RATE_LIMITS.copy()

def save_state(state):
    """Save rate limit state to file."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

def check_rate_limit(provider):
    """Check if we can make a call to the provider."""
    state = load_state()
    now = time.time()
    
    if provider not in state:
        state[provider] = RATE_LIMITS[provider].copy()
    
    limits = state[provider]
    
    # Reset counters based on provider time windows
    if provider == 'coingecko':
        if now - limits['last_reset'] > 60:  # 1 min
            limits['calls'] = 0
            limits['last_reset'] = now
    elif provider == 'yahoo':
        if now - limits['last_reset'] > 3600:  # 1 hour
            limits['calls'] = 0
            limits['last_reset'] = now
    elif provider == 'gold':
        if now - limits['last_reset'] > 900:  # 15 min (cron interval)
            limits['calls'] = 0
            limits['last_reset'] = now
    
    # Check limits
    if provider == 'coingecko' and limits['calls'] >= limits['max_per_min']:
        wait = 60 - (now - limits['last_reset']) + 1
        return False, f"Rate limit reached. Wait {int(wait)}s"
    elif provider == 'yahoo' and limits['calls'] >= limits['max_per_hour']:
        wait = 3600 - (now - limits['last_reset']) + 1
        return False, f"Rate limit reached. Wait {int(wait/60)}min"
    elif provider == 'gold' and limits['calls'] >= limits['max_per_min']:
        wait = 900 - (now - limits['last_reset']) + 1
        return False, f"Gold rate limit reached. Wait {int(wait)}s"
    
    limits['calls'] += 1
    save_state(state)
    return True, None

def log_call(provider, endpoint, status):
    """Log API call."""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    timestamp = datetime.now().isoformat()
    with open(LOG_FILE, 'a') as f:
        f.write(f"{timestamp} | {provider} | {endpoint} | {status}\n")

# Eksportuj funkcje
if __name__ == "__main__":
    print("Rate limit manager loaded")
    print(f"State file: {STATE_FILE}")
    print(f"Log file: {LOG_FILE}")
    print(f"Current limits: {json.dumps(load_state(), indent=2)}")
