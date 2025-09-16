#!/usr/bin/env python3
"""
Close Spot and Sell Handler
Handles closing spot orders and selling assets limited to symbols traded in the session.
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
from utils import make_golang_api_call


def _get_golang_base_url() -> str:
    return os.getenv("GOLANG_API_BASE_URL") or os.getenv("GOLANG_MGMT_API_URL", "http://localhost:8083")


def fetch_session_symbols(session_key: str):
    try:
        base_url = _get_golang_base_url()
        endpoint = f"/api/v1/orders/orders/session/{session_key}?limit=1000"
        resp = make_golang_api_call(method="GET", endpoint=endpoint, data=None, base_url=base_url)
        symbols = []
        if isinstance(resp, dict):
            orders = resp.get("orders") or []
            seen = set()
            for o in orders:
                sym = (o.get("symbol") or "").upper()
                if sym and sym not in seen:
                    seen.add(sym)
                    symbols.append(sym)
        logger_access.info(f"📡 Symbols for session {session_key}: {symbols}")
        return symbols
    except Exception as e:
        logger_error.error(f"❌ Failed to fetch symbols from Go API: {e}")
        return []


def main():
    """
    Close spot orders and sell assets restricted to session symbols.
    Expects: session_key, exchange, api_key, api_secret, strategy, passphrase
    """
    try:
        SESSION_ID     = get_arg(1, '')
        EXCHANGE       = get_arg(2, '')
        API_KEY        = get_arg(3, '')
        SECRET_KEY     = get_arg(4, '')
        STRATEGY_NAME  = get_arg(5, '')
        PASSPHRASE     = get_arg(6, '')

        logger_access.info(f"🔄 Starting spot position closure and selling for session: {SESSION_ID}")

        # Fetch symbols from Go service to limit actions
        session_symbols = fetch_session_symbols(SESSION_ID)

        # Call the close spot positions and sell function
        # This function will internally cancel orders and sell; we pass symbol/quote as defaults.
        result = close_spot_positions_and_sell(
            session_key=SESSION_ID,
            api_key=API_KEY,
            secret_key=SECRET_KEY,
            exchange_name=EXCHANGE
        )

        # Attach session symbols for transparency in output
        result["session_symbols"] = session_symbols

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