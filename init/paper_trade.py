#!/usr/bin/env python3
"""
Paper Trade Init Script
- Initializes a paper portfolio with an initial balance = 1000 USDT
- Emits RESULT: {json} in the same format the Go init parser expects

Output format (aligned with poloniex init expectations):
{
  "success": true,
  "exchange": "paper_trade",
  "session_id": "...",
  "timestamp": 1712345678,
  "balances": {
    "USDT": {"amount": 1000.0, "price": "1"},
    "Total": 1000.0
  },
  "total_value_usd": 1000.0,
  "message": "Initialized paper portfolio"
}
"""
import os
import json
import sys
import time

# Ensure import path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../"))
sys.path.insert(0, PROJECT_ROOT)

from logger import logger_error, logger_database


def main():
    session_id = os.environ.get('STRATEGY_SESSION_KEY', 'paper_demo_session')

    # Fixed paper initial balance
    initial_balance = 1000.0

    # Build balances in the same structure used by real init scripts
    balances = {
        "USDT": {"amount": initial_balance, "price": "1"},
        "Total": initial_balance,
    }

    result = {
        "success": True,
        "exchange": "paper_trade",
        "session_id": session_id,
        "timestamp": int(time.time()),
        "balances": balances,
        # Go init parser reads total_value_usd in the success branch
        "total_value_usd": initial_balance,
        "message": "Initialized paper portfolio",
    }

    # Emit result for Go to parse
    print("RESULT:")
    print(json.dumps(result, indent=2))

    logger_database.info("Paper init executed for session %s", session_id)


if __name__ == "__main__":
    main()