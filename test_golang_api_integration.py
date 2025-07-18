#!/usr/bin/env python3
"""
Test script to demonstrate Poloniex-Golang API integration
"""

import sys
import os
import requests
import json
sys.path.append(os.path.join(os.path.dirname(__file__), 'exchange_api'))

from exchange_api.poloniex.poloniex_private import PoloniexPrivate

def test_server_connection():
    """Test basic server connection"""
    print("=== Testing Server Connection ===")
    
    # Test health endpoint
    try:
        response = requests.get("http://localhost:8083/health", timeout=5)
        print(f"Health check - Status: {response.status_code}")
        print(f"Health check - Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Server is running")
            return True
        else:
            print("❌ Server is not responding correctly")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
        return False

def test_auth_manually():
    """Test authentication manually"""
    print("\n=== Testing Authentication Manually ===")
    
    auth_data = {
        "username": "dattest@the20.vn",
        "password": "Fin20admin@1234"
    }
    
    try:
        # Test the exact endpoint
        print("Testing: POST http://localhost:8083/api/v1/auth/login")
        response = requests.post(
            "http://localhost:8083/api/v1/auth/login",
            json=auth_data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        print(f"Status: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            try:
                response_data = response.json()
                token = response_data.get("access_token")
                if token:
                    print(f"✅ Authentication successful - Token: {token[:20]}...")
                    return token
                else:
                    print("❌ No access token in response")
                    return None
            except json.JSONDecodeError as e:
                print(f"❌ JSON decode error: {e}")
                return None
        else:
            print(f"❌ Authentication failed")
            return None
    except Exception as e:
        print(f"❌ Authentication error: {e}")
        return None

def test_create_order_manually(token):
    """Test creating order manually"""
    print("\n=== Testing Order Creation Manually ===")
    
    order_data = {
        "session_key": "test_session_123",
        "symbol": "BTC_USDT",
        "side": "buy",
        "order_type": "market",
        "quantity": 0.001,
        "price": 0,
        "time_in_force": "GTC"
    }
    
    try:
        print("Testing: POST http://localhost:8083/api/v1/orders")
        response = requests.post(
            "http://localhost:8083/api/v1/orders",
            json=order_data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}"
            },
            timeout=10
        )
        
        print(f"Status: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print(f"Response: {response.text}")
        
        if response.status_code == 201:
            print("✅ Order created successfully")
            return True
        else:
            print("❌ Order creation failed")
            return False
    except Exception as e:
        print(f"❌ Order creation error: {e}")
        return False

def test_poloniex_integration():
    """Test the Poloniex integration"""
    print("\n=== Testing Poloniex Integration ===")
    
    # Initialize Poloniex API
    poloniex = PoloniexPrivate(
        symbol="BTC",
        quote="USDT",
        api_key="42DFVKZ3-2JMTZF9F-C7CK4HLO-VWINY6J2",
        secret_key="618e840d8e92bf4fd8b0b15c3994ca23603535e1faf062813ca708c52d16ae663bfcc2f85961cd3cd620f0a2721cefdbd56674bf3beb669d073d458aab157ee1",
        session_key="test_session_123"
    )
    
    print(f"Session Key: {poloniex.session_key}")
    print(f"Symbol: {poloniex.symbol_ex}")
    
    # Test authentication
    print("\nStep 1: Testing Golang API authentication...")
    if poloniex.authenticate_golang_api():
        print("✅ Authentication successful!")
        
        # Test order storage
        print("\nStep 2: Testing order storage...")
        test_order_data = {
            "symbol": "BTC_USDT",
            "side": "BUY",
            "type": "MARKET",
            "quantity": 0.001,
            "price": 0,
            "timeInForce": "GTC"
        }
        
        if poloniex.store_order_in_golang_api(test_order_data, exchange_order_id="test_order_123"):
            print("✅ Order storage successful!")
        else:
            print("❌ Order storage failed!")
    else:
        print("❌ Authentication failed!")

def main():
    """Main test function"""
    print("=== Poloniex-Golang API Integration Test ===")
    
    # Test 1: Server connection
    if not test_server_connection():
        print("\n❌ Server is not running. Please start the server first.")
        return
    
    # Test 2: Manual authentication
    token = test_auth_manually()
    if not token:
        print("\n❌ Authentication failed. Please check credentials.")
        return
    
    # Test 3: Manual order creation
    if not test_create_order_manually(token):
        print("\n❌ Order creation failed. Please check API endpoints.")
        return
    
    # Test 4: Poloniex integration
    test_poloniex_integration()
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    main()