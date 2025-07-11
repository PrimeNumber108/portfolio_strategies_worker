#!/usr/bin/env python3
"""
Test Strategy for BTC Trading
Calls the execute API to place orders when conditions are met
"""

import os
import sys
import time
import json
import requests
from decimal import Decimal

# Add the parent directory to the path to import our modules
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../../"))
sys.path.insert(0, PROJECT_ROOT)

try:
    from exchange_api.poloniex.poloniex_private import PoloniexPrivate
    from utils import (
        get_line_number,
        update_key_and_insert_error_log,
        generate_random_string,
        get_precision_from_real_number
    )
except ImportError:
    print("⚠️ Warning: Could not import utility modules, continuing without them")
    def generate_random_string():
        return f"run_{int(time.time())}"

class BTCTestStrategy:
    def __init__(self, execute_api_url="http://localhost:8083"):
        """
        Initialize the BTC test strategy
        
        Args:
            execute_api_url (str): Execute API base URL
        """
        self.symbol = "BTCUSDT"  # Bybit format
        self.price_threshold = 90000  # $90k USD threshold
        self.buy_amount = 0.001  # Amount of BTC to buy (adjust as needed)
        self.run_key = generate_random_string()
        self.execute_api_url = execute_api_url
        
        print(f"🔗 Strategy initialized with Execute API: {execute_api_url}")

    def get_current_price(self):
        """
        Get current BTC price (simplified version)
        In a real implementation, you would get this from a price feed
        
        Returns:
            float: Current BTC price in USDT, or None if error
        """
        try:
            # For demo purposes, we'll use a mock price
            # In real implementation, you would call a price API
            mock_price = 85000.0  # Below threshold to trigger buy
            print(f"📊 Current BTC price: ${mock_price:,.2f} USDT (mock data)")
            return mock_price
        except Exception as e:
            print(f"❌ Error getting price: {e}")
            return None

    def place_order_via_execute_api(self, side, quantity, order_type="market", price=None):
        """
        Place order through execute API
        
        Args:
            side (str): 'buy' or 'sell'
            quantity (float): Order quantity
            order_type (str): Order type ('market', 'limit', etc.)
            price (float): Order price (for limit orders)
            
        Returns:
            dict: API response or None if error
        """
        try:
            url = f"{self.execute_api_url}/api/v1/execute/make-order"
            
            payload = {
                "symbol": self.symbol,
                "side": side.lower(),
                "order_type": order_type.lower(),
                "quantity": quantity
            }
            
            if price and order_type.lower() == "limit":
                payload["price"] = price
            
            headers = {
                "Content-Type": "application/json",
                # Note: In real implementation, you would need to add Authorization header
                # "Authorization": f"Bearer {jwt_token}"
            }
            
            print(f"🌐 Calling Execute API: {url}")
            print(f"📦 Payload: {json.dumps(payload, indent=2)}")
            
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Execute API response: {json.dumps(result, indent=2)}")
                return result
            else:
                print(f"❌ Execute API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error calling Execute API: {e}")
            return None

    def place_buy_order(self, current_price):
        """
        Place a buy order for BTC
        
        Args:
            current_price (float): Current BTC price
            
        Returns:
            bool: True if order placed successfully, False otherwise
        """
        try:
            required_amount = self.buy_amount * current_price
            
            print(f"🛒 Placing buy order via Execute API for {self.buy_amount} BTC at market price...")
            
            order_result = self.place_order_via_execute_api(
                side='buy',
                quantity=self.buy_amount,
                order_type='market'
            )
            
            if order_result and order_result.get('order'):
                order_data = order_result.get('order', {})
                order_id = order_data.get('order_id', 'N/A')
                print(f"✅ Buy order placed successfully via Execute API!")
                print(f"📝 Order ID: {order_id}")
                print(f"💵 Quantity: {self.buy_amount} BTC")
                print(f"💰 Estimated cost: ${required_amount:.2f} USDT")
                return True
            else:
                print(f"❌ Failed to place order via Execute API: {order_result}")
                return False
                
        except Exception as e:
            print(f"❌ Error placing order: {e}")
            return False

    def run_strategy(self):
        """
        Main strategy logic
        """
        print("🚀 Starting BTC Test Strategy...")
        print(f"🎯 Target: Buy BTC if price < ${self.price_threshold:,}")
        print(f"📊 Buy amount: {self.buy_amount} BTC")
        print(f"🔗 Execute API: {self.execute_api_url}")
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
            return False

def main():
    """
    Main function to run the strategy
    """
    # Get Execute API URL from environment or use default
    execute_api_url = os.getenv('EXECUTE_API_URL', 'http://localhost:8083')
    
    print("🔄 Running in Execute API mode")
    print(f"🌐 Execute API URL: {execute_api_url}")
    
    try:
        # Initialize strategy for Execute API mode
        strategy = BTCTestStrategy(execute_api_url=execute_api_url)
        
        # Run the strategy
        result = strategy.run_strategy()
        
        if result:
            print("✅ Strategy execution completed successfully")
        else:
            print("⚠️ Strategy execution completed with warnings")
            
        return result
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)