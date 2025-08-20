#!/usr/bin/env python3
"""
Paper Trading Implementation
This module provides paper trading functionality that simulates real trading
using cached data from Redis and stores orders in paper_order table.
"""

import os
import sys
import time
import json
import uuid
import requests
from decimal import Decimal
from typing import Dict, Optional, Any, List
import redis

# Add the parent directory to the path to import our modules
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../../"))
sys.path.insert(0, PROJECT_ROOT)

from utils import (
    get_candle_data_info, 
    convert_order_status, 
    calculate_gap_hours,
    get_line_number,
    update_key_and_insert_error_log,
    generate_random_string
)
from logger import logger_database, logger_error

# Redis configuration
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Go API configuration
# GOLANG_API_BASE_URL = os.environ.get('GOLANG_API_URL', 'http://localhost:8080')
GOLANG_API_BASE_URL = 'http://localhost:8080'

class PaperTrade:
    """
    Paper Trading implementation that simulates real exchange functionality
    using cached data from Redis and stores fake orders in database.
    """
    
    def __init__(self, symbol='BTC', quote='USDT', api_key='', secret_key='', 
                 passphrase='', session_key='', initial_balance=10000, exchange='binance'):
        """
        Initialize paper trading client
        
        Args:
            symbol (str): Base symbol (e.g., 'BTC')
            quote (str): Quote symbol (e.g., 'USDT')
            api_key (str): API key (not used in paper trading but kept for compatibility)
            secret_key (str): Secret key (not used in paper trading)
            passphrase (str): Passphrase (not used in paper trading)
            session_key (str): Session key for tracking
            initial_balance (float): Initial balance for paper trading
        """
        self.symbol = symbol
        self.quote = quote
        self.base = symbol
        self.symbol_ex = f'{symbol}_{quote}'  # BTC_USDT
        self.symbol_redis = f'{symbol}_{quote}'.upper()
        self.api_key = api_key or 'paper_trade'
        self.secret_key = secret_key or 'paper_trade'
        self.session_key = session_key or str(uuid.uuid4())
        self.exchange = exchange
        self.r = r
        
        # Get exchange from environment variable (default to binance if not set)
        self.exchange = os.environ.get('PAPER_TRADE_EXCHANGE', 'binance').lower()
        self.initial_balance = initial_balance
        
        # Initialize scales
        self.qty_scale = 6
        self.price_scale = 2
        self._load_scales()
        
        # Initialize account balances via Go API if not exists
        self._init_account_balance()
        
        print(f"✅ Paper Trade initialized for {self.symbol}/{self.quote} using {self.exchange} data")
        logger_database.info(f"Paper Trade initialized: {self.symbol}/{self.quote}, exchange: {self.exchange}")

    def _load_scales(self):
        """Load price and quantity scales from Redis cache"""
        try:
            scale_redis = self.r.get(f'{self.symbol_redis}_{self.exchange}_scale')
            if scale_redis is not None:
                scale = json.loads(scale_redis)
                self.price_scale = int(scale.get("priceScale", 2))
                self.qty_scale = int(scale.get("qtyScale", 6))
                print(f"📊 Loaded scales from Redis - Price: {self.price_scale}, Qty: {self.qty_scale}")
            else:
                # Try to get scales from exchange data
                self.price_scale, self.qty_scale = self.get_scale()
                print(f"📊 Fetched new scales - Price: {self.price_scale}, Qty: {self.qty_scale}")
        except Exception as e:
            print(f"⚠️ Could not load scales, using defaults: {e}")
            self.price_scale = 2
            self.qty_scale = 6

    def _init_account_balance(self):
        """Initialize account balances via Go API if they don't exist"""
        try:
            # Check if balances already exist by trying to get them
            balance_response = self._api_call('GET', f'/api/v1/paper/balances?session_key={self.session_key}')
            
            if balance_response and balance_response.get('success') and balance_response.get('data'):
                print(f"✅ Paper balances already exist for session {self.session_key}")
                return
            
            # Initialize balances if they don't exist
            init_data = {
                "session_key": self.session_key,
                "base_currency": self.base,
                "quote_currency": self.quote,
                "initial_balance": self.initial_balance
            }
            
            response = self._api_call('POST', '/api/v1/paper/balances', data=init_data)
            
            if response and response.get('success'):
                print(f"✅ Initialized paper balance: {self.initial_balance} {self.quote}")
                logger_database.info(f"Initialized paper balance for session {self.session_key}")
            else:
                error_msg = response.get('error', 'Unknown error') if response else 'No response from API'
                print(f"⚠️ Failed to initialize balances: {error_msg}")
                
        except Exception as e:
            print(f"❌ Failed to initialize account balance: {e}")
            logger_error.error(f"Paper balance init error: {e}")

    def _api_call(self, method: str, endpoint: str, data: dict = None) -> Dict:
        """
        Make API call to Go paper trade service
        
        Args:
            method (str): HTTP method (GET, POST, etc.)
            endpoint (str): API endpoint
            data (dict): Request data for POST requests
            
        Returns:
            dict: API response
        """
        try:
            url = f"{GOLANG_API_BASE_URL}{endpoint}"
            
            if method.upper() == 'GET':
                response = requests.get(url, timeout=10)
            elif method.upper() == 'POST':
                response = requests.post(url, json=data, timeout=10)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"⚠️ API call failed: {response.status_code} - {response.text}")
                return {'success': False, 'error': f'HTTP {response.status_code}'}
                
        except requests.exceptions.RequestException as e:
            print(f"❌ API request failed: {e}")
            logger_error.error(f"Paper trade API call error: {e}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            print(f"❌ API call error: {e}")
            logger_error.error(f"Paper trade API call error: {e}")
            return {'success': False, 'error': str(e)}

    def get_scale(self, base='', quote='') -> tuple:
        """
        Get price and quantity scales from exchange first, then Redis cache as fallback
        
        Args:
            base (str): Base currency
            quote (str): Quote currency
            
        Returns:
            tuple: (price_scale, quantity_scale)
        """
        try:
            symbol = f'{base}_{quote}' if base else self.symbol_ex
            symbol_redis = symbol.upper()
            
            # First try to get from actual exchange using get_client_exchange
            try:
                # Lazy import to avoid circular dependency
                from exchange_api_spot.user import get_client_exchange
                
                acc_info = {
                    'api_key': 'demo_key',
                    'secret_key': 'demo_secret',
                    'passphrase': ''
                }
                
                exchange_client = get_client_exchange(
                    exchange_name=self.exchange,
                    acc_info=acc_info,
                    symbol=base or self.base,
                    quote=quote or self.quote
                )
                
                if exchange_client and hasattr(exchange_client, 'get_scale'):
                    price_scale, qty_scale = exchange_client.get_scale(base, quote)
                    
                    # Cache the result in Redis for future use
                    scale_json = json.dumps({'priceScale': price_scale, 'qtyScale': qty_scale})
                    scale_key = f'{symbol_redis}_{self.exchange}_scale'
                    self.r.set(scale_key, scale_json)
                    
                    # Cache in instance variables
                    if not base:  # If getting for main symbol
                        self.price_scale = price_scale
                        self.qty_scale = qty_scale
                    
                    print(f"📊 Got scales from {self.exchange} exchange - Price: {price_scale}, Qty: {qty_scale}")
                    return price_scale, qty_scale
                        
            except Exception as e:
                print(f"⚠️ Could not get scales from {self.exchange} exchange: {e}")
            
            # Fallback to Redis cache
            scale_key = f'{symbol_redis}_{self.exchange}_scale'
            scale_data = self.r.get(scale_key)
            
            if scale_data:
                scale = json.loads(scale_data)
                price_scale = int(scale.get("priceScale", 2))
                qty_scale = int(scale.get("qtyScale", 6))
                
                # Cache in instance variables
                if not base:  # If getting for main symbol
                    self.price_scale = price_scale
                    self.qty_scale = qty_scale
                
                print(f"📊 Got scales from Redis cache - Price: {price_scale}, Qty: {qty_scale}")
                return price_scale, qty_scale
            else:
                print(f"⚠️ No scale data found for {symbol_redis}_{self.exchange}, using defaults")
                return 2, 6  # Default scales
                
        except Exception as e:
            print(f"❌ Error getting scale: {e}")
            logger_error.error(f"Paper trade get_scale error: {e}")
            return 2, 6

    def get_price(self, base='', quote='') -> Dict[str, Any]:
        """
        Get current price from exchange first, then Redis cache as fallback
        
        Args:
            base (str): Base currency
            quote (str): Quote currency
            
        Returns:
            dict: Price data from exchange or Redis cache
        """
        try:
            symbol = f'{base}_{quote}' if base else self.symbol_ex
            symbol_redis = symbol.upper()
            
            # First try to get from actual exchange using get_client_exchange
            try:
                # Lazy import to avoid circular dependency
                from exchange_api_spot.user import get_client_exchange
                
                acc_info = {
                    'api_key': 'demo_key',
                    'secret_key': 'demo_secret',
                    'passphrase': ''
                }
                
                exchange_client = get_client_exchange(
                    exchange_name=self.exchange,
                    acc_info=acc_info,
                    symbol=base or self.base,
                    quote=quote or self.quote
                )
                
                if exchange_client and hasattr(exchange_client, 'get_price'):
                    price_data = exchange_client.get_price(base, quote)
                    
                    if price_data:
                        # Cache the result in Redis for future use
                        price_key = f'{symbol_redis}_{self.exchange}_price'
                        self.r.set(price_key, json.dumps(price_data))
                        
                        print(f"💰 Got price from {self.exchange} exchange: {price_data.get('price', 'N/A')}")
                        return price_data
                        
            except Exception as e:
                print(f"⚠️ Could not get price from {self.exchange} exchange: {e}")
            
            # Fallback to Redis cache
            price_keys = [
                f'{symbol_redis}_{self.exchange}_price',
                f'{symbol_redis}_{self.exchange}_ticker',
                f'{symbol_redis}_{self.exchange}',
            ]
            
            for price_key in price_keys:
                price_data = self.r.get(price_key)
                if price_data:
                    try:
                        data = json.loads(price_data)
                        # Handle different data formats
                        if isinstance(data, dict):
                            if 'price' in data:
                                print(f"💰 Got price from Redis cache: {data['price']}")
                                return {'price': str(data['price']), 'ts': int(time.time() * 1000)}
                            elif 'last' in data:
                                print(f"💰 Got price from Redis cache: {data['last']}")
                                return {'price': str(data['last']), 'ts': int(time.time() * 1000)}
                            elif 'lastPr' in data:
                                print(f"💰 Got price from Redis cache: {data['lastPr']}")
                                return {'price': str(data['lastPr']), 'ts': int(time.time() * 1000)}
                        elif isinstance(data, (int, float, str)):
                            print(f"💰 Got price from Redis cache: {data}")
                            return {'price': str(data), 'ts': int(time.time() * 1000)}
                    except json.JSONDecodeError:
                        # If it's a plain number string
                        try:
                            float(price_data)
                            print(f"💰 Got price from Redis cache: {price_data}")
                            return {'price': str(price_data), 'ts': int(time.time() * 1000)}
                        except ValueError:
                            continue
            
            print(f"⚠️ No price data found for {symbol_redis}_{self.exchange}")
            return None
            
        except Exception as e:
            print(f"❌ Error getting price: {e}")
            logger_error.error(f"Paper trade get_price error: {e}")
            return None

    def get_ticker(self, base='', quote='') -> Dict[str, Any]:
        """
        Get ticker data from exchange first, then Redis cache as fallback
        
        Args:
            base (str): Base currency
            quote (str): Quote currency
            
        Returns:
            dict: Ticker data from exchange or Redis cache
        """
        try:
            symbol = f'{base}_{quote}' if base else self.symbol_ex
            symbol_redis = symbol.upper()
            
            # First try to get from actual exchange using get_client_exchange
            try:
                # Lazy import to avoid circular dependency
                from exchange_api_spot.user import get_client_exchange
                
                acc_info = {
                    'api_key': 'demo_key',
                    'secret_key': 'demo_secret',
                    'passphrase': ''
                }
                
                exchange_client = get_client_exchange(
                    exchange_name=self.exchange,
                    acc_info=acc_info,
                    symbol=base or self.base,
                    quote=quote or self.quote
                )
                
                if exchange_client and hasattr(exchange_client, 'get_ticker'):
                    ticker_data = exchange_client.get_ticker(base, quote)
                    
                    if ticker_data and isinstance(ticker_data, dict):
                        # Cache the result in Redis for future use
                        ticker_key = f'{symbol_redis}_{self.exchange}_ticker'
                        self.r.set(ticker_key, json.dumps(ticker_data))
                        
                        print(f"📊 Got ticker from {self.exchange} exchange")
                        return ticker_data
                        
            except Exception as e:
                print(f"⚠️ Could not get ticker from {self.exchange} exchange: {e}")
            
            # Fallback to Redis cache
            ticker_key = f'{symbol_redis}_{self.exchange}_ticker'
            ticker_data = self.r.get(ticker_key)
            
            if ticker_data:
                data = json.loads(ticker_data)
                if isinstance(data, dict):
                    print(f"📊 Got ticker from Redis cache")
                    return data
            
            # Fallback to price data if ticker not available
            price_data = self.get_price(base, quote)
            if price_data:
                ticker = {
                    "ts": price_data.get("ts", int(time.time() * 1000)),
                    "last": price_data.get("price", "0"),
                    "lastPr": price_data.get("price", "0"),
                    "bidPr": price_data.get("price", "0"),
                    "askPr": price_data.get("price", "0"),
                    "baseVolume": "0",
                    "quoteVolume": "0"
                }
                print(f"📊 Generated ticker from price data")
                return ticker
            
            print(f"⚠️ No ticker data found for {symbol_redis}_{self.exchange}")
            return {}
            
        except Exception as e:
            print(f"❌ Error getting ticker: {e}")
            logger_error.error(f"Paper trade get_ticker error: {e}")
            return {}

    def get_candles(self, base='', quote='', interval='1h', limit=200, start_time=0) -> Dict[str, Any]:
        """
        Get candle data from exchange first, then Redis cache as fallback
        
        Args:
            base (str): Base currency
            quote (str): Quote currency
            interval (str): Time interval
            limit (int): Number of candles
            start_time (int): Start time
            
        Returns:
            dict: Candle data from exchange or Redis cache
        """
        try:
            symbol = f'{base}_{quote}' if base else self.symbol_ex
            symbol_redis = symbol.upper()
            
            # First try to get from actual exchange using get_client_exchange
            try:
                # Lazy import to avoid circular dependency
                from exchange_api_spot.user import get_client_exchange
                
                acc_info = {
                    'api_key': 'demo_key',
                    'secret_key': 'demo_secret',
                    'passphrase': ''
                }
                
                exchange_client = get_client_exchange(
                    exchange_name=self.exchange,
                    acc_info=acc_info,
                    symbol=base or self.base,
                    quote=quote or self.quote
                )
                
                if exchange_client and hasattr(exchange_client, 'get_candles'):
                    candle_data = exchange_client.get_candles(base, quote, interval, limit, start_time)
                    
                    if candle_data and isinstance(candle_data, dict) and 'candle' in candle_data:
                        # Cache the result in Redis for future use (optional, as candles are large)
                        # We could implement caching here if needed
                        
                        print(f"📈 Got {len(candle_data.get('candle', []))} candles from {self.exchange} exchange")
                        return candle_data
                        
            except Exception as e:
                print(f"⚠️ Could not get candles from {self.exchange} exchange: {e}")
            
            # Fallback to Redis cache
            redis_klines = get_candle_data_info(
                symbol_redis=symbol_redis, 
                exchange_name=self.exchange, 
                interval=interval, 
                r=self.r
            )
            
            if redis_klines and 'candle' in redis_klines:
                candles = redis_klines['candle']
                if start_time:
                    # Filter candles from start_time
                    filtered_candles = []
                    for candle in candles:
                        if len(candle) > 0 and candle[0] >= start_time:
                            filtered_candles.append(candle)
                    candles = filtered_candles[-limit:] if limit else filtered_candles
                else:
                    candles = candles[-limit:] if limit else candles
                
                print(f"📈 Got {len(candles)} candles from Redis cache")
                return {
                    "ts": int(time.time() * 1000),
                    "candle": candles
                }
            
            print(f"⚠️ No candle data found for {symbol_redis}_{self.exchange}")
            return {"ts": int(time.time() * 1000), "candle": []}
            
        except Exception as e:
            print(f"❌ Error getting candles: {e}")
            logger_error.error(f"Paper trade get_candles error: {e}")
            return {"ts": int(time.time() * 1000), "candle": []}

    def get_account_balance(self, account_type=None) -> Dict[str, Any]:
        """
        Get account balance from paper trading via Go API
        
        Args:
            account_type (str): Account type (not used in paper trading)
            
        Returns:
            dict: Account balance data
        """
        try:
            response = self._api_call('GET', f'/api/v1/paper/balances?session_key={self.session_key}')
            
            if response and response.get('success'):
                return {'data': response.get('data', {})}
            else:
                error_msg = response.get('error', 'Unknown error') if response else 'No response from API'
                print(f"❌ Error getting account balance: {error_msg}")
                return {'data': {}}
                
        except Exception as e:
            print(f"❌ Error getting account balance: {e}")
            logger_error.error(f"Paper trade get_account_balance error: {e}")
            return {'data': {}}

    def get_account_assets(self, coin, account_type=None) -> Dict[str, Any]:
        """
        Get specific coin balance from paper trading via Go API
        
        Args:
            coin (str): Currency to get balance for
            account_type (str): Account type (not used in paper trading)
            
        Returns:
            dict: Balance data for specific currency
        """
        try:
            response = self._api_call('GET', f'/api/v1/paper/balances?session_key={self.session_key}')
            
            if response and response.get('success'):
                balances = response.get('data', {})
                if coin in balances:
                    return {'data': balances[coin]}
                else:
                    # Return empty balance for requested coin
                    return {
                        'data': {
                            "asset": coin,
                            "available": 0.0,
                            "locked": 0.0,
                            "total": 0.0
                        }
                    }
            else:
                print(f"❌ Error getting account assets: {response.get('error', 'Unknown error') if response else 'No response'}")
                return {'data': {}}
                
        except Exception as e:
            print(f"❌ Error getting account assets: {e}")
            logger_error.error(f"Paper trade get_account_assets error: {e}")
            return {'data': {}}

    def get_user_asset(self, account_type=None) -> tuple:
        """
        Get user asset balances for base, quote, and USDT
        
        Args:
            account_type (str): Account type (not used in paper trading)
            
        Returns:
            tuple: (base_inventory, quote_inventory, usdt_inventory)
        """
        try:
            balance_data = self.get_account_balance()
            balances = balance_data.get('data', {})
            
            base_inventory = balances.get(self.base, {}).get('total', 0)
            quote_inventory = balances.get(self.quote, {}).get('total', 0)
            usdt_inventory = balances.get('USDT', {}).get('total', 0)
            
            # If quote is not USDT, use quote inventory as USDT equivalent
            if self.quote != 'USDT':
                usdt_inventory = quote_inventory
                
            return float(base_inventory), float(quote_inventory), float(usdt_inventory)
            
        except Exception as e:
            print(f"❌ Error getting user assets: {e}")
            logger_error.error(f"Paper trade get_user_asset error: {e}")
            return 0.0, 0.0, 0.0

    def place_order(self, side_order, quantity, order_type, price='', force='normal') -> Dict[str, Any]:
        """
        Place a paper trade order via Go API (simulate real order with database storage)
        
        Args:
            side_order (str): 'BUY' or 'SELL'
            quantity (float): Order quantity
            order_type (str): 'MARKET' or 'LIMIT'
            price (str): Order price (for limit orders)
            force (str): Time in force
            
        Returns:
            dict: Order result with order details
        """
        try:
            # Get current price for market orders
            current_price_data = self.get_price()
            if not current_price_data:
                return {
                    'code': -1,
                    'message': 'Cannot get current price for paper trading',
                    'data': None
                }
            
            current_price = float(current_price_data['price'])
            
            # Determine execution price
            if order_type.upper() == 'MARKET':
                execution_price = current_price
            else:
                execution_price = float(price) if price else current_price
            
            # Prepare order data for Go API
            order_data = {
                "session_key": self.session_key,
                "symbol": self.symbol_ex,
                "side": side_order.upper(),
                "order_type": order_type.upper(),
                "quantity": quantity,
                "price": execution_price,
                "exchange": self.exchange,
                "quote": self.quote
            }
            
            # Make API call to place order
            response = self._api_call('POST', '/api/v1/paper/orders', data=order_data)
            
            if response and response.get('success'):
                order_result = response.get('data', {})
                
                print(f"✅ Paper trade order placed: {side_order} {quantity} {self.base} at {execution_price}")
                logger_database.info(f"Paper trade order: {order_result.get('order_id')}, {side_order}, {quantity}@{execution_price}")
                
                return {
                    'code': 0,
                    'message': 'Paper trade order placed successfully',
                    'data': {
                        'orderId': order_result.get('order_id'),
                        'symbol': order_result.get('symbol'),
                        'side': order_result.get('side'),
                        'type': order_result.get('type'),
                        'quantity': order_result.get('quantity'),
                        'price': order_result.get('price'),
                        'status': order_result.get('status'),
                        'filledQuantity': order_result.get('filled_quantity'),
                        'avgPrice': order_result.get('avg_price'),
                        'fee': order_result.get('fee'),
                        'createTime': order_result.get('create_time')
                    }
                }
            else:
                error_msg = response.get('error', 'Unknown error') if response else 'No response from API'
                print(f"❌ Failed to place paper order: {error_msg}")
                return {
                    'code': -1,
                    'message': f'Paper trade order failed: {error_msg}',
                    'data': None
                }
            
        except Exception as e:
            print(f"❌ Error placing paper trade order: {e}")
            logger_error.error(f"Paper trade place_order error: {e}")
            update_key_and_insert_error_log(
                self.session_key, self.symbol, get_line_number(),
                "PAPER_TRADE", "paper_trade.py", f"Place order error: {e}"
            )
            return {
                'code': -1,
                'message': f'Paper trade order failed: {str(e)}',
                'data': None
            }



    def get_order_details(self, order_id=None, client_order_id=None) -> Dict[str, Any]:
        """
        Get paper trade order details via Go API
        
        Args:
            order_id (str): Order ID
            client_order_id (str): Client order ID
            
        Returns:
            dict: Order details
        """
        try:
            if not order_id and not client_order_id:
                raise ValueError('Order ID or client order ID required')
            
            # Use order_id or client_order_id
            target_id = order_id or client_order_id
            
            response = self._api_call('GET', f'/api/v1/paper/orders/{target_id}?session_key={self.session_key}')
            
            if response and response.get('success'):
                order_data = response.get('data', {})
                
                return {
                    "orderId": order_data.get("order_id"),
                    "symbol": order_data.get("symbol"),
                    "side": order_data.get("side"),
                    "orderType": order_data.get("order_type"),
                    "quantity": float(order_data.get("quantity", 0)),
                    "price": float(order_data.get("price", 0)),
                    "status": order_data.get("status"),
                    "fillQuantity": float(order_data.get("filled_quantity", 0)),
                    "fillPrice": float(order_data.get("avg_price", 0)),
                    "fee": float(order_data.get("fee", 0)),
                    "createTime": order_data.get("create_time"),
                    "updateTime": order_data.get("update_time")
                }
            else:
                print(f"❌ Order not found or API error: {response.get('error') if response else 'No response'}")
                return None
                
        except Exception as e:
            print(f"❌ Error getting order details: {e}")
            logger_error.error(f"Paper trade get_order_details error: {e}")
            return None

    def get_open_orders(self, symbol=None) -> Dict[str, Any]:
        """
        Get open paper trade orders via Go API (in paper trading, most orders are immediately filled)
        
        Args:
            symbol (str): Trading symbol
            
        Returns:
            dict: List of open orders
        """
        try:
            # Build query parameters
            params = [f'session_key={self.session_key}', 'status=NEW,PENDING']
            
            if symbol:
                params.append(f'symbol={symbol}')
                
            query_string = '&'.join(params)
            
            response = self._api_call('GET', f'/api/v1/paper/orders?{query_string}')
            
            if response and response.get('success'):
                orders_data = response.get('data', [])
                
                # Format orders to match expected structure
                orders = []
                for order_data in orders_data:
                    orders.append({
                        "orderId": order_data.get("order_id"),
                        "symbol": order_data.get("symbol"),
                        "side": order_data.get("side"),
                        "orderType": order_data.get("order_type"),
                        "quantity": float(order_data.get("quantity", 0)),
                        "price": float(order_data.get("price", 0)),
                        "status": order_data.get("status"),
                        "fillQuantity": float(order_data.get("filled_quantity", 0)),
                        "createTime": order_data.get("create_time")
                    })
                
                return {"data": orders}
            else:
                print(f"❌ Error getting open orders: {response.get('error') if response else 'No response'}")
                return {"data": []}
                
        except Exception as e:
            print(f"❌ Error getting open orders: {e}")
            logger_error.error(f"Paper trade get_open_orders error: {e}")
            return {"data": []}

    def cancel_order(self, order_id) -> Dict[str, Any]:
        """
        Cancel a paper trade order via Go API
        
        Args:
            order_id (str): Order ID to cancel
            
        Returns:
            dict: Cancellation result
        """
        try:
            # In paper trading, orders are usually immediately filled,
            # but we'll implement cancellation for completeness
            response = self._api_call('DELETE', f'/api/v1/paper/orders/{order_id}?session_key={self.session_key}')
            
            if response and response.get('success'):
                print(f"✅ Paper trade order {order_id} canceled")
                return {'code': 0, 'message': 'Order canceled successfully'}
            else:
                error_msg = response.get('error', 'Unknown error') if response else 'No response from API'
                print(f"❌ Failed to cancel order: {error_msg}")
                return {'code': -1, 'message': f'Cancel failed: {error_msg}'}
                
        except Exception as e:
            print(f"❌ Error canceling order: {e}")
            logger_error.error(f"Paper trade cancel_order error: {e}")
            return {'code': -1, 'message': f'Cancel failed: {str(e)}'}

    def snap_shot_account(self, coin_list=None) -> List[Dict]:
        """
        Generate account balance snapshot for paper trading
        
        Args:
            coin_list (list): List of coins to include in snapshot
            
        Returns:
            list: Account balance snapshot
        """
        try:
            if coin_list is None:
                coin_list = ['USDT', 'BTC', 'BNB']
                
            balance_data = self.get_account_balance()
            balances = balance_data.get('data', {})
            
            total_balance = []
            balance_asset_temp = {}
            
            # Paper trading spot balances
            balances_spot = {'type': 'PAPER_SPOT'}
            
            for currency, balance in balances.items():
                total = balance['total']
                balances_spot[currency] = total
                balance_asset_temp[currency] = total
                
            total_balance.append(balances_spot)
            
            # Telegram summary
            telegram_snap_shot = {'type': 'PAPER_TELEGRAM_TOTAL'}
            for asset in coin_list:
                telegram_snap_shot[asset] = balance_asset_temp.get(asset, 0)
                
            total_balance.append(telegram_snap_shot)
            
            return total_balance
            
        except Exception as e:
            print(f"❌ Error generating account snapshot: {e}")
            logger_error.error(f"Paper trade snap_shot_account error: {e}")
            return []

    def get_volume_by_interval(self, symbol_input, quote_input, interval, start_time) -> Dict[str, Any]:
        """
        Get volume data by interval from Redis cache
        
        Args:
            symbol_input (str): Base symbol
            quote_input (str): Quote symbol  
            interval (str): Time interval
            start_time (int): Start time
            
        Returns:
            dict: Volume data
        """
        try:
            symbol_redis = f"{symbol_input}_{quote_input}".upper()
            
            redis_klines = get_candle_data_info(
                symbol_redis=symbol_redis, 
                exchange_name=self.exchange, 
                interval=interval, 
                r=self.r
            )
            
            if redis_klines and 'candle' in redis_klines:
                tick_number = calculate_gap_hours(start_time, int(time.time() * 1000))
                candles = redis_klines['candle'][-tick_number:] if tick_number > 0 else redis_klines['candle']
                return {'data': candles}
            
            # Fallback to get_candles if no Redis data
            candles_data = self.get_candles(symbol_input, quote_input, interval, start_time=start_time)
            return {'data': candles_data.get('candle', [])}
            
        except Exception as e:
            print(f"❌ Error getting volume data: {e}")
            logger_error.error(f"Paper trade get_volume_by_interval error: {e}")
            return {'data': []}


def main():
    """Test function for paper trading"""
    print("🧪 Testing Paper Trade functionality...")
    print("⚠️  Make sure the Go API server is running at http://localhost:8080")
    print("-" * 60)
    
    # Set environment for testing
    os.environ['PAPER_TRADE_EXCHANGE'] = 'binance'  # Use binance data for pricing
    
    # Initialize paper trade
    paper_trader = PaperTrade(
        symbol='BTC',
        quote='USDT',
        session_key='test_session_123',
        initial_balance=10000
    )
    
    # Test get price from Redis
    print("\n1️⃣ Testing price retrieval from Redis...")
    price = paper_trader.get_price()
    print(f"📊 Current price: {price}")
    
    # Test get balance via API
    print("\n2️⃣ Testing balance retrieval via Go API...")
    balance = paper_trader.get_account_balance()
    print(f"💰 Account balance: {balance}")
    
    # Test place order via API
    if price and price.get('price'):
        print(f"\n3️⃣ Testing order placement via Go API...")
        order_result = paper_trader.place_order(
            side_order='BUY',
            quantity=0.001,
            order_type='MARKET'
        )
        print(f"📝 Order result: {order_result}")
        
        # Check balance after order
        print(f"\n4️⃣ Testing balance after trade...")
        balance_after = paper_trader.get_account_balance()
        print(f"💰 Balance after trade: {balance_after}")
        
        # Test order details
        if order_result.get('code') == 0:
            order_id = order_result['data']['orderId']
            print(f"\n5️⃣ Testing order details retrieval...")
            order_details = paper_trader.get_order_details(order_id)
            print(f"📋 Order details: {order_details}")
    else:
        print("⚠️  Cannot place order - no price data available")
        print("💡 Make sure Redis has price data for BTC_USDT_binance_price")

    print("\n✅ Paper trading test completed!")
    print("🔧 To use paper trading in strategies:")
    print("   - Set GOLANG_API_URL environment variable if API is not on localhost:8080")
    print("   - Set PAPER_TRADE_EXCHANGE to specify which exchange data to use for pricing")
    print("   - Use PAPER_MODE=True and appropriate EXCHANGE environment variable in get_client_exchange()")


if __name__ == "__main__":
    main()