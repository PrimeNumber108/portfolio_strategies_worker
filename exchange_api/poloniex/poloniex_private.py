import requests
import time, json
from utils import calculate_gap_hours,get_candle_data_info, convert_order_status
import redis
# from logger import logger_poloniex
from .authentication import Request
from decimal import Decimal


base_url = "https://api.poloniex.com"
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

class PoloniexPrivate:
    def __init__(self,  symbol, quote = 'USDT', api_key = '', secret_key='', passphrase=''):
        self.symbol = symbol
        self.quote = quote
        self.base = symbol
        self.symbol_ex = f'{symbol}_{self.quote}' #BTC_USDT
        self.symbol_redis = f'{symbol}_{quote}'.upper()
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url.rstrip("/")
        self.r = r
        self._request = Request(api_key, secret_key, url=base_url)
        self.qty_scale = 0
        self.price_scale = 0
        
        scale_redis = r.get(f'{self.symbol_redis}_poloniex_scale')
        if scale_redis is not None:
            scale = json.loads(scale_redis)
            self.price_scale, self.qty_scale = int(scale["priceScale"]), int(scale["qtyScale"])
        else:
            self.price_scale, self.qty_scale = self.get_scale()
            scale = json.dumps({'priceScale': self.price_scale, 'qtyScale': self.qty_scale})
            r.set(f'{self.symbol_redis}_poloniex_scale', scale)

    
    def get_candles(self, base = "", quote="", interval='1h', limit=200, start_time=0):
        candles_list = {
            "1m": "MINUTE_1",
            "5m": "MINUTE_5",
            "15m": "MINUTE_15",
            "30m": "MINUTE_30",
            "1h": "HOUR_1",
            "4h": "HOUR_4",
            "6h": "HOUR_6",
            "12h": "HOUR_12",
            "1d": "DAY_1",
            "3d": "DAY_3",
            "1w": "WEEK_1",
            "1M": "MONTH_1", 
        }
         
        symbol = f'{base}_{quote}'
        if base == "":
            symbol = self.symbol_ex
        params_map = {
            "symbol": symbol,
            "interval": candles_list.get(interval, "1h"),
            "limit": limit,
        }
        if start_time:
            params_map["startTime"] = start_time
            
        result = self._request('GET', f'/markets/{symbol}/candles', params=params_map)
        if isinstance(result, list):
            candles = []
            for item in result:
                candles.append([
                    item[12],  # open time
                    float(item[2]),  # open price
                    float(item[1]),  # high price
                    float(item[0]),  # low price
                    float(item[3]),  # close price
                    float(item[5]),  # base volume
                    item[12],  # open time (again)
                    float(item[4])   # quote volume
                ])
            return {"ts": int(time.time() * 1000), "candle": candles}
        return result
    
    
    def get_ticker(self, base = "", quote =""): 
        symbol = f'{base}_{quote}'
        if base == "":
            symbol = self.symbol_ex
            
        result = self._request('GET', f'/markets/{symbol}/ticker24h')
        if isinstance(result, dict):
            ticker_data = result
            formatted_ticker = {
                "ts": ticker_data.get("ts", int(time.time() * 1000)),
                "ts-sv": int(time.time() * 1000),
                "last": ticker_data.get("close", "0"),
                "lastPr": ticker_data.get("close", "0"),
                "baseVolume": ticker_data.get("quantity", "0"),
                "quoteVolume": ticker_data.get("amount", "0"),
                "bidPr": ticker_data.get("high", "0"),  # Note: This should probably be actual bid price
                "bestBid": ticker_data.get("high", "0"),  # Note: This should probably be actual bid price
                "askPr": ticker_data.get("low", "0"),  # Note: This should probably be actual ask price
                "bestAsk": ticker_data.get("low", "0"),  # Note: This should probably be actual ask price
                "bidSz": ticker_data.get("quantity", "0"),
                "askSz": ticker_data.get("quantity", "0")
            }
            return formatted_ticker
        return {}
    
    def get_scale(self, base = "", quote =""):
        symbol = f'{base}_{quote}'
        if base == "":
            symbol = self.symbol_ex
        result = self._request('GET', f'/markets/{symbol}')
        if isinstance(result, list) and result:
            trade_limit = result[0].get("symbolTradeLimit", {})  # Access first item in list
        else:
            raise ValueError("Unexpected response format: Expected a list with at least one dictionary")

        qty_scale = trade_limit.get("quantityScale")
        price_scale = trade_limit.get("priceScale")

        return price_scale, qty_scale
    
    def get_account_balance(self, account_type=None): 
        params = {}
        if account_type is not None:
            params.update({'accountType': account_type})

        result = self._request('GET', '/accounts/balances', True, params=params)
        if isinstance(result, list):
            for account in result:
                if "balances" in account:  
                    account_balance = {}
                    for asset in account["balances"]:
                        data = {
                            "asset": asset["currency"],
                            "available": float(asset["available"]),
                            "locked": float(asset["hold"]),
                            "total": float(asset["available"]) + float(asset["hold"])
                        }
                        if data["total"] > 0:
                            account_balance[data["asset"]] = data
            return {'data': account_balance}
        return {'data':{}}
    
    def get_account_assets(self, coin, account_type=None): 
        params = {}
        if account_type is not None:
            params.update({'accountType': account_type})

        result = self._request('GET', '/accounts/balances', True, params=params)
        # logger_poloniex.warning(f'result {result}')


        if isinstance(result, list):
            for account in result:
                if "balances" in account:  
                    for asset in account["balances"]: 
                        if asset["currency"] == coin: 
                            data = {
                                "asset": asset["currency"],
                                "available": float(asset["available"]),
                                "locked": float(asset["hold"]),
                                "total": float(asset["available"]) + float(asset["hold"])
                            }
                            return {'data': data}
        return {'data':{}}
    
    def get_user_asset(self, account_type = None):
        base_inventory, quote_inventory, quote_usdt_inventory = 0, 0, 0
        params = {}
        if account_type is not None:
            params.update({'accountType': account_type})

        result = self._request('GET', '/accounts/balances', True, params=params)
        if isinstance(result, list):
            for account in result:
                if "balances" in account: 
                    for asset in account["balances"]:
                        if float(asset["available"]) > 0 or float(asset["hold"]) > 0:
                            available = asset['available']
                            currency = asset['currency']
                            locked = float(asset['hold'])
                            if currency == self.quote:
                                quote_inventory += float(available) + float(locked)
                            if currency == "USDT":
                                quote_usdt_inventory += float(available) + float(locked)
                            if currency == self.base:
                                base_inventory += float(available) + float(locked)
        return base_inventory, quote_inventory, quote_usdt_inventory

    def get_price(self):
        symbol = f'{self.base}_{self.quote}'
        if self.base == "":
            symbol = self.symbol_ex
        return self._request('GET', f'/markets/{symbol}/price')
    
    def place_order(self, side_order, quantity, order_type, price='', force='normal'): 
        force = 'GTC' if force == 'normal' else force
        symbol = f'{self.base}_{self.quote}'
        if self.base == "":
            symbol = self.symbol_ex        
        get_price = self.get_price()
        if not get_price or 'price' not in get_price:
            raise ValueError("Failed to get current price")
        price_scale = self.price_scale
        quantity_scale = self.qty_scale
        
        params_map = {
            "symbol": symbol,
            "side": side_order.upper(),
            "type": order_type.upper(),
            "quantity": format(float(quantity), f'.{quantity_scale}f'),
            "timeInForce": force
        }
        if price:
            params_map["price"] = price
            
        if order_type.upper() == 'MARKET' and 'price' in params_map:
            del params_map['price']
        
        
        if order_type.upper() == 'MARKET' and side_order.upper() == 'BUY':
            amount_value = float(get_price.get("price"))* quantity
            del params_map['quantity']
            params_map["amount"] = format(amount_value, f'.{price_scale}f')
            
        body = {}
        body.update(params_map)
        result = self._request('POST', '/orders', True, body=body)
        print('result test: ',result)
        if result and isinstance(result, dict) and "id" in result:
            print('run 1')
            result['orderId'] = result['id']
            return {"data": result, "code": 0}
        else:
            return {"data": {}, "code": -1, "message": "Order placement failed"}
    
    def cancel_order(self, order_id=None): 
        """
        Cancel an active order. Order_id or client_order_id is required, order_id is used if both are provided.

        Args:
            order_id (str, optional): Order's id
            client_order_id (str, optional): Order's clientOrderId

        Returns:
            Json object with information on deleted order:
            {
                'orderId': (str) The order id,
                'clientOrderId': (str) clientOrderId of the order,
                'state': (str) Order's state (PENDING_CANCEL),
                'code': (int) Response code,
                'message': (str) Response message
            }
        """
        if order_id is None:
            raise ValueError('get_by_id endpoint requires order_id or client_order_id')

        if order_id is not None:
            path = f'/orders/{order_id}'
        else:
            return self.cancel_orders()

        return self._request('DELETE', path, True)
    
    def cancel_orders(self, symbol=None, account_type=None):
        symbol = f'{self.base}_{self.quote}'
        if self.base == "":
            symbol = self.symbol_ex
            
        if symbol is None and account_type is None:
            raise ValueError('orders().cancel endpoint requires symbol or account_type')

        body = {}
        if symbol is not None:
            body.update({'symbol': symbol})

        if account_type is not None:
            body.update({'accountType': account_type})

        return self._request('DELETE', '/orders', True, body=body)
    

    def get_order_details(self, order_id=None, client_order_id=None): 
        if order_id is None and client_order_id is None:
            raise ValueError('get_by_id endpoint requires order_id or client_order_id')

        if order_id is not None:
            path = f'/orders/{order_id}'
        else:
            path = f'/orders/cid:{client_order_id}'
            
        result = self._request('GET', path, True)
        if "id" in result:
            order_details = {
                "orderId": order_id or result.get("id"),
                "clientOrderId": result.get("clientOrderId", ""),
                "fillQuantity": float(result.get("filledQuantity", 0)),
                "fillSize": float(result.get("filledQuantity", 0)),
                "quantity": float(result.get("quantity", 0)),
                "fillPrice": float(result.get("price", 0)),
                "price": float(result.get("price", 0)),
                "status": convert_order_status(result.get("state", "")),
                "side": result.get("side", ""),
                "orderType": result.get("type", ""),
                "fee": result.get("fee", 0),
                "createTime": result.get("createTime", 0),
                "orderCreateTime": result.get("createTime", 0),
                "updateTime": result.get("updateTime", 0),
                "orderUpdateTime": result.get("updateTime", 0)
            }
            return {"data": order_details}
        return False
    
    def get_open_orders(self): 
        params = {}
       
        result = self._request('GET', '/orders', True, params=params)
        for item in result:
            item.update({"fillQuantity": item["filledQuantity"], 
                        "quantity": item["quantity"],
                        "fillPrice": item["price"],
                        "status": convert_order_status(item["state"]),
                        # "fee": item["sumFeeAmount"],
                        "orderType": item["type"],
                        "createTime": item["createTime"],
                        "updateTime": item["updateTime"],
                        "orderId": item["id"] 
                        })

        return {"data": result}


    def snap_shot_account(self, coin_list = None):
            """
            Generates a snapshot of the account balances for a given list of coins.
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
            spot_assets_list =  self.get_account_balance('spot')
            for keys, value in spot_assets_list['data'].items():
                balances_spot_keys = f'{keys}'
                total = value['total']
                balances_spot[balances_spot_keys] = total
                if balances_spot_keys not in balance_asset_temp:
                    balance_asset_temp[balances_spot_keys] = 0
                balance_asset_temp[balances_spot_keys] += total
            total_balance.append(balances_spot)
            #TELEGRAM
            for asset_snap_shot in coin_list:
                if asset_snap_shot not in balance_asset_temp:
                    telegram_snap_shot[asset_snap_shot] = 0
                else:
                    telegram_snap_shot[asset_snap_shot] = balance_asset_temp[asset_snap_shot]
            total_balance.append(telegram_snap_shot)
            return total_balance
    
    def get_volume_by_interval(self, symbol_input, quote_input, interval, start_time):
        redis_klines = get_candle_data_info(symbol_redis=f"{symbol_input}_{quote_input}", exchange_name="poloniex", interval=interval, r=r)
        tick_number = calculate_gap_hours(start_time, int(time.time() * 1000))
        if redis_klines is not None:
            return {'data': redis_klines['candle'][-tick_number:]}
        klines = self.get_candles(base = symbol_input, 
                                    quote =quote_input, 
                                    interval = interval, 
                                    start_time = start_time)
        return {'data':klines['candle']}