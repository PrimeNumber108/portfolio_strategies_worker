# pylint: disable=too-many-lines,too-many-public-methods
import time
import math
import json
import hmac
import hashlib
import logging
from urllib.parse import urlencode
from typing import Dict, List, Optional, Any

import requests
import redis

class BinanceFuturesOldPrivate:
    """
    Binance Futures Private API Client
    
    This class provides methods to interact with Binance's private API endpoints for futures trading.
    """
    
    def __init__(self, symbol: str, quote: str = 'USDT', api_key: str = '', 
                 secret_key: str = '', redis_client: Optional[redis.Redis] = None, 
                 redis_expiry: int = 60, testnet: bool = False):
        """
        Initialize the Binance Futures Private API client.
        
        Args:
            symbol (str): Base symbol (e.g., "BTC")
            quote (str, optional): Quote currency. Defaults to 'USDT'.
            api_key (str, optional): Your Binance API key. Defaults to ''.
            secret_key (str, optional): Your Binance API secret. Defaults to ''.
            redis_client (redis.Redis, optional): Redis client for caching. Defaults to None.
            redis_expiry (int, optional): Redis cache expiry time in seconds. Defaults to 60.
            testnet (bool, optional): Whether to use testnet. Defaults to False.
        """
        self.symbol = symbol
        self.symbol_ex = f'{symbol}{quote}'
        self.symbol_redis = f'{symbol}_{quote}'.upper()
        self.quote = quote
        self.api_key = api_key
        self.api_secret = secret_key
        self.redis_client = redis_client
        self.redis_expiry = redis_expiry
        
        # Set the base URL based on testnet flag
        if testnet:
            self.base_url = "https://testnet.binancefuture.com"
        else:
            self.base_url = "https://fapi.binance.com"
        
        # Initialize logger
        self.logger = logging.getLogger(__name__)
        
        # Initialize price and quantity scales
        self.price_scale, self.qty_scale = self._get_scale()
    
    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """
        Generate signature for API request.
        
        Args:
            params (Dict[str, Any]): Request parameters
        
        Returns:
            str: HMAC SHA256 signature
        """
        query_string = urlencode(params)
        return hmac.new(
            self.api_secret.encode(), 
            query_string.encode(), 
            hashlib.sha256
        ).hexdigest()
    
    def _send_request(self, method: str, endpoint: str, params: Dict[str, Any] = None, 
                     signed: bool = False) -> Dict[str, Any]:
        """
        Send request to Binance API.
        
        Args:
            method (str): HTTP method (GET, POST, DELETE)
            endpoint (str): API endpoint
            params (Dict[str, Any], optional): Request parameters. Defaults to None.
            signed (bool, optional): Whether the request needs authentication. Defaults to False.
        
        Returns:
            Dict[str, Any]: API response
        """
        url = f'{self.base_url}{endpoint}'
        headers = {'X-MBX-APIKEY': self.api_key} if self.api_key else {}
        
        # Initialize params if None
        if params is None:
            params = {}
            
        if signed:
            params['timestamp'] = int(time.time() * 1000)
            params['signature'] = self._generate_signature(params)
            
        try:
            response = None
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method == 'POST':
                response = requests.post(url, headers=headers, params=params, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, params=params, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
            response.raise_for_status()  # Raise exception for HTTP errors
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error("API request error: %s", e)
            return {"error": str(e)}
    
    def _get_scale(self) -> tuple:
        """
        Get price and quantity scales for the symbol.
        
        Returns:
            tuple: (price_scale, qty_scale)
        """
        # Try to get from Redis cache first
        if self.redis_client:
            try:
                cache_key = f'{self.symbol_redis}_binance_futures_scale'
                cached_data = self.redis_client.get(cache_key)
                if cached_data:
                    scale = json.loads(cached_data)
                    return int(scale["priceScale"]), int(scale["qtyScale"])
            except (redis.RedisError, json.JSONDecodeError, KeyError) as e:
                self.logger.warning("Redis error or invalid data: %s", e)
        
        # If not in cache or no Redis, fetch from API
        try:
            endpoint = '/fapi/v1/exchangeInfo'
            result = self._send_request('GET', endpoint)
            
            for symbol_info in result['symbols']:
                if symbol_info['symbol'] == self.symbol_ex:
                    price_scale = int(-math.log10(float(symbol_info["filters"][0]["tickSize"])))
                    qty_scale = int(-math.log10(float(symbol_info["filters"][1]["stepSize"])))
                    
                    # Cache in Redis if available
                    if self.redis_client:
                        scale_data = {
                            "priceScale": price_scale,
                            "qtyScale": qty_scale
                        }
                        try:
                            self.redis_client.setex(
                                cache_key,
                                self.redis_expiry,
                                json.dumps(scale_data)
                            )
                        except redis.RedisError as e:
                            self.logger.warning("Failed to cache scale in Redis: %s", e)
                    
                    return price_scale, qty_scale
            
            raise ValueError("Symbol not found")
        except Exception as e:
            self.logger.error("Error getting scale: %s", e)
            return 2, 3  # Default values
    
    def get_ticker(self) -> Dict[str, Any]:
        """
        Get ticker information for the symbol.
        
        Returns:
            Dict[str, Any]: Ticker information
        """
        endpoint = '/fapi/v1/ticker/24hr'
        params = {'symbol': self.symbol_ex}
        return self._send_request('GET', endpoint, params)
    
    def get_account_assets(self) -> List[Dict[str, Any]]:
        """
        Get account assets.
        
        Returns:
            List[Dict[str, Any]]: List of assets
        """
        endpoint = '/fapi/v2/account'
        result = self._send_request('GET', endpoint, signed=True)
        
        # Check if result contains error or assets
        if isinstance(result, dict):
            if 'error' in result:
                self.logger.error("Error getting account assets: %s", result['error'])
                return []
            if 'assets' in result:
                return result['assets']
        
        # Return empty list if no assets found or unexpected response format
        return []
    
    def place_order(self, order_side: str, quantity: float, order_type: str, 
                   price: float = None, force: str = 'GTC', 
                   reduce_only: bool = False, close_position: bool = False,
                   stop_price: float = None, working_type: str = 'CONTRACT_PRICE',
                   position_side: str = 'BOTH', time_in_force: str = None,
                   activation_price: float = None, callback_rate: float = None,
                   client_order_id: str = None) -> Dict[str, Any]:
        """
        Place an order.
        
        Args:
            order_side (str): Order side ("BUY" or "SELL")
            quantity (float): Order quantity
            order_type (str): Order type ("LIMIT", "MARKET", "STOP", "STOP_MARKET", "TAKE_PROFIT", 
                             "TAKE_PROFIT_MARKET", "TRAILING_STOP_MARKET")
            price (float, optional): Order price (required for LIMIT orders). Defaults to None.
            force (str, optional): Time in force. Defaults to 'GTC'.
                Options: "GTC" (Good Till Cancel), "IOC" (Immediate or Cancel), "FOK" (Fill or Kill), "GTX" (Post Only)
            reduce_only (bool, optional): Whether the order is reduce-only. Defaults to False.
            close_position (bool, optional): Whether to close position. Defaults to False.
            stop_price (float, optional): Stop price. Defaults to None.
            working_type (str, optional): Working type. Defaults to 'CONTRACT_PRICE'.
                Options: "CONTRACT_PRICE", "MARK_PRICE", "INDEX_PRICE"
            position_side (str, optional): Position side. Defaults to 'BOTH'.
                Options: "BOTH", "LONG", "SHORT"
            time_in_force (str, optional): Time in force (overrides force parameter). Defaults to None.
            activation_price (float, optional): Activation price for TRAILING_STOP_MARKET orders. Defaults to None.
            callback_rate (float, optional): Callback rate for TRAILING_STOP_MARKET orders. Defaults to None.
            client_order_id (str, optional): Client order ID. Defaults to None.
        
        Returns:
            Dict[str, Any]: Order placement result
        """
        endpoint = '/fapi/v1/order'
        
        # Round quantity and price to respect precision
        quantity = round(float(quantity), self.qty_scale)
        
        # Prepare parameters
        params = {
            'symbol': self.symbol_ex,
            'side': order_side.upper(),
            'type': order_type.upper(),
            'quantity': quantity
        }
        
        # Add time in force
        tif = time_in_force if time_in_force else force
        order_type_upper = order_type.upper()
        
        # Add parameters based on order type
        if order_type_upper == 'LIMIT':
            if price is None:
                raise ValueError("Price must be specified for LIMIT orders")
            params['price'] = round(float(price), self.price_scale)
            params['timeInForce'] = tif
        elif order_type_upper == 'MARKET':
            # For MARKET orders, price and timeInForce are not needed
            pass
        elif order_type_upper in ['STOP', 'TAKE_PROFIT']:
            if price is None or stop_price is None:
                raise ValueError("Price and stopPrice must be specified for STOP/TAKE_PROFIT orders")
            params['price'] = round(float(price), self.price_scale)
            params['stopPrice'] = round(float(stop_price), self.price_scale)
            params['timeInForce'] = tif
        elif order_type_upper in ['STOP_MARKET', 'TAKE_PROFIT_MARKET']:
            if stop_price is None:
                raise ValueError("stopPrice must be specified for STOP_MARKET/TAKE_PROFIT_MARKET orders")
            params['stopPrice'] = round(float(stop_price), self.price_scale)
        elif order_type_upper == 'TRAILING_STOP_MARKET':
            if callback_rate is None:
                raise ValueError("callbackRate must be specified for TRAILING_STOP_MARKET orders")
            params['callbackRate'] = callback_rate
            if activation_price is not None:
                params['activationPrice'] = round(float(activation_price), self.price_scale)
        
        # Add optional parameters
        if reduce_only:
            params['reduceOnly'] = 'true'
        
        if close_position:
            params['closePosition'] = 'true'
        
        if working_type != 'CONTRACT_PRICE':
            params['workingType'] = working_type
        
        if position_side != 'BOTH':
            params['positionSide'] = position_side
        
        if client_order_id:
            params['newClientOrderId'] = client_order_id
        
        return self._send_request('POST', endpoint, params, signed=True)
    
    def cancel_order(self, order_id: int = None, client_order_id: str = None) -> Dict[str, Any]:
        """
        Cancel an order.
        
        Args:
            order_id (int, optional): Order ID. Defaults to None.
            client_order_id (str, optional): Client order ID. Defaults to None.
        
        Returns:
            Dict[str, Any]: Order cancellation result
        """
        endpoint = '/fapi/v1/order'
        params = {'symbol': self.symbol_ex}
        
        if order_id:
            params['orderId'] = order_id
        elif client_order_id:
            params['origClientOrderId'] = client_order_id
        else:
            raise ValueError("Either order_id or client_order_id must be provided")
        
        return self._send_request('DELETE', endpoint, params, signed=True)
    
    def cancel_all_orders(self) -> Dict[str, Any]:
        """
        Cancel all open orders.
        
        Returns:
            Dict[str, Any]: Order cancellation result
        """
        endpoint = '/fapi/v1/allOpenOrders'
        params = {'symbol': self.symbol_ex}
        return self._send_request('DELETE', endpoint, params, signed=True)
    
    def get_order_details(self, order_id: int = None, client_order_id: str = None) -> Dict[str, Any]:
        """
        Get order details.
        
        Args:
            order_id (int, optional): Order ID. Defaults to None.
            client_order_id (str, optional): Client order ID. Defaults to None.
        
        Returns:
            Dict[str, Any]: Order details
        """
        endpoint = '/fapi/v1/order'
        params = {'symbol': self.symbol_ex}
        
        if order_id:
            params['orderId'] = order_id
        elif client_order_id:
            params['origClientOrderId'] = client_order_id
        else:
            raise ValueError("Either order_id or client_order_id must be provided")
        
        return self._send_request('GET', endpoint, params, signed=True)
    
    def get_open_orders(self) -> List[Dict[str, Any]]:
        """
        Get all open orders.
        
        Returns:
            List[Dict[str, Any]]: List of open orders
        """
        endpoint = '/fapi/v1/openOrders'
        params = {'symbol': self.symbol_ex}
        result = self._send_request('GET', endpoint, params, signed=True)
        
        if isinstance(result, dict) and 'error' in result:
            self.logger.error("Error getting open orders: %s", result['error'])
            return []
        
        return result if isinstance(result, list) else []
    
    def get_all_orders(self, start_time: int = None, end_time: int = None, 
                      limit: int = 500, order_id: int = None) -> List[Dict[str, Any]]:
        """
        Get all orders history.
        
        Args:
            start_time (int, optional): Start time in milliseconds. Defaults to None.
            end_time (int, optional): End time in milliseconds. Defaults to None.
            limit (int, optional): Limit of orders to return. Defaults to 500.
            order_id (int, optional): Order ID to start from. Defaults to None.
        
        Returns:
            List[Dict[str, Any]]: List of orders
        """
        endpoint = '/fapi/v1/allOrders'
        params = {
            'symbol': self.symbol_ex,
            'limit': limit
        }
        
        if start_time:
            params['startTime'] = start_time
        
        if end_time:
            params['endTime'] = end_time
        
        if order_id:
            params['orderId'] = order_id
        
        result = self._send_request('GET', endpoint, params, signed=True)
        
        if isinstance(result, dict) and 'error' in result:
            self.logger.error("Error getting all orders: %s", result['error'])
            return []
        
        return result if isinstance(result, list) else []
    
    def get_candles(self, interval: str = '1h', limit: int = 200, 
                   start_time: int = None, end_time: int = None) -> List[List[Any]]:
        """
        Get candlestick data.
        
        Args:
            interval (str, optional): Kline interval. Defaults to '1h'.
                Options: "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"
            limit (int, optional): Limit of candles to return. Defaults to 200.
            start_time (int, optional): Start time in milliseconds. Defaults to None.
            end_time (int, optional): End time in milliseconds. Defaults to None.
        
        Returns:
            List[List[Any]]: List of candles
        """
        endpoint = '/fapi/v1/klines'
        params = {
            'symbol': self.symbol_ex, 
            'interval': interval, 
            'limit': limit
        }
        
        if start_time:
            params['startTime'] = start_time
        
        if end_time:
            params['endTime'] = end_time
        
        result = self._send_request('GET', endpoint, params)
        
        if isinstance(result, dict) and 'error' in result:
            self.logger.error("Error getting candles: %s", result['error'])
            return []
        
        return result if isinstance(result, list) else []
    
    def get_trades(self, start_time: int = None, end_time: int = None, 
                  limit: int = 500, from_id: int = None) -> List[Dict[str, Any]]:
        """
        Get trade history.
        
        Args:
            start_time (int, optional): Start time in milliseconds. Defaults to None.
            end_time (int, optional): End time in milliseconds. Defaults to None.
            limit (int, optional): Limit of trades to return. Defaults to 500.
            from_id (int, optional): Trade ID to start from. Defaults to None.
        
        Returns:
            List[Dict[str, Any]]: List of trades
        """
        endpoint = '/fapi/v1/userTrades'
        params = {
            'symbol': self.symbol_ex,
            'limit': limit
        }
        
        if start_time:
            params['startTime'] = start_time
        
        if end_time:
            params['endTime'] = end_time
        
        if from_id:
            params['fromId'] = from_id
        
        result = self._send_request('GET', endpoint, params, signed=True)
        
        if isinstance(result, dict) and 'error' in result:
            self.logger.error("Error getting trades: %s", result['error'])
            return []
        
        return result if isinstance(result, list) else []
    
    def get_position(self) -> Dict[str, Any]:
        """
        Get position information for the symbol.
        
        Returns:
            Dict[str, Any]: Position information
        """
        endpoint = '/fapi/v2/positionRisk'
        params = {'symbol': self.symbol_ex}
        result = self._send_request('GET', endpoint, params=params, signed=True)
        
        # Check for errors in the response
        if isinstance(result, dict) and 'error' in result:
            self.logger.error("Error getting position: %s", result['error'])
            return {"error": result['error']}
            
        # If result is a single position (when filtered by symbol)
        if isinstance(result, dict) and result.get('symbol') == self.symbol_ex:
            return result
            
        # Process positions if result is a list
        if isinstance(result, list):
            for position in result:
                if position.get('symbol') == self.symbol_ex:
                    return position
                    
        return {"message": "No position found for the symbol."}
    
    def get_all_positions(self) -> List[Dict[str, Any]]:
        """
        Get all positions.
        
        Returns:
            List[Dict[str, Any]]: List of positions
        """
        endpoint = '/fapi/v2/positionRisk'
        result = self._send_request('GET', endpoint, signed=True)
        
        if isinstance(result, dict) and 'error' in result:
            self.logger.error("Error getting all positions: %s", result['error'])
            return []
        
        return result if isinstance(result, list) else []
    
    def change_leverage(self, leverage: int) -> Dict[str, Any]:
        """
        Change leverage for the symbol.
        
        Args:
            leverage (int): Leverage value (1-125)
        
        Returns:
            Dict[str, Any]: Leverage change result
        """
        endpoint = '/fapi/v1/leverage'
        params = {
            'symbol': self.symbol_ex,
            'leverage': leverage
        }
        return self._send_request('POST', endpoint, params, signed=True)
    
    def change_margin_type(self, margin_type: str) -> Dict[str, Any]:
        """
        Change margin type for the symbol.
        
        Args:
            margin_type (str): Margin type ("ISOLATED" or "CROSSED")
        
        Returns:
            Dict[str, Any]: Margin type change result
        """
        endpoint = '/fapi/v1/marginType'
        params = {
            'symbol': self.symbol_ex,
            'marginType': margin_type
        }
        return self._send_request('POST', endpoint, params, signed=True)
    
    def change_position_margin(self, amount: float, type_num: int) -> Dict[str, Any]:
        """
        Change position margin.
        
        Args:
            amount (float): Margin amount
            type_num (int): Type (1: Add margin, 2: Reduce margin)
        
        Returns:
            Dict[str, Any]: Position margin change result
        """
        endpoint = '/fapi/v1/positionMargin'
        params = {
            'symbol': self.symbol_ex,
            'amount': amount,
            'type': type_num
        }
        return self._send_request('POST', endpoint, params, signed=True)
    
    def get_position_margin_history(self, type_num: int = None, 
                                   start_time: int = None, end_time: int = None, 
                                   limit: int = 500) -> List[Dict[str, Any]]:
        """
        Get position margin change history.
        
        Args:
            type_num (int, optional): Type (1: Add margin, 2: Reduce margin). Defaults to None.
            start_time (int, optional): Start time in milliseconds. Defaults to None.
            end_time (int, optional): End time in milliseconds. Defaults to None.
            limit (int, optional): Limit of records to return. Defaults to 500.
        
        Returns:
            List[Dict[str, Any]]: Position margin history
        """
        endpoint = '/fapi/v1/positionMargin/history'
        params = {
            'symbol': self.symbol_ex,
            'limit': limit
        }
        
        if type_num is not None:
            params['type'] = type_num
        
        if start_time:
            params['startTime'] = start_time
        
        if end_time:
            params['endTime'] = end_time
        
        result = self._send_request('GET', endpoint, params, signed=True)
        
        if isinstance(result, dict) and 'error' in result:
            self.logger.error("Error getting position margin history: %s", result['error'])
            return []
        
        return result if isinstance(result, list) else []
    
    def get_income_history(self, income_type: str = None, 
                          start_time: int = None, end_time: int = None, 
                          limit: int = 500) -> List[Dict[str, Any]]:
        """
        Get income history.
        
        Args:
            income_type (str, optional): Income type. Defaults to None.
                Options: "TRANSFER", "WELCOME_BONUS", "REALIZED_PNL", "FUNDING_FEE", "COMMISSION", "INSURANCE_CLEAR"
            start_time (int, optional): Start time in milliseconds. Defaults to None.
            end_time (int, optional): End time in milliseconds. Defaults to None.
            limit (int, optional): Limit of records to return. Defaults to 500.
        
        Returns:
            List[Dict[str, Any]]: Income history
        """
        endpoint = '/fapi/v1/income'
        params = {
            'limit': limit
        }
        
        if self.symbol_ex:
            params['symbol'] = self.symbol_ex
        
        if income_type:
            params['incomeType'] = income_type
        
        if start_time:
            params['startTime'] = start_time
        
        if end_time:
            params['endTime'] = end_time
        
        result = self._send_request('GET', endpoint, params, signed=True)
        
        if isinstance(result, dict) and 'error' in result:
            self.logger.error("Error getting income history: %s", result['error'])
            return []
        
        return result if isinstance(result, list) else []
    
    def get_account_info(self) -> Dict[str, Any]:
        """
        Get account information.
        
        Returns:
            Dict[str, Any]: Account information
        """
        endpoint = '/fapi/v2/account'
        return self._send_request('GET', endpoint, signed=True)
    
    def get_balance(self) -> List[Dict[str, Any]]:
        """
        Get account balance.
        
        Returns:
            List[Dict[str, Any]]: Account balance
        """
        endpoint = '/fapi/v2/balance'
        result = self._send_request('GET', endpoint, signed=True)
        
        if isinstance(result, dict) and 'error' in result:
            self.logger.error("Error getting balance: %s", result['error'])
            return []
        
        return result if isinstance(result, list) else []
    
    def get_listen_key(self) -> str:
        """
        Get WebSocket listen key.
        
        Returns:
            str: Listen key
        """
        endpoint = '/fapi/v1/listenKey'
        result = self._send_request('POST', endpoint, signed=True)
        
        if isinstance(result, dict) and 'listenKey' in result:
            return result['listenKey']
        
        self.logger.error("Error getting listen key: %s", result)
        return ""
    
    def keep_alive_listen_key(self, listen_key: str) -> bool:
        """
        Keep alive WebSocket listen key.
        
        Args:
            listen_key (str): Listen key
        
        Returns:
            bool: Success status
        """
        endpoint = '/fapi/v1/listenKey'
        params = {'listenKey': listen_key}
        result = self._send_request('PUT', endpoint, params, signed=True)
        
        if isinstance(result, dict) and 'error' in result:
            self.logger.error("Error keeping listen key alive: %s", result['error'])
            return False
        
        return True
    
    def close_listen_key(self, listen_key: str) -> bool:
        """
        Close WebSocket listen key.
        
        Args:
            listen_key (str): Listen key
        
        Returns:
            bool: Success status
        """
        endpoint = '/fapi/v1/listenKey'
        params = {'listenKey': listen_key}
        result = self._send_request('DELETE', endpoint, params, signed=True)
        
        if isinstance(result, dict) and 'error' in result:
            self.logger.error("Error closing listen key: %s", result['error'])
            return False
        
        return True
    
    def get_funding_rate(self, start_time: int = None, end_time: int = None, 
                        limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get funding rate history.
        
        Args:
            start_time (int, optional): Start time in milliseconds. Defaults to None.
            end_time (int, optional): End time in milliseconds. Defaults to None.
            limit (int, optional): Limit of records to return. Defaults to 100.
        
        Returns:
            List[Dict[str, Any]]: Funding rate history
        """
        endpoint = '/fapi/v1/fundingRate'
        params = {
            'symbol': self.symbol_ex,
            'limit': limit
        }
        
        if start_time:
            params['startTime'] = start_time
        
        if end_time:
            params['endTime'] = end_time
        
        result = self._send_request('GET', endpoint, params)
        
        if isinstance(result, dict) and 'error' in result:
            self.logger.error("Error getting funding rate: %s", result['error'])
            return []
        
        return result if isinstance(result, list) else []
    
    def get_order_book(self, limit: int = 100) -> Dict[str, Any]:
        """
        Get order book.
        
        Args:
            limit (int, optional): Limit of records to return. Defaults to 100.
                Options: 5, 10, 20, 50, 100, 500, 1000
        
        Returns:
            Dict[str, Any]: Order book
        """
        endpoint = '/fapi/v1/depth'
        params = {
            'symbol': self.symbol_ex,
            'limit': limit
        }
        return self._send_request('GET', endpoint, params)
    
    def get_recent_trades(self, limit: int = 500) -> List[Dict[str, Any]]:
        """
        Get recent trades.
        
        Args:
            limit (int, optional): Limit of records to return. Defaults to 500.
        
        Returns:
            List[Dict[str, Any]]: Recent trades
        """
        endpoint = '/fapi/v1/trades'
        params = {
            'symbol': self.symbol_ex,
            'limit': limit
        }
        result = self._send_request('GET', endpoint, params)
        
        if isinstance(result, dict) and 'error' in result:
            self.logger.error("Error getting recent trades: %s", result['error'])
            return []
        
        return result if isinstance(result, list) else []
    
    def get_historical_trades(self, limit: int = 500, from_id: int = None) -> List[Dict[str, Any]]:
        """
        Get historical trades.
        
        Args:
            limit (int, optional): Limit of records to return. Defaults to 500.
            from_id (int, optional): Trade ID to start from. Defaults to None.
        
        Returns:
            List[Dict[str, Any]]: Historical trades
        """
        endpoint = '/fapi/v1/historicalTrades'
        params = {
            'symbol': self.symbol_ex,
            'limit': limit
        }
        
        if from_id:
            params['fromId'] = from_id
        
        result = self._send_request('GET', endpoint, params)
        
        if isinstance(result, dict) and 'error' in result:
            self.logger.error("Error getting historical trades: %s", result['error'])
            return []
        
        return result if isinstance(result, list) else []
    
    def get_aggregate_trades(self, start_time: int = None, end_time: int = None, 
                            limit: int = 500, from_id: int = None) -> List[Dict[str, Any]]:
        """
        Get aggregate trades.
        
        Args:
            start_time (int, optional): Start time in milliseconds. Defaults to None.
            end_time (int, optional): End time in milliseconds. Defaults to None.
            limit (int, optional): Limit of records to return. Defaults to 500.
            from_id (int, optional): Trade ID to start from. Defaults to None.
        
        Returns:
            List[Dict[str, Any]]: Aggregate trades
        """
        endpoint = '/fapi/v1/aggTrades'
        params = {
            'symbol': self.symbol_ex,
            'limit': limit
        }
        
        if start_time:
            params['startTime'] = start_time
        
        if end_time:
            params['endTime'] = end_time
        
        if from_id:
            params['fromId'] = from_id
        
        result = self._send_request('GET', endpoint, params)
        
        if isinstance(result, dict) and 'error' in result:
            self.logger.error("Error getting aggregate trades: %s", result['error'])
            return []
        
        return result if isinstance(result, list) else []
    
    def close_position(self) -> Dict[str, Any]:
        """
        Close all open positions for the current symbol by placing an opposite market order.
        
        Returns:
            Dict[str, Any]: Order placement result
        """
        position = self.get_position()
        
        # Check for errors in position response
        if 'error' in position:
            return position
            
        # Check if there's an active position
        if position and 'positionAmt' in position and float(position['positionAmt']) != 0:
            side = 'SELL' if float(position['positionAmt']) > 0 else 'BUY'
            quantity = abs(float(position['positionAmt']))
            
            # Round quantity to respect the quantity scale
            quantity = round(quantity, self.qty_scale)
            
            return self.place_order(order_side=side, quantity=quantity, order_type='MARKET')
            
        return {"message": "No open position to close."}