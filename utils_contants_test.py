#!/usr/bin/env python3
"""
User Constants
This module provides centralized access to environment variables for the trading system.
"""

import os
from exchange_api_spot.user import get_client_exchange

# API Credentials
API_KEY = os.environ.get("STRATEGY_API_KEY", "")
SECRET_KEY = os.environ.get("STRATEGY_API_SECRET", "")
PASSPHRASE = os.environ.get("STRATEGY_PASSPHRASE", "")

# Exchange Configuration
EXCHANGE = os.environ.get("EXCHANGE", "")
PAPER_MODE = os.environ.get("PAPER_TRADING", False)


def get_client_new(symbol='BTC', quote="USDT"):
    
    return get_client_exchange(exchange_name=EXCHANGE,
                               acc_info={'api_key': API_KEY, 'secret_key': SECRET_KEY, 'passphrase': PASSPHRASE},
                               symbol=symbol,
                               quote=quote,
                               )