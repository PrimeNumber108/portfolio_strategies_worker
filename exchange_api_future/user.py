#!/usr/bin/env python3
"""
Exchange Future Client Factory
This module provides a centralized way to create exchange future client instances.
"""

import sys
import os

# Add the parent directory to the path to import our modules
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../"))
sys.path.insert(0, PROJECT_ROOT)

# Import exchange future classes
from exchange_api_future.binance_future.binance_future_private import BinanceFuturePrivate

# Import user constants
from utils.user_constants import EXCHANGE, PAPER_MODE
from logger import logger_database, logger_error

# Global dictionary to cache client instances
clients_dict = {}

EXCHANGE = EXCHANGE.lower() if EXCHANGE else "binance"
PAPER_MODE = PAPER_MODE if PAPER_MODE else False

logger_database.info(f"Creating exchange future client for {EXCHANGE} with PAPER_MODE={PAPER_MODE}")

def get_client_exchange(acc_info='', symbol='BTC', quote="USDT", use_proxy=False):
    """
    Creates and returns a future client object for the specified exchange.
    
    Args:
        acc_info (dict): Account information containing api_key, secret_key, passphrase
        symbol (str): Base symbol (default: 'BTC')
        quote (str): Quote symbol (default: 'USDT')
        use_proxy (bool): Whether to use proxy for connection (default: False)
    
    Returns:
        Exchange future client instance or None if exchange not supported
    """
    client = None
    exchange_name = EXCHANGE
    
    try:
        # Check if client already exists in cache
        if acc_info and "api_key" in acc_info and acc_info["api_key"] in clients_dict:
            return clients_dict[acc_info['api_key']]
        
        # Validate acc_info
        if not acc_info or not isinstance(acc_info, dict):
            raise ValueError("acc_info must be a dictionary containing API credentials")
        
        if "api_key" not in acc_info or "secret_key" not in acc_info:
            raise ValueError("acc_info must contain 'api_key' and 'secret_key'")
        
        # Create client based on exchange name
        exchange_name = exchange_name.lower()
        
        if exchange_name == 'binance' or exchange_name == 'binance_future':
            client = BinanceFuturePrivate(
                symbol=symbol, 
                quote=quote, 
                api_key=acc_info['api_key'], 
                secret_key=acc_info['secret_key'], 
                passphrase=acc_info.get('passphrase', '')
            )
            
        # Add more future exchanges here as they become available
        elif exchange_name == 'bitget' or exchange_name == 'bitget_future':
            # Placeholder for BitgetFuturePrivate when available
            raise NotImplementedError(f"Exchange '{exchange_name}' is not yet implemented")
            
        elif exchange_name == 'bingx' or exchange_name == 'bingx_future':
            # Placeholder for BingXFuturePrivate when available
            raise NotImplementedError(f"Exchange '{exchange_name}' is not yet implemented")
            
        elif exchange_name == 'gateio' or exchange_name == 'gateio_future':
            # Placeholder for GateioFuturePrivate when available
            raise NotImplementedError(f"Exchange '{exchange_name}' is not yet implemented")
            
        elif exchange_name == 'mexc' or exchange_name == 'mexc_future':
            # Placeholder for MexcFuturePrivate when available
            raise NotImplementedError(f"Exchange '{exchange_name}' is not yet implemented")
            
        elif exchange_name == 'okx' or exchange_name == 'okx_future':
            # Placeholder for OkxFuturePrivate when available
            raise NotImplementedError(f"Exchange '{exchange_name}' is not yet implemented")
            
        elif exchange_name == 'bybit' or exchange_name == 'bybit_future':
            # Placeholder for BybitFuturePrivate when available
            raise NotImplementedError(f"Exchange '{exchange_name}' is not yet implemented")
            
        elif exchange_name == 'poloniex' or exchange_name == 'poloniex_future':
            # Placeholder for PoloniexFuturePrivate when available
            raise NotImplementedError(f"Exchange '{exchange_name}' is not yet implemented")
            
        elif exchange_name == 'kucoin' or exchange_name == 'kucoin_future':
            # Placeholder for KucoinFuturePrivate when available
            raise NotImplementedError(f"Exchange '{exchange_name}' is not yet implemented")
            
        elif exchange_name == 'huobi' or exchange_name == 'huobi_future':
            # Placeholder for HuobiFuturePrivate when available
            raise NotImplementedError(f"Exchange '{exchange_name}' is not yet implemented")
            
        elif PAPER_MODE == True:
            # Paper trading - no real money involved
            # For now, use the spot paper trading as futures paper trading isn't implemented yet
            from exchange_api_spot.paper_trade.paper_trade import PaperTrade
            
            initial_balance = acc_info.get('initial_balance', 10000)  # Default $10,000 balance
            client = PaperTrade(
                symbol=symbol,
                quote=quote,
                api_key=acc_info.get('api_key', 'paper_trade_future'),
                secret_key=acc_info.get('secret_key', 'paper_trade_future'),
                passphrase=acc_info.get('passphrase', ''),
                session_key=acc_info.get('session_key', ''),
                initial_balance=initial_balance,
                exchange=exchange_name
            )
            logger_database.info(f"Using spot paper trading for future trading simulation: {exchange_name}")
            
        else:
            raise ValueError(f"Unsupported future exchange: {exchange_name}")
        
        # Cache the client instance
        if client and acc_info.get("api_key"):
            clients_dict[acc_info['api_key']] = client
            
        return client
        
    except Exception as e:
        print(f"❌ Error creating {exchange_name} future client: {e}")
        logger_error.error(f"Failed to create future client for {exchange_name}: {e}")
        raise

