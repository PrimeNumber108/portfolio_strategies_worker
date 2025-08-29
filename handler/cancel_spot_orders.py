#!/usr/bin/env python3
"""
Cancel Spot Orders Handler
Handles canceling all open spot orders only.
"""

import sys
import os
import json

# Add the parent directory to the path to import our modules
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../"))
sys.path.insert(0, PROJECT_ROOT)

from cancel_order import cancel_spot_orders
from logger import logger_access, logger_error
from utils import get_arg


def main():
    """
    Main function to cancel spot orders.
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
        
        logger_access.info(f"🔄 Starting spot order cancellation for session: {SESSION_ID}")
        logger_access.info(f"🔄 Starting spot order cancellation for exchange: {EXCHANGE}")
        logger_access.info(f"🔄 Starting spot order cancellation for api_key: {API_KEY}")
        logger_access.info(f"🔄 Starting spot order cancellation for api_secret: {SECRET_KEY}")
        # Call the cancel spot orders function
        result = cancel_spot_orders(
            session_key=SESSION_ID,
            api_key=API_KEY,
            secret_key=SECRET_KEY,
            exchange_name=EXCHANGE
        )
        
        # Output result as JSON
        print(json.dumps(result))
        logger_access.info(json.dumps("output: ", result))
        
    except Exception as e:
        logger_error.error(f"❌ Error in cancel_spot_orders main: {str(e)}")
        error_result = {
            'success': False,
            'message': f'Error canceling spot orders: {str(e)}',
            'cancelled_orders': [],
            'failed_orders': []
        }
        print(json.dumps(error_result))


if __name__ == "__main__":
    main()