#!/usr/bin/env python3
"""
Close Future Positions Handler
Handles closing all open future positions only.
"""

import sys
import os
import json

# Add the parent directory to the path to import our modules
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../"))
sys.path.insert(0, PROJECT_ROOT)

from closs_position import close_all_futures_positions
from logger import logger_access, logger_error


def main():
    """
    Main function to close future positions.
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
        
        logger_access.info(f"🔄 Starting future position closure for session: {session_key}")
        
        # Call the close all futures positions function
        result = close_all_futures_positions(
            session_key=session_key,
            api_key=api_key,
            secret_key=api_secret,
            exchange_name=exchange
        )
        
        # Output result as JSON
        print(json.dumps(result))
        
    except Exception as e:
        logger_error.error(f"❌ Error in close_future_positions main: {str(e)}")
        error_result = {
            'success': False,
            'message': f'Error closing future positions: {str(e)}',
            'closed_positions': [],
            'failed_positions': []
        }
        print(json.dumps(error_result))


if __name__ == "__main__":
    main()