def get_supported_exchanges():
    """
    Returns a list of supported future exchange names.
    
    Returns:
        list: List of supported future exchange names
    """
    return [
        'binance',
        'binance_future',
        # Future exchanges (not yet implemented)
        # 'bitget',
        # 'bitget_future',
        # 'bingx', 
        # 'bingx_future',
        # 'gateio',
        # 'gateio_future',
        # 'mexc',
        # 'mexc_future',
        # 'okx',
        # 'okx_future',
        # 'bybit',
        # 'bybit_future',
        # 'poloniex_future',
        # 'kucoin_future',
        # 'huobi_future'
    ]

def clear_client_cache(api_key=None):
    """
    Clear the client cache.
    
    Args:
        api_key (str, optional): Specific API key to remove. If None, clears all.
    """
    global clients_dict
    
    if api_key:
        if api_key in clients_dict:
            del clients_dict[api_key]
            print(f"✅ Cleared cache for API key: {api_key[:8]}...")
    else:
        clients_dict.clear()
        print("✅ Cleared all future client cache")

def get_client_info(api_key):
    """
    Get information about a cached client.
    
    Args:
        api_key (str): API key to look up
        
    Returns:
        dict: Client information or None if not found
    """
    if api_key in clients_dict:
        client = clients_dict[api_key]
        return {
            "api_key": api_key[:8] + "...",
            "symbol": getattr(client, 'symbol', 'Unknown'),
            "quote": getattr(client, 'quote', 'Unknown'),
            "exchange": client.__class__.__name__,
            "type": "future"
        }
    return None

def get_all_cached_clients():
    """
    Get information about all cached clients.
    
    Returns:
        list: List of client information dictionaries
    """
    return [get_client_info(api_key) for api_key in clients_dict.keys()]

def is_exchange_supported(exchange_name):
    """
    Check if an exchange is supported.
    
    Args:
        exchange_name (str): Name of the exchange to check
        
    Returns:
        bool: True if supported, False otherwise
    """
    return exchange_name.lower() in [ex.lower() for ex in get_supported_exchanges()]

# Example usage and testing
if __name__ == "__main__":
    print("🔧 Exchange Future Client Factory")
    print("Supported exchanges:", get_supported_exchanges())
    
    # Example account info structure
    example_acc_info = {
        "api_key": "your_api_key_here",
        "secret_key": "your_secret_key_here",
        "passphrase": "your_passphrase_here"  # Optional, not used by all exchanges
    }
    
    print(f"\n📝 Current configuration:")
    print(f"- EXCHANGE: {EXCHANGE}")
    print(f"- PAPER_MODE: {PAPER_MODE}")
    
    print("\n📝 Example usage:")
    print("client = get_client_exchange(")
    print("    acc_info=account_info,")
    print("    symbol='BTC',")
    print("    quote='USDT'")
    print(")")
    
    print("\n🔍 Available functions:")
    print("- get_client_exchange(acc_info, symbol, quote, use_proxy)")
    print("- get_supported_exchanges()")
    print("- clear_client_cache(api_key=None)")
    print("- get_client_info(api_key)")
    print("- get_all_cached_clients()")
    print("- is_exchange_supported(exchange_name)")
    
    print("\n🔧 Environment Variables:")
    print("- EXCHANGE: Set the default exchange name (e.g., 'binance')")
    print("- PAPER_TRADING: Set to 'true' for paper trading mode")