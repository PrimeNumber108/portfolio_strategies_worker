from exchange_api_spot.binance.binance_private_new import BinancePrivateNew
import time, json
import asyncio

SECRET = 'c35FvHdmEprSdqXqv11pCA8mjTvoswWW90VqWzEcHuN3RIQ5fZ0PZboqW3ed8Ta2'  # Your wallet private key
API = 'aunuHUuEqX4PGB8pj8lA3jFYlCSzLpTME4VU2B7hiGyc0YFJN8xqpQD7Fy3433Js'  # Your wallet address (0x...)
# symbol = "SPOT_BTC_USDT"  

symbol = "SOL"  


async def main():
    # client = BinancePrivateNew(symbol, 'USDT', API, SECRET)
    # try:
    #     get_candles = client.get_candles()
    #     print("get_candles:", get_candles)
    # except Exception as e:
    #     print("Error getting get_candles:", e)
        
        
    # client = BinancePrivateNew(symbol, 'USDT', API, SECRET)
    # try:
    #     ticker = client.get_ticker()
    #     print("ticker:", ticker)
    # except Exception as e:
    #     print("Error getting ticker:", e)
    
    # client = BinancePrivateNew(symbol, 'USDT', API, SECRET)
    # try:
    #     result = client.get_price()
    #     print("result:", result)
    # except Exception as e:
    #     print("Error getting result:", e)
    
    # client = BinancePrivateNew(symbol, 'USDT', API, SECRET)
    # try:
    #     result = client.get_scale()
    #     print("result:", result)
    # except Exception as e:
    #     print("Error getting result:", e)
    
    
    # client = BinancePrivateNew(symbol, 'USDT', API, SECRET)
    # try:
    #     result = client.place_order("BUY",0.01, "LIMIT","100")
    #     print("result:", result)
    # except Exception as e:
    #     print("Error getting result:", e)
    
    # client = BinancePrivateNew(symbol, 'USDT', API, SECRET)
    # try:
    #     result = client.cancel_order("483344109646462976")
    #     print("result:", result)
    # except Exception as e:
    #     print("Error getting result:", e)
    
    # client = BinancePrivateNew(symbol, 'USDT', API, SECRET)
    # try:
    #     result = client.cancel_orders()
    #     print("result:", result)
    # except Exception as e:
    #     print("Error getting result:", e)
    
    client = BinancePrivateNew(symbol, 'USDT', API, SECRET)
    try:
        result = client.get_open_orders()
        print("result:", result)
    except Exception as e:
        print("Error getting result:", e)
        
    # client = BinancePrivateNew(symbol, 'USDT', API, SECRET)
    # try:
    #     result = client.get_order_details("487337199218561024")
    #     print("result detail:", result)
    # except Exception as e:
    #     print("Error getting result:", e)
    
    client = BinancePrivateNew(symbol, 'USDT', API, SECRET)
    try:
        result = client.get_account_balance()
        print("result:", result)
    except Exception as e:
        print("Error getting result:", e)
        
    # client = BinancePrivateNew(symbol, 'USDT', API, SECRET)
    # try:
    #     result = client.get_account_assets("USDT")
    #     print("result:", result)
    # except Exception as e:
    #     print("Error getting result:", e)
    
    # client = BinancePrivateNew(symbol, 'USDT', API, SECRET)
    # try:
    #     result = client.get_user_asset()
    #     print("result:", result)
    # except Exception as e:
    #     print("Error getting result:", e)
    
    # client = BinancePrivateNew(symbol, 'USDT', API, SECRET)
    # try:
    #     utc_0h = int(time.time() * 1000)//86400000*86400000
    #     print('utc_0h: ',utc_0h)
    #     result = client.get_volume_by_interval('BTC','USDT','1h', utc_0h)
    #     print("result:", result)
    # except Exception as e:
    #     print("Error getting result:", e)
        
    
    
    # client = await PoloniexPrivate.create(symbol, 'USDT', API, SECRET)


if __name__ == "__main__":
    asyncio.run(main())  # Try to run with asyncio.run()

   

