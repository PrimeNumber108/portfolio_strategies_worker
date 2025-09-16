import json
import time
import requests
import uuid
# from pybitget.stream import SubscribeReq
# # from pybitget.enums import TradeTypeEnum
# from pybitget import Client
import redis
from bitget.v2.spot.order_api import OrderApi
from bitget.v2.spot.account_api import AccountApi
from bitget.v2.spot.market_api import MarketApi
from logger import logger_error, logger_access, logger_database

from utils import calculate_gap_hours, get_candle_data_info, convert_order_status, make_golang_api_call
r = redis.Redis(host='localhost', port=6379, decode_responses=True)
URL = "https://api.bitget.com"

# Golang API configuration
GOLANG_API_BASE_URL = "http://localhost:8083"
class BitgetPrivateNew:
    """
    Class for interacting with the BitGet Spot API.
    """
    def __init__ (self, symbol, quote ='USDT', api_key ='', secret_key='', passphrase='', session_key=''):
        """
        Initializes a BitgetPrivate object with the provided symbol, quote, api_key, secret_key, and passphrase.

        Args:
            symbol (str): The symbol for the object.
            quote (str, optional): The quote currency, defaults to 'USDT'.
            api_key (str, optional): The API key for authentication, defaults to an empty string.
            secret_key (str, optional): The secret key for authentication, defaults to an empty string.
            passphrase (str, optional): The passphrase for authentication, defaults to an empty string.

        Returns:
            None
        """
        self.symbol = symbol
        self.symbol_ex = f'{symbol}{quote}' #SPOT _SPBL
        self.symbol_redis = f'{symbol}_{quote}'.upper()
        self.quote = quote
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase
        self.session_key = session_key or str(uuid.uuid4())  # Generate unique session key if not provided
        self.client_order = OrderApi(api_key, secret_key, passphrase)
        self.client_account = AccountApi(api_key, secret_key, passphrase)
        self.client_market = MarketApi(api_key, secret_key, passphrase)
        self.channels = []
            # multi subscribe  - Public Channels
        scale_redis = r.get(f'{self.symbol_redis}_bitget_scale')
        if scale_redis is not None:
            scale = json.loads(scale_redis)
            self.price_scale, self.qty_scale = int(scale["priceScale"]), int(scale["qtyScale"])
        else:
            self.price_scale, self.qty_scale = self.get_scale()
            scale = json.dumps({'priceScale':self.price_scale,
                                'qtyScale':self.qty_scale})
            r.set(f'{self.symbol_redis}_bitget_scale', scale)

    def get_scale(self):
        """
        This function retrieves the price and quantity scales from the Bitget API for a given symbol.
        It stores the scales in Redis and returns them as a JSON string.
        """
        price_scale, qty_scale = 0, 0        
        url = f'{URL}/api/v2/spot/public/symbols?symbol={self.symbol_ex}'
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            result = response.json()
            if result['code'] == "00000":
                item = result['data'][0]
                price_scale = item['pricePrecision']
                qty_scale = item['quantityPrecision']
        return price_scale, qty_scale

    def get_ticker(self, base = "", quote =""):
        """
        Retrieves the ticker information for a given symbol.

        Args:
            base (str, optional): The base currency of the symbol. Defaults to "".
            quote (str, optional): The quote currency of the symbol. Defaults to "".

        Returns:
            dict: A dictionary containing the ticker information. 
        """
        symbol = f'{base}{quote}'
        if base == "":
            symbol = self.symbol_ex
        params = {"symbol": symbol}
        tick_dict = self.client_market.tickers(params=params)
        tick_dict = tick_dict["data"][0]
        tick_dict["ts"] = int(tick_dict["ts"])
        tick_dict["high"] = tick_dict["high24h"]
        tick_dict["low"] = tick_dict["low24h"]
        tick_dict["open"] = tick_dict["openUtc"]
        tick_dict["last"] = tick_dict["lastPr"]
        tick_dict["bestBid"] = tick_dict["bidPr"]
        tick_dict["bestAsk"] = tick_dict["askPr"]
        ticker_str = json.dumps(tick_dict)
        r.set(f'{self.symbol_redis}_bitget_ticker', ticker_str)
        return tick_dict
    def get_candles(self, base ='', quote ='USDT', interval = '1h', limit= 200, start_time = 0):
        """
        Retrieves candlestick data for a given symbol and time range.

        Args:
            base (str, optional): The base asset symbol. Defaults to an empty string.
            quote (str, optional): The quote asset symbol. Defaults to 'USDT'.
            interval (str, optional): The candlestick interval. Defaults to '1h'.
            limit (int, optional): The maximum number of candlesticks to retrieve. Defaults to 200.
            startime (int, optional): The start time of the time range in milliseconds. Defaults to 0.

        Returns:
            dict: A dictionary containing the retrieved candlestick data. The keys are 'ts' (timestamp) and 'candle'.
        """
        interval_dict = {"1m": "1min",
                        "5m": "5min",
                        "15m": "15min",
                        "30m": "30min",
                        "1h": "1h",
                        "4h": "4h",
                        "6h": "6h",
                        "12h": "12h",
                        "1d": "1day",
                        "3d": "3day",
                        "1w": "1week",
                        "1M": "1M"}
        symbol = self.symbol_ex
        if base != '':
            symbol = f'{base}{quote}'
        candles_list = []
        granularity = interval_dict.get(interval, "1h")
        params = {"symbol": symbol, "granularity": granularity}
        if start_time == 0:
            params["limit"] = limit
        else:
            params["startTime"] = start_time

        candles_list = self.client_market.candles(params=params)
        candles =[]
        for candle in candles_list['data']:
            candles.append([
                        int(candle[0]), # open time
                        float(candle[1]), # open
                        float(candle[2]), # high
                        float(candle[3]), # low
                        float(candle[4]), # close
                        float(candle[5]), # base
                        int(candle[0]), # open time
                        float(candle[6]),# quote volume
                       ])
        data = {"ts": int(time.time()*1000), "candle": candles}
        return data

    def place_order(self, side_order:str, quantity, order_type:str, price ='',force = 'GTC', base = '', quote = 'USDT'):
        """
        Places an order on the Bitget exchange.

        Args:
            side_order (str): The side of the order. Can be 'buy', 'sell', or 'BUY' for a buy order, 
                or 'sell', 'BUY', or 'SELL' for a sell order.
            quantity (float): The quantity of the asset to be traded.
            order_type (str): The type of the order. Can be 'limit' or 'market'.
            price (str, optional): The price at which to execute the order for a limit order. Only required for limit orders.
            force (str, optional): The time in force for the order. Can be 'normal' or 'GTC' (Good Till Cancelled). Defaults to 'normal'.

        Returns:
            dict: A dictionary containing the result of the order placement operation. It has the following keys:
                - 'data' (dict): The data of the order.
                - 'code' (int): The status code of the order.
        """
        symbol = self.symbol_ex
        # If the function cannot get the input value of price, then get last price from api   
        if price == '':
            price = str(self.client_market.tickers(params={"symbol": symbol})['data'][0]['lastPr'])
        if base != "":
            symbol = f'{base}{quote}'
            
        if force == 'normal':
            force = 'GTC'
        
        # Prepare order data for Golang API storage
        order_data = {
            "symbol": symbol,
            "side": side_order.capitalize(),
            "type": order_type.lower(),
            "quantity": str(quantity),
            "timeInForce": force.lower()
        }
        if price:
            order_data["price"] = str(price)
        
        # Store order in Golang API first (pending status)
        golang_stored = self.store_order_in_golang_api(order_data, status="pending")
        if not golang_stored:
            logger_access.info("⚠️ Failed to store order in Golang API, continuing with exchange order")
            
        params = {
            "symbol": symbol,
            "side": side_order.capitalize(),
            "price": str(price) if order_type.lower() == 'limit' else '',
            "orderType": order_type.lower(),
            "size": str(quantity),
            "force": force.lower(),
            }
        if order_type.lower() == 'market' and side_order.lower == 'buy':
            params['size'] = round(float(quantity)* float(price), int(self.qty_scale))
        result = self.client_order.placeOrder(params=params)
        
        if result['code'] == "00000":
            result["code"] = 0
            # Update Golang API with exchange order ID and status
            if 'data' in result and 'orderId' in result['data']:
                exchange_order_id = str(result['data']['orderId'])
                status = "filled" if result['data'].get('status') == 'filled' else "pending"
                
                # Store/update order with exchange order ID
                if golang_stored:
                    order_data["exchange_order_id"] = exchange_order_id
                    self.store_order_in_golang_api(order_data, exchange_order_id, status)
                else:
                    self.store_order_in_golang_api(order_data, exchange_order_id, status)
                
                logger_access.info(f"✅ Bitget order placed successfully: {exchange_order_id}")
        else:
            # Order failed, update Golang API if we stored it
            if golang_stored:
                logger_access.info("❌ Bitget order failed, should update Golang API status to rejected")
            
            logger_access.info(f"❌ Bitget order failed: {result}")
            result = False
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
        params = {
            "symbol": f'{self.symbol_ex}',
            "orderId": order_id
        }
        result = self.client_order.cancelOrder(params=params)
        if result['code'] == "00000":
            result["code"] = 0
        else:
            result = False  
        return result
    
    def get_open_orders(self):
        """
        Retrieves a list of open orders for a given symbol.

        Returns:
            list: A list of dictionaries representing the open orders.
        """
        params = {
            "symbol": f'{self.symbol_ex}'
        }
        open_order_list = self.client_order.currentOrders(params=params)
        for item in open_order_list['data']:
            item['status'] = convert_order_status(item['status'])
        return open_order_list
    
    def get_order_details(self, order_id, base="", quote = "USDT"):
        """
        Retrieves the details of an order with the given order ID.

        Args:
            order_id (int): The ID of the order.

        Returns:
            dict: A dictionary containing the details of the order. The dictionary has the following keys:
                - 'data' (dict): A nested dictionary containing the details of the order. It has the following keys:
                    - 'fee' (str): The fee associated with the order.
                    - 'orderCreateTime' (int): The creation time of the order.
                    - 'orderUpdateTime' (int): The update time of the order.

        Raises:
            None
        """
        symbol = self.symbol_ex
        if base!= "":
            symbol = f"{base}{quote}"
        # logger_temp.info(f'order_id {order_id}') #print(self.order_dict)
        params = {
            "symbol": symbol,
            "orderId": order_id
        }
        re = self.client_order.orderInfos(params = params)
        order_detail = re['data'][0]
        order_detail['clientOrderId'] = order_detail.get('userId')
        order_detail['status'] = convert_order_status(order_detail['status'])
        order_detail['fee'] = order_detail.get('feeDetail')
        order_detail['fillPrice'] = order_detail.get('priceAvg')
        order_detail['fillQuantity'] = order_detail.get('baseVolume')
        order_detail['order_type'] = order_detail.get('orderType')
        order_detail['fillSize'] = float(order_detail.get('baseVolume'))
        order_detail['orderCreateTime'] = order_detail.get('cTime')    
        order_detail['orderUpdateTime'] = order_detail.get('uTime', order_detail.get('cTime'))
        return {'data':order_detail}

    def get_account_assets(self, coin):
        """
        Retrieves the account assets for a given coin.

        Args:
            coin (str): The cryptocurrency symbol of the coin.

        Returns:
            dict: A dictionary containing the account assets information. 
        """
        params = {'coin': coin}
        result = self.client_account.assets(params = params)
        data ={}
        asset = result['data'][0]
        data = {
            "asset": coin,
            "free": float(asset["available"]),
            "available": float(asset["available"]),
            "locked": float(asset["locked"]),
            "freeze": float(asset["locked"]),
            "frozen": float(asset["locked"]),
            "total": float(asset["available"]) + float(asset["locked"])
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
        result = self.client_account.assets(params = {})
        account_balance = {}
        for asset in result['data']:
            data = {
                "asset": asset["coin"],
                "available": float(asset["available"]),
                "locked": float(asset["locked"]),
                "total": float(asset["available"]) + float(asset["locked"])
            }
            if data["total"] > 0:
                account_balance[asset["coin"]] = data
        return {'data':account_balance} #result
    
    def cancel_adjust(self, order_type: str = 'all', range_upper: str = '', range_lower: str = '', side_cancel: str = "both") -> bool:
        """
        Cancels open orders based on the specified criteria.

        Args:
            order_type (str, optional): The type of cancellation. Defaults to 'all'.
                - 'all': Cancels all open orders.
                - 'cancel_range_price': Cancels open orders within a specified price range.
            range_upper (str, optional): The upper bound of the price range. Defaults to ''.
            range_lower (str, optional): The lower bound of the price range. Defaults to ''.
            side_cancel (str, optional): The side of the orders to cancel. Defaults to "both".
                - 'both': Cancels orders on both sides.
                - 'Buy': Cancels orders on the buy side.
                - 'Sell': Cancels orders on the sell side.

        Returns:
            bool: True if the cancellation was successful, False otherwise.
        """
        open_orders = self.get_open_orders()
        if order_type == 'all':
            if side_cancel == "both":
                for item in open_orders['data']:
                    self.cancel_order(item['orderId'])
            else:
                for item in open_orders['data']:
                    if item['side'] in [side_cancel, side_cancel.upper(), side_cancel.lower()]:
                        self.cancel_order(item['orderId'])
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
    
    def get_fee_order(self, symbol = "", quote="USDT", 
                    strategy_params ="", strategy_file ="", symbol_redis ="", 
                    exchange_name ="", start_time ="", end_time =int(time.time()*1000)):
        """
        Retrieves the fee information for a given symbol and quote.

        Args:
            symbol (str): The symbol for which to retrieve the fee information. 
                Defaults to an empty string, in which case the default symbol is used.
            quote (str): The quote currency for the symbol. Defaults to 'USDT'.
            strategy_params (str): The parameters for the strategy. Defaults to an empty string.
            strategy_file (str): The file name of the strategy. Defaults to an empty string.
            symbol_redis (str): The symbol used in Redis. Defaults to an empty string.
            exchange_name (str): The name of the exchange. Defaults to an empty string.
            start_time (str): The start time of the order history. Defaults to the current time in milliseconds.
            end_time (int): The end time of the order history. Defaults to the current time in milliseconds.

        Returns:
            dict: A dictionary containing the fee information, including the API key, start time, symbol, exchange name, 
                strategy name, strategy parameters, and end time. The fee information is stored in the 'fee_dict' dictionary, 
                with the asset commission as the key and the total fee as the value.
        """
        symbol_ = self.symbol_ex
        if symbol!= "":
            symbol_ = f"{symbol}{quote}"
        fee_dict = {}
        params = {"symbol":symbol_}
        list_orders = self.client_order.historyOrders(params=params)
        for item in list_orders['data']:
            if convert_order_status(item['status'])  == "FILLED":
                fee = json.loads(item['feeDetail'])
                fee_list = list(fee.items())
                symbol_in_fee = [item[0] for item in fee_list if item[0] != 'newFees']
                fee_details = fee[symbol_in_fee[0]]
                asset_commsion = f'{fee_details["feeCoinCode"]}_commsion'
                if asset_commsion not in fee_dict:
                    fee_dict[asset_commsion] = 0
                fee_dict[asset_commsion] += float(fee_details["totalFee"])

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
        Retrieves a snapshot of the account balances for a list of specified coins.

        Args:
            coin_list (list, optional): A list of coin symbols to retrieve the balances for. Defaults to ['USDT', 'BTC', 'BNB'].

        Returns:
            list: A list containing two dictionaries. The first dictionary contains the account balances for each coin in the spot market. 
                The keys are in the format '{symbol}_inventory' and the values are the total balances for each coin. 
                The second dictionary contains the account balances for each coin in the telegram market. 
                The keys are in the format '{symbol}_inventory' and the values are the total balances for each coin.
        """
        if coin_list is None:
            coin_list = ['USDT', 'BTC', 'BNB']
        total_balance = []
        balance_asset_temp ={}
        telegram_snap_shot = {
            'type': 'TELEGRAM_TOTAL'
        }
        #SPOT
        balances_spot = {
            'type': 'SPOT'
        }
        for symbol in coin_list:
            params = {'coin': symbol}
            result = self.client_account.assets(params = params)
            asset = result['data'][0]
            total = float(asset['available']) + float(asset['locked']) + float(asset['frozen'])
            balances_spot_keys = f'{symbol}'
            balances_spot[balances_spot_keys] = total
            if symbol not in balance_asset_temp:
                balance_asset_temp[symbol] = 0
            balance_asset_temp[symbol] += total
        total_balance.append(balances_spot)
        #TELEGRAM
        for asset_snap_shot in coin_list:
            if asset_snap_shot not in balance_asset_temp:
                telegram_snap_shot[asset_snap_shot] = 0
            else:
                telegram_snap_shot[asset_snap_shot] = balance_asset_temp[asset_snap_shot]
        total_balance.append(telegram_snap_shot)
        return total_balance
    
    def get_user_asset(self):
        """
        Retrieves the user's assets from the spot_accounts list and calculates the base inventory, quote inventory, 
        and USDT inventory based on the assets' availability and locks. 

        Returns:
            tuple: A tuple containing three elements:
                - base_inventory (float): The base asset inventory.
                - quote_inventory (float): The quote asset inventory.
                - quote_usdt_inventory (float): The USDT asset inventory.
        """
        params = {}
        spot_assets_list = self.client_account.assets(params = params)
        base_inventory, quote_inventory, quote_usdt_inventory = 0, 0, 0
        for asset in spot_assets_list['data']:
            if float(asset["available"]) > 0 or float(asset["locked"]) > 0 or float(asset["frozen"]) > 0:
                available = asset['available']
                currency = asset['coin']
                locked = float(asset['locked']) + float(asset['frozen'])
                if currency == self.quote:
                    quote_inventory += float(available) + float(locked)
                if currency == "USDT":
                    quote_usdt_inventory += float(available) + float(locked)
                if currency == self.symbol:
                    base_inventory += float(available) + float(locked)
        return base_inventory, quote_inventory, quote_usdt_inventory
       
    def get_volume_by_interval(self, symbol_input, quote_input, interval, start_time):
        """
        Retrieves the volume of a given symbol and quote within a specified interval and time range.

        Args:
            symbol_input (str): The symbol to retrieve the volume for.
            quote_input (str): The quote currency to retrieve the volume for.
            interval (str): The time interval for the volume retrieval.
            start_time (int): The start time of the time range for the volume retrieval.

        Returns:
            dict: A dictionary containing the volume data. The 'data' key contains a list of candles representing the volume
              within the specified interval and time range.
        """
        tick_number = calculate_gap_hours(start_time, int(time.time() * 1000))
        redis_klines = get_candle_data_info(symbol_redis=f"{symbol_input}_{quote_input}", exchange_name="bitget", interval=interval, r=r)
        if redis_klines is not None:
            return {'data': redis_klines['candle'][-tick_number:]}
        
        klines = self.get_candles(base = symbol_input, 
                                    quote =quote_input, 
                                    interval = interval, 
                                    start_time = start_time)
        return {'data':klines['candle']}
    
    def store_order_in_golang_api(self, order_data, exchange_order_id=None, status="pending"):
        """Store order data in Golang API using the new authentication utility"""
        try:
            # Prepare order data for Golang API
            golang_order_data = {
                "session_key": self.session_key,
                "symbol": order_data.get("symbol", self.symbol_ex),
                "side": order_data.get("side", "").lower(),
                "order_type": order_data.get("type", "market").lower(),
                "quantity": float(order_data.get("quantity", 0)),
                "price": float(order_data.get("price", 0)) if order_data.get("price") else 0,
                "time_in_force": order_data.get("timeInForce", "GTC"),
                "status": status,
            }
            
            # Add exchange order ID if provided
            if exchange_order_id:
                golang_order_data["exchange_order_id"] = exchange_order_id
            
            # Use the new authentication utility to make the API call
            logger_access.info(f"📝 Creating order in Golang API: {golang_order_data}")
            response = make_golang_api_call(
                method="POST",
                endpoint="/api/v1/orders/orders",
                data=golang_order_data,
                base_url=GOLANG_API_BASE_URL
            )
            
            if response and response.get("success"):
                order_id = response.get("order", {}).get("order_id")
                logger_access.info(f"✅ Order stored in Golang API with ID: {order_id}")
                
                # If we have exchange order ID, update the order
                if exchange_order_id:
                    self.update_order_in_golang_api(order_id, exchange_order_id, status)
                
                return True
            else:
                error_msg = response.get("error", "Unknown error") if response else "No response"
                logger_access.info(f"❌ Failed to store order in Golang API: {error_msg}")
                return False
                
        except Exception as e:
            logger_error.error(f"❌ Error storing order in Golang API: {str(e)}")
            return False
    
    def update_order_in_golang_api(self, order_id, exchange_order_id=None, status="pending", filled_qty=0, avg_price=0):
        """Update order status in Golang API using the new authentication utility"""
        try:
            # Validate status
            valid_statuses = ["pending", "filled", "canceled", "rejected", "partially_filled"]
            if status not in valid_statuses:
                logger_access.info(f"❌ Invalid status '{status}'. Must be one of: {valid_statuses}")
                return False
            
            update_data = {
                "status": status
            }
            
            if exchange_order_id:
                update_data["exchange_order_id"] = exchange_order_id
            if filled_qty > 0:
                update_data["filled_qty"] = filled_qty
            if avg_price > 0:
                update_data["avg_price"] = avg_price
            
            # Use the new authentication utility to make the API call
            logger_access.info(f"🔄 Updating order {order_id} with data: {update_data}")
            response = make_golang_api_call(
                method="PUT",
                endpoint=f"/api/v1/orders/{order_id}/status",
                data=update_data,
                base_url=GOLANG_API_BASE_URL
            )
            
            if response and response.get("success"):
                logger_access.info(f"✅ Order {order_id} updated in Golang API")
                return True
            else:
                error_msg = response.get("error", "Unknown error") if response else "No response"
                logger_access.info(f"❌ Failed to update order in Golang API: {error_msg}")
                return False
                
        except Exception as e:
            logger_error.error(f"❌ Error updating order in Golang API: {str(e)}")
            return False
    