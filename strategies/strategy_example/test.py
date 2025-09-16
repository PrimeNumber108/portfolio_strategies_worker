#!/usr/bin/env python3
"""
Test Strategy for Poloniex BTC Trading
Checks BTC price and places buy order if price < $100k USD
"""

##Test Paper Trade


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

from constants import set_constants, get_constants
from exchange_api_spot.user import get_client_exchange
from utils import (
    get_line_number,
    update_key_and_insert_error_log,
    generate_random_string,
    get_precision_from_real_number,
    get_arg
)
## General log ##
from logger import logger_access, logger_error

## Private log ##
from logger import setup_logger_global



class BTCTestStrategy:
    def __init__(self, api_key="", secret_key="", passphrase="", session_key=""):
        """
        Initialize the BTC test strategy
        
        Args:
            api_key (str): Poloniex API key
            secret_key (str): Poloniex secret key
            passphrase (str): Poloniex passphrase
            session_key (str): Session key for tracking
        """
        self.symbol = "BTC"
        self.quote = "USDT"
        self.price_threshold = 90000  # $90k USD (changed from 100k)
        self.buy_amount = 0.0005  # Amount of BTC to buy (adjust as needed)
        self.run_key = generate_random_string()
        self.session_key = session_key

        # Config logger
        self.exchange = "poloniex"
        self.class_name = self.__class__.__name__  
        strategy_log_name = f'{self.symbol}_{self.exchange}_{self.class_name}'
        self.logger_strategy = setup_logger_global(strategy_log_name, strategy_log_name + '.log') 

        
        # Initialize Poloniex client using get_client_exchange
        try:
            account_info = {
                "api_key": api_key,
                "secret_key": secret_key,
                "passphrase": passphrase,
            }
            
            self.client = get_client_exchange(
                exchange_name="poloniex",
                acc_info=account_info,
                symbol=self.symbol,
                quote=self.quote,
                session_key=session_key,  # Pass session_key to get_client_exchange
            )

            self.logger_strategy.info(f"✅ Poloniex client initialized successfully for {self.symbol}/{self.quote}")
            self.logger_strategy.info(f"BTC test strategy initialized for {self.symbol}/{self.quote}")
        except Exception as e:
            self.logger_strategy.error(f"❌ Failed to initialize Poloniex client: {e}")
            self.logger_strategy.error(f"Failed to initialize Poloniex client: {e}")
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
            self.logger_strategy.info('price_data')
            if price_data and 'price' in price_data:
                current_price = float(price_data['price'])
                self.logger_strategy.info(f"📊 Current BTC price: ${current_price:,.2f} USDT")
                self.logger_strategy.info(f"Current {self.symbol} price: {current_price:.2f} {self.quote}")
                return current_price
            else:
                self.logger_strategy.info("❌ Failed to get price data")
                self.logger_strategy.error("Failed to get price data - invalid response")
                return None
        except Exception as e:
            self.logger_strategy.error(f"❌ Error getting price: {e}")
            self.logger_strategy.error(f"Error getting {self.symbol} price: {e}")
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
                    self.logger_strategy.info(f"💰 Available {self.quote} balance: ${available:,.2f}")
                    self.logger_strategy.info(f"Account balance check: {available:.2f} {self.quote} available")
                    return available
                else:
                    self.logger_strategy.info(f"❌ No {self.quote} balance found")
                    self.logger_strategy.warning(f"No {self.quote} balance found in account")
                    return 0
            else:
                self.logger_strategy.info("❌ Failed to get account balance")
                self.logger_strategy.error("Failed to get account balance - invalid response")
                return 0
        except Exception as e:
            self.logger_strategy.error(f"❌ Error checking balance: {e}")
            self.logger_strategy.error(f"Error checking account balance: {e}")
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
            # balance = self.check_account_balance()
            required_amount = self.buy_amount * current_price
            self.logger_strategy.info("required_amount: ",required_amount)
            # if balance < required_amount:
            #     self.logger_strategy.info(f"❌ Insufficient balance. Required: ${required_amount:.2f}, Available: ${balance:.2f}")
            #     return False
            
            # Place market buy order
            self.logger_strategy.info(f"🛒 Placing buy order for {self.buy_amount} BTC at market price...")
            
            order_result = self.client.place_order(
                side_order='BUY',
                quantity=self.buy_amount,
                order_type='MARKET',
                force='normal'
            )
            
            if order_result and order_result.get('code') == 0:
                order_data = order_result.get('data', {})
                order_id = order_data.get('orderId', 'N/A')
                self.logger_strategy.info(f"✅ Buy order placed successfully!")
                self.logger_strategy.info(f"📝 Order ID: {order_id}")
                self.logger_strategy.info(f"💵 Quantity: {self.buy_amount} BTC")
                self.logger_strategy.info(f"💰 Estimated cost: ${required_amount:.2f} USDT")
                
                self.logger_strategy.info(f"Buy order placed successfully - ID: {order_id}, Quantity: {self.buy_amount} {self.symbol}, Cost: {required_amount:.2f} {self.quote}")
                return True
            else:
                self.logger_strategy.info(f"❌ Failed to place order: {order_result}")
                self.logger_strategy.error(f"Failed to place buy order: {order_result}")
                return False
                
        except Exception as e:
            self.logger_strategy.error(f"❌ Error placing order: {e}")
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
        self.logger_strategy.info("🚀 Starting BTC Test Strategy...")
        self.logger_strategy.info(f"🎯 Target: Buy BTC if price < ${self.price_threshold:,}")
        self.logger_strategy.info(f"📊 Buy amount: {self.buy_amount} BTC")
        self.logger_strategy.info("-" * 50)
        
        try:
            # Get current price
            current_price = self.get_current_price()
            self.logger_strategy.info(f"Current price: {current_price}")
            if current_price is None:
                self.logger_strategy.info("❌ Cannot proceed without price data")
                return False
            
            # Check if price is below threshold
            # if current_price < self.price_threshold:
            #     self.logger_strategy.info(f"🎉 Price is below threshold!")
            #     self.logger_strategy.info(f"💡 Current: ${current_price:,.2f} < Target: ${self.price_threshold:,}")
                
                
            # else:
            #     self.logger_strategy.info(f"⏳ Price is above threshold")
            #     self.logger_strategy.info(f"💡 Current: ${current_price:,.2f} >= Target: ${self.price_threshold:,}")
            #     self.logger_strategy.info("🔄 Waiting for better price...")
            #     return True

            # Place buy order
            success = self.place_buy_order(current_price)
            self.logger_strategy.info(f"Buy order placed successfully {success}")
            if success:
                self.logger_strategy.info("✅ Strategy executed successfully!")
                return True
            else:
                self.logger_strategy.info("❌ Failed to execute buy order")
                return False
                
        except Exception as e:
            self.logger_strategy.error(f"❌ Strategy error: {e}")
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

    params = get_constants()
    SESSION_ID     = params.get("SESSION_ID", "")
    EXCHANGE       = params.get("EXCHANGE", "")
    API_KEY        = params.get("API_KEY", "")
    SECRET_KEY     = params.get("SECRET_KEY", "")
    PASSPHRASE     = params.get("PASSPHRASE", "")
    STRATEGY_NAME  = params.get("STRATEGY_NAME", "")
    PAPER_MODE     = params.get("PAPER_MODE", True)     
    
   

    if not API_KEY or not SECRET_KEY:
        logger_access.info("❌ API credentials are required")
        return
    
    if not SESSION_ID:
        logger_access.info("❌ Session key is required")
        return
    
    logger_access.info("✅ Environment variables loaded successfully")
    logger_access.info(f"🔑 Session Key: {SESSION_ID}")
    logger_access.info("BTC Test Strategy starting...")

    try:
        # Initialize strategy
        strategy = BTCTestStrategy(
            api_key=API_KEY,
            secret_key=SECRET_KEY,
            passphrase=PASSPHRASE,
            session_key=SESSION_ID,
        )
        # balance = strategy.get_account_balance()
        # self.logger_strategy.info(f"💰 Account Balance: {balance}")
        logger_access.info(f"🎯 Strategy initialized - Target price: ${strategy.price_threshold:,}")
        logger_access.info("BTC Test Strategy initialized successfully")

        # Strategy execution loop
        iteration = 0
        while True:
            iteration += 1
            logger_access.info(f"\n🔄 Strategy iteration #{iteration}")
            logger_access.info(f"Running strategy iteration #{iteration}")
            
            success = strategy.run_strategy()
            
            if success:
                logger_access.info("✅ Strategy iteration completed successfully")
            else:
                logger_access.info("⚠️ Strategy iteration completed with issues")
            
            # Sleep between iterations to avoid spamming API
            logger_access.info(f"⏸️ Waiting 30 seconds before next iteration...")
            time.sleep(30)  # Check every 30 seconds
        
    except KeyboardInterrupt:
        logger_access.info("\n🛑 Strategy stopped by user")
        logger_access.info("BTC Test Strategy stopped by user")
    except Exception as e:
        logger_access.error(f"❌ Fatal error: {e}")
        logger_access.error(f"BTC Test Strategy fatal error: {e}")
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
