#!/usr/bin/env python3
"""
Cancel Order Handler
Handles canceling open orders for both spot and futures trading.
"""

import sys
import os
import json
from typing import Dict, Any, Optional, List, Set

# Add the parent directory to the path to import our modules
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../"))
sys.path.insert(0, PROJECT_ROOT)

from exchange_api_spot.user import get_client_exchange
from exchange_api_future.user import get_client_exchange as get_future_client_exchange
from logger import logger_database, logger_error, logger_access
from utils import get_arg
from utils import make_golang_api_call


def _get_golang_base_url() -> str:
    # Prefer GOLANG_API_BASE_URL if provided; fallback to GOLANG_MGMT_API_URL used in auth util
    return os.getenv("GOLANG_API_BASE_URL") or os.getenv("GOLANG_MGMT_API_URL", "http://localhost:8083")


def fetch_session_symbols(session_key: str) -> Set[str]:
    """Fetch symbols from Go service for a session and return an uppercase set.
    Uses GET /api/v1/orders/orders/session/:session_key
    """
    try:
        base_url = _get_golang_base_url()
        endpoint = f"/api/v1/orders/orders/session/{session_key}?limit=1000"
        logger_access.info(f"📡 Fetching session symbols from {endpoint}")
        resp = make_golang_api_call(method="GET", endpoint=endpoint, data=None, base_url=base_url)
        symbols: Set[str] = set()
        if isinstance(resp, dict):
            orders = resp.get("orders") or []
            for o in orders:
                sym = o.get("symbol")
                if sym:
                    symbols.add(str(sym).upper())
        logger_access.info(f"📡 Session {session_key} symbols from Go: {sorted(symbols)}")
        return symbols
    except Exception as e:
        logger_error.error(f"❌ Failed to fetch session symbols: {e}")
        return set()


def _extract_order_symbol(order: Dict[str, Any]) -> Optional[str]:
    """Try to extract a symbol like BTCUSDT from various order schemas."""
    sym = order.get("symbol") or order.get("pair") or order.get("symbol_pair")
    if not sym and order.get("base") and order.get("quote"):
        sym = f"{order['base']}{order['quote']}"
    return str(sym).upper() if sym else None


