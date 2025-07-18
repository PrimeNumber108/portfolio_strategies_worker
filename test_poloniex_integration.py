#!/usr/bin/env python3
"""
Test Poloniex integration with Golang API
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from exchange_api.poloniex.poloniex_private import PoloniexPrivate

def test_poloniex_integration():
    """Test Poloniex integration"""
    print("=== Poloniex-Golang Integration Test ===")
    
    # Initialize Poloniex API
    poloniex = PoloniexPrivate(
        symbol="BTC",
        quote="USDT",
        api_key="42DFVKZ3-2JMTZF9F-C7CK4HLO-VWINY6J2",
        secret_key="618e840d8e92bf4fd8b0b15c3994ca23603535e1faf062813ca708c52d16ae663bfcc2f85961cd3cd620f0a2721cefdbd56674bf3beb669d073d458aab157ee1",
        session_key="test_session_poloniex"
    )
    
    print(f"Session Key: {poloniex.session_key}")
    print(f"Symbol: {poloniex.symbol_ex}")
    print()
    
    # Test 1: Authentication
    print("Step 1: Testing Golang API authentication...")
    try:
        if poloniex.authenticate_golang_api():
            print("✅ Authentication successful!")
        else:
            print("❌ Authentication failed!")
            return
    except Exception as e:
        print(f"❌ Authentication error: {e}")
        return
    
    print()
    
    # Test 2: Order storage simulation
    print("Step 2: Testing order storage simulation...")
    
    # Simulate order data that would come from Poloniex
    test_order_data = {
        "symbol": "BTC_USDT",
        "side": "BUY",
        "type": "MARKET",
        "quantity": 0.001,
        "price": 0,
        "timeInForce": "GTC"
    }
    
    print(f"Test order data: {test_order_data}")
    
    try:
        if poloniex.store_order_in_golang_api(test_order_data, exchange_order_id="test_poloniex_order_123"):
            print("✅ Order storage successful!")
        else:
            print("❌ Order storage failed!")
    except Exception as e:
        print(f"❌ Order storage error: {e}")
    
    print()
    print("=== Test Complete ===")
    print("If all tests passed, the integration is working correctly!")

if __name__ == "__main__":
    test_poloniex_integration()