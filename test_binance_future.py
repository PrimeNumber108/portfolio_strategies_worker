import time, json
import asyncio
from exchange_api_future.binance_future import BinanceFuturePrivate

# Replace these with your actual Hyperliquid credentials
SECRET_KEY = 'GlqwZKkXFMPW0YZBB8ow3fsBXHVK7iT5VppwJrWnYU1Ibal7JBZWSvXt2bD3qsI6'  # Your wallet private key
API_KEY = 'I1ji7rWqb3lhwScJeq5nyELErdVe6Z3rupwG8iCGYqK47dZQOfHjDpbk1fJmsyKT'  # Your wallet address (0x...)

symbol = 'BTC'  # Default symbol to test with
def main():
    # Test get_account_balance
    # client = BinanceFuturePrivate(symbol, 'USDT', API_KEY, SECRET_KEY)
    # try:
    #     get_balance = client.get_account_assets('BTC')
    #     print("get_balance:", get_balance)
    # except Exception as e:
    #     print("Error getting get_balance:", e)

    # client = BinanceFuturePrivate(symbol, 'USDT', API_KEY, SECRET_KEY)
    # try:
    #     get_position = client.get_position_info('BTC')
    #     print("get_position: ", get_position)
    # except Exception as e:
    #     print("Error getting get_position:", e)
    
    # Test get_user_asset
    # client = BinanceFuturePrivate(symbol, 'USDC',  API_KEY,SECRET_KEY)
    # try:
    #     get_balance = client.get_user_asset()
    #     print("get_user_asset:", get_balance)
    # except Exception as e:
    #     print("Error getting get_user_asset:", e)
   
    # Test get_candles
    # client = BinanceFuturePrivate(symbol, 'USDC', API_KEY, SECRET_KEY)
    # try:
    #     get_candles = client.get_candles(symbol, 'USDC')
    # except Exception as e:
    #     print("Error getting get_candles:", e)

    # Test get_scale
    # client = BinanceFuturePrivate(symbol, 'USDT', API_KEY, SECRET_KEY)
    # try:
    #     get_scale = client.get_scale()
    #     print("get_scale:", get_scale)
    # except Exception as e:
    #     print("Error getting get_scale:", e)

    # Test get_account_assets
    # client = BinanceFuturePrivate(symbol, 'USDC', API_KEY, SECRET_KEY)
    # try:
    #     get_assets = client.get_account_assets("BTC")
    #     print("get_account_assets:", get_assets)
    # except Exception as e:
    #     print("Error getting get_account_assets:", e)

    # Test get_ticker
    # client = BinanceFuturePrivate(symbol, 'USDC', API_KEY, SECRET_KEY)
    # try:
    #     get_ticker = client.get_ticker()
    #     print("get_ticker:", get_ticker)
    # except Exception as e:
    #     print("Error getting get_ticker:", e)

    # Test get_price
    # client = BinanceFuturePrivate(symbol, 'USDC', API_KEY, SECRET_KEY)
    # try:
    #     result = client.get_price()
    #     print("get_price result:", result)
    # except Exception as e:
    #     print("Error getting price:", e)

    # Test get_symbol
    # client = BinanceFuturePrivate(symbol, 'USDC', API_KEY, SECRET_KEY)
    # try:
    #     result = client.get_pair_name(symbol, 'USDC')
    #     print("get_pair_name:", result)
    # except Exception as e:
    #     print("Error getting price:", e)


    
    # Test place_order - Uncomment when ready to test with real orders
    # WARNING: This will place a real order on Binance Futures!
    client = BinanceFuturePrivate(symbol, 'USDT', API_KEY, SECRET_KEY)
    
    print(f"Symbol: {symbol}USDT")
    print(f"Price scale: {client.price_scale}, Quantity scale: {client.qty_scale}")
    print(f"Minimum quantity step: {1 / (10 ** client.qty_scale)}")
    
    try:
        # Use 0.001 which matches the step size for BTCUSDT futures (qty_scale=3 means 0.001 minimum)
        result = client.place_order_v2(side_order="buy", quantity="0.001", price='10000', order_type='limit', base="", quote="USDT")
        print('place_order_v2 result:', result)
    except Exception as e:
        print("Error placing order:", e)

     # Test get_open_orders
    # client = BinanceFuturePrivate(symbol, 'USDC', API_KEY, SECRET_KEY)
    # try:
    #     result = client.get_open_orders()
    #     print(json.dumps(result, indent=4))
    #     print('Open order: ',result)
    # except Exception as e:
    #     print("Error getting open orders:", e)


    # SPOT MARKET ORDER - BTC/USDC
    # print("\n=== Testing SPOT Market Order ===")
    # client = BinanceFuturePrivate(symbol, 'USD', API_KEY, SECRET_KEY)
    # try:
    #     print(f"Placing Perp market order for {symbol}/USDC")
    #     result = client.place_order("BUY", "0.0025", "MARKET")
    #     print('place_order result:', result)
    # except Exception as e:
    #     print("Error placing order:", e)

    # SPOT MARKET ORDER - BTC/USDC
    # print("\n=== Testing SPOT Market Order ===")
    # client = BinanceFuturePrivate(symbol, 'USD', API_KEY, SECRET_KEY)
    # try:
    #     result = client.close_position("BTC")
    #     print('close pos result:', result)
    # except Exception as e:
    #     print("Error close pos:", e)

    print("\n=== Testing SPOT Market Order ===")
    # client = BinanceFuturePrivate(symbol, 'USD', API_KEY, SECRET_KEY)
    # try:
    #     result = client.close_all_positions()
    #     print('close all result:', result)
    # except Exception as e:
    #     print("Error close all:", e)
    
    # Test cancel_order - Uncomment when ready to test with real orders
    # client = BinanceFuturePrivate(symbol, 'USDC', API_KEY, SECRET_KEY)
    # try:
    #     result = client.cancel_order("125631025402")  # Replace with actual order ID
    #     print("cancel_order result:", result)
    # except Exception as e:
    #     print("Error canceling order:", e)
    
    # Test cancel_orders - Uncomment when ready to test with real orders
    # client = BinanceFuturePrivate(symbol, 'USDC', API_KEY, SECRET_KEY)
    # try:
    #     result = client.cancel_orders()
    #     print("cancel_orders result:", result)
    # except Exception as e:
    #     print("Error canceling all orders:", e)
   
    # # Test get_order_details - Uncomment when you have an order ID to test with
    # client = BinanceFuturePrivate(symbol, 'USDC', API_KEY, SECRET_KEY)
    # try:
    #     result = client.get_order_details("125643701853")  # Replace with actual order ID
    #     print("get_order_details result:", result)
    # except Exception as e:
    #     print("Error getting order details:", e)

    # Test get_volume_by_interval
    # client = BinanceFuturePrivate(symbol, 'USDC', API_KEY, SECRET_KEY)
    # try:
    #     utc_0h = int(time.time() * 1000)//86400000*86400000
    #     print('utc_0h:', utc_0h)
    #     result = client.get_volume_by_interval(symbol, 'USDC', '1h', utc_0h)
    #     print("get_volume_by_interval result:", result)
    # except Exception as e:
    #     print("Error getting volume by interval:", e)

    # Test snap_shot_account
    # client = BinanceFuturePrivate(symbol, 'USDC', API_KEY, SECRET_KEY)
    # try:
    #     result = client.snap_shot_account()
    #     print("snap_shot_account result:", result)
    # except Exception as e:
    #     print("Error getting account snapshot:", e)



if __name__ == "__main__":
    print("=== Binance API Test ===")
    print("Note: Replace SECRET_KEY and API_KEY with your actual credentials")
    print("Most tests are commented out to prevent accidental trading")
    print()
    
    # Test symbol availability first
    # test_symbol_availability()
    
    # # Test RAGE symbol specifically
    # test_rage_symbol()
    
    # # Test public endpoints (no credentials needed)
    # test_public_endpoints()
    
    # Test private endpoints (requires credentials)
    if SECRET_KEY != 'your_SECRET_KEY_here' and API_KEY != 'your_API_KEY_here':
        print("\n=== Testing Private Endpoints ===")
        main()
    else:
        print("\n=== Skipping Private Endpoints ===")
        print("Please set your SECRET_KEY and API_KEY to test private endpoints")
        print("WARNING: Private endpoints will interact with your real Binance account!")