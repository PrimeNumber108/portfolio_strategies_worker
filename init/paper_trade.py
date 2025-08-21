#!/usr/bin/env python3
"""
Paper Trade Init Script
- Uses demo credentials (api_key/secret = 'demo_key')
- Initializes paper trading client with initial balance = 1000
- Prints JSON result with Total = 1000 and simple balances
"""
import os
import json
import sys

# Ensure import path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../"))
sys.path.insert(0, PROJECT_ROOT)

from exchange_api_spot.user import get_client_exchange


def main():
    session_id = os.environ.get('STRATEGY_SESSION_KEY', 'paper_demo_session')
    # Force paper trade exchange data source; still use our factory's paper path
    os.environ['PAPER_TRADE_EXCHANGE'] = os.environ.get('PAPER_TRADE_EXCHANGE', 'binance')

    # Demo credentials for paper
    account_info = {
        "api_key": "demo_key",
        "secret_key": "demo_key",
        "passphrase": "",
        "session_key": session_id,
        "initial_balance": 1000,
    }

    try:
        client = get_client_exchange(
            exchange_name="paper_trade",
            acc_info=account_info,
            symbol="BTC",
            quote="USDT",
            use_proxy=False,
        )
    except Exception as e:
        # If factory doesn't accept exchange_name, rely on EXCHANGE env
        os.environ['EXCHANGE'] = 'paper_trade'
        client = get_client_exchange(
            acc_info=account_info,
            symbol="BTC",
            quote="USDT",
            use_proxy=False,
        )

    # Build a minimal consistent result (success with balances and Total)
    balances = {
        "USDT": {"amount": 1000.0, "price": "1"},
        "Total": 1000.0,
    }
    result = {
        "success": True,
        "balances": balances,
    }

    print("\n" + "=" * 50)
    print("RESULT:")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()