#!/usr/bin/env python3
"""
Sell Spot Handler
Handles selling all spot positions (converting all assets to quote currency).
"""

import sys
import os

# Add the parent directory to the path to import our modules
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../"))
sys.path.insert(0, PROJECT_ROOT)

from exchange_api_spot.user import get_client_exchange
from logger import logger_database, logger_error, logger_access
from typing import Dict, Any, Optional, List
import time


def get_account_balances(client, exchange_name: str) -> Dict[str, Any]:
    """
    Get account balances from the exchange client.
    
    Args:
        client: Exchange client instance
        exchange_name: Name of the exchange
        
    Returns:
        Dict containing balance information
    """
    try:
        if hasattr(client, 'get_account_balance'):
            return client.get_account_balance()
        elif hasattr(client, 'get_balance'):
            return client.get_balance()
        elif hasattr(client, 'get_account'):
            account_info = client.get_account()
            if 'balances' in account_info:
                return account_info['balances']
            return account_info
        else:
            logger_error.error(f"❌ No balance method found for {exchange_name} client")
            return {}
    except Exception as e:
        logger_error.error(f"❌ Error getting balances: {str(e)}")
        return {}


def sell_all_spot_assets(session_key: str, api_key: str, secret_key: str, exchange_name: str,
                        passphrase: str = "", symbol: str = "BTC", quote: str = "USDT",
                        min_balance_threshold: float = 0.001) -> Dict[str, Any]:
    """
    Sell all spot assets to convert them to the quote currency.
    
    Args:
        session_key: Trading session identifier
        api_key: Exchange API key
        secret_key: Exchange secret key
        exchange_name: Name of the exchange (binance, poloniex, etc.)
        passphrase: Exchange passphrase (if required)
        symbol: Base symbol (default: BTC)
        quote: Quote symbol to convert to (default: USDT)
        min_balance_threshold: Minimum balance to consider for selling
        
    Returns:
        Dict containing success status and details
    """
    try:
        logger_access.info(f"🔄 Starting spot asset liquidation for session: {session_key}")
        
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
        
        # Get account balances
        try:
            balances = get_account_balances(client, exchange_name)
            logger_access.info(f"📊 Retrieved account balances: {len(balances) if balances else 0} assets")
            
            if not balances:
                return {
                    'success': True,
                    'message': 'No balances found to liquidate',
                    'sold_assets': [],
                    'failed_assets': [],
                    'skipped_assets': []
                }
            
        except Exception as e:
            logger_error.error(f"❌ Error getting account balances: {str(e)}")
            return {
                'success': False,
                'message': f'Failed to get account balances: {str(e)}',
                'sold_assets': [],
                'failed_assets': [],
                'skipped_assets': []
            }
        
        # Process balances and identify assets to sell
        assets_to_sell = []
        skipped_assets = []
        
        for balance_item in balances:
            try:
                # Handle different balance formats from different exchanges
                if isinstance(balance_item, dict):
                    asset = balance_item.get('asset') or balance_item.get('currency') or balance_item.get('coin')
                    free_balance = float(balance_item.get('free', 0) or balance_item.get('available', 0) or balance_item.get('balance', 0))
                else:
                    # Skip if balance format is not recognized
                    continue
                
                if not asset:
                    continue
                
                # Skip the quote currency (we're converting TO this currency)
                if asset.upper() == quote.upper():
                    skipped_assets.append({
                        'asset': asset,
                        'balance': free_balance,
                        'reason': 'Quote currency - no need to sell'
                    })
                    continue
                
                # Skip assets with balance below threshold
                if free_balance < min_balance_threshold:
                    skipped_assets.append({
                        'asset': asset,
                        'balance': free_balance,
                        'reason': f'Balance below threshold ({min_balance_threshold})'
                    })
                    continue
                
                assets_to_sell.append({
                    'asset': asset,
                    'balance': free_balance
                })
                
            except Exception as e:
                logger_error.error(f"❌ Error processing balance item {balance_item}: {str(e)}")
                continue
        
        logger_access.info(f"📋 Found {len(assets_to_sell)} assets to sell, {len(skipped_assets)} skipped")
        
        if not assets_to_sell:
            return {
                'success': True,
                'message': 'No assets found that need to be sold',
                'sold_assets': [],
                'failed_assets': [],
                'skipped_assets': skipped_assets
            }
        
        # Sell each asset
        sold_assets = []
        failed_assets = []
        
        for asset_info in assets_to_sell:
            try:
                asset = asset_info['asset']
                balance = asset_info['balance']
                trading_pair = f"{asset}{quote}"  # e.g., BTCUSDT
                
                logger_access.info(f"🔄 Selling {balance} {asset} for {quote} (pair: {trading_pair})")
                
                # Create market sell order
                try:
                    # Different exchanges may have different method names
                    if hasattr(client, 'create_market_sell_order'):
                        order_result = client.create_market_sell_order(trading_pair, balance)
                    elif hasattr(client, 'market_sell'):
                        order_result = client.market_sell(trading_pair, balance)
                    elif hasattr(client, 'create_order'):
                        order_result = client.create_order(
                            symbol=trading_pair,
                            side='SELL',
                            type='MARKET',
                            quantity=balance
                        )
                    else:
                        raise Exception(f"No market sell method found for {exchange_name}")
                    
                    if order_result:
                        logger_access.info(f"✅ Successfully sold {balance} {asset}")
                        sold_assets.append({
                            'asset': asset,
                            'balance': balance,
                            'trading_pair': trading_pair,
                            'order_result': order_result
                        })
                    else:
                        logger_error.error(f"❌ Failed to sell {asset}: Order result was None/False")
                        failed_assets.append({
                            'asset': asset,
                            'balance': balance,
                            'trading_pair': trading_pair,
                            'error': 'Order result was None/False'
                        })
                        
                except Exception as e:
                    logger_error.error(f"❌ Error creating sell order for {asset}: {str(e)}")
                    failed_assets.append({
                        'asset': asset,
                        'balance': balance,
                        'trading_pair': trading_pair,
                        'error': str(e)
                    })
                
                # Add small delay between orders to avoid rate limits
                time.sleep(0.1)
                
            except Exception as e:
                logger_error.error(f"❌ Error processing asset {asset_info}: {str(e)}")
                failed_assets.append({
                    'asset': asset_info.get('asset', 'unknown'),
                    'balance': asset_info.get('balance', 0),
                    'error': str(e)
                })
        
        success = len(failed_assets) == 0
        message = f"Sold {len(sold_assets)} assets"
        if failed_assets:
            message += f", {len(failed_assets)} failed"
        if skipped_assets:
            message += f", {len(skipped_assets)} skipped"
        
        logger_access.info(f"📊 Spot asset liquidation summary: {message}")
        
        return {
            'success': success,
            'message': message,
            'sold_assets': sold_assets,
            'failed_assets': failed_assets,
            'skipped_assets': skipped_assets
        }
        
    except Exception as e:
        logger_error.error(f"❌ Error in sell_all_spot_assets: {str(e)}")
        return {
            'success': False,
            'message': f'Error selling spot assets: {str(e)}',
            'sold_assets': [],
            'failed_assets': [],
            'skipped_assets': []
        }


