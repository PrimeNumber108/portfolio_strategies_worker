#!/usr/bin/env python3
"""
Test Strategy for Binance BTC Trading
Checks BTC price and places buy order if price < $100k USD
"""

##Test Real Trade

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

from logger import logger_database, logger_error,logger_access
from exchange_api_spot.user import get_client_exchange
from utils import (
    get_line_number,
    update_key_and_insert_error_log,
    generate_random_string,
    get_precision_from_real_number,
    get_arg
)
from constants import set_constants, get_constants



class BTCTestStrategy:
    def __init__(self, api_key="", secret_key="", passphrase=""):
        """
        Initialize the BTC test strategy
        
        Args:
            api_key (str): Biannce API key
            secret_key (str): Biannce secret key
            passphrase (str): Biannce passphrase
            session_id (str): Session ID for tracking (optional)
        """
        self.symbol = "SOL"
        self.quote = "USDT"
        self.price_threshold = 100  # $90k USD (changed from 100k)
        self.buy_amount = 0.01  # Amount of BTC to buy (adjust as needed)
        self.run_key = generate_random_string()
        
        # Initialize Binance client using get_client_exchange
        try:
            account_info = {
                "api_key": api_key,
                "secret_key": secret_key,
                "passphrase": passphrase,
            }
            
            self.client = get_client_exchange(
                exchange_name="binance",
                acc_info=account_info,
                symbol=self.symbol,
                quote=self.quote,
            )
            logger_access.info(f"✅ Binance client initialized successfully for {self.symbol}/{self.quote}")
            logger_database.info(f"BTC test strategy initialized for {self.symbol}/{self.quote}")
        except Exception as e:
            logger_error.error(f"❌ Failed to initialize Binance client: {e}")
            logger_error.error(f"Failed to initialize Binance client: {e}")
            raise
    
    def get_account_balance(self):
        balance = self.client.get_account_balance()
        return balance
    
    def get_current_price(self):
        """
        Get current BTC price from Binance
        
        Returns:
            float: Current BTC price in USDT, or None if error
        """
        try:
            price_data = self.client.get_price()
            if price_data and 'price' in price_data:
                current_price = float(price_data['price'])
                logger_access.info(f"📊 Current BTC price: ${current_price:,.2f} USDT")
                logger_database.info(f"Current {self.symbol} price: {current_price:.2f} {self.quote}")
                return current_price
            else:
                logger_access.info("❌ Failed to get price data")
                logger_error.error("Failed to get price data - invalid response")
                return None
        except Exception as e:
            logger_error.error(f"❌ Error getting price: {e}")
            logger_error.error(f"Error getting {self.symbol} price: {e}")
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
                    logger_access.info(f"💰 Available {self.quote} balance: ${available:,.2f}")
                    logger_database.info(f"Account balance check: {available:.2f} {self.quote} available")
                    return available
                else:
                    logger_access.info(f"❌ No {self.quote} balance found")
                    logger_error.warning(f"No {self.quote} balance found in account")
                    return 0
            else:
                logger_access.info("❌ Failed to get account balance")
                logger_error.error("Failed to get account balance - invalid response")
                return 0
        except Exception as e:
            logger_error.error(f"❌ Error checking balance: {e}")
            logger_error.error(f"Error checking account balance: {e}")
            update_key_and_insert_error_log(
                self.run_key,
                self.quote,
                get_line_number(),
                "BINANCE",
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
            logger_access.info(f"💵 Required USDT for purchase: ${balance} ${required_amount:.2f}")
            if balance < required_amount:
                logger_access.info(f"❌ Insufficient balance. Required: ${required_amount:.2f}, Available: ${balance:.2f}")
                return False
            
            # Place market buy order
            logger_access.info(f"🛒 Placing buy order for {self.buy_amount} BTC at market price...")
            
            order_result = self.client.place_order(
                side_order='BUY',
                quantity=self.buy_amount,
                price='100',
                order_type='LIMIT',
                force='normal'
            )
            
            if order_result and order_result.get('code') == 0:
                order_data = order_result.get('data', {})
                order_id = order_data.get('orderId', 'N/A')
                logger_access.info(f"✅ Buy order placed successfully!")
                logger_access.info(f"📝 Order ID: {order_id}")
                logger_access.info(f"💵 Quantity: {self.buy_amount} BTC")
                logger_access.info(f"💰 Estimated cost: ${required_amount:.2f} USDT")
                
                logger_database.info(f"Buy order placed successfully - ID: {order_id}, Quantity: {self.buy_amount} {self.symbol}, Cost: {required_amount:.2f} {self.quote}")
                return True
            else:
                logger_access.info(f"❌ Failed to place order: {order_result}")
                logger_error.error(f"Failed to place buy order: {order_result}")
                return False
                
        except Exception as e:
            logger_error.error(f"❌ Error placing order: {e}")
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
        logger_access.info("🚀 Starting BTC Test Strategy...")
        logger_access.info(f"🎯 Target: Buy BTC if price < ${self.price_threshold:,}")
        logger_access.info(f"📊 Buy amount: {self.buy_amount} BTC")
        logger_access.info("-" * 50)
        
        try:
            # Get current price
            current_price = self.get_current_price()
            
            if current_price is None:
                logger_access.info("❌ Cannot proceed without price data")
                return False
            
            # Check if price is below threshold
            # if current_price < self.price_threshold:
            #     logger_access.info(f"🎉 Price is below threshold!")
            #     logger_access.info(f"💡 Current: ${current_price:,.2f} < Target: ${self.price_threshold:,}")
                
            #     # Place buy order
            #     success = self.place_buy_order(current_price)
            #     if success:
            #         logger_access.info("✅ Strategy executed successfully!")
            #         return True
            #     else:
            #         logger_access.info("❌ Failed to execute buy order")
            #         return False
            # else:
            #     logger_access.info(f"⏳ Price is above threshold")
            #     logger_access.info(f"💡 Current: ${current_price:,.2f} >= Target: ${self.price_threshold:,}")
            #     logger_access.info("🔄 Waiting for better price...")
            #     return True

            # logger_access.info(f"🎉 Price is below threshold!")
            # logger_access.info(f"💡 Current: ${current_price:,.2f} < Target: ${self.price_threshold:,}")
            
            # Place buy order
            success = self.place_buy_order(current_price)
            if success:
                logger_access.info("✅ Strategy executed successfully!")
                return True
            else:
                logger_access.info("❌ Failed to execute buy order")
                return False
                
        except Exception as e:
            logger_error.error(f"❌ Strategy error: {e}")
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
    logger_access.info("🚀 Running BTC Test Strategy...")
    logger_access.info("-" * 50)
   

    params = get_constants()
    SESSION_ID     = params.get("SESSION_ID", "")
    EXCHANGE       = params.get("EXCHANGE", "")
    API_KEY        = params.get("API_KEY", "")
    SECRET_KEY     = params.get("SECRET_KEY", "")
    PASSPHRASE     = params.get("PASSPHRASE", "")
    STRATEGY_NAME  = params.get("STRATEGY_NAME", "")
    PAPER_MODE     = params.get("PAPER_MODE", True)     
    
    logger_access.info(f"Parameters 2: {params}")


    if not API_KEY or not SECRET_KEY:
        logger_access.info("❌ Please set your Binance API credentials in environment variables:")
        logger_access.info("   STRATEGY_API_KEY")
        logger_access.info("   STRATEGY_API_SECRET") 
        logger_access.info("   STRATEGY_PASSPHRASE (optional)")
        logger_access.info("   STRATEGY_SESSION_KEY (optional)")
        return
    
    logger_access.info("✅ Environment variables loaded successfully")
    logger_database.info("BTC Test Strategy starting...")

    try:
        # Initialize strategy
        strategy = BTCTestStrategy(
            api_key=API_KEY,
            secret_key=SECRET_KEY,
            passphrase=PASSPHRASE,
        )
        balance = strategy.get_account_balance()
        logger_access.info(f"💰 Account Balance: {balance}")
        logger_access.info(f"🎯 Strategy initialized - Target price: ${strategy.price_threshold:,}")
        logger_database.info("BTC Test Strategy initialized successfully")

        # Strategy execution loop
        iteration = 0
        while True:
            iteration += 1
            logger_access.info(f"\n🔄 Strategy iteration #{iteration}")
            logger_database.info(f"Running strategy iteration #{iteration}")
            
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
        logger_database.info("BTC Test Strategy stopped by user")

    except Exception as e:
        logger_error.error(f"❌ Fatal error: {e}")
        logger_error.error(f"BTC Test Strategy fatal error: {e}")
        update_key_and_insert_error_log(
            generate_random_string(),
            "BTC",
            get_line_number(),
            "BINANCE",
            "test-strategy.py",
            f"Fatal error: {e}"
        )

if __name__ == "__main__":
    main()
