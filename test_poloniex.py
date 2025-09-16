from exchange_api_spot.poloniex.poloniex_private import PoloniexPrivate
import time, json
import asyncio

SECRET = '618e840d8e92bf4fd8b0b15c3994ca23603535e1faf062813ca708c52d16ae663bfcc2f85961cd3cd620f0a2721cefdbd56674bf3beb669d073d458aab157ee1'
API = '42DFVKZ3-2JMTZF9F-C7CK4HLO-VWINY6J2'
# symbol = "SPOT_BTC_USDT"  

symbol = "SOL"  


async def main():
    # client = PoloniexPrivate(symbol, 'USDT', API, SECRET)
    # try:
    #     get_candles = client.get_candles()
    #     print("get_candles:", get_candles)
    # except Exception as e:
    #     print("Error getting get_candles:", e)
        
        
    # client = PoloniexPrivate(symbol, 'USDT', API, SECRET)
    # try:
    #     ticker = client.get_ticker()
    #     print("ticker:", ticker)
    # except Exception as e:
    #     print("Error getting ticker:", e)
    
    # client = PoloniexPrivate(symbol, 'USDT', API, SECRET)
    # try:
    #     result = client.get_price()
    #     print("result:", result)
    # except Exception as e:
    #     print("Error getting result:", e)
    
    # client = PoloniexPrivate(symbol, 'USDT', API, SECRET)
    # try:
    #     result = client.get_scale()
    #     print("result:", result)
    # except Exception as e:
    #     print("Error getting result:", e)
    
    
    # client = PoloniexPrivate(symbol, 'USDT', API, SECRET)
    # try:
    #     result = client.place_order("BUY",0.01, "LIMIT","100")
    #     print("result:", result)
    # except Exception as e:
    #     print("Error getting result:", e)
    
    # client = PoloniexPrivate(symbol, 'USDT', API, SECRET)
    # try:
    #     result = client.cancel_order("483344109646462976")
    #     print("result:", result)
    # except Exception as e:
    #     print("Error getting result:", e)
    
    # client = PoloniexPrivate(symbol, 'USDT', API, SECRET)
    # try:
    #     result = client.cancel_orders()
    #     print("result:", result)
    # except Exception as e:
    #     print("Error getting result:", e)
    
    client = PoloniexPrivate(symbol, 'USDT', API, SECRET)
    try:
        result = client.get_open_orders()
        print("result:", result)
    except Exception as e:
        print("Error getting result:", e)
        
    # client = PoloniexPrivate(symbol, 'USDT', API, SECRET)
    # try:
    #     result = client.get_order_details("487337199218561024")
    #     print("result detail:", result)
    # except Exception as e:
    #     print("Error getting result:", e)
    
    client = PoloniexPrivate(symbol, 'USDT', API, SECRET)
    try:
        result = client.get_account_balance()
        print("result:", result)
    except Exception as e:
        print("Error getting result:", e)
        
    # client = PoloniexPrivate(symbol, 'USDT', API, SECRET)
    # try:
    #     result = client.get_account_assets("USDT")
    #     print("result:", result)
    # except Exception as e:
    #     print("Error getting result:", e)
    
    # client = PoloniexPrivate(symbol, 'USDT', API, SECRET)
    # try:
    #     result = client.get_user_asset()
    #     print("result:", result)
    # except Exception as e:
    #     print("Error getting result:", e)
    
    # client = PoloniexPrivate(symbol, 'USDT', API, SECRET)
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

   

