#!/usr/bin/env python3
"""
Poloniex Result Checker
This script is called when a trading session is stopped to check various results.
It can perform multiple types of checks: balance, portfolio, trades, etc.
"""

import os
import sys
import time
import json
from decimal import Decimal

# Add the parent directory to the path to import our modules
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../"))
sys.path.insert(0, PROJECT_ROOT)

from logger import logger_database, logger_error
from exchange_api_spot.user import get_client_exchange
from utils import (
    get_line_number,
    update_key_and_insert_error_log,
    generate_random_string,
    get_precision_from_real_number
)

class PoloniexBalanceChecker:
    def __init__(self, api_key="", secret_key="", passphrase="", session_id=""):
        """
        Initialize the Poloniex balance checker
        
        Args:
            api_key (str): Poloniex API key
            secret_key (str): Poloniex secret key
            passphrase (str): Poloniex passphrase
            session_id (str): Session ID for tracking
        """
        self.symbol = "BTC"
        self.quote = "USDT"
        self.session_id = session_id
        self.exchange = "poloniex"
        self.run_key = generate_random_string()
        
        # Initialize Poloniex client using the factory function
        try:
            account_info = {
                "api_key": api_key,
                "secret_key": secret_key,
                "passphrase": passphrase,
                "session_key": session_id  # Poloniex uses session_key
            }
            
            self.client = get_client_exchange(
                acc_info=account_info,
                symbol=self.symbol,
                quote=self.quote,
                use_proxy=False  # Disable proxy to avoid connection issues
            )
            print(f"✅ Poloniex client initialized successfully for session: {session_id}")
            logger_database.info(f"Poloniex balance checker initialized for session: {session_id}")
        except Exception as e:
            print(f"❌ Failed to initialize Poloniex client: {e}")
            logger_error.error(f"Failed to initialize Poloniex client for session {session_id}: {e}")
            raise

    def get_all_balances(self):
        """
        Get all account balances from Poloniex using user_asset() and ticker_price
        
        Returns:
            dict: Complete balance information for all assets with prices
        """
        try:
            print(f"📊 Fetching all account balances for session: {self.session_id}")
            logger_database.info(f"Fetching all account balances for session: {self.session_id}")
            
            # Get account balance using get_account_balance() method
            balance_data = self.client.get_account_balance()
            
            if not balance_data or 'data' not in balance_data:
                error_msg = "No balance data received from get_account_balance() API"
                print(f"❌ {error_msg}")
                logger_error.error(f"Balance fetch failed for session {self.session_id}: {error_msg}")
                
                return {
                    "success": False,
                    "exchange": self.exchange,
                    "session_id": self.session_id,
                    "timestamp": int(time.time()),
                    "error": error_msg,
                    "Total": 0.0
                }
            
            balances = balance_data['data']
            print(f"📊 Retrieved {len(balances)} assets from get_account_balance()")
            
            # Format balance data with prices
            formatted_balances = {}
            total_value_usd = 0.0
            
            for asset_symbol, asset_info in balances.items():
                amount = float(asset_info.get('total', 0))
                
                if amount > 0:
                    try:
                        # Get price for the asset
                        if asset_symbol == 'USDT':
                            # USDT price is always 1.0
                            price = 1.0
                        else:
                            # Try to get price using get_ticker method
                            try:
                                ticker_data = self.client.get_ticker(asset_symbol, "USDT")
                                price = float(ticker_data.get('last', 0)) if ticker_data else 0.0
                            except Exception as ticker_error:
                                print(f"⚠️ Could not get ticker for {asset_symbol}_USDT: {ticker_error}")
                                # Try get_price method if available
                                try:
                                    # Create a temporary client with the asset as base
                                    temp_client = get_client_exchange(
                                        acc_info={
                                            "api_key": self.client.api_key,
                                            "secret_key": self.client.secret_key,
                                            "passphrase": self.client.passphrase,
                                            "session_key": self.session_id
                                        },
                                        symbol=asset_symbol,
                                        quote="USDT",
                                        use_proxy=False
                                    )
                                    price_data = temp_client.get_price()
                                    price = float(price_data.get('price', 0)) if price_data else 0.0
                                except Exception as price_error:
                                    print(f"⚠️ Could not get price for {asset_symbol}: {price_error}")
                                    price = 0.0
                        
                        # Add to formatted balances
                        formatted_balances[asset_symbol] = {
                            "amount": amount,
                            "price": str(price)
                        }
                        
                        # Calculate USD value
                        usd_value = amount * price
                        total_value_usd += usd_value
                        
                        print(f"💰 {asset_symbol}: Amount: {amount:.8f}, Price: ${price:.8f}, Value: ${usd_value:.2f}")
                        
                    except Exception as price_error:
                        print(f"⚠️ Error processing {asset_symbol}: {price_error}")
                        # Still add the asset with 0 price
                        formatted_balances[asset_symbol] = {
                            "amount": amount,
                            "price": "0"
                        }
            
            # Add total to the result
            formatted_balances["Total"] = total_value_usd
            
            result = {
                "success": True,
                "exchange": self.exchange,
                "session_id": self.session_id,
                "timestamp": int(time.time()),
                "balances": formatted_balances,
                "total_value_usd": total_value_usd,
                "message": "Account balance retrieved successfully"
            }
            
            print(f"✅ Successfully retrieved {len(formatted_balances)-1} assets with balance > 0")
            print(f"💰 Total portfolio value: ${total_value_usd:.2f} USD")
            logger_database.info(f"Successfully retrieved account balance for session: {self.session_id}")
            return result
                
        except Exception as e:
            error_msg = f"Error fetching account balance: {str(e)}"
            print(f"❌ {error_msg}")
            logger_error.error(f"Balance fetch exception for session {self.session_id}: {error_msg}")
            
            update_key_and_insert_error_log(
                self.run_key,
                self.symbol,
                get_line_number(),
                "POLONIEX",
                "poloniex.py",
                error_msg
            )
            
            return {
                "success": False,
                "exchange": self.exchange,
                "session_id": self.session_id,
                "timestamp": int(time.time()),
                "error": error_msg,
                "Total": 0.0
            }

    def get_specific_asset_balance(self, asset_symbol):
        """
        Get balance for a specific asset
        
        Args:
            asset_symbol (str): Asset symbol (e.g., 'BTC', 'USDT')
            
        Returns:
            dict: Balance information for the specific asset
        """
        try:
            print(f"📊 Fetching {asset_symbol} balance for session: {self.session_id}")
            logger_database.info(f"Fetching {asset_symbol} balance for session: {self.session_id}")
            
            balance_data = self.client.get_account_assets(asset_symbol)
            
            if balance_data and 'data' in balance_data and balance_data['data']:
                balance = balance_data['data']
                
                result = {
                    "success": True,
                    "exchange": self.exchange,
                    "session_id": self.session_id,
                    "timestamp": int(time.time()),
                    "asset": asset_symbol,
                    "available": balance['available'],
                    "locked": balance['locked'],
                    "total": balance['total'],
                    "message": f"{asset_symbol} balance retrieved successfully"
                }
                
                print(f"✅ {asset_symbol} balance: Available: {balance['available']:.8f}, Locked: {balance['locked']:.8f}, Total: {balance['total']:.8f}")
                logger_database.info(f"{asset_symbol} balance retrieved successfully for session: {self.session_id}")
                return result
                
            else:
                error_msg = f"No {asset_symbol} balance found"
                print(f"❌ {error_msg}")
                logger_error.warning(f"{asset_symbol} balance not found for session {self.session_id}")
                
                return {
                    "success": False,
                    "exchange": self.exchange,
                    "session_id": self.session_id,
                    "timestamp": int(time.time()),
                    "asset": asset_symbol,
                    "available": 0.0,
                    "locked": 0.0,
                    "total": 0.0,
                    "error": error_msg
                }
                
        except Exception as e:
            error_msg = f"Error fetching {asset_symbol} balance: {str(e)}"
            print(f"❌ {error_msg}")
            logger_error.error(f"{asset_symbol} balance fetch exception for session {self.session_id}: {error_msg}")
            
            update_key_and_insert_error_log(
                self.run_key,
                asset_symbol,
                get_line_number(),
                "POLONIEX",
                "poloniex.py",
                error_msg
            )
            
            return {
                "success": False,
                "exchange": self.exchange,
                "session_id": self.session_id,
                "timestamp": int(time.time()),
                "asset": asset_symbol,
                "available": 0.0,
                "locked": 0.0,
                "total": 0.0,
                "error": error_msg
            }

    def check_balance(self, asset_filter=None):
        """
        Main balance checking function
        
        Args:
            asset_filter (str, optional): Specific asset to check. If None, gets all balances.
            
        Returns:
            dict: Balance information
        """
        print("🚀 Starting Poloniex Balance Check...")
        print(f"📊 Session ID: {self.session_id}")
        print(f"🔍 Asset Filter: {asset_filter if asset_filter else 'All assets'}")
        print("-" * 50)
        
        try:
            if asset_filter:
                result = self.get_specific_asset_balance(asset_filter)
            else:
                result = self.get_all_balances()
            
            print("-" * 50)
            if result['success']:
                print("✅ Balance check completed successfully!")
            else:
                print("❌ Balance check failed!")
            
            print('result is: ',result)
            return result
            
        except Exception as e:
            error_msg = f"Balance check error: {str(e)}"
            print(f"❌ {error_msg}")
            logger_error.error(f"Balance check error for session {self.session_id}: {error_msg}")
            
            update_key_and_insert_error_log(
                self.run_key,
                self.symbol,
                get_line_number(),
                "POLONIEX",
                "poloniex.py",
                error_msg
            )
            
            return {
                "success": False,
                "exchange": self.exchange,
                "session_id": self.session_id,
                "timestamp": int(time.time()),
                "error": error_msg,
                "balances": [],
                "total_assets": 0,
                "total_value_usd": 0.0
            }

