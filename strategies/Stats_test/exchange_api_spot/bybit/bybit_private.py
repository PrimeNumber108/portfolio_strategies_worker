import time
import sys
import os
import json
import math
import redis
from pybit.unified_trading import HTTP
from logger import logger_bybit, logger_error, logger_access
from utils import calculate_gap_hours,get_candle_data_info,convert_order_status, ORDER_PARTIALLY_FILLED
sys.path.append(os.getcwd())



FEE_PERCENT = 0.1/100
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

class BybitPrivate:
    """
    BybitPrivate
    """
    def __init__ (self, symbol, quote = 'USDT', api_key ='', secret_key ='', passphrase ='', instype= 'spot'):
        """
        Initializes a new instance of the BybitPrivate class.

        Args:
            symbol (str): The symbol for the object.
            quote (str, optional): The quote currency, defaults to 'USDT'.
            api_key (str, optional): The API key for authentication, defaults to an empty string.
            secret_key (str, optional): The secret key for authentication, defaults to an empty string.
            passphrase (str, optional): The passphrase for authentication, defaults to an empty string.
            instype (str, optional): The type of the instance, defaults to 'spot'.

        Returns:
            None
        """
        self.symbol = symbol
        self.symbol_ex = f'{symbol}{quote}'
        self.quote = quote
        self.symbol_redis = f'{symbol}_{quote}'.upper()
        self.channels = []
        self.order_dict = {}
        self.api_key = api_key
        self.secret_key = secret_key
        self.clientws = None
        self.client = HTTP(api_key=api_key,api_secret=secret_key,testnet = False)
        self.passphrase = passphrase
        self.instype = instype
        scale_redis = r.get(f'{self.symbol_redis}_bybit_scale')
        if scale_redis is not None:
            scale = json.loads(scale_redis)
            self.price_scale, self.qty_scale = int(scale["priceScale"]), int(scale["qtyScale"])
        else:
            self.price_scale, self.qty_scale = self.get_scale()
            scale = json.dumps({'priceScale':self.price_scale,
                                'qtyScale':self.qty_scale})
            r.set(f'{self.symbol_redis}_bybit_scale', scale)

    def get_scale(self):
        """
        Retrieves the price and quantity scales for the given symbol from the Bybit API.

        Parameters:
            None

        Returns:
            str: A JSON string containing the price scale and quantity scale.
        """
        kwargs = {
            'category': self.instype,
            'symbol': self.symbol_ex,
        }
        re = self.client.get_instruments_info(**kwargs)
        exchange_info = re['result']['list']
        tick_price = exchange_info[0]['priceFilter']['tickSize']
        qty_scaleraw = exchange_info[0]['lotSizeFilter']['basePrecision']
        price_scale = int(-math.log10(float(tick_price)))
        qty_scale =  int(-math.log10(float(qty_scaleraw)))
        return price_scale, qty_scale

    def delete_full_filled_order(self,order_id):
        """
        Deletes a full-filled order from the order dictionary.

        Args:
            order_id (int): The ID of the order to be deleted.

        Returns:
            None

        This function checks if the given order ID exists in the order dictionary. If it does, it removes the order from the dictionary. It also logs the order ID using the logger_temp logger.

        Example:
            >>> bybit = BybitPrivate()
            >>> bybit.delete_full_filled_order(12345)
            INFO:root:order_id 12345
        """
        if order_id in self.order_dict:
            self.order_dict.pop(order_id)
        # logger_temp.info(f'order_id {order_id}') #logger_access.info(self.order_dict)

    def get_ticker(self, base = "", quote ="USDT"):
        """
        Retrieves the ticker information for a given symbol.

        Args:
            base (str, optional): The base currency of the symbol. Defaults to "".
            quote (str, optional): The quote currency of the symbol. Defaults to "USDT".

        Returns:
            dict: A dictionary containing the ticker information.

        This function constructs a symbol using the base and quote currencies. 
        If the base currency is empty, it uses the symbol_ex attribute. 
        It then calls the get_tickers method of the client object with the category "spot" and the constructed symbol. 
        The result is stored in the tick_dict variable. The function then updates the tick_dict dictionary with new keys 
        and values based on the data in the result. Finally, it returns the tick_dict dictionary.

        Example:
            >>> bybit = BybitPrivate()
            >>> bybit.get_ticker(base="BTC", quote="USDT")
            {'bidPr': 10000.0, 'askPr': 10001.0, 'bestBid': 10000.0, 'bestAsk': 10001.0, 'bidSz': 10.0, 'askSz': 10.0, 
                'last': 10000.5, 'lastPr': 10000.5, 'ts': 1620000000}
        """
        symbol = f'{base}{quote}'
        if base == "":
            symbol = self.symbol_ex
        re = self.client.get_tickers(category="spot",symbol=symbol)
        tick_dict = re["result"]["list"][0]
        tick_dict["bidPr"] = tick_dict["bid1Price"]
        tick_dict["askPr"] = tick_dict["ask1Price"]
        tick_dict["bestBid"] = tick_dict["bid1Price"]
        tick_dict["bestAsk"] = tick_dict["ask1Price"]
        tick_dict["bidSz"] = tick_dict["bid1Size"]
        tick_dict["askSz"] = tick_dict["ask1Size"]
        tick_dict["last"] = tick_dict["lastPrice"]
        tick_dict["lastPr"] = tick_dict["lastPrice"]
        tick_dict["ts"] = re["time"]
        r.set(f'{self.symbol_redis}_bybit_ticker', json.dumps(tick_dict))
        return tick_dict #tick_dict

    def get_account_assets(self, coin):
        """
        Retrieves the account assets for a given coin.

        Args:
            coin (str): The coin for which to retrieve the account assets.

        Returns:
            dict: A dictionary containing the account assets. The dictionary has the following keys:
                - asset (str): The asset.
                - total (float): The total balance.

        """
        data = {'asset': 0,
                'total': 0}
        account_info = self.client.get_account_info()
        if account_info['result']['unifiedMarginStatus'] == 1: #Kiểm tra account là classic hay unified
            kwargs = {'accountType':'SPOT', 'coin': coin}
            result = self.client.get_spot_asset_info(**kwargs)
            asset = result['result']['spot']['assets'][0]
            if len(asset) == 0:
                return {'data': data}
            data = {
                        "asset": coin,
                        "available": float(asset["free"]),
                        "locked": float(asset["frozen"]),
                        "total": float(asset["free"]) + float(asset["frozen"])
                    }
            return {'data':data} #result
        
        kwargs = {'accountType':'UNIFIED'}
        result = self.client.get_wallet_balance(**kwargs)
        wallet_balance = result['result']['list']    
        wallet_balance = wallet_balance[0]['coin']
        if len(wallet_balance) > 0:
            for asset in wallet_balance:
                if asset['coin'] == coin:
                    data = {
                        "asset": coin,
                        "available": float(asset["free"]) if "free" in asset else float(asset["walletBalance"]) - float(asset["locked"]),
                        "locked": float(asset["locked"]),
                        "total": float(asset["walletBalance"])
                        }
        return {'data': data}

    def get_account_balance(self):
        """
        Retrieves the account balance.

        Args:
            coin (str): The coin for which to retrieve the account assets.

        Returns:
            dict: A dictionary containing the account assets. The dictionary has the following keys:
                - asset (str): The asset.
                - total (float): The total balance.
        """
        account_info = self.client.get_account_info()
        if account_info['result']['unifiedMarginStatus'] == 1: #Kiểm tra xem account là classic hay unified
            kwargs = {'accountType':'SPOT'}
        else: 
            kwargs = {'accountType':'UNIFIED'}
        result = self.client.get_wallet_balance(**kwargs)
        account_balance = {}
        wallet_balance = result['result']['list']    
        wallet_balance = wallet_balance[0]['coin']
        if len(wallet_balance) > 0:
            for asset in wallet_balance:
                data = {
                        "asset": asset['coin'],
                        "total": float(asset["walletBalance"])
                    }
                if data["total"] > 0:
                    account_balance[asset["coin"]] = data


        return {'data':account_balance} #result
    
    def get_user_asset(self):
        """
        Retrieves the user's asset information, including the base inventory, quote inventory, USDT inventory.

        Returns:
            tuple: A tuple containing the base inventory, quote inventory, USDT inventory.
        """
        account_info = self.client.get_account_info()
        if account_info['result']['unifiedMarginStatus'] == 1: #Kiểm tra xem account là classic hay unified
            kwargs = {'accountType':'SPOT'}
        else: 
            kwargs = {'accountType':'UNIFIED'}
        result = self.client.get_wallet_balance(**kwargs)
        wallet_balance = result['result']['list']        
        base_inventory, quote_inventory, quote_usdt_inventory = 0, 0, 0
        
        if len(wallet_balance) == 0:
            return base_inventory, quote_inventory, quote_usdt_inventory
        
        wallet_balance = wallet_balance[0]['coin']

        for asset in wallet_balance:
            walletBalance = asset['walletBalance']
            coin = asset['coin']

            if coin == self.quote:
                quote_inventory += float(walletBalance)
            if coin == "USDT":
                quote_usdt_inventory += float(walletBalance)
            if coin == self.symbol:
                base_inventory += float(walletBalance)
        logger_access.info(f"BYBIT: base_inventory: {base_inventory}, quote_inventory: {quote_inventory}, quote_usdt_inventory: {quote_usdt_inventory}")
        return base_inventory, quote_inventory, quote_usdt_inventory 
    
    def place_order(self, side_order, quantity, order_type, price ='', force = 'GTC', base = '', quote = 'USDT'):
        """
        Place an order on the Bybit platform.

        Args:
            side_order (str): The side of the order (buy or sell).
            quantity (float): The quantity of the order.
            order_type (str): The type of the order (limit or market).
            price (str, optional): The price of the order (default is an empty string).
            force (str, optional): The time in force of the order (default is 'GTC').

        Returns:
            dict or bool: If the order is successfully placed, a dictionary with the following keys is returned:
                - code (int): The code indicating the success of the order placement.
                - data (dict): The result of the order placement.
            If the order placement fails, False is returned.

        This function places an order on the Bybit platform. It constructs a dictionary called kwargs with 
        the necessary parameters for the order, including the category, symbol, side, orderType, qty, price, and timeInForce. 
        It then calls the place_order method of the client object with the kwargs dictionary. If the order is successfully placed,
        a dictionary with the code and data keys is returned. If the order placement fails, False is returned.

        Example:
            >>> bybit = BybitPrivate()
            >>> bybit.place_order("buy", 1.0, "limit", "100.0", "GTC")
            {'code': 0, 'data': {'orderId': '1234567890'}}
        """
        try:
            # If the function cannot get the input value of price, then get last price from api   
            symbol = self.symbol_ex
            if base != "":
                symbol = f'{base}{quote}'
                    
            if price == '':
                price = str(self.client.get_tickers(category="spot",symbol=symbol)["result"]["list"][0]['lastPrice'])
            if force == "normal":
                force = "GTC"
            kwargs ={
                "category":self.instype,
                "symbol":symbol,
                "side":side_order,
                "orderType":order_type.capitalize(),
                "qty":quantity,
                "price":price if order_type.lower() == 'limit' else '',
                "timeInForce":force
            }
            if order_type.lower() == 'market' and side_order.lower() == 'buy':
                kwargs['qty'] = round(float(quantity)*float(price), int(self.qty_scale))
            re_place = self.client.place_order(**kwargs)
            if re_place['retMsg'] == 'OK' or re_place['retCode'] == 0:
                return {"code": 0, "data": re_place['result']}
        except Exception as e:
            logger_error.error(f"{e} {e.__traceback__.tb_lineno}")
        return  False #result
    
    def cancel_order(self,order_id):
        """
        Cancels an order with the given order ID.

        Args:
            order_id (str): The ID of the order to be cancelled.

        Returns:
            dict or bool: If the order is successfully cancelled, a dictionary with the result of the cancellation is returned.
            If the cancellation fails, False is returned.

        This function cancels an order on the Bybit platform. It constructs a dictionary called kwargs with the necessary parameters
        for the order cancellation, including the category, symbol, and orderId. It then calls the cancel_order method of the client object
        with the kwargs dictionary. If the order is successfully cancelled, a dictionary with the result of the cancellation is returned.
        If the cancellation fails, False is returned.

        Example:
            >>> bybit = BybitPrivate()
            >>> bybit.cancel_order("1234567890")
            {'retCode': 0, 'retMsg': 'OK', 'result': {'orderId': '1234567890'}}
        """
        kwargs ={
            "category":self.instype,
            "symbol":self.symbol_ex,
            "orderId":order_id
        }
        result = self.client.cancel_order(**kwargs)
        if result['retCode'] == 0:
            re_cancel = result['result']
            return re_cancel
        return False
    
    def get_order_details(self, order_id, base = '', quote = 'USDT'):
        """
        Retrieves the details of an order with the given order ID.

        Args:
            order_id (str): The ID of the order.

        Returns:
            dict: A dictionary containing the details of the order.

        This function retrieves the details of an order with the given order ID. It constructs a dictionary called kwargs
        with the necessary parameters for the order retrieval, including the category, symbol, and orderId. It then calls
        the get_order_history method of the client object with the kwargs dictionary. If the order is found in the order
        history, a dictionary with the order details is returned. If the order is not found, the function calls the
        spot_get_open_orders method to retrieve the list of open orders. It then iterates over the list and checks if
        the order ID matches. If a matching order is found, a dictionary with the order details is returned.

        Example:
            >>> bybit = BybitPrivate()
            >>> bybit.order_details("1234567890")
            {'data': {'clientOrderId': '', 'quantity': 1.0, 'orderId': '1234567890', 'status': 'PartiallyFilled', 'price': 100.0,
              'side': 'Buy', 'order_type': 'Limit', 'fillQuantity': 0.5}}
        """
        # New order has been placed successfully
        # PartiallyFilled
        # Untriggered Conditional orders are created
        # closed status

        # Rejected
        # PartiallyFilledCanceled Only spot has this order status
        # Filled
        # Cancelled In derivatives, orders with this status may have an executed qty
        # Triggered instantaneous state for conditional orders from Untriggered to New
        # Deactivated UTA: Spot tp/sl order, conditional order, OCO order are cancelled before they are triggered
        try:
            symbol = self.symbol_ex
            if base != "":
                symbol = f'{base}{quote}'
            kwargs ={
                "category":self.instype,
                "symbol":symbol,
                "orderId":order_id,
            }
            re =self.client.get_order_history(**kwargs)
            if len(re['result']['list'])>0:
                order_details = re['result']['list'][0]
                fee = str(FEE_PERCENT * float(order_details["price"]) * (float(order_details["cumExecQty"] 
                                                                              if len(order_details["cumExecQty"]) != 0  
                                                                              else int(0))))
                details  = {'data':{
                    'clientOrderId': order_details["orderLinkId"],
                    'quantity': order_details["qty"],
                    'orderId':order_details["orderId"],
                    'status': ORDER_PARTIALLY_FILLED if 0 < float(order_details["cumExecQty"]) < float(order_details["qty"]) else convert_order_status(order_details["orderStatus"]),
                    'price': order_details["price"],
                    'fillPrice':order_details["avgPrice"] if order_details["avgPrice"]!= '' else 0.0 ,
                    'side': order_details["side"],
                    'fillSize': order_details.get("cumExecQty",0),
                    'fillQuantity':order_details.get("cumExecQty", 0),
                    'order_type':order_details["orderType"],
                    'orderType':order_details["orderType"],
                    'fee': fee,
                    'createTime':order_details["createdTime"],
                    'orderCreateTime': order_details["createdTime"],
                    'updateTime':order_details["updatedTime"],
                    'orderUpdateTime' :order_details["updatedTime"],
                }}
                logger_bybit.info(f"1 :{details}")
                return details
            #Bybit đôi khi bị lỗi không trả về detail của order nếu order chỉ khớp 1 phần (PartiallyFilled), thì tìm theo detail order bằng get_open_order
            re = self.get_open_orders()
            for order in re['data']:
                if str(order['orderId']) == str(order_id):
                    fee = str(FEE_PERCENT * float(order["price"]) * (float(order["fillQuantity"])))
                    details  = {'data':{
                        'clientOrderId': order["clientOrderId"],
                        'quantity': order["quantity"],
                        'orderId':order["orderId"],
                        'status': order["status"],
                        'price':order["price"],
                        'fillPrice':order["price"],
                        'side':order["side"],
                        'fillSize': float(order["fillQuantity"])*float(order["price"]),
                        'fillQuantity':order["fillQuantity"],
                        'order_type':order["order_type"],
                        'orderType':order["order_type"],
                        'fee': fee,
                        'createTime':order["createdTime"],
                        'orderCreateTime': order["createdTime"],
                        'updateTime':order["updatedTime"],
                        'orderUpdateTime' :order["updatedTime"],
                    }}
                    logger_bybit.info(f"2 :{details}")
                    return details 
        except Exception as e:
            logger_error.error(f"{e} {e.__traceback__.tb_lineno}")
            logger_error.error(f"{e} {e.__traceback__.tb_lineno}")
        return {'data':None}

    def get_open_orders(self):
        """
        Retrieves the open orders for the current instance.

        Returns:
            dict: A dictionary containing the open orders. The dictionary has the following structure:
                - 'data' (list): A list of dictionaries representing each open order. Each dictionary has the following keys:
                    - 'clientOrderId' (str): The client order ID.
                    - 'quantity' (float): The quantity of the order.
                    - 'orderId' (int): The order ID.
                    - 'status' (str): The status of the order (currently set to 'PENDING').
                    - 'price' (float): The price of the order.
                    - 'side' (str): The side of the order (e.g., 'BUY', 'SELL').
                    - 'order_type' (str): The type of the order.
                    - 'fillQuantity' (int): The quantity filled (currently set to 0).
        """
        # Create a dictionary of parameters to pass to the API
        kwargs ={
            "category":self.instype,
            "symbol":self.symbol_ex            
        }
        # Get the open orders from the API
        re = self.client.get_open_orders(**kwargs)
        # Get the list of open orders
        open_orders = re['result']['list']
        # Create an empty list to store the formatted open orders
        open_list =[]
        # Iterate over each open order and format it
        for item in open_orders:
            # Create a dictionary with the relevant information
            item_format = {
                'clientOrderId':item['orderLinkId'],
                'quantity': item["qty"],
                'orderId':item["orderId"],
                'status':convert_order_status(item["orderStatus"]),
                'price':float(item["price"]),
                'side':item["side"],
                'order_type':item["orderType"],
                'fillQuantity': item['cumExecQty'],
                'createdTime':item["createdTime"],
                'updatedTime':item["updatedTime"],
            }
            # Add the formatted open order to the list
            open_list.append(item_format)

        # Return the list of open orders
        return {"data":open_list} #result
    
    def get_order_history(self, start_time ='', end_time = int(time.time()*1000), limit = 100):
        """
        Retrieves the order history for a given time range.

        Args:
            start_time (str, optional): The start time of the order history in milliseconds. Defaults to ''.
            end_time (int, optional): The end time of the order history in milliseconds. Defaults to the current time.
            limit (int, optional): The maximum number of orders to retrieve. Defaults to 100.

        Returns:
            list: A list of dictionaries representing the order history. Each dictionary has the following keys:
                - 'clientOrderId' (str): The client order ID.
                - 'quantity' (float): The quantity of the order.
                - 'orderId' (int): The order ID.
                - 'status' (str): The status of the order.
                - 'price' (float): The price of the order.
                - 'side' (str): The side of the order.
                - 'order_type' (str): The type of the order.
                - 'fillQuantity' (int): The quantity filled.
        """
        kwargs ={
            "category":self.instype,
            "symbol":self.symbol_ex,
            "startTime": start_time,
            "endTime":end_time,
            "limit":limit
        }
        re =self.client.get_order_history(**kwargs)
        order = re['result']['list']
        list_order = []
        for order_detais in order:
            details  = {
                'clientOrderId':'',
                'quantity': order_detais["qty"],
                'orderId':order_detais["orderId"],
                'status':convert_order_status(order_detais["orderStatus"]),
                'price':order_detais["price"],
                'side':order_detais["side"],
                'order_type':order_detais["orderType"],
                'fillQuantity': order_detais["cumExecQty"]
            }
            
            if details['orderStatus'] == 'NEW':
                details['data']['fillQuantity'] = 0

            list_order.append(details)
        return list_order
    # def spot_place_batch_orders(self, orderList):
    #     result = self.client.create_market_order()

    def cancel_adjust(self,order_type ='all', range_upper= '', range_lower='', side_cancel = "both"):
        """
        Cancels open orders based on the specified criteria.

        Args:
            type (str, optional): The type of cancellation. Defaults to 'all'.
                - 'all': Cancels all open orders.
                - 'cancel_range_price': Cancels open orders within a specified price range.
            range_upper (str, optional): The upper bound of the price range. Defaults to ''.
            range_lower (str, optional): The lower bound of the price range. Defaults to ''.
            side_cancel (str, optional): The side of the orders to cancel. Defaults to "both".
                - 'both': Cancels orders on both sides.
                - 'Buy': Cancels orders on the buy side.
                - 'Sell': Cancels orders on the sell side.

        Returns:
            None
        """
        open_orders = self.get_open_orders()
        if order_type == 'all':
            if side_cancel == "both":
                for item in open_orders['data']:
                    self.cancel_order(item['orderId'])
            elif side_cancel in ["Buy", "Sell"]:
                for item in open_orders['data']:
                    if item['side'] in [side_cancel, side_cancel.upper(), side_cancel.lower()]:
                        self.cancel_order(item['orderId'])
            else:
                logger_bybit.warning("side_cancel must be 'Buy', 'Sell' or 'both'.")
            return True
        if order_type == "cancel_range_price":
            for item in open_orders['data']:
                if range_lower <= float(item['price']) <= float(range_upper):
                    if side_cancel == "both":
                        self.cancel_order(item['orderId'])
                    else:
                        if item['side'] in [side_cancel, side_cancel.upper(), side_cancel.lower()]:
                            self.cancel_order(item['orderId'])
                    
            return True
        return False
    
    INTERVAL_MAP = {
        "3m": 3,
        "5m": 5,
        "15m": 15,
        "30m": 30,
        "1h": 60,
        "2h": 120,
        "4h": 240,
        "1d": "D",
        "1w": "W",
        "1M": "M"
    }

    def get_interval_for_api(self, interval_input):
        """
        Returns the interval value for the given interval input from the INTERVAL_MAP dictionary.
        
        Parameters:
        interval_input (str): The interval input to be looked up in the INTERVAL_MAP dictionary.
        
        Returns:
        int or str: The interval value corresponding to the interval input, or 1 if the input is not found in the dictionary.
        """
        return self.INTERVAL_MAP.get(interval_input, 1)
        
    def get_candle_data(self, symbol ='', interval='', quote_asset='', limit = 200):
        """
        Retrieves candlestick data for a given symbol and time interval.

        Args:
            symbol (str, optional): The symbol of the asset. Defaults to an empty string.
            interval (str, optional): The time interval for the candlestick data. Defaults to an empty string.
            quote_asset (str, optional): The quote asset of the symbol. Defaults to an empty string.
            limit (int, optional): The maximum number of candlesticks to retrieve. Defaults to 200.

        Returns:
            dict: A dictionary containing the retrieved candlestick data. The keys are 'ts' (timestamp) and 'candle'.
                - 'ts' (int): The timestamp of the data retrieval in milliseconds.
                - 'candle' (list): A list of candlestick data. Each candlestick is represented as a list with the following elements:
                    - open time (int): The timestamp of the opening of the candlestick in milliseconds.
                    - open (float): The opening price of the candlestick.
                    - high (float): The highest price of the candlestick.
                    - low (float): The lowest price of the candlestick.
                    - close (float): The closing price of the candlestick.
                    - base (float): The base asset volume of the candlestick.
                    - open time (int): The timestamp of the opening of the candlestick in milliseconds.
                    - quote volume (float): The quote asset volume of the candlestick.
        """
        if symbol == '':
            symbol = self.symbol
        if quote_asset =='':
            quote_asset = self.quote
        interval = self.get_interval_for_api(interval)
        kwargs = {
            'category': self.instype,
            'symbol':  f'{symbol}{quote_asset}',
            'interval': interval,
            'limit': limit,
            'info': "Info"
        } 
        price = self.client.get_kline(**kwargs)
        candles_raw = price['result']['list']
        candles =[]
        for candle in candles_raw:
            candles.append([
                        candle[0], # open time
                        candle[1], # open
                        candle[2], # high
                        candle[3], # low
                        candle[4], # close
                        candle[6], # base
                        candle[0],# open time
                        candle[5] # quote volume
                       ])
        candles.reverse()
        data = {"ts": int(time.time()*1000), "candle": candles}
        return data

    def get_fee_order(self, symbol = "", quote="USDT", 
                    strategy_params ="",
                    strategy_file ="", symbol_redis ="", 
                    exchange_name ="", start_time ="", 
                    end_time = int(time.time()*1000)):
        """
        Retrieves the fee information for a given symbol and quote asset.

        Args:
            symbol (str, optional): The symbol of the asset. Defaults to "".
            quote (str, optional): The quote asset. Defaults to "USDT".
            strategy_params (str, optional): The strategy parameters. Defaults to "".
            strategy_file (str, optional): The strategy file. Defaults to "".
            symbol_redis (str, optional): The symbol in Redis. Defaults to "".
            exchange_name (str, optional): The exchange name. Defaults to "".
            start_time (str, optional): The start time of the transaction log. Defaults to "".
            type (str, optional): The category of the transaction log. Defaults to "spot".
            end_time (int, optional): The end time of the transaction log. Defaults to the current time.

        Returns:
            dict: A dictionary containing the fee information. The dictionary has the following keys:
                - api_key (str): The API key.
                - startTime (int): The start time of the transaction log in milliseconds.
                - symbol (str): The symbol in Redis.
                - exchange_name (str): The exchange name.
                - strategy_name (str): The strategy file.
                - strategy_params (str): The strategy parameters.
                - endTime (int): The end time of the transaction log in milliseconds.
                - {asset_commsion} (float): The fee for each asset. The key is the asset name followed by "_commsion".
        """
        if symbol == "":
            symbol = self.symbol
        if quote == "":
            quote = self.quote
        order_type = 'spot'
        fee_dict = {}
        list_orders = self.client.get_transaction_log(symbol = f'{symbol}{quote}'.upper(), 
                                                      startTime = start_time, 
                                                      endTime = end_time,
                                                      category = order_type)

        for item in list_orders['result']['list']:
            asset_commsion = f'{item["currency"]}_commsion'
            if asset_commsion not in fee_dict:
                fee_dict[asset_commsion] = 0
            fee_dict[asset_commsion] += float(item["fee"])

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
            list: A list containing dictionaries representing the account balances. 
            Each dictionary has keys in the format '{coin}_inventory' and values representing the total balance for that coin.
            The list also includes a dictionary representing the total account balances for the given coins, with keys in the format '{coin}_inventory'.
        """
        if coin_list is None:
            coin_list = ['USDT', 'BTC', 'BNB']
        total_balance = []
        balance_asset_temp ={}
        telegram_snap_shot = {
            'type': 'TELEGRAM_TOTAL'
        }
        #SPOT, FUNDING
        type_list = ['SPOT','FUND']
        for type_account in type_list:
            balances_account = {}
            balances_account['type'] = type_account
            for symbol in  coin_list:
                result = self.get_account_assets(coin=symbol)
                # kwargs = {
                # 'accountType':type_account,
                # 'coin': symbol
                # }
                # result = self.client.get_coin_balance(**kwargs)
                # asset = result['result']['balance']
                # total = float(asset['walletBalance'])
                total = float(result['data']['total'])
                balances_account_keys = f'{symbol}'
                balances_account[balances_account_keys] = total
                if symbol not in balance_asset_temp:
                    balance_asset_temp[symbol] = 0
                balance_asset_temp[symbol] += total
                time.sleep(1)
            total_balance.append(balances_account)
        #TELEGRAM
        for asset_snap_shot in coin_list:
            if asset_snap_shot not in balance_asset_temp:
                telegram_snap_shot[asset_snap_shot] = 0
            else:
                telegram_snap_shot[asset_snap_shot] = balance_asset_temp[asset_snap_shot]
        total_balance.append(telegram_snap_shot)
        return total_balance

        
        # kwargs = {
        #     'accountType':'UNIFIED'
        # }
        # result = self.client.get_coins_balance(**kwargs)
        # account_balance = {}
        # wallet_balance = result['result']['balance']
        # if len(wallet_balance) > 0:  
        #     for asset in wallet_balance:
        #         data = {
        #                 "asset": asset['coin'],
        #                 "total": float(asset["walletBalance"])
        #             }
        #         if data["total"] > 0:
        #             account_balance[asset["coin"]] = data
    BYBIT_INTERVAL_MAP = {
        "5m": "5",
        "15m": "15",
        "30m": "30",
        "1h": "60",
        "4h": "240",
        "1d": "1440",
        "1w": "10080"
    }

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
            kwargs = {
                'category': 'spot',
                'symbol': symbol,
                'interval': self.BYBIT_INTERVAL_MAP.get(interval, "60"),
                'limit': limit,
                'start': start_time
            }            
        else:
            kwargs = {
                'category': 'spot',
                'symbol': symbol,
                'interval': self.BYBIT_INTERVAL_MAP.get(interval, "60"),
                'limit': limit,
            }
        # logger_access.info(kwargs)
        candles_list = self.client.get_kline(**kwargs)
        candles_list = candles_list['result']['list']
        candles = []
        for candle in candles_list:
            candles.append([
                candle[0], # open time
                candle[1], # open
                candle[2], # high
                candle[3], # low
                candle[4], # close
                candle[5], # base
                candle[0],# open time
                float(candle[5]) * float(candle[4]) # quote volume
            ])
        data = {"ts": int(time.time()*1000),"candle": candles}
        return data
    
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
        redis_klines = get_candle_data_info(symbol_redis=f"{symbol_input}_{quote_input}", exchange_name="bybit", interval=interval, r=r)
        logger_bybit.warning(f'tick_number {tick_number}')
        if redis_klines is not None:
            logger_access.info('tick_number bybit', tick_number)
            return {'data': redis_klines['candle'][-tick_number:]}
        result = self.get_candles(base = symbol_input,
                            quote = quote_input,
                            interval = "1h",
                            start_time = start_time,)
        result["candle"] = result["candle"][-tick_number:]
        logger_bybit.warning(f'reuslt candle {result["candle"]}')
        return {'data':result['candle']}

