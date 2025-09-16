# pylint: disable=too-many-lines,too-many-public-methods
import time
import json
import hmac
import hashlib
import logging
import urllib.parse
from typing import Dict, Optional, Any

import requests
import redis

class BybitPerpsPrivate:
    """
    Bybit Perpetual Swaps Private API Client
    
    This class provides methods to interact with Bybit's private API endpoints for perpetual swaps trading.
    """
    
    def __init__(self, api_key: str, api_secret: str, symbol: str, testnet: bool = False, 
                 redis_client: Optional[redis.Redis] = None, redis_expiry: int = 60):
        """
        Initialize the Bybit Perpetual Swaps Private API client.
        
        Args:
            api_key (str): Your Bybit API key
            api_secret (str): Your Bybit API secret
            symbol (str): Trading symbol (e.g., "BTCUSDT" for USDT-margined perps)
            testnet (bool, optional): Whether to use testnet. Defaults to False.
            redis_client (redis.Redis, optional): Redis client for caching. Defaults to None.
            redis_expiry (int, optional): Redis cache expiry time in seconds. Defaults to 60.
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.symbol = symbol
        self.testnet = testnet
        self.redis_client = redis_client
        self.redis_expiry = redis_expiry
        
        # Set the base URL based on testnet flag
        if testnet:
            self.base_url = "https://api-testnet.bybit.com"
        else:
            self.base_url = "https://api.bybit.com"
        
        # Initialize price and quantity scales
        self.price_scale = 2
        self.qty_scale = 3
        
        # Initialize min/max values for validation
        self.min_price = 0
        self.max_price = 1000000
        self.min_qty = 0
        self.max_qty = 1000000
        
        # Initialize logger
        self.logger = logging.getLogger(__name__)
        
        # Get instrument info to set price and quantity scales
        self._get_instrument_info()
    
    def _get_instrument_info(self) -> None:
        """
        Get instrument information to set price and quantity scales.
        """
        try:
            # Try to get from Redis cache first
            if self.redis_client:
                cache_key = f"bybit_instrument_info_{self.symbol}"
                cached_data = self.redis_client.get(cache_key)
                if cached_data:
                    instrument_info = json.loads(cached_data)
                    self._set_scales_from_instrument_info(instrument_info)
                    return
            
            # If not in cache or no Redis, fetch from API
            endpoint = "/v5/market/instruments-info"
            params = {
                "category": "linear",  # For USDT-margined perpetual swaps
                "symbol": self.symbol
            }
            
            response = requests.get(f"{self.base_url}{endpoint}", params=params, timeout=30)
            data = response.json()
            
            if data["retCode"] == 0 and data["result"]["list"]:
                instrument_info = data["result"]["list"][0]
                
                # Cache in Redis if available
                if self.redis_client:
                    self.redis_client.setex(
                        cache_key,
                        self.redis_expiry,
                        json.dumps(instrument_info)
                    )
                
                self._set_scales_from_instrument_info(instrument_info)
            else:
                self.logger.warning("Failed to get instrument info: %s", data)
        except Exception as e:
            self.logger.error("Error getting instrument info: %s", e)
    
    def _set_scales_from_instrument_info(self, instrument_info: Dict[str, Any]) -> None:
        """
        Set price and quantity scales from instrument info.
        
        Args:
            instrument_info (Dict[str, Any]): Instrument information
        """
        try:
            # Extract price and quantity precision from instrument info
            price_filter = instrument_info.get("priceFilter", {})
            lot_size_filter = instrument_info.get("lotSizeFilter", {})
            
            # Set price scale based on tick size
            tick_size = price_filter.get("tickSize", "0.01")
            decimal_places = len(tick_size.rsplit('.', maxsplit=1)[-1])
            self.price_scale = decimal_places
            
            # Set quantity scale based on qty step
            qty_step = lot_size_filter.get("qtyStep", "0.001")
            decimal_places = len(qty_step.rsplit('.', maxsplit=1)[-1])
            self.qty_scale = decimal_places
            
            # Store min/max values for validation
            self.min_price = float(price_filter.get("minPrice", "0"))
            self.max_price = float(price_filter.get("maxPrice", "1000000"))
            self.min_qty = float(lot_size_filter.get("minOrderQty", "0"))
            self.max_qty = float(lot_size_filter.get("maxOrderQty", "1000000"))
            
            self.logger.info("Set scales for %s: price_scale=%s, qty_scale=%s", 
                            self.symbol, self.price_scale, self.qty_scale)
        except Exception as e:
            self.logger.error("Error setting scales: %s", e)
            # Set default values if there's an error
            self.price_scale = 2
            self.qty_scale = 3
            self.min_price = 0
            self.max_price = 1000000
            self.min_qty = 0
            self.max_qty = 1000000
    
    def _generate_signature(self, timestamp: int, params: Dict[str, Any]) -> str:
        """
        Generate signature for API request.
        
        Args:
            timestamp (int): Current timestamp in milliseconds
            params (Dict[str, Any]): Request parameters
        
        Returns:
            str: HMAC SHA256 signature
        """
        param_str = ""
        
        # Add timestamp and API key to params
        params_with_auth = {
            "api_key": self.api_key,
            "timestamp": str(timestamp),
            **params
        }
        
        # Sort parameters by key
        sorted_params = dict(sorted(params_with_auth.items()))
        
        # Create parameter string
        param_str = urllib.parse.urlencode(sorted_params)
        
        # Generate signature
        signature = hmac.new(
            bytes(self.api_secret, "utf-8"),
            bytes(param_str, "utf-8"),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _send_request(self, method: str, endpoint: str, params: Dict[str, Any] = None, 
                      signed: bool = True) -> Dict[str, Any]:
        """
        Send request to Bybit API.
        
        Args:
            method (str): HTTP method (GET, POST, etc.)
            endpoint (str): API endpoint
            params (Dict[str, Any], optional): Request parameters. Defaults to None.
            signed (bool, optional): Whether the request needs authentication. Defaults to True.
        
        Returns:
            Dict[str, Any]: API response
        """
        url = f"{self.base_url}{endpoint}"
        headers = {}
        
        # Initialize params if None
        if params is None:
            params = {}
        
        # Add authentication if required
        if signed:
            timestamp = int(time.time() * 1000)
            recv_window = 5000  # 5 seconds
            
            # Add authentication headers
            headers = {
                "X-BAPI-API-KEY": self.api_key,
                "X-BAPI-TIMESTAMP": str(timestamp),
                "X-BAPI-RECV-WINDOW": str(recv_window)
            }
            
            # Generate signature
            signature = self._generate_signature(timestamp, params)
            headers["X-BAPI-SIGN"] = signature
        
        try:
            # Send request based on method
            if method == "GET":
                response = requests.get(url, params=params, headers=headers, timeout=30)
            elif method == "POST":
                headers["Content-Type"] = "application/json"
                response = requests.post(url, json=params, headers=headers, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Parse response
            data = response.json()
            
            # Check for errors
            if data["retCode"] != 0:
                self.logger.error("API error: %s, code: %s", data['retMsg'], data['retCode'])
            
            return data
        except Exception as e:
            self.logger.error("Request error: %s", e)
            return {"retCode": -1, "retMsg": str(e), "result": {}}
    
    def get_wallet_balance(self, coin: str = None) -> Dict[str, Any]:
        """
        Get wallet balance.
        
        Args:
            coin (str, optional): Coin name (e.g., "USDT"). Defaults to None.
        
        Returns:
            Dict[str, Any]: Wallet balance information
        """
        endpoint = "/v5/account/wallet-balance"
        params = {
            "accountType": "UNIFIED"  # For UTA 2.0 account
        }
        
        if coin:
            params["coin"] = coin
        
        return self._send_request("GET", endpoint, params, signed=True)
    
    def get_positions(self, symbol: str = None) -> Dict[str, Any]:
        """
        Get perpetual swap positions.
        
        Args:
            symbol (str, optional): Symbol name. Defaults to None (uses instance symbol).
        
        Returns:
            Dict[str, Any]: Position information
        """
        endpoint = "/v5/position/list"
        params = {
            "category": "linear"  # For USDT-margined perpetual swaps
        }
        
        if symbol:
            params["symbol"] = symbol
        elif self.symbol:
            params["symbol"] = self.symbol
        
        return self._send_request("GET", endpoint, params, signed=True)
    
# pylint: disable=too-many-arguments
    def place_order(self, side: str, order_type: str, qty: float, price: float = None, 
                    time_in_force: str = "GTC", reduce_only: bool = False, 
                    close_on_trigger: bool = False, position_idx: int = 0,
                    take_profit: float = None, stop_loss: float = None,
                    tp_trigger_by: str = "LastPrice", sl_trigger_by: str = "LastPrice",
                    trigger_price: float = None, trigger_by: str = "LastPrice",
                    order_link_id: str = None) -> Dict[str, Any]:
        """
        Place an order for perpetual swaps.
        
        Args:
            side (str): Order side ("Buy" or "Sell")
            order_type (str): Order type ("Limit" or "Market")
            qty (float): Order quantity
            price (float, optional): Order price (required for Limit orders). Defaults to None.
            time_in_force (str, optional): Time in force. Defaults to "GTC".
                Options: "GTC" (Good Till Cancel), "IOC" (Immediate or Cancel), 
                "FOK" (Fill or Kill), "PostOnly"
            reduce_only (bool, optional): Whether the order is reduce-only. Defaults to False.
            close_on_trigger (bool, optional): Whether to close position on trigger. Defaults to False.
            position_idx (int, optional): Position index (0: one-way, 1: hedge-buy, 2: hedge-sell). Defaults to 0.
            take_profit (float, optional): Take profit price. Defaults to None.
            stop_loss (float, optional): Stop loss price. Defaults to None.
            tp_trigger_by (str, optional): Take profit trigger price type. Defaults to "LastPrice".
            sl_trigger_by (str, optional): Stop loss trigger price type. Defaults to "LastPrice".
            trigger_price (float, optional): Trigger price for conditional orders. Defaults to None.
            trigger_by (str, optional): Trigger price type. Defaults to "LastPrice".
            order_link_id (str, optional): User customized order ID. Defaults to None.
        
        Returns:
            Dict[str, Any]: Order placement result
        """
        endpoint = "/v5/order/create"
        
        # Round quantity and price to respect precision
        qty = round(float(qty), self.qty_scale)
        
        # Validate quantity
        if qty < self.min_qty or qty > self.max_qty:
            self.logger.error("Invalid quantity: %s. Must be between %s and %s", 
                             qty, self.min_qty, self.max_qty)
            return {"retCode": -1, "retMsg": f"Invalid quantity: {qty}", "result": {}}
        
        # Prepare parameters
        params = {
            "category": "linear",  # For USDT-margined perpetual swaps
            "symbol": self.symbol,
            "side": side,
            "orderType": order_type,
            "qty": str(qty),
            "timeInForce": time_in_force,
            "positionIdx": position_idx
        }
        
        # Add price for Limit orders
        if order_type == "Limit" and price is not None:
            price = round(float(price), self.price_scale)
            
            # Validate price
            if price < self.min_price or price > self.max_price:
                self.logger.error("Invalid price: %s. Must be between %s and %s", 
                                 price, self.min_price, self.max_price)
                return {"retCode": -1, "retMsg": f"Invalid price: {price}", "result": {}}
            
            params["price"] = str(price)
        
        # Add optional parameters if provided
        if reduce_only:
            params["reduceOnly"] = True
        
        if close_on_trigger:
            params["closeOnTrigger"] = True
        
        if take_profit is not None:
            params["takeProfit"] = str(round(float(take_profit), self.price_scale))
            params["tpTriggerBy"] = tp_trigger_by
        
        if stop_loss is not None:
            params["stopLoss"] = str(round(float(stop_loss), self.price_scale))
            params["slTriggerBy"] = sl_trigger_by
        
        if trigger_price is not None:
            params["triggerPrice"] = str(round(float(trigger_price), self.price_scale))
            params["triggerBy"] = trigger_by
        
        if order_link_id:
            params["orderLinkId"] = order_link_id
        
        return self._send_request("POST", endpoint, params, signed=True)
    
    def cancel_order(self, order_id: str = None, order_link_id: str = None) -> Dict[str, Any]:
        """
        Cancel an order.
        
        Args:
            order_id (str, optional): Order ID. Defaults to None.
            order_link_id (str, optional): User customized order ID. Defaults to None.
        
        Returns:
            Dict[str, Any]: Order cancellation result
        """
        endpoint = "/v5/order/cancel"
        params = {
            "category": "linear",  # For USDT-margined perpetual swaps
            "symbol": self.symbol
        }
        
        if order_id:
            params["orderId"] = order_id
        elif order_link_id:
            params["orderLinkId"] = order_link_id
        else:
            return {"retCode": -1, "retMsg": "Either order_id or order_link_id must be provided", "result": {}}
        
        return self._send_request("POST", endpoint, params, signed=True)
    
    def cancel_all_orders(self) -> Dict[str, Any]:
        """
        Cancel all active orders.
        
        Returns:
            Dict[str, Any]: Order cancellation result
        """
        endpoint = "/v5/order/cancel-all"
        params = {
            "category": "linear",  # For USDT-margined perpetual swaps
            "symbol": self.symbol
        }
        
        return self._send_request("POST", endpoint, params, signed=True)
    
    def get_order_history(self, limit: int = 50, cursor: str = None, 
                          order_status: str = None) -> Dict[str, Any]:
        """
        Get order history.
        
        Args:
            limit (int, optional): Limit for data size per page. Defaults to 50.
            cursor (str, optional): Cursor for pagination. Defaults to None.
            order_status (str, optional): Order status. Defaults to None.
                Options: "Created", "New", "Rejected", "PartiallyFilled", "PartiallyFilledCanceled", 
                "Filled", "Cancelled", "Untriggered", "Triggered", "Deactivated", "Active"
        
        Returns:
            Dict[str, Any]: Order history
        """
        endpoint = "/v5/order/history"
        params = {
            "category": "linear",  # For USDT-margined perpetual swaps
            "symbol": self.symbol,
            "limit": limit
        }
        
        if cursor:
            params["cursor"] = cursor
        
        if order_status:
            params["orderStatus"] = order_status
        
        return self._send_request("GET", endpoint, params, signed=True)
    
    def get_active_orders(self, limit: int = 50, cursor: str = None) -> Dict[str, Any]:
        """
        Get active orders.
        
        Args:
            limit (int, optional): Limit for data size per page. Defaults to 50.
            cursor (str, optional): Cursor for pagination. Defaults to None.
        
        Returns:
            Dict[str, Any]: Active orders
        """
        endpoint = "/v5/order/realtime"
        params = {
            "category": "linear",  # For USDT-margined perpetual swaps
            "symbol": self.symbol,
            "limit": limit
        }
        
        if cursor:
            params["cursor"] = cursor
        
        return self._send_request("GET", endpoint, params, signed=True)
    
    def get_order(self, order_id: str = None, order_link_id: str = None) -> Dict[str, Any]:
        """
        Get order details.
        
        Args:
            order_id (str, optional): Order ID. Defaults to None.
            order_link_id (str, optional): User customized order ID. Defaults to None.
        
        Returns:
            Dict[str, Any]: Order details
        """
        endpoint = "/v5/order/realtime"
        params = {
            "category": "linear",  # For USDT-margined perpetual swaps
            "symbol": self.symbol
        }
        
        if order_id:
            params["orderId"] = order_id
        elif order_link_id:
            params["orderLinkId"] = order_link_id
        else:
            return {"retCode": -1, "retMsg": "Either order_id or order_link_id must be provided", "result": {}}
        
        return self._send_request("GET", endpoint, params, signed=True)
    
    def get_execution_history(self, limit: int = 50, cursor: str = None) -> Dict[str, Any]:
        """
        Get execution history.
        
        Args:
            limit (int, optional): Limit for data size per page. Defaults to 50.
            cursor (str, optional): Cursor for pagination. Defaults to None.
        
        Returns:
            Dict[str, Any]: Execution history
        """
        endpoint = "/v5/execution/list"
        params = {
            "category": "linear",  # For USDT-margined perpetual swaps
            "symbol": self.symbol,
            "limit": limit
        }
        
        if cursor:
            params["cursor"] = cursor
        
        return self._send_request("GET", endpoint, params, signed=True)
    
    def set_leverage(self, leverage: int, symbol: str = None) -> Dict[str, Any]:
        """
        Set leverage.
        
        Args:
            leverage (int): Leverage value
            symbol (str, optional): Symbol name. Defaults to None (uses instance symbol).
        
        Returns:
            Dict[str, Any]: Leverage setting result
        """
        endpoint = "/v5/position/set-leverage"
        params = {
            "category": "linear",  # For USDT-margined perpetual swaps
            "symbol": symbol if symbol else self.symbol,
            "buyLeverage": str(leverage),
            "sellLeverage": str(leverage)
        }
        
        return self._send_request("POST", endpoint, params, signed=True)
    
    def set_position_mode(self, mode: str) -> Dict[str, Any]:
        """
        Set position mode.
        
        Args:
            mode (str): Position mode ("0": Merged Single, "3": Both Sides)
        
        Returns:
            Dict[str, Any]: Position mode setting result
        """
        endpoint = "/v5/position/switch-mode"
        params = {
            "category": "linear",  # For USDT-margined perpetual swaps
            "symbol": self.symbol,
            "mode": mode
        }
        
        return self._send_request("POST", endpoint, params, signed=True)
    
    def set_margin_mode(self, margin_mode: str) -> Dict[str, Any]:
        """
        Set margin mode.
        
        Args:
            margin_mode (str): Margin mode ("ISOLATED", "CROSS")
        
        Returns:
            Dict[str, Any]: Margin mode setting result
        """
        endpoint = "/v5/position/switch-isolated"
        params = {
            "category": "linear",  # For USDT-margined perpetual swaps
            "symbol": self.symbol,
            "tradeMode": 1 if margin_mode == "ISOLATED" else 0,
            "buyLeverage": "10",  # Default leverage
            "sellLeverage": "10"  # Default leverage
        }
        
        return self._send_request("POST", endpoint, params, signed=True)
    
    def set_risk_limit(self, risk_id: int) -> Dict[str, Any]:
        """
        Set risk limit.
        
        Args:
            risk_id (int): Risk limit ID
        
        Returns:
            Dict[str, Any]: Risk limit setting result
        """
        endpoint = "/v5/position/set-risk-limit"
        params = {
            "category": "linear",  # For USDT-margined perpetual swaps
            "symbol": self.symbol,
            "riskId": risk_id
        }
        
        return self._send_request("POST", endpoint, params, signed=True)
    
    def get_risk_limit(self) -> Dict[str, Any]:
        """
        Get risk limit.
        
        Returns:
            Dict[str, Any]: Risk limit information
        """
        endpoint = "/v5/market/risk-limit"
        params = {
            "category": "linear",  # For USDT-margined perpetual swaps
            "symbol": self.symbol
        }
        
        return self._send_request("GET", endpoint, params, signed=False)
    
    def get_tickers(self, symbol: str = None) -> Dict[str, Any]:
        """
        Get tickers.
        
        Args:
            symbol (str, optional): Symbol name. Defaults to None (uses instance symbol).
        
        Returns:
            Dict[str, Any]: Ticker information
        """
        endpoint = "/v5/market/tickers"
        params = {
            "category": "linear"  # For USDT-margined perpetual swaps
        }
        
        if symbol:
            params["symbol"] = symbol
        elif self.symbol:
            params["symbol"] = self.symbol
        
        return self._send_request("GET", endpoint, params, signed=False)
    
    def get_orderbook(self, symbol: str = None, limit: int = 25) -> Dict[str, Any]:
        """
        Get orderbook.
        
        Args:
            symbol (str, optional): Symbol name. Defaults to None (uses instance symbol).
            limit (int, optional): Limit for data size. Defaults to 25.
                Options: 1, 25, 50, 100, 500, 1000
        
        Returns:
            Dict[str, Any]: Orderbook information
        """
        endpoint = "/v5/market/orderbook"
        params = {
            "category": "linear",  # For USDT-margined perpetual swaps
            "symbol": symbol if symbol else self.symbol,
            "limit": limit
        }
        
        return self._send_request("GET", endpoint, params, signed=False)
    
    def get_kline(self, interval: str, start_time: int = None, end_time: int = None, 
                 limit: int = 200) -> Dict[str, Any]:
        """
        Get kline/candlestick data.
        
        Args:
            interval (str): Kline interval
                Options: "1", "3", "5", "15", "30", "60", "120", "240", "360", "720", "D", "M", "W"
            start_time (int, optional): Start timestamp (ms). Defaults to None.
            end_time (int, optional): End timestamp (ms). Defaults to None.
            limit (int, optional): Limit for data size. Defaults to 200.
                Max: 1000
        
        Returns:
            Dict[str, Any]: Kline data
        """
        endpoint = "/v5/market/kline"
        params = {
            "category": "linear",  # For USDT-margined perpetual swaps
            "symbol": self.symbol,
            "interval": interval,
            "limit": limit
        }
        
        if start_time:
            params["start"] = start_time
        
        if end_time:
            params["end"] = end_time
        
        return self._send_request("GET", endpoint, params, signed=False)
    
    def get_mark_price_kline(self, interval: str, start_time: int = None, end_time: int = None, 
                            limit: int = 200) -> Dict[str, Any]:
        """
        Get mark price kline/candlestick data.
        
        Args:
            interval (str): Kline interval
                Options: "1", "3", "5", "15", "30", "60", "120", "240", "360", "720", "D", "M", "W"
            start_time (int, optional): Start timestamp (ms). Defaults to None.
            end_time (int, optional): End timestamp (ms). Defaults to None.
            limit (int, optional): Limit for data size. Defaults to 200.
                Max: 1000
        
        Returns:
            Dict[str, Any]: Mark price kline data
        """
        endpoint = "/v5/market/mark-price-kline"
        params = {
            "category": "linear",  # For USDT-margined perpetual swaps
            "symbol": self.symbol,
            "interval": interval,
            "limit": limit
        }
        
        if start_time:
            params["start"] = start_time
        
        if end_time:
            params["end"] = end_time
        
        return self._send_request("GET", endpoint, params, signed=False)
    
    def get_index_price_kline(self, interval: str, start_time: int = None, end_time: int = None, 
                             limit: int = 200) -> Dict[str, Any]:
        """
        Get index price kline/candlestick data.
        
        Args:
            interval (str): Kline interval
                Options: "1", "3", "5", "15", "30", "60", "120", "240", "360", "720", "D", "M", "W"
            start_time (int, optional): Start timestamp (ms). Defaults to None.
            end_time (int, optional): End timestamp (ms). Defaults to None.
            limit (int, optional): Limit for data size. Defaults to 200.
                Max: 1000
        
        Returns:
            Dict[str, Any]: Index price kline data
        """
        endpoint = "/v5/market/index-price-kline"
        params = {
            "category": "linear",  # For USDT-margined perpetual swaps
            "symbol": self.symbol,
            "interval": interval,
            "limit": limit
        }
        
        if start_time:
            params["start"] = start_time
        
        if end_time:
            params["end"] = end_time
        
        return self._send_request("GET", endpoint, params, signed=False)
    
    def get_premium_index_kline(self, interval: str, start_time: int = None, end_time: int = None, 
                               limit: int = 200) -> Dict[str, Any]:
        """
        Get premium index kline/candlestick data.
        
        Args:
            interval (str): Kline interval
                Options: "1", "3", "5", "15", "30", "60", "120", "240", "360", "720", "D", "M", "W"
            start_time (int, optional): Start timestamp (ms). Defaults to None.
            end_time (int, optional): End timestamp (ms). Defaults to None.
            limit (int, optional): Limit for data size. Defaults to 200.
                Max: 1000
        
        Returns:
            Dict[str, Any]: Premium index kline data
        """
        endpoint = "/v5/market/premium-index-kline"
        params = {
            "category": "linear",  # For USDT-margined perpetual swaps
            "symbol": self.symbol,
            "interval": interval,
            "limit": limit
        }
        
        if start_time:
            params["start"] = start_time
        
        if end_time:
            params["end"] = end_time
        
        return self._send_request("GET", endpoint, params, signed=False)
    
    def get_instruments_info(self) -> Dict[str, Any]:
        """
        Get instruments information.
        
        Returns:
            Dict[str, Any]: Instruments information
        """
        endpoint = "/v5/market/instruments-info"
        params = {
            "category": "linear",  # For USDT-margined perpetual swaps
            "symbol": self.symbol
        }
        
        return self._send_request("GET", endpoint, params, signed=False)
    
    def get_funding_rate_history(self, start_time: int = None, end_time: int = None, 
                                limit: int = 200) -> Dict[str, Any]:
        """
        Get funding rate history.
        
        Args:
            start_time (int, optional): Start timestamp (ms). Defaults to None.
            end_time (int, optional): End timestamp (ms). Defaults to None.
            limit (int, optional): Limit for data size. Defaults to 200.
        
        Returns:
            Dict[str, Any]: Funding rate history
        """
        endpoint = "/v5/market/funding/history"
        params = {
            "category": "linear",  # For USDT-margined perpetual swaps
            "symbol": self.symbol,
            "limit": limit
        }
        
        if start_time:
            params["startTime"] = start_time
        
        if end_time:
            params["endTime"] = end_time
        
        return self._send_request("GET", endpoint, params, signed=False)
    
    def get_recent_trades(self, limit: int = 50) -> Dict[str, Any]:
        """
        Get recent trades.
        
        Args:
            limit (int, optional): Limit for data size. Defaults to 50.
                Max: 1000
        
        Returns:
            Dict[str, Any]: Recent trades
        """
        endpoint = "/v5/market/recent-trade"
        params = {
            "category": "linear",  # For USDT-margined perpetual swaps
            "symbol": self.symbol,
            "limit": limit
        }
        
        return self._send_request("GET", endpoint, params, signed=False)
    
    def get_open_interest(self, interval: str = "5min", start_time: int = None, 
                         end_time: int = None, limit: int = 50) -> Dict[str, Any]:
        """
        Get open interest.
        
        Args:
            interval (str, optional): Data recording interval. Defaults to "5min".
                Options: "5min", "15min", "30min", "1h", "4h", "1d"
            start_time (int, optional): Start timestamp (ms). Defaults to None.
            end_time (int, optional): End timestamp (ms). Defaults to None.
            limit (int, optional): Limit for data size. Defaults to 50.
                Max: 200
        
        Returns:
            Dict[str, Any]: Open interest
        """
        endpoint = "/v5/market/open-interest"
        params = {
            "category": "linear",  # For USDT-margined perpetual swaps
            "symbol": self.symbol,
            "intervalTime": interval,
            "limit": limit
        }
        
        if start_time:
            params["startTime"] = start_time
        
        if end_time:
            params["endTime"] = end_time
        
        return self._send_request("GET", endpoint, params, signed=False)
    
    def get_account_info(self) -> Dict[str, Any]:
        """
        Get account information.
        
        Returns:
            Dict[str, Any]: Account information
        """
        endpoint = "/v5/account/info"
        return self._send_request("GET", endpoint, {}, signed=True)
    
    def get_transaction_log(self, category: str = "linear", 
                           start_time: int = None, end_time: int = None, 
                           limit: int = 50, cursor: str = None) -> Dict[str, Any]:
        """
        Get transaction log.
        
        Args:
            category (str, optional): Product type. Defaults to "linear".
                Options: "linear", "spot", "option"
            start_time (int, optional): Start timestamp (ms). Defaults to None.
            end_time (int, optional): End timestamp (ms). Defaults to None.
            limit (int, optional): Limit for data size. Defaults to 50.
                Max: 50
            cursor (str, optional): Cursor for pagination. Defaults to None.
        
        Returns:
            Dict[str, Any]: Transaction log
        """
        endpoint = "/v5/account/transaction-log"
        params = {
            "category": category,
            "limit": limit
        }
        
        if start_time:
            params["startTime"] = start_time
        
        if end_time:
            params["endTime"] = end_time
        
        if cursor:
            params["cursor"] = cursor
        
        return self._send_request("GET", endpoint, params, signed=True)
    
    def set_trading_stop(self, position_idx: int = 0, take_profit: float = None, 
                        stop_loss: float = None, tp_trigger_by: str = "LastPrice", 
                        sl_trigger_by: str = "LastPrice", 
                        trailing_stop: float = None, 
                        tp_size: float = None, sl_size: float = None) -> Dict[str, Any]:
        """
        Set trading stop.
        
        Args:
            position_idx (int, optional): Position index. Defaults to 0.
                Options: 0 (one-way), 1 (hedge-buy), 2 (hedge-sell)
            take_profit (float, optional): Take profit price. Defaults to None.
            stop_loss (float, optional): Stop loss price. Defaults to None.
            tp_trigger_by (str, optional): Take profit trigger price type. Defaults to "LastPrice".
                Options: "LastPrice", "IndexPrice", "MarkPrice"
            sl_trigger_by (str, optional): Stop loss trigger price type. Defaults to "LastPrice".
                Options: "LastPrice", "IndexPrice", "MarkPrice"
            trailing_stop (float, optional): Trailing stop. Defaults to None.
            tp_size (float, optional): Take profit size. Defaults to None.
            sl_size (float, optional): Stop loss size. Defaults to None.
        
        Returns:
            Dict[str, Any]: Trading stop setting result
        """
        endpoint = "/v5/position/trading-stop"
        params = {
            "category": "linear",  # For USDT-margined perpetual swaps
            "symbol": self.symbol,
            "positionIdx": position_idx
        }
        
        if take_profit is not None:
            params["takeProfit"] = str(round(float(take_profit), self.price_scale))
            params["tpTriggerBy"] = tp_trigger_by
        
        if stop_loss is not None:
            params["stopLoss"] = str(round(float(stop_loss), self.price_scale))
            params["slTriggerBy"] = sl_trigger_by
        
        if trailing_stop is not None:
            params["trailingStop"] = str(trailing_stop)
        
        if tp_size is not None:
            params["tpSize"] = str(round(float(tp_size), self.qty_scale))
        
        if sl_size is not None:
            params["slSize"] = str(round(float(sl_size), self.qty_scale))
        
        return self._send_request("POST", endpoint, params, signed=True)
    
    def close_position(self) -> Dict[str, Any]:
        """
        Close position.
        
        Returns:
            Dict[str, Any]: Position closing result
        """
        # First, get current position
        position_result = self.get_positions()
        
        if position_result["retCode"] != 0:
            return position_result
        
        positions = position_result["result"]["list"]
        if not positions:
            return {"retCode": 0, "retMsg": "No position to close", "result": {}}
        
        # Find the position for the current symbol
        position = None
        for pos in positions:
            if pos["symbol"] == self.symbol:
                position = pos
                break
        
        if not position:
            return {"retCode": 0, "retMsg": "No position to close", "result": {}}
        
        # Get position size and side
        size = float(position["size"])
        if size == 0:
            return {"retCode": 0, "retMsg": "No position to close", "result": {}}
        
        # Determine side for closing order
        side = "Sell" if position["side"] == "Buy" else "Buy"
        
        # Place market order to close position
        return self.place_order(
            side=side,
            order_type="Market",
            qty=size,
            reduce_only=True
        )