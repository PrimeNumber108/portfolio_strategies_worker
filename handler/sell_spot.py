#!/usr/bin/env python3
"""
Sell Spot Handler
Handles selling spot positions (converting assets to quote currency) with optional symbol filtering.
"""

import sys
import os
import time
from typing import Dict, Any, Optional, List, Set

# Add the parent directory to the path to import our modules
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../"))
sys.path.insert(0, PROJECT_ROOT)

from exchange_api_spot.user import get_client_exchange
from logger import logger_database, logger_error, logger_access
from utils import get_arg
from utils import make_golang_api_call


def _get_golang_base_url() -> str:
    return os.getenv("GOLANG_API_BASE_URL") or os.getenv("GOLANG_MGMT_API_URL", "http://localhost:8083")


def fetch_session_symbols(session_key: str) -> Set[str]:
    try:
        base_url = _get_golang_base_url()
        endpoint = f"/api/v1/orders/orders/session/{session_key}?limit=1000"
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
        logger_error.error(f"❌ Failed to fetch session symbols from Go: {e}")
        return set()


def get_account_balances(client, exchange_name: str) -> List[Dict[str, Any]]:
    """Get account balances from the exchange client."""
    try:
        if hasattr(client, 'get_account_balance'):
            return client.get_account_balance()
        elif hasattr(client, 'get_balance'):
            return client.get_balance()
        elif hasattr(client, 'get_account'):
            account_info = client.get_account()
            if isinstance(account_info, dict) and 'balances' in account_info:
                return account_info['balances']
            return account_info
        else:
            logger_error.error(f"❌ No balance method found for {exchange_name} client")
            return []
    except Exception as e:
        logger_error.error(f"❌ Error getting balances: {str(e)}")
        return []


def sell_all_spot_assets(session_key: str, api_key: str, secret_key: str, exchange_name: str,
                        passphrase: str = "", symbol: str = "BTC", quote: str = "USDT",
                        min_balance_threshold: float = 0.001,
                        allowed_symbols: Optional[Set[str]] = None) -> Dict[str, Any]:
    """
    Sell spot assets to convert them to the quote currency.
    If allowed_symbols is provided, only sell assets whose trading pair (e.g., BTCUSDT) is in that set.
    """
    try:
        logger_access.info(f"🔄 Starting spot asset liquidation for session: {session_key}")

        # If caller didn't pass allowed_symbols, fetch from Go API by session
        if allowed_symbols is None:
            allowed_symbols = fetch_session_symbols(session_key)
        if allowed_symbols:
            logger_access.info(f"✅ Will only sell symbols: {sorted(allowed_symbols)}")

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
                    continue

                if not asset:
                    continue

                trading_pair = f"{str(asset).upper()}{quote.upper()}"

                # If allowed_symbols present, skip assets not in allowed set
                if allowed_symbols and trading_pair.upper() not in allowed_symbols:
                    skipped_assets.append({
                        'asset': asset,
                        'balance': free_balance,
                        'reason': f'symbol filtered (allowed {sorted(allowed_symbols)})'
                    })
                    continue

                # Skip the quote currency (we're converting TO this currency)
                if str(asset).upper() == quote.upper():
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
                    'asset': str(asset).upper(),
                    'balance': free_balance,
                    'trading_pair': trading_pair
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
                trading_pair = asset_info['trading_pair']

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
    Close spot positions by cancelling open orders and selling assets, restricted to session symbols.
    """
    try:
        logger_access.info(f"🔄 Starting complete spot position closure for session: {session_key}")

        # First, cancel open orders (filtered inside by session symbols)
        from .cancel_order import cancel_spot_orders

        logger_access.info("📋 Step 1: Cancelling open spot orders")
        cancel_result = cancel_spot_orders(session_key, api_key, secret_key, exchange_name, passphrase, symbol, quote)

        # Get allowed symbols once to reuse for selling
        allowed_symbols = fetch_session_symbols(session_key)

        # Then, sell assets filtered by allowed symbols
        logger_access.info("💰 Step 2: Selling spot assets filtered by session symbols")
        sell_result = sell_all_spot_assets(session_key, api_key, secret_key, exchange_name,
                                          passphrase, symbol, quote, allowed_symbols=allowed_symbols)

        overall_success = cancel_result.get('success', False) and sell_result.get('success', False)
        combined_message = f"Orders: {cancel_result.get('message', 'Unknown')}, Assets: {sell_result.get('message', 'Unknown')}"

        logger_access.info(f"📊 Complete spot closure summary: {combined_message}")

        return {
            'success': overall_success,
            'message': combined_message,
            'cancel_result': cancel_result,
            'sell_result': sell_result,
            'allowed_symbols': sorted(list(allowed_symbols)) if allowed_symbols else []
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

    SESSION_ID     = get_arg(1, '')
    EXCHANGE       = get_arg(2, '')
    API_KEY        = get_arg(3, '')
    SECRET_KEY     = get_arg(4, '')
    STRATEGY_NAME  = get_arg(5, '')
    PASSPHRASE     = get_arg(6, '')

    # Test spot asset selling
    result = sell_all_spot_assets(
        session_key=SESSION_ID,
        api_key=API_KEY,
        secret_key=SECRET_KEY,
        exchange_name=EXCHANGE
    )

    logger_access.info(f"📊 Test result: {result}")