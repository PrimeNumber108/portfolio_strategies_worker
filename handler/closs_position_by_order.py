#!/usr/bin/env python3
"""
Close Position Handler
Handles closing all futures positions.
"""

import sys
import os

# Add the parent directory to the path to import our modules
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../"))
sys.path.insert(0, PROJECT_ROOT)

from exchange_api_future.user import get_client_exchange as get_future_client_exchange
from logger import logger_database, logger_error, logger_access
from typing import Dict, Any, Optional, List
import time


def get_open_positions(client, exchange_name: str) -> List[Dict[str, Any]]:
    """
    Get open positions from the futures exchange client.
    
    Args:
        client: Futures exchange client instance
        exchange_name: Name of the exchange
        
    Returns:
        List of open positions
    """
    try:
        if hasattr(client, 'get_positions'):
            positions = client.get_positions()
        elif hasattr(client, 'get_open_positions'):
            positions = client.get_open_positions()
        elif hasattr(client, 'get_position_info'):
            positions = client.get_position_info()
        else:
            logger_error.error(f"❌ No position method found for {exchange_name} client")
            return []
        
        # Filter only positions with non-zero size
        if positions:
            open_positions = []
            for pos in positions:
                # Different exchanges may have different field names
                size = float(pos.get('positionAmt', 0) or pos.get('size', 0) or pos.get('contracts', 0) or pos.get('amount', 0))
                if abs(size) > 0:
                    open_positions.append(pos)
            return open_positions
        
        return []
        
    except Exception as e:
        logger_error.error(f"❌ Error getting positions: {str(e)}")
        return []


