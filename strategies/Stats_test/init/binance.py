#!/usr/bin/env python3
"""
Binance Result Checker
This script is called when a trading session is stopped to check various results.
It can perform multiple types of checks: balance, portfolio, trades, etc.
"""

import os
import sys
import time
import json
from decimal import Decimal

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../"))
sys.path.insert(0, PROJECT_ROOT)

from logger import logger_database, logger_error, logger_access
from exchange_api_spot.user import get_client_exchange
from utils import (
    get_line_number,
    update_key_and_insert_error_log,
    generate_random_string,
    get_precision_from_real_number
)

class BinanceBalanceChecker:
    def __init__(self, api_key="", secret_key="", passphrase="", session_id=""):
        """
        Initialize the Binance balance checker
        
        Args:
            api_key (str): Binance API key
            secret_key (str): Binance secret key
            passphrase (str): Binance passphrase (not used for Binance)
            session_id (str): Session ID for tracking
        """
        self.symbol = "BTC"
        self.quote = "USDT"
        self.session_id = session_id
        self.exchange = "binance"
        self.run_key = generate_random_string()
        
        # Initialize Binance client using the factory function
        try:
            logger_access.info(f"Initializing Binance client for session: {session_id}")
            logger_access.info(f"API Key: {api_key[:10]}... (truncated)")
            logger_access.info(f"API Secret: {secret_key[:10]}... (truncated)")
            
            account_info = {
                "api_key": api_key,
                "secret_key": secret_key,
                "passphrase": passphrase
            }
            
            self.client = get_client_exchange(
                exchange_name="binance",
                acc_info=account_info,
                symbol=self.symbol,
                quote=self.quote,
                use_proxy=False  # Disable proxy to avoid connection issues
            )
            logger_access.info(f"Binance client initialized successfully for session: {session_id}")
            logger_access.info(f"Client type: {type(self.client)}")
            logger_access.info(f"Client methods: {[method for method in dir(self.client) if not method.startswith('_')]}")
            logger_database.info(f"Binance balance checker initialized for session: {session_id}")
        except Exception as e:
            logger_error.error(f"Failed to initialize Binance client: {e}")
            logger_error.error(f"Exception details: {type(e).__name__}: {str(e)}")
            import traceback
            logger_error.error(f"Traceback: {traceback.format_exc()}")
            logger_error.error(f"Failed to initialize Binance client for session {session_id}: {e}")
            raise

    def get_all_balances(self):
        """
        Get all account balances from Binance using get_account_balance() and ticker prices
        
        Returns:
            dict: Complete balance information for all assets with prices in the requested format
        """
        try:
            logger_access.info(f"Fetching all account balances for session: {self.session_id}")
            logger_database.info(f"Fetching all account balances for session: {self.session_id}")
            
            logger_access.info(f"Calling client.get_account_balance()...")
            balance_data = self.client.get_account_balance()
            logger_access.info(f"Raw balance_data response: {balance_data}")
            
            if not balance_data or 'data' not in balance_data:
                error_msg = f"No balance data received from get_account_balance() API. Response: {balance_data}"
                logger_access.info(f" {error_msg}")
                logger_error.error(f"Balance fetch failed for session {self.session_id}: {error_msg}")
                
                return {
                    "Total": 0.0
                }
            
            balances = balance_data['data']
            logger_access.info(f"Retrieved {len(balances)} assets from get_account_balance()")
            logger_access.info(f"Raw balances data: {balances}")
            
            # Format balance data with prices in the requested format
            formatted_balances = {}
            total_value_usd = 0.0
            
            for asset_symbol, asset_info in balances.items():
                amount = float(asset_info.get('total', 0))
                logger_access.info(f"🔍 Processing {asset_symbol}: amount = {amount}")
                
                if amount > 0:
                    try:
                        # Get price for the asset
                        if asset_symbol == 'USDT':
                            price = 1.0
                        else:
                            # Try to get price using get_ticker method
                            try:
                                ticker_data = self.client.get_ticker(asset_symbol, "USDT")
                                price = float(ticker_data.get('last', 0)) if ticker_data else 0.0
                            except Exception as ticker_error:
                                logger_error.error(f"Could not get ticker for {asset_symbol}_USDT: {ticker_error}")
                                # Try get_price method if available
                                try:
                                    # Create a temporary client with the asset as base
                                    temp_client = get_client_exchange(
                                        exchange_name="binance",
                                        acc_info={
                                            "api_key": self.client.api_key,
                                            "secret_key": self.client.secret_key,
                                            "passphrase": ""
                                        },
                                        symbol=asset_symbol,
                                        quote="USDT",
                                        use_proxy=False
                                    )
                                    price_data = temp_client.get_price()
                                    price = float(price_data.get('price', 0)) if price_data else 0.0
                                except Exception as price_error:
                                    logger_error.error(f"Could not get price for {asset_symbol}: {price_error}")
                                    price = 0.0
                        
                        formatted_balances[asset_symbol] = {
                            "amount": amount,
                            "price": str(price)
                        }
                        
                        # Calculate USD value
                        usd_value = amount * price
                        total_value_usd += usd_value
                        
                        logger_access.info(f"💰 {asset_symbol}: Amount: {amount:.8f}, Price: ${price:.8f}, Value: ${usd_value:.2f}")
                        
                    except Exception as price_error:
                        logger_error.error(f"⚠️ Error processing {asset_symbol}: {price_error}")
                        # Still add the asset with 0 price
                        formatted_balances[asset_symbol] = {
                            "amount": amount,
                            "price": "0"
                        }
            
            # Add total to the result as requested
            formatted_balances["Total"] = total_value_usd
         
            logger_database.info(f"Successfully retrieved account balance for session: {self.session_id}")
            return formatted_balances
                
        except Exception as e:
            error_msg = f"Error fetching account balance: {str(e)}"
            logger_error.error(f"{error_msg}")
            logger_error.error(f"Exception details: {type(e).__name__}: {str(e)}")
            import traceback
            logger_error.error(f"Traceback: {traceback.format_exc()}")
            logger_error.error(f"Balance fetch exception for session {self.session_id}: {error_msg}")
            
            update_key_and_insert_error_log(
                self.run_key,
                self.symbol,
                get_line_number(),
                "BINANCE",
                "binance.py",
                error_msg
            )
            
            return {
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
            logger_access.info(f"📊 Fetching {asset_symbol} balance for session: {self.session_id}")
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
                
                logger_access.info(f"{asset_symbol} balance: Available: {balance['available']:.8f}, Locked: {balance['locked']:.8f}, Total: {balance['total']:.8f}")
                logger_database.info(f"{asset_symbol} balance retrieved successfully for session: {self.session_id}")
                return result
                
            else:
                error_msg = f"No {asset_symbol} balance found"
                logger_access.info(f"{error_msg}")
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
            logger_error.error(f"{error_msg}")
            logger_error.error(f"{asset_symbol} balance fetch exception for session {self.session_id}: {error_msg}")
            
            update_key_and_insert_error_log(
                self.run_key,
                asset_symbol,
                get_line_number(),
                "BINANCE",
                "binance.py",
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
            dict: Balance information in the requested format
        """
        logger_access.info("🚀 Starting Binance Balance Check...")
        logger_access.info(f"📊 Session ID: {self.session_id}")
        logger_access.info(f"🔍 Asset Filter: {asset_filter if asset_filter else 'All assets'}")
        logger_access.info("-" * 50)
        
        try:
            if asset_filter:
                # For specific asset, still return the old format for compatibility
                result = self.get_specific_asset_balance(asset_filter)
                logger_access.info("-" * 50)
                if result.get('success'):
                    logger_access.info("Balance check completed successfully!")
                else:
                    logger_access.info("Balance check failed!")
                return result
            else:
                # For all balances, return the new format
                result = self.get_all_balances()
                logger_access.info("-" * 50)
                if 'Total' in result:
                    logger_access.info("Balance check completed successfully!")
                else:
                    logger_access.info("Balance check failed!")
                return result
            
        except Exception as e:
            error_msg = f"Balance check error: {str(e)}"
            logger_error.error(f"{error_msg}")
            logger_error.error(f"Balance check error for session {self.session_id}: {error_msg}")
            
            update_key_and_insert_error_log(
                self.run_key,
                self.symbol,
                get_line_number(),
                "BINANCE",
                "binance.py",
                error_msg
            )
            
            return {
                "Total": 0.0
            }

def main():
    """
    Main function to run the balance checker
    """
    logger_access.info("🔍 Running Binance Balance Checker...")
    
    API_KEY = os.environ.get('STRATEGY_API_KEY', '')
    SECRET_KEY = os.environ.get('STRATEGY_API_SECRET', '')
    PASSPHRASE = os.environ.get('STRATEGY_PASSPHRASE', '')  # Not used for Binance
    SESSION_ID = os.environ.get('STRATEGY_SESSION_KEY', '')
    ASSET_FILTER = os.environ.get('STRATEGY_ASSET_FILTER', '')

    if not API_KEY or not SECRET_KEY:
        error_result = {
            "Total": 0.0
        }
       
        
        logger_access.info("\n" + "="*50)
        logger_access.info("RESULT:")
        logger_access.info(json.dumps(error_result, indent=2))
        return error_result
    
    try:
        checker = BinanceBalanceChecker(
            api_key=API_KEY,
            secret_key=SECRET_KEY,
            passphrase=PASSPHRASE,
            session_id=SESSION_ID
        )
        
        result = checker.check_balance(asset_filter=ASSET_FILTER if ASSET_FILTER else None)
        
        # Output JSON for Golang to parse
        logger_access.info("\n" + "="*50)
        logger_access.info("RESULT:")
        logger_access.info(json.dumps(result, indent=2))
        
        return result
        
    except Exception as e:
        error_result = {
            "Total": 0.0
        }
        logger_error.error(f"Fatal error: {e}")
        
        # Output JSON for Golang to parse
        logger_error.error("\n" + "="*50)
        logger_error.error("RESULT:")
        logger_error.error(json.dumps(error_result, indent=2))
        return error_result

if __name__ == "__main__":
    result = main()
    sys.exit(0 if 'Total' in result else 1)