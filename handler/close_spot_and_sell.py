#!/usr/bin/env python3
"""
Close Spot and Sell Handler
Handles closing all spot orders and selling all assets.
"""

import sys
import os
import json

# Add the parent directory to the path to import our modules
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../"))
sys.path.insert(0, PROJECT_ROOT)

from sell_spot import close_spot_positions_and_sell
from logger import logger_access, logger_error
from utils import get_arg


def main():
    """
    Main function to close spot orders and sell all assets.
    Expects command line arguments: session_key, exchange, api_key, api_secret
    """
    try:

        SESSION_ID     = get_arg(1, '')
        EXCHANGE       = get_arg(2, '')
        API_KEY        = get_arg(3, '')
        SECRET_KEY     = get_arg(4, '')
        STRATEGY_NAME  = get_arg(5, '')
        PASSPHRASE     = get_arg(6, '')
        ASSET_FILTER   = ''
        
        
        logger_access.info(f"🔄 Starting spot position closure and asset selling for session: {SESSION_ID}")
        
        # Call the close spot positions and sell function
        result = close_spot_positions_and_sell(
            session_key=SESSION_ID,
            api_key=API_KEY,
            secret_key=SECRET_KEY,
            exchange_name=EXCHANGE
        )
        
        # Output result as JSON
        print(json.dumps(result))
        
    except Exception as e:
        logger_error.error(f"❌ Error in close_spot_and_sell main: {str(e)}")
        error_result = {
            'success': False,
            'message': f'Error closing spot positions and selling: {str(e)}',
            'cancel_result': {},
            'sell_result': {}
        }
        print(json.dumps(error_result))


if __name__ == "__main__":
    main()