def close_futures_position(client, position: Dict[str, Any], exchange_name: str) -> Dict[str, Any]:
    """
    Close a single futures position.
    
    Args:
        client: Futures exchange client instance
        position: Position information
        exchange_name: Name of the exchange
        
    Returns:
        Dict containing close result
    """
    try:
        # Extract position details
        symbol = position.get('symbol') or position.get('instrument_name') or position.get('pair')
        size = float(position.get('positionAmt', 0) or position.get('size', 0) or position.get('contracts', 0) or position.get('amount', 0))
        side = position.get('positionSide') or position.get('side')
        
        if not symbol or size == 0:
            return {
                'success': False,
                'error': 'Invalid position data - missing symbol or zero size'
            }
        
        logger_access.info(f"🔄 Closing position: {symbol}, Size: {size}, Side: {side}")
        
        # Determine the opposite side to close the position
        close_side = 'SELL' if size > 0 else 'BUY'
        close_quantity = abs(size)
        
        # Create market order to close position
        try:
            if hasattr(client, 'create_market_order'):
                order_result = client.create_market_order(
                    symbol=symbol,
                    side=close_side,
                    quantity=close_quantity,
                    reduce_only=True  # This ensures we're closing, not opening new positions
                )
            elif hasattr(client, 'close_position'):
                order_result = client.close_position(symbol, close_quantity)
            elif hasattr(client, 'create_order'):
                order_result = client.create_order(
                    symbol=symbol,
                    side=close_side,
                    type='MARKET',
                    quantity=close_quantity,
                    reduce_only=True
                )
            else:
                return {
                    'success': False,
                    'error': f'No close position method found for {exchange_name}'
                }
            
            if order_result:
                logger_access.info(f"✅ Successfully closed position: {symbol}")
                return {
                    'success': True,
                    'symbol': symbol,
                    'size': size,
                    'close_side': close_side,
                    'close_quantity': close_quantity,
                    'order_result': order_result
                }
            else:
                logger_error.error(f"❌ Failed to close position: {symbol} - Order result was None/False")
                return {
                    'success': False,
                    'symbol': symbol,
                    'error': 'Order result was None/False'
                }
                
        except Exception as e:
            logger_error.error(f"❌ Error creating close order for {symbol}: {str(e)}")
            return {
                'success': False,
                'symbol': symbol,
                'error': str(e)
            }
            
    except Exception as e:
        logger_error.error(f"❌ Error in close_futures_position: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def close_all_futures_positions(session_key: str, api_key: str, secret_key: str, exchange_name: str,
                               passphrase: str = "", symbol: str = "BTC", quote: str = "USDT") -> Dict[str, Any]:
    """
    Close all open futures positions for a trading session.
    
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
        logger_access.info(f"🔄 Starting futures position closure for session: {session_key}")
        
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
        
        # Get open positions
        try:
            open_positions = get_open_positions(client, exchange_name)
            logger_access.info(f"📋 Found {len(open_positions)} open futures positions")
            
            if not open_positions:
                return {
                    'success': True,
                    'message': 'No open futures positions to close',
                    'closed_positions': [],
                    'failed_positions': []
                }
            
        except Exception as e:
            logger_error.error(f"❌ Error getting open positions: {str(e)}")
            return {
                'success': False,
                'message': f'Failed to get open positions: {str(e)}',
                'closed_positions': [],
                'failed_positions': []
            }
        
        # Close each position
        closed_positions = []
        failed_positions = []
        
        for position in open_positions:
            try:
                close_result = close_futures_position(client, position, exchange_name)
                
                if close_result.get('success'):
                    closed_positions.append({
                        'original_position': position,
                        'close_result': close_result
                    })
                else:
                    failed_positions.append({
                        'position': position,
                        'error': close_result.get('error', 'Unknown error')
                    })
                
                # Add small delay between orders to avoid rate limits
                time.sleep(0.1)
                
            except Exception as e:
                logger_error.error(f"❌ Error closing position {position}: {str(e)}")
                failed_positions.append({
                    'position': position,
                    'error': str(e)
                })
        
        success = len(failed_positions) == 0
        message = f"Closed {len(closed_positions)} futures positions"
        if failed_positions:
            message += f", {len(failed_positions)} failed"
        
        logger_access.info(f"📊 Futures position closure summary: {message}")
        
        return {
            'success': success,
            'message': message,
            'closed_positions': closed_positions,
            'failed_positions': failed_positions
        }
        
    except Exception as e:
        logger_error.error(f"❌ Error in close_all_futures_positions: {str(e)}")
        return {
            'success': False,
            'message': f'Error closing futures positions: {str(e)}',
            'closed_positions': [],
            'failed_positions': []
        }


def close_positions_and_cancel_orders(session_key: str, api_key: str, secret_key: str, exchange_name: str,
                                    passphrase: str = "", symbol: str = "BTC", quote: str = "USDT") -> Dict[str, Any]:
    """
    Close all futures positions and cancel all futures orders.
    This is the main function to be called for "Both" option in futures.
    
    Args:
        session_key: Trading session identifier
        api_key: Exchange API key
        secret_key: Exchange secret key
        exchange_name: Name of the exchange
        passphrase: Exchange passphrase (if required)
        symbol: Base symbol
        quote: Quote symbol
        
    Returns:
        Dict containing success status and details
    """
    try:
        logger_access.info(f"🔄 Starting complete futures closure (positions + orders) for session: {session_key}")
        
        # First, close all positions
        logger_access.info("📊 Step 1: Closing all futures positions")
        close_result = close_all_futures_positions(session_key, api_key, secret_key, exchange_name,
                                                 passphrase, symbol, quote)
        
        # Then, cancel all orders (import from cancel_order.py)
        from .cancel_order import cancel_future_orders
        
        logger_access.info("📋 Step 2: Cancelling all futures orders")
        cancel_result = cancel_future_orders(session_key, api_key, secret_key, exchange_name,
                                           passphrase, symbol, quote)
        
        # Combine results
        overall_success = close_result.get('success', False) and cancel_result.get('success', False)
        
        combined_message = f"Positions: {close_result.get('message', 'Unknown')}, Orders: {cancel_result.get('message', 'Unknown')}"
        
        logger_access.info(f"📊 Complete futures closure summary: {combined_message}")
        
        return {
            'success': overall_success,
            'message': combined_message,
            'close_result': close_result,
            'cancel_result': cancel_result
        }
        
    except Exception as e:
        logger_error.error(f"❌ Error in close_positions_and_cancel_orders: {str(e)}")
        return {
            'success': False,
            'message': f'Error closing futures positions and orders: {str(e)}',
            'close_result': {},
            'cancel_result': {}
        }


if __name__ == "__main__":
    # Test the functions
    logger_access.info("🧪 Testing closs_position.py")
    
    # Example usage
    test_session_key = "test_session_123"
    test_api_key = "test_api_key"
    test_secret_key = "test_secret_key"
    test_exchange = "binance"
    
    # Test futures position closing
    result = close_all_futures_positions(
        session_key=test_session_key,
        api_key=test_api_key,
        secret_key=test_secret_key,
        exchange_name=test_exchange
    )
    
    logger_access.info(f"📊 Test result: {result}")