#!/usr/bin/env python3
"""
Multi-source crypto price fetcher with fallback.
Uses Coinpaprika, Coinlore, and CryptoCompare as backups.
"""

import requests
import json
import time
from typing import Optional, Dict

class CryptoPriceFetcher:
    def __init__(self):
        self.sources = {
            'coinpaprika': {
                'url': 'https://api.coinpaprika.com/v1/tickers/btc-bitcoin',
                'timeout': 10,
                'cache_time': 30
            },
            'coinlore': {
                'url': 'https://api.coinlore.net/api/ticker/?id=90',
                'timeout': 10,
                'cache_time': 60
            },
            'cryptocompare': {
                'url': 'https://min-api.cryptocompare.com/data/price?fsym=BTC&tsyms=USD',
                'timeout': 10,
                'cache_time': 10
            }
        }
        self.cache = {}
        
    def fetch_price(self, source: str) -> Optional[Dict]:
        """Fetch price from specific source."""
        if source not in self.sources:
            return None
            
        config = self.sources[source]
        
        # Check cache
        if source in self.cache:
            cached_time, cached_data = self.cache[source]
            if time.time() - cached_time < config['cache_time']:
                return cached_data
        
        try:
            response = requests.get(
                config['url'],
                timeout=config['timeout'],
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            response.raise_for_status()
            data = response.json()
            
            # Parse based on source
            if source == 'coinpaprika':
                result = {
                    'price': data['quotes']['USD']['price'],
                    'ath': data['quotes']['USD']['ath_price'],
                    'ath_date': data['quotes']['USD']['ath_date'],
                    'change_24h': data['quotes']['USD']['percent_change_24h'],
                    'source': source
                }
            elif source == 'coinlore':
                btc_data = data[0] if isinstance(data, list) else data
                result = {
                    'price': float(btc_data['price_usd']),
                    'change_24h': float(btc_data['percent_change_24h']),
                    'source': source
                }
            elif source == 'cryptocompare':
                result = {
                    'price': data['USD'],
                    'source': source
                }
            else:
                return None
            
            # Cache result
            self.cache[source] = (time.time(), result)
            return result
            
        except Exception as e:
            print(f"Error fetching from {source}: {e}")
            return None
    
    def get_price_with_fallback(self) -> Optional[Dict]:
        """Try sources in order until one works."""
        for source in ['coinpaprika', 'coinlore', 'cryptocompare']:
            result = self.fetch_price(source)
            if result:
                return result
            time.sleep(0.5)  # Brief delay between attempts
        return None

if __name__ == '__main__':
    fetcher = CryptoPriceFetcher()
    
    # Test all sources
    print("Testing crypto price fetcher...\n")
    
    for source in ['coinpaprika', 'coinlore', 'cryptocompare']:
        print(f"Testing {source}...")
        result = fetcher.fetch_price(source)
        if result:
            print(f"  ✓ Price: ${result['price']:,.2f}")
            if 'ath' in result:
                print(f"  ✓ ATH: ${result['ath']:,.2f}")
            if 'change_24h' in result:
                print(f"  ✓ 24h change: {result['change_24h']:+.2f}%")
        else:
            print(f"  ✗ Failed")
        print()
    
    # Test fallback
    print("Testing fallback mechanism...")
    best_price = fetcher.get_price_with_fallback()
    if best_price:
        print(f"✓ Best price from {best_price['source']}: ${best_price['price']:,.2f}")
    else:
        print("✗ All sources failed")
