#!/usr/bin/env python3
"""
Account Snapshot Utility
This module provides functionality to take a snapshot of account balances
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


class AccountSnapshot:
    """
    Class for taking account snapshots and calculating portfolio values.
    """
    
    def __init__(self, exchange_name='binance', acc_info=None):
        """
        Initialize the AccountSnapshot with exchange client.
        
        Args:
            exchange_name (str): Name of the exchange ('binance', 'poloniex', etc.)
            acc_info (dict): Account information containing api_key, secret_key, passphrase
        """
        self.exchange_name = exchange_name
        self.acc_info = acc_info
        self.client = None
        
        if acc_info:
            try:
                self.client = get_client_exchange(
                    exchange_name=exchange_name,
                    acc_info=acc_info,
                    symbol='BTC',
                    quote='USDT'
                )
            except Exception as e:
                logger_error.error(f"Failed to initialize exchange client: {e}")
                raise
    
    def get_account_balances(self):
        """
        Get account balances from the exchange.
        
        Returns:
            list: List of asset balances
        """
        if not self.client:
            raise ValueError("Exchange client not initialized")
        
        try:
            # Get asset snapshot using the client's internal user_asset method
            asset_snapshot = self.client.client.user_asset()
            logger_error.info(f"asset_snapshot: {asset_snapshot}")
            balances = asset_snapshot
            
            # Filter out assets with zero balance
            filtered_balances = []
            for asset in balances:
                total_balance = float(asset['free']) + float(asset['locked']) + float(asset.get('freeze', 0))
                if total_balance > 0:
                    filtered_balances.append({
                        'asset': asset['asset'],
                        'free': asset['free'],
                        'locked': asset['locked'],
                        'freeze': asset.get('freeze', '0'),
                        'total': str(total_balance)
                    })
            
            return filtered_balances
            
        except Exception as e:
            logger_error.error(f"Failed to get account balances: {e}")
            raise
    
    def get_asset_price(self, asset, quote='USDT'):
        """
        Get current price for an asset.
        
        Args:
            asset (str): Asset symbol (e.g., 'BTC', 'ETH')
            quote (str): Quote currency (default: 'USDT')
            
        Returns:
            float: Current price of the asset
        """
        if not self.client:
            raise ValueError("Exchange client not initialized")
        
        try:
            # For USDT and other stablecoins, return 1.0
            if asset.upper() in ['USDT', 'USDC', 'BUSD', 'DAI']:
                return 1.0
            
            # Get ticker information for the asset
            ticker_data = self.client.get_ticker(base=asset, quote=quote)
            price = float(ticker_data.get('lastPrice', ticker_data.get('last', 0)))
            
            return price
            
        except Exception as e:
            logger_error.error(f"Failed to get price for {asset}: {e}")
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
                
                logger_error.info(f"{asset}: {amount} @ ${price} = ${value:.2f}")
                
            except Exception as e:
                logger_error.error(f"Failed to calculate value for {asset}: {e}")
                portfolio[asset] = {
                    'amount': amount,
                    'price': '0',
                    'value': '0'
                }
        
        portfolio['Total'] = round(total_value, 2)
        return portfolio
    
    def take_snapshot(self, quote='USDT'):
        """
        Take a complete account snapshot with current values.
        
        Args:
            quote (str): Quote currency for valuation (default: 'USDT')
            
        Returns:
            dict: Complete portfolio snapshot
        """
        try:
            logger_error.info("Taking account snapshot...")
            
            # Get account balances
            balances = self.get_account_balances()
            logger_error.info(f"Found {len(balances)} assets with non-zero balance")
            
            # Calculate portfolio value
            portfolio = self.calculate_portfolio_value(balances, quote)
            
            logger_error.info(f"Total portfolio value: ${portfolio['Total']}")
            
            return portfolio
            
        except Exception as e:
            logger_error.error(f"Failed to take account snapshot: {e}")
            raise


def create_account_snapshot(exchange_name='binance', acc_info=None, quote='USDT'):
    """
    Convenience function to create an account snapshot.
    
    Args:
        exchange_name (str): Name of the exchange
        acc_info (dict): Account information
        quote (str): Quote currency for valuation
        
    Returns:
        dict: Portfolio snapshot
    """
    snapshot = AccountSnapshot(exchange_name, acc_info)
    return snapshot.take_snapshot(quote)


# Example usage and testing
if __name__ == "__main__":
    # Example account info structure
    example_acc_info = {
        'api_key': '',
        'secret_key': '',
        'passphrase': ''  # Optional for some exchanges
    }
    
    # Get actual portfolio snapshot with real credentials
    try:
        print("🔄 Fetching account snapshot...")
        portfolio = create_account_snapshot('binance', example_acc_info, 'USDT')
        print("\n📊 Portfolio Snapshot (All balances converted to USDT):")
        print(json.dumps(portfolio, indent=2))
    except Exception as e:
        print(f"❌ Error fetching portfolio: {e}")
        print("\n📝 Make sure your API credentials are correct and have the required permissions")