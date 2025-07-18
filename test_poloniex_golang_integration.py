#!/usr/bin/env python3
"""
Test script to demonstrate Poloniex-Golang API integration
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'exchange_api'))

from exchange_api.poloniex.poloniex_private import PoloniexPrivate

def test_poloniex_golang_integration():
    """Test placing an order with Poloniex and storing it in Golang API"""
    
    print("=== Poloniex-Golang API Integration Test ===")
    
    # Initialize Poloniex API
    # Replace with your actual API credentials
    poloniex = PoloniexPrivate(
        symbol="BTC",
        quote="USDT",
        api_key="42DFVKZ3-2JMTZF9F-C7CK4HLO-VWINY6J2",
        secret_key="618e840d8e92bf4fd8b0b15c3994ca23603535e1faf062813ca708c52d16ae663bfcc2f85961cd3cd620f0a2721cefdbd56674bf3beb669d073d458aab157ee1",
        session_key="test_session_123"  # Custom session key for testing
    )
    
    print(f"Session Key: {poloniex.session_key}")
    print(f"Symbol: {poloniex.symbol_ex}")
    print()
    
    # Test authentication with Golang API
    print("Step 1: Testing Golang API authentication...")
    if poloniex.authenticate_server_api():
        print("✅ Authentication successful!")
    else:
        print("❌ Authentication failed!")
        return
    
    print()
    
    # Example: Place a small test order (DEMO - don't use real money)
    print("Step 2: Testing order placement...")
    print("⚠️  This is a demo - make sure to use testnet/sandbox APIs!")
    
    try:
        # This would place a real order - BE CAREFUL!
        # Uncomment only if you're using testnet/sandbox
        # """
        # result = poloniex.place_order(
        #     side_order="buy",
        #     quantity=0.00006,  # Small amount for testing
        #     order_type="market",
        #     price="",  # Market order doesn't need price
        #     force="normal"
        # )
        
        # if result["code"] == 0:
        #     print(f"✅ Order placed successfully!")
        #     print(f"   Order ID: {result['data']['orderId']}")
        #     print(f"   Status: {result['data'].get('status', 'pending')}")
        # else:
        #     print(f"❌ Order placement failed: {result.get('message', 'Unknown error')}")
        # """
        
        # Instead, let's simulate the order storage
        print("🔄 Simulating order storage in Golang API...")
        
        # Simulate order data
        test_order_data = {
            "symbol": "BTC_USDT",
            "side": "BUY",
            "type": "MARKET",
            "quantity": 0.001,
            "price": 0,
            "timeInForce": "GTC"
        }
        
        # Test storing the order
        if poloniex.store_order_in_golang_api(test_order_data, exchange_order_id="test_order_123"):
            print("✅ Order simulation successful!")
        else:
            print("❌ Order simulation failed!")
            
    except Exception as e:
        print(f"❌ Error during order test: {str(e)}")
    
    print()
    print("=== Test Complete ===")
    print("To use this in production:")
    print("1. Replace API credentials with real ones")
    print("2. Use testnet/sandbox for testing")
    print("3. Ensure Golang API server is running")
    print("4. Test with small amounts first")

if __name__ == "__main__":
    test_poloniex_golang_integration()