def main():
    """
    Main function to run the balance checker
    """
    print("🔍 Running Poloniex Balance Checker...")
    
    # Get API credentials from environment variables
    API_KEY = os.environ.get('STRATEGY_API_KEY', '')
    SECRET_KEY = os.environ.get('STRATEGY_API_SECRET', '')
    PASSPHRASE = os.environ.get('STRATEGY_PASSPHRASE', '')
    SESSION_ID = os.environ.get('STRATEGY_SESSION_KEY', '')
    ASSET_FILTER = os.environ.get('STRATEGY_ASSET_FILTER', '')

    if not API_KEY or not SECRET_KEY:
        error_result = {
            "success": False,
            "exchange": "poloniex",
            "session_id": SESSION_ID,
            "timestamp": int(time.time()),
            "error": "API credentials not provided",
            "balances": [],
            "total_assets": 0,
            "total_value_usd": 0.0
        }
       
        
        # Output JSON for Golang to parse
        print("\n" + "="*50)
        print("RESULT:")
        print(json.dumps(error_result, indent=2))
        return error_result
    
    try:
        # Initialize balance checker
        checker = PoloniexBalanceChecker(
            api_key=API_KEY,
            secret_key=SECRET_KEY,
            passphrase=PASSPHRASE,
            session_id=SESSION_ID
        )
        
        # Check balance
        result = checker.check_balance(asset_filter=ASSET_FILTER if ASSET_FILTER else None)
        
        # Output JSON for Golang to parse
        print("\n" + "="*50)
        print("RESULT:")
        print(json.dumps(result, indent=2))
        
        return result
        
    except Exception as e:
        error_result = {
            "success": False,
            "exchange": "poloniex",
            "session_id": SESSION_ID,
            "timestamp": int(time.time()),
            "error": f"Fatal error: {str(e)}",
            "balances": [],
            "total_assets": 0,
            "total_value_usd": 0.0
        }
        print(f"❌ Fatal error: {e}")
        
        # Output JSON for Golang to parse
        print("\n" + "="*50)
        print("RESULT:")
        print(json.dumps(error_result, indent=2))
        return error_result

if __name__ == "__main__":
    result = main()
    sys.exit(0 if result.get('success', False) else 1)