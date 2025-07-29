#!/usr/bin/env python3
"""
Poloniex Account Snapshot Utility
This module provides functionality to take a snapshot of Poloniex account balances
and calculate their current USD values.
"""

import sys
import os
import json
from decimal import Decimal, ROUND_DOWN

# Add the parent directory to the path to import our modules
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../"))
sys.path.insert(0, PROJECT_ROOT)

from exchange_api_spot.user import get_client_exchange
from logger import logger_error


class PoloniexAccountSnapshot:
    """
    Class for taking Poloniex account snapshots and calculating portfolio values.
    """
    
    def __init__(self, acc_info=None):
        """
        Initialize the PoloniexAccountSnapshot with exchange client.
        
        Args:
            acc_info (dict): Account information containing api_key, secret_key, passphrase
        """
        self.exchange_name = 'poloniex'
        self.acc_info = acc_info
        self.client = None
        
        if acc_info:
            try:
                self.client = get_client_exchange(
                    exchange_name='poloniex',
                    acc_info=acc_info,
                    symbol='BTC',
                    quote='USDT'
                )
            except Exception as e:
                logger_error.error(f"Failed to initialize Poloniex client: {e}")
                raise
    
    def get_account_balances(self):
        """
        Get account balances from Poloniex.
        
        Returns:
            list: List of asset balances
        """
        if not self.client:
            raise ValueError("Poloniex client not initialized")
        
        try:
            # Get account balance using the client's get_account_balance method
            balance_data = self.client.get_account_balance()
            logger_error.info(f"Poloniex balance_data: {balance_data}")
            
            if not balance_data or 'data' not in balance_data:
                logger_error.warning("No balance data received from Poloniex")
                return []
            
            balances = balance_data['data']
            
            # Filter out assets with zero balance and format the data
            filtered_balances = []
            for asset_symbol, balance_info in balances.items():
                total_balance = balance_info.get('total', 0)
                if total_balance > 0:
                    filtered_balances.append({
                        'asset': asset_symbol,
                        'available': str(balance_info.get('available', 0)),
                        'locked': str(balance_info.get('locked', 0)),
                        'total': str(total_balance)
                    })
            
            return filtered_balances
            
        except Exception as e:
            logger_error.error(f"Failed to get Poloniex account balances: {e}")
            raise
    
    def get_asset_price(self, asset, quote='USDT'):
        """
        Get current price for an asset from Poloniex.
        
        Args:
            asset (str): Asset symbol (e.g., 'BTC', 'ETH')
            quote (str): Quote currency (default: 'USDT')
            
        Returns:
            float: Current price of the asset
        """
        if not self.client:
            raise ValueError("Poloniex client not initialized")
        
        try:
            # For USDT and other stablecoins, return 1.0
            if asset.upper() in ['USDT', 'USDC', 'BUSD', 'DAI', 'TUSD']:
                return 1.0
            
            # Get ticker information for the asset
            ticker_data = self.client.get_ticker(base=asset, quote=quote)
            logger_error.info(f"Poloniex ticker for {asset}/{quote}: {ticker_data}")
            
            # Extract price from ticker data
            if ticker_data and 'data' in ticker_data:
                price = float(ticker_data['data'].get('price', ticker_data['data'].get('last', 0)))
            else:
                price = 0.0
            
            return price
            
        except Exception as e:
            logger_error.error(f"Failed to get Poloniex price for {asset}: {e}")
            # Return 0 if price cannot be fetched
            return 0.0
    
    def calculate_portfolio_value(self, balances, quote='USDT'):
        """
        Calculate the total portfolio value in the specified quote currency.
        
        Args:
            balances (list): List of asset balances
            quote (str): Quote currency for valuation (default: 'USDT')
            
        Returns:
            dict: Portfolio snapshot with individual asset values and total
        """
        portfolio = {}
        total_value = 0.0
        
        for balance in balances:
            asset = balance['asset']
            amount = float(balance['total'])
            
            if amount <= 0:
                continue
            
            try:
                # Get current price
                price = self.get_asset_price(asset, quote)
                value = amount * price
                
                portfolio[asset] = {
                    'amount': amount,
                    'price': str(price),
                    'value': str(round(value, 2))
                }
                
                total_value += value
                
                logger_error.info(f"Poloniex {asset}: {amount} @ ${price} = ${value:.2f}")
                
            except Exception as e:
                logger_error.error(f"Failed to calculate value for Poloniex {asset}: {e}")
                portfolio[asset] = {
                    'amount': amount,
                    'price': '0',
                    'value': '0'
                }
        
        portfolio['Total'] = round(total_value, 2)
        return portfolio
    
    def take_snapshot(self, quote='USDT'):
        """
        Take a complete Poloniex account snapshot with current values.
        
        Args:
            quote (str): Quote currency for valuation (default: 'USDT')
            
        Returns:
            dict: Complete portfolio snapshot
        """
        try:
            logger_error.info("Taking Poloniex account snapshot...")
            
            # Get account balances
            balances = self.get_account_balances()
            logger_error.info(f"Found {len(balances)} Poloniex assets with non-zero balance")
            
            # Calculate portfolio value
            portfolio = self.calculate_portfolio_value(balances, quote)
            
            logger_error.info(f"Total Poloniex portfolio value: ${portfolio['Total']}")
            
            return portfolio
            
        except Exception as e:
            logger_error.error(f"Failed to take Poloniex account snapshot: {e}")
            raise


def create_poloniex_account_snapshot(acc_info=None, quote='USDT'):
    """
    Convenience function to create a Poloniex account snapshot.
    
    Args:
        acc_info (dict): Account information
        quote (str): Quote currency for valuation
        
    Returns:
        dict: Portfolio snapshot
    """
    snapshot = PoloniexAccountSnapshot(acc_info)
    return snapshot.take_snapshot(quote)


# Example usage and testing
if __name__ == "__main__":
    example_acc_info = {
        'api_key': '',
        'secret_key': '',
        'passphrase': ''  # Required for Poloniex
    }
    
    # Check if API credentials are provided
    if not example_acc_info['api_key'] or not example_acc_info['secret_key']:
        print("\n📝 Example usage:")
        print("from init.poloniex import create_poloniex_account_snapshot")
        print("")
        print("# Create Poloniex account snapshot")
        print("portfolio = create_poloniex_account_snapshot(")
        print("    acc_info=account_info,")
        print("    quote='USDT'")
        print(")")
        print("")
        print("⚠️  Please provide Poloniex API credentials in the example_acc_info to get actual balances")
        print("Note: Poloniex requires api_key, secret_key, and passphrase")
        exit()
    
    # Get actual portfolio snapshot with real credentials
    try:
        portfolio = create_poloniex_account_snapshot(example_acc_info, 'USDT')
        print("\n📊 Poloniex Portfolio Snapshot (All balances converted to USDT):")
        print(json.dumps(portfolio, indent=2))
    except Exception as e:
        print(f"❌ Error fetching Poloniex portfolio: {e}")
        print("Note: Poloniex requires api_key, secret_key, and passphrase")