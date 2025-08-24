#!/usr/bin/env python3
"""
Exchange Client Factory
This module provides a centralized way to create exchange client instances.
"""

import sys
import os

# Add the parent directory to the path to import our modules
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../"))
sys.path.insert(0, PROJECT_ROOT)

# Import exchange classes
from exchange_api_spot.binance.binance_private_new import BinancePrivateNew
from exchange_api_spot.binance.binance_private import BinancePrivate
from exchange_api_spot.poloniex.poloniex_private import PoloniexPrivate
from exchange_api_spot.paper_trade.paper_trade import PaperTrade

# Import user constants
from utils.user_constants import EXCHANGE, PAPER_MODE
from logger import logger_database, logger_error, logger_access

clients_dict = {}

PAPER_MODE = PAPER_MODE if PAPER_MODE else False

def get_client_exchange(exchange_name = "", acc_info='', symbol='BTC', quote="USDT", session_key="", paper_mode=False):
    """
    Creates and returns a client object for the specified exchange.
    
    Args:
        exchange_name (str): Name of the exchange ('binance', 'poloniex', etc.)
        acc_info (dict): Account information containing api_key, secret_key, passphrase
        symbol (str): Base symbol (default: 'BTC')
        quote (str): Quote symbol (default: 'USDT')
        session_key (str): Session key for tracking (default: '')
        use_proxy (bool): Whether to use proxy for connection (default: False)
    
    Returns:
        Exchange client instance or None if exchange not supported
    """
    client = None
    exchange_name = EXCHANGE or exchange_name 
    
    PAPER_MODE = 'true'
    # logger_error.error("PAPER_MODE 2: ",PAPER_MODE)
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
        exchange_name = str(exchange_name).lower()
        if PAPER_MODE == 'true':
             # Paper trading - no real money involved
                initial_balance = acc_info.get('initial_balance', 10000)  # Default $10,000 balance
                # Use session_key parameter first, then fall back to acc_info
                final_session_key = session_key or acc_info.get('session_key', '')
                client = PaperTrade(
                    symbol=symbol,
                    quote=quote,
                    api_key=acc_info.get('api_key', 'paper_trade'),
                    secret_key=acc_info.get('secret_key', 'paper_trade'),
                    passphrase=acc_info.get('passphrase', ''),
                    session_key=final_session_key,
                    initial_balance=initial_balance,
                    exchange_name=exchange_name,
                    client_x = _get_client_exchange(
                            exchange_name=exchange_name,  
                            acc_info=acc_info,
                            symbol=symbol,
                            quote=quote,
                            session_key = final_session_key
                            )
                )
        else:
            client = _get_client_exchange(
                    exchange_name=exchange_name,
                    acc_info=acc_info,
                    symbol=symbol,
                    quote=quote,
                    session_key=session_key
                    )
            
        
        # Cache the client instance
        if client and acc_info.get("api_key"):
            clients_dict[acc_info['api_key']] = client
            
        return client
        
    except Exception as e:
        logger_error.error(f"❌ Error creating {exchange_name} client: {e}")
        raise

def _get_client_exchange(exchange_name = "", acc_info='', symbol='BTC', quote="USDT", session_key=""):
    client = None
    if exchange_name == 'binance':
        client = BinancePrivateNew(
            symbol=symbol, 
            quote=quote, 
            api_key=acc_info['api_key'], 
            secret_key=acc_info['secret_key'], 
            passphrase=acc_info.get('passphrase', ''),
            use_proxy=False
        )
        
    elif exchange_name == 'binance_old':
        client = BinancePrivate(
            symbol=symbol, 
            quote=quote, 
            api_key=acc_info['api_key'], 
            secret_key=acc_info['secret_key'], 
            passphrase=acc_info.get('passphrase', '')
        )
        
    elif exchange_name == 'poloniex':
        client = PoloniexPrivate(
            symbol=symbol, 
            quote=quote, 
            api_key=acc_info['api_key'], 
            secret_key=acc_info['secret_key'], 
            passphrase=acc_info.get('passphrase', ''),
            session_key=acc_info.get('session_key', '')
        )
        
    # Add more exchanges here as they become available
    elif exchange_name == 'bitget':
        # Placeholder for BitgetPrivate when available
        raise NotImplementedError(f"Exchange '{exchange_name}' is not yet implemented")
        
    elif exchange_name == 'bingx':
        # Placeholder for BingXPrivate when available
        raise NotImplementedError(f"Exchange '{exchange_name}' is not yet implemented")
        
    elif exchange_name == 'gateio':
        # Placeholder for GateioPrivate when available
        raise NotImplementedError(f"Exchange '{exchange_name}' is not yet implemented")
        
    elif exchange_name == 'mexc':
        # Placeholder for MexcPrivate when available
        raise NotImplementedError(f"Exchange '{exchange_name}' is not yet implemented")
        
    elif exchange_name == 'okx':
        # Placeholder for OkxPrivate when available
        raise NotImplementedError(f"Exchange '{exchange_name}' is not yet implemented")
        
    elif exchange_name == 'bybit':
        # Placeholder for BybitPrivate when available
        raise NotImplementedError(f"Exchange '{exchange_name}' is not yet implemented")
        
        
    else:
        raise ValueError(f"Unsupported exchange: {exchange_name}")
    
    return client
    

# Example usage and testing
if __name__ == "__main__":
    
    logger_access.info("\n📝 Example usage:")
    logger_access.info("client = get_client_exchange(")
    logger_access.info("    exchange_name='binance',")
    logger_access.info("    acc_info=account_info,")
    logger_access.info("    symbol='BTC',")
    logger_access.info("    quote='USDT'")
    logger_access.info(")")