def close_spot_positions_and_sell(session_key: str, api_key: str, secret_key: str, exchange_name: str,
                                 passphrase: str = "", symbol: str = "BTC", quote: str = "USDT") -> Dict[str, Any]:
    """
    Close all spot positions by selling all assets to quote currency.
    This is the main function to be called for "Close open orders and Sell All" option.
    
    Args:
        session_key: Trading session identifier
        api_key: Exchange API key
        secret_key: Exchange secret key
        exchange_name: Name of the exchange
        passphrase: Exchange passphrase (if required)
        symbol: Base symbol
        quote: Quote symbol to convert to
        
    Returns:
        Dict containing success status and details
    """
    try:
        logger_access.info(f"🔄 Starting complete spot position closure for session: {session_key}")
        
        # First, cancel all open orders (import from cancel_order.py)
        from .cancel_order import cancel_spot_orders
        
        logger_access.info("📋 Step 1: Cancelling open spot orders")
        cancel_result = cancel_spot_orders(session_key, api_key, secret_key, exchange_name, 
                                         passphrase, symbol, quote)
        
        # Then, sell all assets
        logger_access.info("💰 Step 2: Selling all spot assets")
        sell_result = sell_all_spot_assets(session_key, api_key, secret_key, exchange_name,
                                         passphrase, symbol, quote)
        
        # Combine results
        overall_success = cancel_result.get('success', False) and sell_result.get('success', False)
        
        combined_message = f"Orders: {cancel_result.get('message', 'Unknown')}, Assets: {sell_result.get('message', 'Unknown')}"
        
        logger_access.info(f"📊 Complete spot closure summary: {combined_message}")
        
        return {
            'success': overall_success,
            'message': combined_message,
            'cancel_result': cancel_result,
            'sell_result': sell_result
        }
        
    except Exception as e:
        logger_error.error(f"❌ Error in close_spot_positions_and_sell: {str(e)}")
        return {
            'success': False,
            'message': f'Error closing spot positions: {str(e)}',
            'cancel_result': {},
            'sell_result': {}
        }


if __name__ == "__main__":
    # Test the functions
    logger_access.info("🧪 Testing sell_spot.py")
    
    # Example usage
    test_session_key = "test_session_123"
    test_api_key = "test_api_key"
    test_secret_key = "test_secret_key"
    test_exchange = "binance"
    
    # Test spot asset selling
    result = sell_all_spot_assets(
        session_key=test_session_key,
        api_key=test_api_key,
        secret_key=test_secret_key,
        exchange_name=test_exchange
    )
    
    logger_access.info(f"📊 Test result: {result}")