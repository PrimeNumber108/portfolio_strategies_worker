#!/usr/bin/env python3
"""
Test Strategy for Binance BTC Trading
Checks BTC price and places buy order if price < $100k USD
"""

import os
import sys
import time
import json
from decimal import Decimal

# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../../"))
sys.path.insert(0, PROJECT_ROOT)

from logger import logger_database, logger_error
from exchange_api_spot.user import get_client_exchange
from utils import (
    get_line_number,
    update_key_and_insert_error_log,
    generate_random_string,
    get_precision_from_real_number
)

class BTCTestStrategy:
    def __init__(self, api_key="", secret_key="", passphrase=""):
        """
        Initialize the BTC test strategy
        
        Args:
            api_key (str): Binance API key
            secret_key (str): Binance secret key
            passphrase (str): Binance passphrase (not used for Binance)
        """
        self.symbol = "BTC"
        self.quote = "USDT"
        self.price_threshold = 90000  # $100k USD
        self.buy_amount = 0.0001  # Amount of BTC to buy (adjust as needed)
        self.run_key = generate_random_string()
        
        # Initialize Binance client using the factory function
        try:
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
            print(f"✅ Binance client initialized successfully for {self.symbol}/{self.quote}")
        except Exception as e:
            print(f"❌ Failed to initialize Binance client: {e}")
            raise

    def get_current_price(self):
        """
        Get current BTC price from Binance
        
        Returns:
            float: Current BTC price in USDT, or None if error
        """
        try:
            ticker_data = self.client.get_ticker()
            if ticker_data and 'lastPrice' in ticker_data:
                current_price = float(ticker_data['lastPrice'])
                print(f"📊 Current BTC price: ${current_price:,.2f} USDT")
                return current_price
            else:
                print("❌ Failed to get price data")
                return None
        except Exception as e:
            print(f"❌ Error getting price: {e}")
            update_key_and_insert_error_log(
                self.run_key, 
                self.symbol, 
                get_line_number(),
                "BINANCE",
                "test-strategy.py",
                f"Error getting price: {e}"
            )
            return None

    def check_account_balance(self):
        """
        Check account balance for USDT
        
        Returns:
            float: Available USDT balance
        """
        try:
            balance_data = self.client.get_account_assets(self.quote)
            if balance_data and 'data' in balance_data:
                balance = balance_data['data']
                if balance:
                    available = float(balance.get('available', 0))
                    print(f"💰 Available {self.quote} balance: ${available:,.2f}")
                    return available
                else:
                    print(f"❌ No {self.quote} balance found")
                    return 0
            else:
                print("❌ Failed to get account balance")
                return 0
        except Exception as e:
            print(f"❌ Error checking balance: {e}")
            return 0

    def place_buy_order(self, current_price):
        """
        Place a buy order for BTC
        
        Args:
            current_price (float): Current BTC price
            
        Returns:
            bool: True if order placed successfully, False otherwise
        """
        try:
            # Check if we have enough balance
            balance = self.check_account_balance()
            required_amount = self.buy_amount * current_price
            
            if balance < required_amount:
                print(f"❌ Insufficient balance. Required: ${required_amount:.2f}, Available: ${balance:.2f}")
                return False
            
            # Place market buy order
            print(f"Placing buy order for {self.buy_amount} BTC at market price...")
            
            order_result = self.client.place_order(
                side_order='BUY',
                quantity=self.buy_amount,
                order_type='MARKET',
                force='normal'
            )
            
            if order_result and order_result.get('code') == 0:
                order_data = order_result.get('data', {})
                order_id = order_data.get('orderId', 'N/A')
                print(f"Buy order placed successfully 2!")
                print(f"Order ID: {order_id}")
                print(f"Quantity: {self.buy_amount} BTC")
                print(f"Estimated cost: ${required_amount:.2f} USDT")
                return True
            else:
                print(f"❌ Failed to place order: {order_result}")
                return False
                
        except Exception as e:
            print(f"Error placing order: {e}")
            update_key_and_insert_error_log(
                self.run_key,
                self.symbol,
                get_line_number(),
                "BINANCE",
                "test-strategy.py",
                f"Error placing order: {e}"
            )
            return False

    def run_strategy(self):
        """
        Main strategy logic
        """
        print("🚀 Starting BTC Test Strategy...")
        print(f"🎯 Target: Buy BTC if price < ${self.price_threshold:,}")
        print(f"📊 Buy amount: {self.buy_amount} BTC")
        print("-" * 50)
        
        try:
            # Get current price
            current_price = self.get_current_price()
            account_balance = self.client.get_account_balance()
            print('account_balance: ',account_balance)
            
            if current_price is None:
                print("Cannot proceed without price data")
                return False
            
            # Check if price is below threshold
            if current_price < self.price_threshold:
                print(f"🎉 Price is below threshold!")
                print(f"💡 Current: ${current_price:,.2f} < Target: ${self.price_threshold:,}")
                
                # Place buy order
                success = self.place_buy_order(current_price)
                if success:
                    print("✅ Strategy executed successfully!")
                    return True
                else:
                    print("❌ Failed to execute buy order")
                    return False
            else:
                print(f"⏳ Price is above threshold")
                print(f"💡 Current: ${current_price:,.2f} >= Target: ${self.price_threshold:,}")
                print("🔄 Waiting for better price...")
                return True
                
        except Exception as e:
            print(f"Strategy error: {e}")
            update_key_and_insert_error_log(
                self.run_key,
                self.symbol,
                get_line_number(),
                "BINANCE",
                "test-strategy.py",
                f"Strategy error: {e}"
            )
            return False

def main():
    """
    Main function to run the strategy
    """
    print("Running BTC Test Strategy...")
    
    API_KEY = os.environ.get("STRATEGY_API_KEY")
    SECRET_KEY = os.environ.get("STRATEGY_API_SECRET")

    
    PASSPHRASE = os.environ.get("STRATEGY_PASSPHRASE", "")  # Default to empty string if not set

    if not API_KEY or not SECRET_KEY:
        print("Please set your Binance API credentials in environment variables:")
        print("   BINANCE_API_KEY")
        print("   BINANCE_SECRET_KEY")
        return
    
    try:
        # Initialize strategy
        strategy = BTCTestStrategy(
            api_key=API_KEY,
            secret_key=SECRET_KEY,
            passphrase=PASSPHRASE
        )
        
        # # Run the strategy
        # strategy.run_strategy()
        # ✅ Always run in loop
        while True:
            success = strategy.run_strategy()

            # Sleep between iterations to avoid spamming API (adjust as needed)
            time.sleep(5)  # check every 5 seconds

        
    except Exception as e:
        print(f"Fatal error: {e}")

if __name__ == "__main__":
    logger_database.warning("it's oke")
    main()
