#!/usr/bin/env python3
"""
Cancel Order Handler
Handles canceling open orders for both spot and futures trading.
"""

import sys
import os

# Add the parent directory to the path to import our modules
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../"))
sys.path.insert(0, PROJECT_ROOT)

from exchange_api_spot.user import get_client_exchange
from exchange_api_future.user import get_client_exchange as get_future_client_exchange
from logger import logger_database, logger_error, logger_access
from typing import Dict, Any, Optional, List


def cancel_spot_orders(session_key: str, api_key: str, secret_key: str, exchange_name: str, 
                      passphrase: str = "", symbol: str = "BTC", quote: str = "USDT") -> Dict[str, Any]:
    """
    Cancel all open spot orders for a trading session.
    
    Args:
        session_key: Trading session identifier
        api_key: Exchange API key
        secret_key: Exchange secret key
        exchange_name: Name of the exchange (binance, poloniex, etc.)
        passphrase: Exchange passphrase (if required)
        symbol: Base symbol (default: BTC)
        quote: Quote symbol (default: USDT)
        
    Returns:
        Dict containing success status and details
    """
    try:
        logger_access.info(f"🔄 Starting spot order cancellation for session: {session_key}")
        
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
            paper_mode=False
        )
        
        if not client:
            raise Exception(f"Failed to create client for exchange: {exchange_name}")
        
        logger_access.info(f"✅ Created {exchange_name} spot client successfully")
        
        # Get open orders
        try:
            open_orders = client.get_open_orders()
            logger_access.info(f"📋 Found {len(open_orders) if open_orders else 0} open spot orders")
            
            if not open_orders:
                return {
                    'success': True,
                    'message': 'No open spot orders to cancel',
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
    
    Args:
        session_key: Trading session identifier
        api_key: Exchange API key
        secret_key: Exchange secret key
        exchange_name: Name of the exchange (binance, poloniex, etc.)
        passphrase: Exchange passphrase (if required)
        symbol: Base symbol (default: BTC)
        quote: Quote symbol (default: USDT)
        
    Returns:
        Dict containing success status and details
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
            paper_mode=False
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
    
    Args:
        session_key: Trading session identifier
        api_key: Exchange API key
        secret_key: Exchange secret key
        exchange_name: Name of the exchange
        trading_type: Type of trading ("spot" or "futures")
        passphrase: Exchange passphrase (if required)
        symbol: Base symbol
        quote: Quote symbol
        
    Returns:
        Dict containing success status and details
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
    
    # Example usage
    test_session_key = "test_session_123"
    test_api_key = "test_api_key"
    test_secret_key = "test_secret_key"
    test_exchange = "binance"
    
    # Test spot order cancellation
    result = cancel_orders(
        session_key=test_session_key,
        api_key=test_api_key,
        secret_key=test_secret_key,
        exchange_name=test_exchange,
        trading_type="spot"
    )
    
    logger_access.info(f"📊 Test result: {result}")