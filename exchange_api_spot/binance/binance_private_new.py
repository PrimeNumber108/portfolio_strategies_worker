import time
import sys
import os
import json
import math
import redis
from binance.spot import Spot
from logger import logger_error
from utils import calculate_gap_hours, get_candle_data_info,convert_order_status
# from  binance.client import Client
sys.path.append(os.getcwd())

FEE_PERCENT = 0.1/100
r = redis.Redis(host='localhost', port=6379, decode_responses=True)
proxy_list = [
    None,
    {'http': 'http://45.32.28.52:3128', 'https': 'http://45.32.28.52:3128'}, #stagging server
    {'http': 'http://47.129.237.109:3128', 'https': 'http://47.129.237.109:3128'}, #amazone server
    ]

class BinancePrivateNew:
    """
    Class for interacting with the Binance Spot API.
    """
    def __init__ (self, symbol, quote, api_key, secret_key, passphrase ='', use_proxy=True):
        self.symbol = symbol
        self.quote = quote
        self.symbol_ex = f'{symbol}{quote}'
        self.symbol_redis = f'{symbol}_{quote}'.upper()
        self.channels = []
        self.order_dict = {}
        self.api_key = api_key
        self.secret_key = secret_key
        # self.trade = Client(api_key, secret_key)
        self.passphrase = passphrase
        # Use proxy_list[0] (None) for no proxy, or proxy_list[1] for proxy
        proxy_to_use = proxy_list[1] if use_proxy else proxy_list[0]
        self.client = Spot(api_key, secret_key, proxies=proxy_to_use)
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
        response = self.client.exchange_info(symbol=self.symbol_ex)
        re = response['symbols'][0]
        scale_price_raw= re["filters"][0]["tickSize"]
        scale_qty_raw = re["filters"][1]["stepSize"]
        price_scale = int(-math.log10(float(scale_price_raw)))
        qty_scale =  int(-math.log10(float(scale_qty_raw)))
        return price_scale, qty_scale
    
    def delete_full_filled_order(self, order_id):
        """
        Deletes a full-filled order from the order dictionary.

        Args:
            order_id (int): The ID of the order to be deleted.

        Returns:
            None
        """
        if order_id in self.order_dict:
            self.order_dict.pop(order_id)
        
    def get_account_assets(self, coin):
        """
        Retrieves the account assets for a specific coin.

        Args:
            coin (str): The symbol of the coin.

        Returns:
            dict: A dictionary containing the asset information for the specified coin. The dictionary has the following keys:
                - 'asset' (str): The symbol of the asset.
                - 'free' (float): The amount of the asset that is not locked.
                - 'available' (float): The amount of the asset that is not locked.
                - 'locked' (float): The amount of the asset that is locked.
                - 'freeze' (float): The amount of the asset that is frozen.
                - 'total' (float): The total amount of the asset.

            If the specified coin is not found in the account balances, an empty dictionary is returned.
        """
        # {
        #     "asset": "AVAX",
        #     "free": "1",
        #     "locked": "0",
        #     "freeze": "0",
        #     "withdrawing": "0",
        #     "ipoable": "0",
        #     "btcValuation": "0"
        # },
        # result = self.client.account_snapshot(type="SPOT")
        # data = result["snapshotVos"][0]["data"]
        # for asset in data["balances"]:
        spot_assets_list = self.client.user_asset()
        data = spot_assets_list
        for asset in data:
            if asset["asset"] == coin:
                data = {
                    "asset": asset["asset"],
                    "available": float(asset["free"]),
                    "locked": float(asset["locked"]),
                    "total": float(asset["free"]) + float(asset["locked"])
                }
                return {'data':data}
        return {'data':data} #result
    def get_account_balance(self):
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
        # result = self.client.account_snapshot(type="SPOT")
        # data = result["snapshotVos"][0]["data"]
        # for asset in data["balances"]:
        account_balance = {}
        spot_assets_list = self.client.user_asset()
        data = spot_assets_list
        for asset in data:
            data = {
                    "asset": asset["asset"],
                    "available": float(asset["free"]),
                    "locked": float(asset["locked"]),
                    "total": float(asset["free"]) + float(asset["locked"])
                }
            if data["total"] > 0:
                account_balance[asset["asset"]] = data
        return {'data':account_balance} #result
    
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
      
        time_stamp = int(time.time()*1000)
        tick_dict = self.client.ticker_24hr(symbol=symbol.upper())
        tick_dict["bidPr"] = tick_dict["bidPrice"]
        tick_dict["askPr"] = tick_dict["askPrice"]
        tick_dict["bestBid"] = tick_dict["bidPrice"]
        tick_dict["bestAsk"] = tick_dict["askPrice"]
        tick_dict["bidSz"] = tick_dict["bidQty"]
        tick_dict["askSz"] = tick_dict["askQty"]
        tick_dict["last"] = tick_dict["lastPrice"]
        tick_dict["lastPr"] = tick_dict["lastPrice"]
        tick_dict["ts"] = time_stamp
        ticker_str = json.dumps(tick_dict)
        r.set(f'{self.symbol_redis}_binance_ticker', ticker_str)
        return tick_dict
    
    def place_order(self, side_order, quantity, order_type, price ='', force = 'normal', base = "", quote ="USDT"):
        """
        Places an order on the exchange.

        Args:
            side_order (str): The side of the order. Can be 'buy', 'Buy', or 'BUY' for a buy order,
                or 'sell', 'Sell', or 'SELL' for a sell order.
            quantity (float): The quantity of the asset to be traded.
            order_type (str): The type of the order. Can be 'limit', 'LIMIT', or 'Limit' for a limit order, 
                or 'market', 'MARKET', or 'Market' for a market order.
            price (str, optional): The price at which to execute the order for a limit order. Defaults to ''.
            force (str, optional): The time in force for the order. Can be 'normal' or 'GTC' (Good Till Cancelled). Defaults to 'normal'.

        Returns:
            dict or bool: If the order is successfully placed, returns a dictionary with the following keys:
                - code (int): The status code of the order.
                - data (dict): The data of the order.
            If the order is not successfully placed, returns False.
        """
        symbol = self.symbol_ex.upper()
        if base != "":
            symbol = f'{base}{quote}'.upper()
        force_ = force
        if force == 'normal':
            force_ = 'GTC'
            
        if order_type.upper() == "LIMIT":
            result = self.client.new_order(symbol = symbol,
                                           side = str(side_order).upper(),
                                           type = 'LIMIT',
                                           quantity = str(quantity),
                                           price = str(price), 
                                           timeInForce = force_)
            
        elif order_type.upper() == "MARKET":
            result = self.client.new_order(symbol = symbol,
                                           side=str(side_order).upper(),
                                           type='MARKET',
                                           quantity=str(quantity))
        else:
            result = {}
        if "orderId" in result:
            return {"code": 0, "data": result}
        return False
    
    def cancel_order(self,order_id):
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
        Retrieves the details of an order by its ID.

        Args:
            order_id (int): The ID of the order.
            symbol (str, optional): The symbol of the order. Defaults to an empty string.

        Returns:
            dict: A dictionary containing the details of the order. The dictionary has the following keys:
                - 'clientOrderId' (str): The client order ID.
                - 'quantity' (float): The quantity of the order.
                - 'orderId' (int): The ID of the order.
                - 'status' (str): The status of the order.
                - 'price' (float): The price of the order.
                - 'side' (str): The side of the order (e.g., 'BUY' or 'SELL').
                - 'fillSize' (float): The filled size of the order.
                - 'fillQuantity' (float): The filled quantity of the order.
                - 'order_type' (str): The type of the order.
                - 'fee' (str): The fee associated with the order.
                - 'createTime' (str): The creation time of the order.
                - 'orderCreateTime' (str): The creation time of the order.
                - 'updateTime' (str): The update time of the order.
                - 'orderUpdateTime' (str): The update time of the order.

                If the order is not successfully retrieved, the dictionary will have the key 'data' with a value of None.

        Raises:
            Exception: If an error occurs while retrieving the order details.

        """
        try:
            symbol = self.symbol_ex
            if base!= "":
                symbol = f"{base}{quote}".upper()
            order_detais = self.client.get_order(symbol = symbol,orderId = str(order_id))
            details = {'data':None}
            if 'orderId'in order_detais:
                details  = {'data':{
                    'clientOrderId':order_detais["clientOrderId"],
                    'quantity': order_detais["origQty"],
                    'orderId':order_detais["orderId"],
                    'status':convert_order_status(order_detais["status"]),
                    'price':order_detais["price"],
                    'side':order_detais["side"],
                    'fillSize':order_detais["executedQty"],
                    'fillQuantity':order_detais["executedQty"],
                    'order_type':order_detais["type"],
                    'orderType':order_detais["type"],
                    'fee': str(FEE_PERCENT * float(order_detais["price"]) *float(order_detais["executedQty"])),
                    'createTime':order_detais["workingTime"],
                    'orderCreateTime': order_detais["workingTime"],
                    'updateTime':order_detais["updateTime"],
                    'orderUpdateTime' :order_detais["updateTime"],
                }}
            if details['data']['status'] not in ['PARTIALLY_FILLED','FILLED']:
                details['data']['fillPrice'] = 0
            else:
                if "fills" in order_detais:
                    details['data']['fillPrice'] = order_detais['fills'][0]['price']
                else: 
                    details['data']['fillPrice'] = order_detais["price"] # Fill price is the price of the first fill
            return details
        except Exception as e:
            logger_error.error(f"{e} {e.__traceback__.tb_lineno}")
            print(f"{e} {e.__traceback__.tb_lineno}")
            return {'data':None}

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
                'status':convert_order_status(order["status"]),
                'price':order["price"],
                'side':order["side"],
                'fillPrice':'0',
                'fillSize':order["executedQty"],
                'order_type':order["type"],
                'time':order["time"]
            }
            open_orders.append(order_format)
        return {'data':open_orders}

    def get_user_asset(self):
        """
        Retrieves the user's asset information, including the base inventory, quote inventory, USDT inventory, and BNB inventory.

        Returns:
            tuple: A tuple containing the base inventory, quote inventory, USDT inventory, and BNB inventory.
        """
        spot_assets_list = self.client.user_asset()
        base_inventory, quote_inventory, quote_usdt_inventory, quote_bnb_inventory = 0, 0, 0, 0
        for asset in spot_assets_list:
            available = asset['free']
            currency = asset['asset']
            locked = float(asset['locked']) + float(asset['freeze'])

            if currency == self.quote:
                quote_inventory += float(available) + float(locked)
            if currency == "USDT":
                quote_usdt_inventory += float(available) + float(locked)
            if currency == self.symbol:
                base_inventory += float(available) + float(locked)
            if currency == "BNB":
                quote_bnb_inventory += float(available) + float(locked)

        funding_assets_list = self.client.funding_wallet()
        for asset in funding_assets_list:
            available = asset['free']
            currency = asset['asset']
            locked = float(asset['locked']) + float(asset['freeze'])
            if currency == self.quote:
                quote_inventory += float(available) + float(locked)
            if currency == "USDT":
                quote_usdt_inventory += float(available) + float(locked)
            if currency == self.symbol:
                base_inventory += float(available) + float(locked)
            if currency == "BNB":
                quote_bnb_inventory += float(available) + float(locked)
        return base_inventory, quote_inventory, quote_usdt_inventory, quote_bnb_inventory

    def get_volume_by_interval(self, symbol_input = '', quote_input ='', interval ='', start_time =''):
        """
        Retrieves the volume of a given symbol and quote within a specified interval and time range.

        Args:
            symbol_input (str): The symbol to retrieve the volume for. Defaults to an empty string, in which case the default symbol is used.
            quote_input (str): The quote currency to retrieve the volume for. Defaults to an empty string, in which case the default quote currency is used.
            interval (str): The time interval for the volume retrieval. Defaults to an empty string.
            start_time (int): The start time of the time range for the volume retrieval. Defaults to an empty string.

        Returns:
            dict: A dictionary containing the volume data. The 'data' key contains a list of candles representing the volume within the specified interval and time range.
        """
        if symbol_input =='':
            symbol_input = self.symbol
        if quote_input == '':
            quote_input = self.quote
        tick_number = calculate_gap_hours(start_time, int(time.time() * 1000))
        redis_klines = get_candle_data_info(symbol_redis=f"{symbol_input}_{quote_input}", exchange_name="binance", interval=interval, r=r)
        if redis_klines is not None:
            
            # print("redis kline:", redis_klines['candle'][-tick_number:])
            return {'data': redis_klines['candle'][-tick_number:]}
        # klines = self.client.klines(symbol = f"{symbol_input}{quote_input}",interval = interval, startTime = start_time)
        result = self.get_candles(base = symbol_input,
                            quote = quote_input,
                            interval = interval,
                            start_time = start_time,)
        # print("platform kline:", klines)
        return {'data':result['candle']}

    def get_fee_order(self, symbol ="", quote="USDT", 
                    strategy_params ="",
                    strategy_file ="", symbol_redis ="", 
                    exchange_name ="", start_time ="", end_time = int(time.time()*1000)):
        """
        Retrieves the fee information for a given symbol, quote, and time range.

        Args:
            symbol (str): The symbol to retrieve the fee information for. Defaults to an empty string, in which case the default symbol is used.
            quote (str): The quote currency to retrieve the fee information for. Defaults to an empty string, in which case the default quote currency is used.
            strategy_params (str): The strategy parameters. Defaults to an empty string.
            strategy_file (str): The strategy file. Defaults to an empty string.
            symbol_redis (str): The symbol in Redis. Defaults to an empty string.
            exchange_name (str): The name of the exchange. Defaults to an empty string.
            start_time (str): The start time of the time range for the fee retrieval. Defaults to an empty string.

        Returns:
            dict: A dictionary containing the fee information. The keys are the asset names and the values are the corresponding commissions.
        """
        if symbol == "":
            symbol = self.symbol
        if quote == "":
            quote = self.quote
        fee_dict = {}
        list_orders = self.client.my_trades(symbol = f'{symbol}{quote}'.upper(), startTime = start_time, endTime = end_time)

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
            candles_list = self.client.klines(symbol = symbol,
                                            interval = interval, 
                                            limit = 1000,
                                            startTime = start_time)
        else:
            candles_list = self.client.klines(symbol = symbol,
                                            interval = interval, 
                                            limit = limit)
        data = {"ts": int(time.time()*1000),"candle": candles_list}
        return data
    
    def snap_shot_account(self, coin_list = None):
        """
        Generates a snapshot of the account balances for a given list of coins.

        Args:
            coin_list (list, optional): A list of coins for which to generate the account balances. Defaults to None.

        Returns:
            list: A list containing three dictionaries representing the account balances. 
            The first dictionary contains the spot account balances, 
            the second dictionary contains the funding account balances, 
            and the third dictionary contains the total account balances for the given coins. 
            Each dictionary has keys in the format '{coin}_inventory' and values representing the total balance for that coin.
        """
        try:
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
            asset_snapshot = self.client.user_asset()
            # logger_error.info(f"asset_snapshot: {asset_snapshot}")
            balances = asset_snapshot
            
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
                    if key not in balance_asset_temp:
                        balance_asset_temp[key] = 0
                    key = asset['asset']    
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
        except Exception as e:
            logger_error.error(f"{e}  line {e.__traceback__.tb_lineno}  {coin_list}")