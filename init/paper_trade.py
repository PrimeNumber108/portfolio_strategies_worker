#!/usr/bin/env python3
"""
Paper Trade Initialization Example
Shows how to initialize and use the paper trading module similar to poloniex.py
"""

import os
import sys

# Add the parent directory to the path to import our modules
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../"))
sys.path.insert(0, PROJECT_ROOT)

from exchange_api_spot.user import get_client_exchange

def initialize_paper_trading():
    """
    Initialize paper trading client using the same pattern as poloniex.py
    """
    print("🧪 Initializing Paper Trading Client...")
    
    # Account information for paper trading
    account_info = {
        "api_key": "paper_trade_demo",
        "secret_key": "paper_trade_demo", 
        "passphrase": "",
        "session_key": "demo_session_12345",
        "initial_balance": 50000  # $50,000 starting balance
    }
    
    try:
        # Create paper trading client using get_client_exchange factory
        client = get_client_exchange(
            exchange_name="paper_trade",  # or "paper"
            acc_info=account_info,
            symbol="BTC", 
            quote="USDT",
            use_proxy=False
        )
        
        print(f"✅ Paper trading client initialized successfully!")
        print(f"📊 Trading pair: BTC/USDT")
        print(f"💰 Initial balance: $50,000 USDT")
        print(f"🔧 Session ID: {account_info['session_key']}")
        
        return client
        
    except Exception as e:
        print(f"❌ Failed to initialize paper trading client: {e}")
        return None

def demo_paper_trading_operations(client):
    """
    Demonstrate paper trading operations
    """
    if not client:
        print("❌ No client available for demo")
        return
        
    print("\n" + "="*50)
    print("🎯 PAPER TRADING DEMO")
    print("="*50)
    
    try:
        # 1. Get current price
        print("\n1️⃣ Getting current BTC price...")
        price_data = client.get_price()
        if price_data:
            current_price = float(price_data['price'])
            print(f"📊 Current BTC price: ${current_price:,.2f}")
        else:
            print("⚠️ Price data not available - make sure exchange data is cached in Redis")
            current_price = 50000  # Fallback price for demo
            
        # 2. Check initial balance
        print("\n2️⃣ Checking account balance...")
        balance = client.get_account_balance()
        print(f"💰 Account balance: {balance}")
        
        # 3. Get trading scales
        print("\n3️⃣ Getting trading scales...")
        price_scale, qty_scale = client.get_scale()
        print(f"📏 Price scale: {price_scale}, Quantity scale: {qty_scale}")
        
        # 4. Place a paper buy order
        print("\n4️⃣ Placing paper BUY order...")
        buy_result = client.place_order(
            side_order='BUY',
            quantity=0.01,  # Buy 0.01 BTC
            order_type='MARKET'
        )
        print(f"📝 Buy order result: {buy_result}")
        
        # 5. Check balance after buy
        print("\n5️⃣ Checking balance after buy...")
        balance_after_buy = client.get_account_balance()
        print(f"💰 Balance after buy: {balance_after_buy}")
        
        # 6. Place a paper sell order  
        print("\n6️⃣ Placing paper SELL order...")
        sell_result = client.place_order(
            side_order='SELL',
            quantity=0.005,  # Sell 0.005 BTC
            order_type='MARKET'
        )
        print(f"📝 Sell order result: {sell_result}")
        
        # 7. Check final balance
        print("\n7️⃣ Checking final balance...")
        final_balance = client.get_account_balance()
        print(f"💰 Final balance: {final_balance}")
        
        # 8. Get ticker data
        print("\n8️⃣ Getting ticker data...")
        ticker = client.get_ticker()
        print(f"📊 Ticker data: {ticker}")
        
        # 9. Account snapshot
        print("\n9️⃣ Account snapshot...")
        snapshot = client.snap_shot_account(['USDT', 'BTC', 'ETH'])
        print(f"📸 Account snapshot: {snapshot}")
        
        print("\n✅ Paper trading demo completed successfully!")
        
    except Exception as e:
        print(f"❌ Demo error: {e}")
        import traceback
        traceback.print_exc()

def main():
    """
    Main function - demonstrates paper trading initialization and usage
    """
    print("🚀 Paper Trading Example")
    print("-" * 50)
    
    # Set environment variable for paper trading exchange data source
    # This tells the paper trader which exchange to use for cached price data
    os.environ['PAPER_TRADE_EXCHANGE'] = 'binance'  # Can be 'binance', 'poloniex', etc.
    
    # Initialize paper trading client
    client = initialize_paper_trading()
    
    if client:
        # Run demo operations
        demo_paper_trading_operations(client)
    else:
        print("❌ Failed to initialize paper trading client")

if __name__ == "__main__":
    main()