def cancel_spot_orders(session_key: str, api_key: str, secret_key: str, exchange_name: str, 
                      passphrase: str = "", symbol: str = "BTC", quote: str = "USDT") -> Dict[str, Any]:
    """
    Cancel open spot orders for a trading session, filtered by symbols traded in the session (from Go API).
    """
    try:
        logger_access.info(f"🔄 Starting spot order cancellation for session: {session_key}")

        # Fetch allowed symbols from Go service for this session
        allowed_symbols = fetch_session_symbols(session_key)
        if allowed_symbols:
            logger_access.info(f"✅ Will only cancel symbols: {sorted(allowed_symbols)}")
        else:
            logger_access.info("⚠️ No symbols from Go service; will not filter (cancel all open spot orders)")
        
        # Prepare account info
        acc_info = {
            'api_key': api_key,
            'secret_key': secret_key,
            'passphrase': passphrase,
            'session_key': session_key
        }
        
        # Get exchange client
        client = get_client_exchange(
            exchange_name=exchange_name,
            acc_info=acc_info,
            symbol=symbol,
            quote=quote,
            session_key=session_key,
        )
        logger_access.info(f"✅ Created {exchange_name} spot client successfully")
        
        if not client:
            raise Exception(f"Failed to create client for exchange: {exchange_name}")
        
        # Get open orders (any symbol) and filter/cancel by order ID
        try:
            open_orders_resp = client.get_open_orders()
            # Normalize to a list for all client types
            if isinstance(open_orders_resp, dict):
                open_orders = open_orders_resp.get('data') or open_orders_resp.get('orders') or []
            elif isinstance(open_orders_resp, list):
                open_orders = open_orders_resp
            else:
                open_orders = []

            logger_access.info(f"📋 Found {len(open_orders)} open spot orders (before filter)")
            logger_access.info(f"📋 allowed_symbols: {allowed_symbols}")
            if allowed_symbols:
                filtered_orders: List[Dict[str, Any]] = []
                for o in open_orders:
                    osym = _extract_order_symbol(o)
                    if osym and osym in allowed_symbols:
                        filtered_orders.append(o)
                open_orders = filtered_orders
                logger_access.info(f"📋 {len(open_orders)} orders remain after symbol filter")
            
            if not open_orders:
                return {
                    'success': True,
                    'message': 'No open spot orders to cancel (after filtering)',
                    'cancelled_orders': [],
                    'failed_orders': []
                }
            
        except Exception as e:
            logger_error.error(f"❌ Error getting open orders: {str(e)}")
            return {
                'success': False,
                'message': f'Failed to get open orders: {str(e)}',
                'cancelled_orders': [],
                'failed_orders': []
            }
        
        # Cancel each order
        cancelled_orders = []
        failed_orders = []
        
        for order in open_orders:
            try:
                order_id = order.get('orderId') or order.get('id') or order.get('order_id')
                if not order_id:
                    logger_error.error(f"❌ Order missing ID: {order}")
                    failed_orders.append({
                        'order': order,
                        'error': 'Order ID not found'
                    })
                    continue
                
                logger_access.info(f"🔄 Cancelling spot order: {order_id}")
                
                # Cancel the order
                cancel_result = client.cancel_order(order_id)
                
                if cancel_result:
                    logger_access.info(f"✅ Successfully cancelled spot order: {order_id}")
                    cancelled_orders.append({
                        'order_id': order_id,
                        'original_order': order,
                        'cancel_result': cancel_result
                    })
                else:
                    logger_error.error(f"❌ Failed to cancel spot order: {order_id}")
                    failed_orders.append({
                        'order_id': order_id,
                        'order': order,
                        'error': 'Cancel operation returned False'
                    })
                    
            except Exception as e:
                logger_error.error(f"❌ Error cancelling spot order {order_id if 'order_id' in locals() else 'unknown'}: {str(e)}")
                failed_orders.append({
                    'order_id': order_id if 'order_id' in locals() else 'unknown',
                    'order': order,
                    'error': str(e)
                })
        
        success = len(failed_orders) == 0
        message = f"Cancelled {len(cancelled_orders)} spot orders"
        if failed_orders:
            message += f", {len(failed_orders)} failed"
        
        logger_access.info(f"📊 Spot order cancellation summary: {message}")
        
        return {
            'success': success,
            'message': message,
            'cancelled_orders': cancelled_orders,
            'failed_orders': failed_orders
        }
        
    except Exception as e:
        logger_error.error(f"❌ Error in cancel_spot_orders: {str(e)}")
        return {
            'success': False,
            'message': f'Error cancelling spot orders: {str(e)}',
            'cancelled_orders': [],
            'failed_orders': []
        }


