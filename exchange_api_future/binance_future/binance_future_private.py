import time
import math
import json
import redis
from  binance.client import Client
from utils import convert_order_status

r = redis.Redis(host='localhost', port=6379, decode_responses=True)
class BinanceFuturePrivate:
    """
    Class for interacting with the Binance Futures API.
    """
    def __init__ (self, symbol, quote = 'USDT', api_key = '', secret_key ='', passphrase = ''):
        self.symbol = symbol
        self.symbol_ex = f'{symbol}{quote}'
        self.symbol_redis = f'{symbol}_{quote}'.upper()
        self.quote = quote
        self.channels = []
        self.order_dict = {}
        self.api_key = api_key
        self.api_secret = secret_key
        self.trade = Client(api_key = api_key, api_secret=secret_key)
        self.passphrase = passphrase
        scale_redis = r.get(f'{self.symbol_redis}_binance_future_scale')
        if scale_redis is not None:
            scale = json.loads(scale_redis)
            self.price_scale, self.qty_scale = int(scale["priceScale"]), int(scale["qtyScale"])
        else:
            self.price_scale, self.qty_scale = self.get_scale()

    def get_scale(self):
        """
        Retrieves the price and quantity scales for the given symbol from the Binance Futures API.

        Parameters:
            None

        Returns:
            None
        """
        re = self.trade.get_symbol_info(symbol=self.symbol_ex)
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
        symbol = f'{base}_{quote}'  
        if base == "":
            symbol = self.symbol_ex
        tick_dict = self.trade.futures_ticker(symbol=symbol)
        tick_book = self.trade.futures_orderbook_ticker(symbol=symbol)
        tick_dict.update(tick_book)
        tick_dict["bidPr"] = tick_book["bidPrice"]
        tick_dict["askPr"] = tick_book["askPrice"]
        tick_dict["bestBid"] = tick_book["bidPrice"]
        tick_dict["bestAsk"] = tick_book["askPrice"]
        tick_dict["bidSz"] = tick_book["bidQty"]
        tick_dict["askSz"] = tick_book["askQty"]
        tick_dict["last"] = tick_dict["lastPrice"]
        tick_dict["lastPr"] = tick_dict["lastPrice"]
        tick_dict["ts"] = tick_book["time"]
        return tick_dict

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
        result = self.trade.futures_account_balance()
        # print(result)
        data ={"asset": '',
                    "free": 0,
                    "available": 0,
                    "locked": 0,
                    "freeze": 0,
                    "frozen": 0,
                    "total": 0}
        for asset in result:
            if asset["asset"] == coin:
                # print('asset',asset["asset"])
                data = {
                    "asset": asset["asset"],
                    "free": float(asset["availableBalance"]),
                    "available": float(asset["availableBalance"]),
                    "locked": float(asset["balance"]) - float(asset["availableBalance"]),
                    "freeze": float(asset["balance"]) - float(asset["availableBalance"]),
                    "frozen": float(asset["balance"]) - float(asset["availableBalance"]),
                    "total": float(asset["balance"])
                }
        return {'data':data} #result
       
    def place_order(self, side_order, quantity,  order_type = 'market',force = 'normal', price ='', base = "", quote ="USDT"):
        """
        Places an order on the Binance Futures exchange.

        Args:
            side_order (str): The side of the order. Can be 'buy', 'Buy', or 'BUY' for a buy order, or 'sell', 'Sell', or 'SELL' for a sell order.
            quantity (float): The quantity of the asset to be traded.
            order_type (str): The type of the order. Can be 'limit', 'LIMIT', or 'Limit' for a limit order, or 'market', 'MARKET', or 'Market' for a market order.
            force (str, optional): The time in force for the order. Can be 'normal' or 'GTC' (Good Till Cancelled). Defaults to 'normal'.
            price (str, optional): The price at which to execute the order for a limit order. Only required for limit orders.

        Returns:
            dict or bool: If the order is successfully placed, returns a dictionary with the following keys:
                - code (int): The status code of the order.
                - data (dict): The data of the order.
            If the order is not successfully placed, returns False.
        """

        symbol = self.symbol_ex
        if base != "":
            symbol = f'{base}{quote}'.upper()

        # if side_order.upper()  == 'BUY':
        #     side_order = 'LONG'
        # elif side_order.upper()  == 'SELL':
        #     side_order = 'SHORT'

        if force == 'normal':
            force_ = 'GTC'
        else:
            force_ = force
        result = False

        if order_type.upper() == "LIMIT":
            params = {'symbol':symbol.upper(), 
                      'side': str(side_order).upper(), 
                      'type':"LIMIT", 
                      'quantity':str(quantity), 
                      'price': str(price), 
                      'timeInForce':force_ }
            result = self.trade.futures_create_order(**params)
        elif order_type.upper() == "MARKET":
            params = {'symbol':symbol.upper(), 
                      'side': str(side_order).upper(), 
                      'type':"MARKET", 
                      'quantity':str(quantity),
                      'timeInForce':force_ }
            result = self.trade.futures_create_order(**params)

        if "orderId" in result:
            return {"code": 0, "data": result}
        return False
    
    def cancel_order(self, order_id):
        """
        Cancels an order with the given order ID.

        Args:
            order_id (int): The ID of the order to be cancelled.

        Returns:
            dict: A dictionary containing the result of the cancellation operation. It has the following keys:
                - 'data' (dict): The result of the cancellation operation.
        """
        params = {'symbol':self.symbol_ex, 'orderId': order_id}
        result = self.trade.futures_cancel_order(**params)
        return {'data':result}
    
    def get_order_details(self, order_id):
        """
        Retrieves the details of an order with the given order ID.

        Args:
            order_id (int): The ID of the order.

        Returns:
            dict: A dictionary containing the details of the order. The dictionary has the following keys:
                - 'data' (dict): A nested dictionary containing the details of the order. It has the following keys:
                    - 'clientOrderId' (str): The client order ID.
                    - 'quantity' (float): The original quantity of the order.
                    - 'orderId' (int): The ID of the order.
                    - 'status' (str): The status of the order.
                    - 'price' (float): The price of the order.
                    - 'side' (str): The side of the order ('LONG' for buy orders, 'SELL' for sell orders).
                    - 'fillSize' (float): The executed quantity of the order.
                    - 'fillQuantity' (float): The filled quantity of the order.
                    - 'order_type' (str): The type of the order.
                    - 'createTime' (int): The creation time of the order.
                    - 'updateTime' (int): The update time of the order.
                    - 'ts' (int): The update time of the order.
                    - 'fillPrice' (float): The fill price of the order. If the order is not filled, the value is 0.
                        If the order is filled, the value is the price of the first fill.

        Raises:
            None
        """
        params = {"symbol": self.symbol_ex.upper(), "orderId": str(order_id)}
        order_detais = self.trade.futures_get_order(**params)
        details ={}
        # If the order exists
        if 'order_id' in order_detais:
            # Initialize the details dictionary
            details  = {'data':{
                'clientOrderId': order_detais["clientOrderId"],  # Client order ID
                'quantity': order_detais["origQty"],              # Original quantity
                'orderId': order_detais["orderId"],                # Order ID
                'status': convert_order_status(order_detais["status"]),                 # Order status
                'price': order_detais["price"],                   # Order price
                'side': order_detais["side"],                     # Order side
                'fillSize': order_detais["executedQty"],          # Executed quantity
                'fillQuantity': order_detais["executedQty"],      # Fill quantity
                'order_type': order_detais["type"],               # Order type
                'createTime': order_detais["time"],       # Creation time
                'updateTime': order_detais["updateTime"], 
                'ts': order_detais["time"],         # Update time
            }}
            if details['data']['status'] not in ['PARTIALLY_FILLED', 'FILLED']:
                details['data']['fillPrice'] = 0  # Fill price is 0
            else:
                if "fills" in order_detais:
                    details['data']['fillPrice'] = order_detais['fills'][0]['price']
                else: 
                    details['data']['fillPrice'] = order_detais["price"] # Fill price is the price of the first fill

        # Return the details dictionary
        return details

    def get_open_orders(self):
        """
        Retrieves a list of open orders for the current symbol.

        Returns:
            dict: A dictionary containing the following keys:
                - 'data' (list): A list of dictionaries representing the open orders. Each dictionary contains the following keys:
                    - 'clientOrderId' (str): The client order ID.
                    - 'quantity' (float): The original quantity of the order.
                    - 'orderId' (str): The order ID.
                    - 'status' (str): The status of the order.
                    - 'price' (float): The order price.
                    - 'side' (str): The order side ('buy' or 'sell').
                    - 'fillPrice' (str): The fill price of the order ('0' if not filled).
                    - 'fillSize' (float): The executed quantity of the order.
                    - 'order_type' (str): The type of the order.
                    - 'time' (int): The creation time of the order.
                    - 'ts' (int): The update time of the order.
        """
        params = {'symbol':self.symbol_ex.upper()}
        list_oders = self.trade.futures_get_open_orders(**params)
        open_orders = []
        for order in list_oders:
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
                'time':order["time"],
                'ts':order['time']
            }
            open_orders.append(order_format)
        return {'data':open_orders}
    
    def get_candles(self, base ='', quote ='USDT', interval = '1h', limit= 200, start_time = 0):
        """
        Retrieves candlestick data for a given symbol and time interval.

        Args:
            base (str, optional): The base asset of the symbol. Defaults to ''.
            quote (str, optional): The quote asset of the symbol. Defaults to 'USDT'.
            interval (str, optional): The time interval for the candlestick data. Defaults to '1h'.
            limit (int, optional): The maximum number of candlesticks to retrieve. Defaults to 200.
            startime (int, optional): The start time of the candlestick data in milliseconds. Defaults to 0.

        Returns:
            dict: A dictionary containing the retrieved candlestick data. The dictionary has the following keys:
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
        symbol = self.symbol_ex
        if base != '':
            symbol = f'{base}{quote}'
        params = {'symbol': symbol,'interval': interval}
        if start_time != 0:
            params['startTime'] = start_time
        else:
            params['limit'] = limit
        results = self.trade.futures_klines(**params)
        # candles =[]
        # for candle in r:
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
        data = {"ts": int(time.time()*1000),"candle": results}
        return data
    
    def get_fee_order(self, symbol = "", quote = "", 
                    strategy_params ="", strategy_file ="",
                    symbol_redis ="", exchange_name ="", 
                    start_time ="", end_time = int(time.time()*1000)):
        """
        Retrieves fee information for a specific order.

        Args:
            symbol (str, optional): The symbol of the order. Defaults to "".
            quote (str, optional): The quote asset of the order. Defaults to "".
            strategy_params (str, optional): The parameters of the strategy. Defaults to "".
            strategy_file (str, optional): The name of the strategy file. Defaults to "".
            symbol_redis (str, optional): The symbol used in Redis. Defaults to "".
            exchange_name (str, optional): The name of the exchange. Defaults to "".
            start_time (str, optional): The start time of the order. Defaults to "".
            end_time (int, optional): The end time of the order in milliseconds. Defaults to the current time.

        Returns:
            dict: A dictionary containing the fee information for the order. The dictionary has the following keys:
                - 'api_key' (str): The API key used to authenticate the request.
                - 'start_time' (str): The start time of the order.
                - 'symbol' (str): The symbol used in Redis.
                - 'exchange_name' (str): The name of the exchange.
                - 'strategy_name' (str): The name of the strategy file.
                - 'strategy_params' (str): The parameters of the strategy.
                - 'end_time' (int): The end time of the order in milliseconds.
                - 'commissionAsset_commsion' (float): The commission amount for each commission asset.
        """
        if symbol == "":
            symbol = self.symbol
        if quote == "":
            quote = self.quote
            
        fee_dict = {}
        list_orders = self.trade.futures_account_trades(symbol = f'{symbol}{quote}'.upper(), startTime = start_time, endTime = end_time)

        for item in list_orders:
            asset_commsion = f'{item["commissionAsset"]}_commsion'
            if asset_commsion not in fee_dict:
                fee_dict[asset_commsion] = 0
            fee_dict[asset_commsion] += abs(float(item["commission"]))

        fee_dict["api_key"] = self.api_key
        fee_dict['startTime'] = start_time
        fee_dict["symbol"] = symbol_redis
        fee_dict["exchange_name"] = exchange_name
        fee_dict["strategy_name"] = strategy_file
        fee_dict["strategy_params"] = strategy_params
        fee_dict["endTime"] = end_time
        return fee_dict
    
    def snap_shot_account(self, coin_list = None):
        """
        Generates a snapshot of the account balances for a given list of coins.

        Args:
            coin_list (list, optional): A list of coins for which to generate the account balances. Defaults to ['METIS', 'USDT', 'BTC', 'BNB'].

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
        asset_snapshot = self.trade.get_account()
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
        funding_assets_list = self.trade.funding_wallet()
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
       
        
    def get_user_asset(self, base_asset ='', quote_asset =''):
        """
        Retrieves the user's asset information.

        Args:
            base_asset (str, optional): The base asset. Defaults to an empty string.
            quote_asset (str, optional): The quote asset. Defaults to an empty string.

        Returns:
            tuple: A tuple containing two elements:
                - balance_account (list): A list of dictionaries representing the user's asset balances for different types. Each dictionary has the following keys:
                    - type (str): The type of the account (SPOT, FUTURES, MARGIN, or FUNDING).
                    - base_inventory (float): The base asset inventory.
                    - quote_inventory (float): The quote asset inventory.
                    - quote_usdt_inventory (float): The USDT asset inventory.
                    - quote_bnb_inventory (float): The BNB asset inventory.
                - telegram_snap_shot (dict): A dictionary representing the user's asset balances for the base asset, quote asset, USDT asset, and BNB asset. The dictionary has the following keys:
                    - base_inventory (float): The base asset inventory.
                    - quote_inventory (float): The quote asset inventory.
                    - quote_usdt_inventory (float): The USDT asset inventory.
                    - quote_bnb_inventory (float): The BNB asset inventory.
        """
        if base_asset == '':
            base_asset = self.symbol
        if quote_asset == '':
            quote_asset = self.quote
        balance_account =[]
        base_inventory, quote_inventory, quote_usdt_inventory, quote_bnb_inventory = 0, 0, 0, 0
        type_list = ['SPOT', 'FUTURES', 'MARGIN']
        for type_ in type_list:
            balance = {}
            base_inventory_type, quote_inventory_type, quote_usdt_inventory_type, quote_bnb_inventory_type = 0, 0, 0, 0
            asset_snapshot = self.trade.get_account_snapshot(type = "SPOT", limit = 1)
            balances = asset_snapshot['snapshotVos'][0]['data']['balances']
            for asset in balances:
                if asset['asset'] == base_asset:
                    total = float(asset['free']) + float(asset['locked'])
                    base_inventory += total
                    base_inventory_type += total
                elif asset['asset'] == quote_asset:
                    total = float(asset['free']) + float(asset['locked'])
                    quote_inventory += total
                    quote_inventory_type += total
                elif asset['asset'] == "USDT":
                    total =float(asset['free']) + float(asset['locked'])
                    quote_usdt_inventory += total
                    quote_usdt_inventory_type += total
                elif asset['asset'] == "BNB":
                    total = float(asset['free']) +  float(asset['locked'])
                    quote_bnb_inventory += total
                    quote_bnb_inventory_type += total
                else:
                    pass
            balance['type'] = type_
            balance['base_inventory'] = base_inventory_type
            balance['quote_inventory'] = quote_inventory_type
            balance['quote_usdt_inventory'] = quote_usdt_inventory_type
            balance['quote_bnb_inventory'] = quote_bnb_inventory_type
            balance_account.append(balance)
        return base_inventory, quote_inventory, quote_usdt_inventory, quote_bnb_inventory 


    def get_position_info(self,symbol = "",quote = 'USDT'):
        """Fetch the position information for a given symbol."""
        try:
            # Fetch account position info
            positions = self.trade.futures_position_information()
            if symbol != "":
                symbol = f'{symbol}{quote}'
            else:
                symbol = self.symbol_ex
            # Find the relevant position
            for pos in positions:
                if pos['symbol'] == symbol:
                    return {
                        "symbol": pos['symbol'],
                        "positionAmt": float(pos['positionAmt']),  # Position size
                        "entryPrice": float(pos['entryPrice']),  # Average entry price
                        "unRealizedProfit": float(pos['unRealizedProfit']),  # Unrealized PnL
                        "leverage": float(pos.get('leverage', 0)),  # Leverage (0 if not found)
                        "marginType": pos.get('marginType', ""),          # Margin type
                        "liquidationPrice": float(pos['liquidationPrice']),  # Liquidation price
                    }
            
            return None

        except Exception as e:
            return f"Error: {e}"

    
        

       
    




