import time
import math
import json
import redis
import sys
import os

_original_path = sys.path[:]
# Remove directories that might contain the local binance.py file
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../"))
result_dir = os.path.join(project_root, "result")


from logger import logger_access, logger_error
# Create a new sys.path that prioritizes site-packages over local directories
new_path = []
# Add all paths that don't start with our project root first
for p in sys.path:
    if not p.startswith(project_root) and p != '' and p != '.':
        new_path.append(p)
# Then add project paths, but exclude the result directory
for p in sys.path:
    if p.startswith(project_root) and not p.startswith(result_dir):
        new_path.append(p)

sys.path = new_path

try:
    from binance.client import Client
finally:
    # Restore original sys.path
    sys.path = _original_path

from utils import convert_order_status
FEE_PERCENT = 0.1/100
r = redis.Redis(host='localhost', port=6379, decode_responses=True)
proxy_list = [
    None,
    {'http': 'http://45.32.28.52:3128', 'https': 'http://45.32.28.52:3128'}, #stagging server
    {'http': 'http://47.129.237.109:3128', 'https': 'http://47.129.237.109:3128'}, #amazone server
]

class BinancePrivate:
    """
    Class for interacting with the Binance Spot API.
    """
    def __init__ (self, symbol, quote = 'USDT', api_key = '', secret_key = '', passphrase = ''):
        self.symbol = symbol
        self.symbol_ex = f'{symbol}{quote}'
        self.symbol_redis = f'{symbol}_{quote}'.upper()
        self.quote = quote
        self.channels = []
        self.order_dict = {}
        self.api_key = api_key
        self.api_secret = secret_key
        self.client = Client(api_key = api_key, api_secret=secret_key, requests_params={'proxies': proxy_list[2]})
        self.passphrase = passphrase

        scale_redis = r.get(f'{self.symbol_redis}_binance_scale')
        if scale_redis is not None:
            scale = json.loads(scale_redis)
            self.price_scale, self.qty_scale = int(scale["priceScale"]), int(scale["qtyScale"])
        else:
            self.price_scale, self.qty_scale = self.get_scale()
            scale = json.dumps({'priceScale':self.price_scale,
                                'qtyScale':self.qty_scale})
            r.set(f'{self.symbol_redis}_binance_scale', scale)

    def get_scale(self):
        """
        Retrieves the price and quantity scales for the given symbol from the Binance API.

        Parameters:
            None

        Returns:
            None
        """
        re = self.client.get_symbol_info(symbol=self.symbol_ex)
        # re = response['symbols'][0]
        scale_price_raw= re["filters"][0]["tickSize"]
        scale_qty_raw = re["filters"][1]["stepSize"]
        price_scale = int(-math.log10(float(scale_price_raw)))
        qty_scale =  int(-math.log10(float(scale_qty_raw)))
        return price_scale, qty_scale
        
    def delete_full_filled_order(self,order_id):
        """
        Deletes a full-filled order from the order dictionary.

        Args:
            order_id (int): The ID of the order to be deleted.

        Returns:
            None
        """
        if order_id in self.order_dict:
            self.order_dict.pop(order_id)
        # logger_temp.info(f'order_id {order_id}') 

    def get_ticker(self, base = "", quote ="USDT"):
        """
        Retrieves the ticker information for a given symbol.

        Args:
            base (str, optional): The base currency of the symbol. Defaults to "".
            quote (str, optional): The quote currency of the symbol. Defaults to "USDT".

        Returns:
            dict: A dictionary containing the ticker information. The dictionary has the following keys:
                - bidPr (float): The bid price.
                - askPr (float): The ask price.
                - bestBid (float): The best bid price.
                - bestAsk (float): The best ask price.
                - bidSz (float): The bid quantity.
                - askSz (float): The ask quantity.
                - last (float): The last traded price.
                - lastPr (float): The last traded price.
                - ts (int): The timestamp of the last update.
        """
        symbol = f'{base}{quote}'
        if base == "":
            symbol = self.symbol_ex
        tick_dict = self.client.get_ticker(symbol=symbol.upper())
        tick_dict["bidPr"] = tick_dict["bidPrice"]
        tick_dict["askPr"] = tick_dict["askPrice"]
        tick_dict["bestBid"] = tick_dict["bidPrice"]
        tick_dict["bestAsk"] = tick_dict["askPrice"]
        tick_dict["bidSz"] = tick_dict["bidQty"]
        tick_dict["askSz"] = tick_dict["askQty"]
        tick_dict["last"] = tick_dict["lastPrice"]
        tick_dict["lastPr"] = tick_dict["lastPrice"]
        tick_dict["ts"] = tick_dict["closeTime"]
        ticker_str = json.dumps(tick_dict)
        r.set(f'{self.symbol_redis}_binance_ticker', ticker_str)
        return tick_dict
    
    def get_price(self, base="", quote="USDT"):
        """
        Get the latest price for a symbol using Binance Symbol Price Ticker endpoint.
        
        Args:
            base (str, optional): The base currency of the symbol. Defaults to "".
            quote (str, optional): The quote currency of the symbol. Defaults to "USDT".
        
        Returns:
            dict: A dictionary containing the price information with the following key:
                - price (str): The latest price for the symbol.
        
        Reference:
            https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints#symbol-price-ticker
        """
        symbol = f'{base}{quote}'
        if base == "":
            symbol = self.symbol_ex
        
        try:
            # Use get_symbol_ticker method from binance.client.Client
            # This calls GET /api/v3/ticker/price endpoint
            price_data = self.client.get_symbol_ticker(symbol=symbol.upper())
            return price_data
        except Exception as e:
            logger_error.error(f"Error fetching price for {symbol}: {str(e)}")
            return {"price": "0"}
    
    def get_account_assets(self, coin):
        """
        Retrieves the account assets for a given coin.

        Args:
            coin (str): The coin for which to retrieve the account assets.

        Returns:
            dict: A dictionary containing the account assets. The dictionary has the following keys:
                - asset (str): The asset.
                - free (float): The free balance.
                - available (float): The available balance.
                - locked (float): The locked balance.
                - freeze (float): The frozen balance.
                - frozen (float): The frozen balance.
                - total (float): The total balance.
        """
        result = self.client.get_account()
        data ={}
        for asset in result["balances"]:
            if asset["asset"] == coin.upper():
                data = {
                    "asset": asset["asset"],
                    "free": float(asset["free"]),
                    "available": float(asset["free"]),
                    "locked": float(asset["locked"]),
                    "freeze": float(asset["locked"]),
                    "frozen": float(asset["locked"]),
                    "total": float(asset["free"]) + float(asset["locked"])
                }
        
        return {'data':data} #result
    
    def get_account_balance(self):
        """
        Retrieves the account assets.

        Args:
            coin (str): The coin for which to retrieve the account assets.

        Returns:
            dict: A dictionary containing the account assets. The dictionary has the following keys:
                - asset (str): The asset.
                - available (float): The available balance.
                - locked (float): The locked balance.
                - total (float): The total balance.
        """
        result = self.client.get_account()
        account_balance = {}
        for asset in result["balances"]:
            data = {
                "asset": asset["asset"],
                "available": float(asset["free"]),
                "locked": float(asset["locked"]),
                "total": float(asset["free"]) + float(asset["locked"])
            }
            if data["total"] > 0:
                account_balance[asset["asset"]] = data
        return {'data':account_balance} #result
    def place_order(self, side_order, quantity, order_type,force = 'normal', price ='', base = "", quote = "USDT"):
        """
        Places an order on the Binance exchange.

        Args:
            side_order (str): The side of the order. Can be 'buy', 'Buy', or 'BUY' for a buy order, 
                or 'sell', 'Sell', or 'SELL' for a sell order.
            quantity (float): The quantity of the asset to be traded.
            order_type (str): The type of the order. Can be 'limit', 'LIMIT', or 'Limit' for a limit order, 
                or 'market', 'MARKET', or 'Market' for a market order.
            force (str, optional): The time in force for the order. Can be 'normal' or 'GTC' (Good Till Cancelled). Defaults to 'normal'.
            price (str, optional): The price at which to execute the order for a limit order. Only required for limit orders.

        Returns:
            dict or bool: If the order is successfully placed, returns a dictionary with the following keys:
                - code (int): The status code of the order.
                - data (dict): The data of the order.
            If the order is not successfully placed, returns False.
        """
        symbol = self.symbol_ex.upper()
        if base != "":
            symbol = f'{base}{quote}'.upper()
        result = False
        if force == 'normal':
            force_ = 'GTC'
        else:
            force_ = force
        if order_type.upper() == "LIMIT":
            result = self.client.create_order(symbol = symbol,
                                             side = str(side_order.upper()),
                                             type = 'LIMIT',
                                             quantity = str(quantity),
                                             price = str(price),
                                             timeInForce = force_)
        elif order_type.upper() == "MARKET":
            result = self.client.create_order(symbol =symbol,
                                             side = str(side_order.upper()),
                                             type = 'MARKET',
                                             quantity = str(quantity))
        if "orderId" in result:
            return {"code": 0, "data": result}
        return result
    
    def cancel_order(self, order_id):
        """
        Cancels an order with the given order ID.

        Args:
            order_id (int): The ID of the order to be cancelled.

        Returns:
            dict: A dictionary containing the result of the cancellation operation. It has the following keys:
                - 'data' (dict): The result of the cancellation operation.
        """
        result = self.client.cancel_order(symbol = self.symbol_ex.upper(),orderId = order_id)
        return {'data':result}
    
    def get_order_details(self, order_id, base="", quote="USDT"):
        """
        Retrieves the details of an order with the given order ID.

        Args:
            order_id (str): The ID of the order.
            symbol (str, optional): The symbol of the order. Defaults to "".

        Returns:
            dict: A dictionary containing the details of the order. The dictionary has the following keys:
                - 'data' (dict): The details of the order. It has the following keys:
                    - 'clientOrderId' (str): The client order ID.
                    - 'quantity' (str): The original quantity of the order.
                    - 'orderId' (str): The order ID.
                    - 'status' (str): The status of the order.
                    - 'price' (str): The price of the order.
                    - 'side' (str): The side of the order.
                    - 'fillSize' (str): The executed quantity of the order.
                    - 'fillQuantity' (str): The fill quantity of the order.
                    - 'order_type' (str): The type of the order.
                    - 'fee' (str): The fee of the order.
                    - 'orderType' (str): The type of the order.
                    - 'createTime' (str): The creation time of the order.
                    - 'updateTime' (str): The update time of the order.
                    - 'orderCreateTime' (str): The creation time of the order.
                    - 'orderUpdateTime' (str): The update time of the order.
                - 'data' (dict): An empty dictionary if the order is not found.

        Raises:
            Exception: If an error occurs while retrieving the order details.

        """
        try:
            symbol = self.symbol_ex
            if base!= "":
                symbol = f"{base}{quote}".upper()
            # order_detais = self.client.get_order(symbol = self.symbol_ex.upper(),orderId = str(order_id))
            order_detais = self.client.get_order(symbol = symbol, orderId = str(order_id))
            details = {'data':None}
            if 'orderId'in order_detais:
                # Initialize the details dictionary
                details  = {'data':{
                    'clientOrderId': order_detais["clientOrderId"],  # Client order ID
                    'quantity': order_detais["origQty"],              # Original quantity
                    'orderId': order_detais["orderId"],                # Order ID
                    'status': convert_order_status(order_detais["status"]), # thêm convert_order_status (order_detais["status"])             # Order status
                    'price': order_detais["price"],                   # Order price
                    'side': order_detais["side"],                     # Order side
                    'fillSize': order_detais["executedQty"],          # Executed quantity
                    'fillQuantity': order_detais["executedQty"],      # Fill quantity
                    'order_type': order_detais["type"],               # Order type
                    'fee': str(FEE_PERCENT * float(order_detais["price"]) *float(order_detais["executedQty"])),
                    'orderType':order_detais["type"],
                    'createTime': order_detais["workingTime"],       # Creation time
                    'updateTime': order_detais["updateTime"],         # Update time
                    'orderCreateTime': order_detais["workingTime"],
                    'orderUpdateTime' :order_detais["updateTime"]
                }}

                # If the order is not partially filled or filled
                if details['data']['status'] not in ['PARTIALLY_FILLED', 'FILLED']:
                    details['data']['fillPrice'] = 0  # Fill price is 0
                else:
                    if "fills" in order_detais:
                        details['data']['fillPrice'] = order_detais['fills'][0]['price']
                    else: 
                        details['data']['fillPrice'] = order_detais["price"] # Fill price is the price of the first fill
            else:
                details = {"data": {}}
            # Return the details dictionary
            return details
        except Exception as e:
            logger_error.error(e)
            return {"data": None}
        
    def get_volume_by_interval(self, symbol_input, quote_input, interval, start_time):
        """
        Retrieves the volume of a given symbol and quote within a specified interval and time range.

        Args:
            symbol_input (str): The symbol to retrieve the volume for.
            quote_input (str): The quote currency to retrieve the volume for.
            interval (str): The time interval for the volume retrieval.
            start_time (int): The start time of the time range for the volume retrieval.

        Returns:
            dict: A dictionary containing the volume data. The 'data' key contains a list of candles representing the volume within the specified interval and time range.
        """
        result = self.get_candles(base = symbol_input,
                                quote = quote_input,
                                interval = interval,
                                start_time = start_time,)
        # result["candle"] = result["candle"][-tick_number:]
        return {'data':result['candle']}
    
    def get_candles(self, base ='', quote ='USDT', interval = '1h', limit= 200, start_time = 0):
        """
        Retrieves candlestick data for a given symbol and time range.

        Args:
            base (str, optional): The base asset symbol. Defaults to an empty string.
            quote (str, optional): The quote asset symbol. Defaults to 'USDT'.
            interval (str, optional): The candlestick interval. Defaults to '1h'.
            limit (int, optional): The maximum number of candlesticks to retrieve. Defaults to 200.
            start_time (int, optional): The start time of the time range in milliseconds. Defaults to 0.

        Returns:
            dict: A dictionary containing the retrieved candlestick data. The keys are 'ts' (timestamp) and 'candle'.
        """
        symbol = self.symbol_ex
        if base != '':
            symbol = f'{base}{quote}'
        candles_list = []
        if start_time != 0:
            candles_list = self.client.get_klines(symbol = symbol, 
                                                 interval = interval, 
                                                 limit = limit,
                                                 startTime = start_time)
        else:
            candles_list = self.client.get_klines(symbol = symbol, 
                                                 interval = interval, 
                                                 limit = limit)
        # candles =[]
        # for candle in list_candles:
        #     candles.append([
        #                 candle[0], # open time
        #                 candle[1], # open
        #                 candle[2], # high
        #                 candle[3], # low
        #                 candle[4], # close
        #                 candle[5], # base
        #                 candle[6],# open time
        #                 candle[7] # quote volume
        #                ])
        data = {"ts": int(time.time()*1000),"candle": candles_list}
        return data
       
    def get_fee_order(self, symbol = "", quote="USDT", 
                    strategy_params ="",
                    strategy_file ="", symbol_redis ="", 
                    exchange_name ="", start_time ="", end_time = int(time.time()*1000)):
        """
        Retrieves the fee order details for a given symbol.

        Args:
            symbol (str, optional): The symbol to retrieve the fee order for. Defaults to an empty string.
            quote (str, optional): The quote asset symbol. Defaults to 'USDT'.
            strategy_params (str, optional): The strategy parameters. Defaults to an empty string.
            strategy_file (str, optional): The strategy file name. Defaults to an empty string.
            symbol_redis (str, optional): The symbol in Redis. Defaults to an empty string.
            exchange_name (str, optional): The name of the exchange. Defaults to an empty string.
            start_time (int, optional): The start time of the fee order. Defaults to an empty string.
            end_time (int): The end time of the fee order in milliseconds. Defaults to the current time.

        Returns:
            dict: A dictionary containing the fee order details including the fee, API key, start and end times, symbol, exchange name, strategy name, and strategy parameters.
        """
        if symbol == "":
            symbol = self.symbol
        if quote == "":
            quote = self.quote
        fee_dict = {}
        list_orders = self.client.get_my_trades(symbol = f'{symbol}{quote}'.upper(), startTime = start_time, endTime = end_time)

        for item in list_orders:
            asset_commsion = f'{item["commissionAsset"]}_commsion'
            if asset_commsion not in fee_dict:
                fee_dict[asset_commsion] = 0
            fee_dict[asset_commsion] += float(item["commission"])

        fee_dict["api_key"] = self.api_key
        fee_dict['startTime'] = int(start_time)
        fee_dict["symbol"] = symbol_redis
        fee_dict["exchange_name"] = exchange_name
        fee_dict["strategy_name"] = strategy_file
        fee_dict["strategy_params"] = strategy_params
        fee_dict["endTime"] = int(end_time)
        return fee_dict

    def snap_shot_account(self, coin_list = None):
        """
        Generates a snapshot of the account balances for a given list of coins.

        Args:
            coin_list (list, optional): A list of coins for which to generate the account balances. Defaults to ['USDT', 'BTC', 'BNB'].

        Returns:
            list: A list containing three dictionaries representing the account balances. 
            The first dictionary contains the spot account balances, 
            the second dictionary contains the funding account balances, 
            and the third dictionary contains the total account balances for the given coins. 
            Each dictionary has keys in the format '{coin}_inventory' and values representing the total balance for that coin.
        """
        if coin_list is None:
            coin_list = ['USDT', 'BTC', 'BNB']

        total_balance = []
        telegram_snap_shot = {
            'type': 'TELEGRAM_TOTAL'
        }
        #SPOT
        balances_spot = {
            'type': 'SPOT'
        }
        balances_funding ={
            'type': 'FUND'
        }
        asset_snapshot = self.client.get_account()
        balances = asset_snapshot['balances']
        
        balance_asset_temp ={}
        for asset in balances:
            if asset['asset'] in coin_list:
                key = asset['asset']
                if key not in balance_asset_temp:
                    balance_asset_temp[key] = 0
                total = float(asset['free']) + float(asset['locked'])
                balances_spot_keys = f'{key}'
                balances_spot[balances_spot_keys] = total
                balance_asset_temp[key] += total
        
                
        total_balance.append(balances_spot)
        #FUNDING
        
        funding_assets_list = self.client.funding_wallet()
        for asset in funding_assets_list:
            if asset['asset'] in coin_list:
                key = asset['asset']    
                if key not in balance_asset_temp:
                    balance_asset_temp[key] = 0
                total = float(asset['free']) + float(asset['locked'])
                balances_funding_keys = f'{key}'
                balances_funding[balances_funding_keys] = total
                balance_asset_temp[key] += total
        total_balance.append(balances_funding)
        #TELEGRAM
        for asset_snap_shot in coin_list:
            if asset_snap_shot not in balance_asset_temp:
                telegram_snap_shot[asset_snap_shot] = 0
            else:
                telegram_snap_shot[asset_snap_shot] = balance_asset_temp[asset_snap_shot]
        total_balance.append(telegram_snap_shot)
        return total_balance


    def get_open_orders(self):
        """
        Retrieves a list of open orders for the current symbol.

        Returns:
            dict: A dictionary containing the list of open orders. The dictionary has the following keys:
                - 'data' (list): A list of dictionaries, where each dictionary represents an open order. Each dictionary has the following keys:
                    - 'clientOrderId' (str): The client order ID.
                    - 'quantity' (float): The original quantity of the order.
                    - 'orderId' (int): The ID of the order.
                    - 'status' (str): The status of the order.
                    - 'price' (float): The price of the order.
                    - 'side' (str): The side of the order ('BUY' for buy orders, 'SELL' for sell orders).
                    - 'fillPrice' (str): The fill price of the order. If the order is not filled, the value is '0'.
                    - 'fillSize' (float): The executed quantity of the order.
                    - 'order_type' (str): The type of the order.
                    - 'time' (int): The time the order was created.
        """
        list_orders = self.client.get_open_orders(symbol = self.symbol_ex.upper())
        open_orders = []
        for order in list_orders:
            order_format  = {
                'clientOrderId':order["clientOrderId"],
                'quantity': order["origQty"],
                'orderId':order["orderId"],
                'status':convert_order_status(order["status"]), # convert_order_status(order["status"]),
                'price':order["price"],
                'side':order["side"],
                'fillPrice':'0',
                'fillSize':order["executedQty"],
                'order_type':order["type"],
                'time':order["time"]
            }
            open_orders.append(order_format)
        return {'data':open_orders}
    
    def get_history_trade_list(self, base='', quote='USDT', limit=1000, start_time=int, end_time=int(time.time()*1000)):
        """
        Retrieves a list of historical trades for a given symbol, within a specified time range.

        Parameters:
            base (str): The base asset of the symbol (default is an empty string).
            quote (str): The quote asset of the symbol (default is 'USDT').
            limit (int): The maximum number of trades to retrieve (default is 1000).
            start_time (int): The start time of the time range in milliseconds (default is the minimum possible value).
            end_time (int): The end time of the time range in milliseconds (default is the current time in milliseconds).

        Returns:
            list: A list of historical trades, where each trade is a dictionary containing the trade details.
        """
        symbol = self.symbol_ex
        if base != '':
            symbol = f'{base}{quote}'

        end_temp = end_time
        trades = []
        fromId = None

        while True:
            time.sleep(2)
            if fromId is not None:
                re = self.client.get_historical_trades(symbol=symbol, limit=limit, fromId=fromId)
            else:
                re = self.client.get_historical_trades(symbol=symbol, limit=limit)
            start_temp = int(re[0]['time'])
            filtered_trades = [trade for trade in re if start_time <= int(trade['time']) <= end_temp]
            trades.extend(filtered_trades)
            if start_temp <= start_time:
                break
            end_temp = start_temp
            fromId = int(re[0]['id']) - limit -1
        return trades



       







