#!/usr/bin/env python3
"""
Test Strategy for Poloniex BTC Trading
Checks BTC price and places buy order if price < $100k USD
"""



import os
import sys
import time
import json
from decimal import Decimal

# Add the parent directory to the path to import our modules
# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../../"))
sys.path.insert(0, PROJECT_ROOT)

from logger import logger_database, logger_error
from exchange_api_spot.user import get_client_exchange, get_client_new
from utils import (
    get_line_number,
    update_key_and_insert_error_log,
    generate_random_string,
    get_precision_from_real_number
)

symbol_input = "BTC"
quote_input = "USDT"

class BTCTestStrategy:
    def __init__(self, client):
        """
        Initialize the BTC test strategy
        
        Args:
            api_key (str): Poloniex API key
            secret_key (str): Poloniex secret key
            passphrase (str): Poloniex passphrase
            session_id (str): Session ID for tracking (optional)
        """
        self.symbol = client.symbol
        self.quote = client.quote
        self.price_threshold = 90000  # $90k USD (changed from 100k)
        self.buy_amount = 0.0001  # Amount of BTC to buy (adjust as needed)
        self.run_key = generate_random_string()
        
        # Initialize Poloniex client using get_client_exchange
        try:
           
            
            self.client = client

            print(f"✅ Poloniex client initialized successfully for {self.symbol}/{self.quote}")
            logger_database.info(f"BTC test strategy initialized for {self.symbol}/{self.quote}")
        except Exception as e:
            print(f"❌ Failed to initialize Poloniex client: {e}")
            logger_error.error(f"Failed to initialize Poloniex client: {e}")
            raise
    
    def get_account_balance(self):
        balance = self.client.get_account_balance()
        return balance
    def get_current_price(self):
        """
        Get current BTC price from Poloniex
        
        Returns:
            float: Current BTC price in USDT, or None if error
        """
        try:
            price_data = self.client.get_price()
            if price_data and 'price' in price_data:
                current_price = float(price_data['price'])
                print(f"📊 Current BTC price: ${current_price:,.2f} USDT")
                logger_database.info(f"Current {self.symbol} price: {current_price:.2f} {self.quote}")
                return current_price
            else:
                print("❌ Failed to get price data")
                logger_error.error("Failed to get price data - invalid response")
                return None
        except Exception as e:
            print(f"❌ Error getting price: {e}")
            logger_error.error(f"Error getting {self.symbol} price: {e}")
            update_key_and_insert_error_log(
                self.run_key, 
                self.symbol, 
                get_line_number(),
                "POLONIEX",
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
                    logger_database.info(f"Account balance check: {available:.2f} {self.quote} available")
                    return available
                else:
                    print(f"❌ No {self.quote} balance found")
                    logger_error.warning(f"No {self.quote} balance found in account")
                    return 0
            else:
                print("❌ Failed to get account balance")
                logger_error.error("Failed to get account balance - invalid response")
                return 0
        except Exception as e:
            print(f"❌ Error checking balance: {e}")
            logger_error.error(f"Error checking account balance: {e}")
            update_key_and_insert_error_log(
                self.run_key,
                self.quote,
                get_line_number(),
                "POLONIEX",
                "test-strategy.py",
                f"Error checking balance: {e}"
            )
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
            print(f"🛒 Placing buy order for {self.buy_amount} BTC at market price...")
            
            order_result = self.client.place_order(
                side_order='BUY',
                quantity=self.buy_amount,
                order_type='MARKET',
                force='normal'
            )
            
            if order_result and order_result.get('code') == 0:
                order_data = order_result.get('data', {})
                order_id = order_data.get('orderId', 'N/A')
                print(f"✅ Buy order placed successfully!")
                print(f"📝 Order ID: {order_id}")
                print(f"💵 Quantity: {self.buy_amount} BTC")
                print(f"💰 Estimated cost: ${required_amount:.2f} USDT")
                
                logger_database.info(f"Buy order placed successfully - ID: {order_id}, Quantity: {self.buy_amount} {self.symbol}, Cost: {required_amount:.2f} {self.quote}")
                return True
            else:
                print(f"❌ Failed to place order: {order_result}")
                logger_error.error(f"Failed to place buy order: {order_result}")
                return False
                
        except Exception as e:
            print(f"❌ Error placing order: {e}")
            update_key_and_insert_error_log(
                self.run_key,
                self.symbol,
                get_line_number(),
                "POLONIEX",
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
            
            if current_price is None:
                print("❌ Cannot proceed without price data")
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
            print(f"❌ Strategy error: {e}")
            update_key_and_insert_error_log(
                self.run_key,
                self.symbol,
                get_line_number(),
                "test-strategy.py",
                f"Strategy error: {e}"
            )
            return False

def main():
    """
    Main function to run the strategy
    """
    print("🚀 Running BTC Test Strategy...")
    print("-" * 50)
    # get_sys


    # Get configuration from environment variables
    # API_KEY = os.environ.get("STRATEGY_API_KEY", "")
    # SECRET_KEY = os.environ.get("STRATEGY_API_SECRET", "")
    # PASSPHRASE = os.environ.get("STRATEGY_PASSPHRASE", "")
    # # # client = get_client_new(symbol_input, quote_input)
    # exchange_name = os.environ.get("EXCHANGE", "binance")
    args = sys.argv[1:]
    run_mode = args[0]
    exchange_name = args[1]
    session_key = args[2]
    api_key = args[3]
    secret_key = args[4]
    passphrase = args[5]
    account_info = {
        "api_key": api_key,
        "secret_key": secret_key,
        "passphrase": passphrase
    }
    


    client = get_client_exchange(
        exchange_name=exchange_name,
        acc_info=account_info,
        symbol=self.symbol,
        quote=self.quote,
        run_mode= run_mode,
        session_key = session_key
    )
    BTCTestStrategy(client)
    logger_error.error(
        "API_KEY, SECRET_KEY: ", API_KEY, SECRET_KEY
    )


    # if not API_KEY or not SECRET_KEY:
    #     logger_error.error("❌ Please set your Poloniex API credentials in environment variables:")
    #     logger_error.error("   STRATEGY_API_KEY")
    #     logger_error.error("   STRATEGY_API_SECRET") 
    #     logger_error.error("   STRATEGY_PASSPHRASE (optional)")
    #     logger_error.error("   STRATEGY_SESSION_KEY (optional)")
    #     return
    
    print("✅ Environment variables loaded successfully")
    logger_database.info("BTC Test Strategy starting...")

    try:
        # Initialize strategy
        strategy = BTCTestStrategy(
            client
        )
        balance = strategy.get_account_balance()
        print(f"💰 Account Balance: {balance}")
        print(f"🎯 Strategy initialized - Target price: ${strategy.price_threshold:,}")
        logger_database.info("BTC Test Strategy initialized successfully")

        # Strategy execution loop
        iteration = 0
        while True:
            iteration += 1
            print(f"\n🔄 Strategy iteration #{iteration}")
            logger_database.info(f"Running strategy iteration #{iteration}")
            
            success = strategy.run_strategy()
            
            if success:
                print("✅ Strategy iteration completed successfully")
            else:
                print("⚠️ Strategy iteration completed with issues")
            
            # Sleep between iterations to avoid spamming API
            print(f"⏸️ Waiting 30 seconds before next iteration...")
            time.sleep(30)  # Check every 30 seconds
        
    except KeyboardInterrupt:
        print("\n🛑 Strategy stopped by user")
        logger_database.info("BTC Test Strategy stopped by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        logger_error.error(f"BTC Test Strategy fatal error: {e}")
        update_key_and_insert_error_log(
            generate_random_string(),
            "BTC",
            get_line_number(),
            "POLONIEX",
            "test-strategy.py",
            f"Fatal error: {e}"
        )

if __name__ == "__main__":
    main()
