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


def main():
    """
    Main function to close spot orders and sell all assets.
    Expects command line arguments: session_key, exchange, api_key, api_secret
    """
    try:
        # Get arguments from command line
        if len(sys.argv) < 5:
            raise ValueError("Missing required arguments: session_key, exchange, api_key, api_secret")
        
        session_key = sys.argv[1]
        exchange = sys.argv[2]
        api_key = sys.argv[3]
        api_secret = sys.argv[4]
        
        logger_access.info(f"🔄 Starting spot position closure and asset selling for session: {session_key}")
        
        # Call the close spot positions and sell function
        result = close_spot_positions_and_sell(
            session_key=session_key,
            api_key=api_key,
            secret_key=api_secret,
            exchange_name=exchange
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