def cancel_future_orders(session_key: str, api_key: str, secret_key: str, exchange_name: str,
                        passphrase: str = "", symbol: str = "BTC", quote: str = "USDT") -> Dict[str, Any]:
    """
    Cancel all open futures orders for a trading session.
    """
    try:
        logger_access.info(f"🔄 Starting futures order cancellation for session: {session_key}")
        
        # Prepare account info
        acc_info = {
            'api_key': api_key,
            'secret_key': secret_key,
            'passphrase': passphrase,
            'session_key': session_key
        }
        
        # Get futures exchange client
        client = get_future_client_exchange(
            exchange_name=exchange_name,
            acc_info=acc_info,
            symbol=symbol,
            quote=quote,
            session_key=session_key,
        )
        
        if not client:
            raise Exception(f"Failed to create futures client for exchange: {exchange_name}")
        
        logger_access.info(f"✅ Created {exchange_name} futures client successfully")
        
        # Get open orders
        try:
            open_orders = client.get_open_orders()
            logger_access.info(f"📋 Found {len(open_orders) if open_orders else 0} open futures orders")
            
            if not open_orders:
                return {
                    'success': True,
                    'message': 'No open futures orders to cancel',
                    'cancelled_orders': [],
                    'failed_orders': []
                }
            
        except Exception as e:
            logger_error.error(f"❌ Error getting open futures orders: {str(e)}")
            return {
                'success': False,
                'message': f'Failed to get open futures orders: {str(e)}',
                'cancelled_orders': [],
                'failed_orders': []
            }
        
        # Cancel each order
        cancelled_orders = []
        failed_orders = []
        
        for order in open_orders:
            try:
                order_id = order.get('orderId') or order.get('id') or order.get('order_id')
                if not order_id:
                    logger_error.error(f"❌ Futures order missing ID: {order}")
                    failed_orders.append({
                        'order': order,
                        'error': 'Order ID not found'
                    })
                    continue
                
                logger_access.info(f"🔄 Cancelling futures order: {order_id}")
                
                # Cancel the order
                cancel_result = client.cancel_order(order_id)
                
                if cancel_result:
                    logger_access.info(f"✅ Successfully cancelled futures order: {order_id}")
                    cancelled_orders.append({
                        'order_id': order_id,
                        'original_order': order,
                        'cancel_result': cancel_result
                    })
                else:
                    logger_error.error(f"❌ Failed to cancel futures order: {order_id}")
                    failed_orders.append({
                        'order_id': order_id,
                        'order': order,
                        'error': 'Cancel operation returned False'
                    })
                    
            except Exception as e:
                logger_error.error(f"❌ Error cancelling futures order {order_id if 'order_id' in locals() else 'unknown'}: {str(e)}")
                failed_orders.append({
                    'order_id': order_id if 'order_id' in locals() else 'unknown',
                    'order': order,
                    'error': str(e)
                })
        
        success = len(failed_orders) == 0
        message = f"Cancelled {len(cancelled_orders)} futures orders"
        if failed_orders:
            message += f", {len(failed_orders)} failed"
        
        logger_access.info(f"📊 Futures order cancellation summary: {message}")
        
        return {
            'success': success,
            'message': message,
            'cancelled_orders': cancelled_orders,
            'failed_orders': failed_orders
        }
        
    except Exception as e:
        logger_error.error(f"❌ Error in cancel_future_orders: {str(e)}")
        return {
            'success': False,
            'message': f'Error cancelling futures orders: {str(e)}',
            'cancelled_orders': [],
            'failed_orders': []
        }


def cancel_orders(session_key: str, api_key: str, secret_key: str, exchange_name: str,
                 trading_type: str = "spot", passphrase: str = "", symbol: str = "BTC", 
                 quote: str = "USDT") -> Dict[str, Any]:
    """
    Cancel orders based on trading type (spot or futures).
    """
    try:
        logger_access.info(f"🔄 Starting order cancellation - Type: {trading_type}, Exchange: {exchange_name}")
        
        if trading_type.lower() == "spot":
            return cancel_spot_orders(session_key, api_key, secret_key, exchange_name, 
                                    passphrase, symbol, quote)
        elif trading_type.lower() in ["futures", "future"]:
            return cancel_future_orders(session_key, api_key, secret_key, exchange_name,
                                      passphrase, symbol, quote)
        else:
            raise ValueError(f"Unsupported trading type: {trading_type}")
            
    except Exception as e:
        logger_error.error(f"❌ Error in cancel_orders: {str(e)}")
        return {
            'success': False,
            'message': f'Error cancelling orders: {str(e)}',
            'cancelled_orders': [],
            'failed_orders': []
        }


if __name__ == "__main__":
    # Test the functions
    logger_access.info("🧪 Testing cancel_order.py")
    
    SESSION_ID     = get_arg(1, '')
    EXCHANGE       = get_arg(2, '')
    API_KEY        = get_arg(3, '')
    SECRET_KEY     = get_arg(4, '')
    STRATEGY_NAME  = get_arg(5, '')
    PASSPHRASE     = get_arg(6, '')
    ASSET_FILTER   = ''
    
    # Test spot order cancellation
    result = cancel_orders(
        session_key=SESSION_ID,
        api_key=API_KEY,
        secret_key=SECRET_KEY,
        exchange_name=EXCHANGE,
        trading_type="spot"
    )
    
    logger_access.info(f"📊 Test result: {json.dumps(result)}")