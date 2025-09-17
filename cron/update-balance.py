#!/usr/bin/env python3
"""
Cron job to update paper sessions' current balance every 5 minutes.

Flow:
1) Fetch running paper sessions from Go API (/api/v1/execute/paper-sessions?status=running)
2) For each session_key:
   - Fetch current token balances from Go API (/api/v1/execute/paper/balances?session_key=...)
   - Get current prices to value tokens in USDT
   - Compute total current balance and serialize current_tokens_value
   - Subtract cumulative paper order fees (in USDT) for the session
   - POST update to Go API (/api/v1/execute/paper/update-balance)
"""

import os
import sys
import time
import json
from typing import Dict, Any, Optional, List

# Path setup (project root is one level up from this cron folder)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
sys.path.insert(0, PROJECT_ROOT)

# Local imports from project
from utils.golang_auth import make_golang_api_call
from exchange_api_spot.user import get_client_exchange
from logger import logger_access, logger_error, logger_database

# Fee helpers
try:
    from exchange_api_spot.paper_trade.compute_bl import compute_trade_fee, split_symbol
except Exception:
    # Fallback in case of path differences
    from paper_trade.compute_bl import compute_trade_fee, split_symbol

# Use same execution service base URL as other modules
GOLANG_API_BASE_URL = os.environ.get("GOLANG_API_URL", "http://localhost:8083")

USDT = "USDT"

# Env toggle: subtract paper order fees from computed balance (default: on)
APPLY_PAPER_ORDER_FEES_IN_BALANCE = os.environ.get("APPLY_PAPER_ORDER_FEES_IN_BALANCE", "1") not in ("0", "false", "False")


def to_float(v: Any) -> float:
    try:
        if v is None:
            return 0.0
        if isinstance(v, (int, float)):
            return float(v)
        return float(str(v))
    except Exception:
        return 0.0


def fetch_running_sessions(page: int = 1, limit: int = 10000) -> list:
    """Fetch running paper sessions (manager role to get all)."""
    endpoint = f"/api/v1/execute/paper-sessions?status=running&role=1&page={page}&limit={limit}"
    resp = make_golang_api_call(method="GET", endpoint=endpoint, data=None, base_url=GOLANG_API_BASE_URL)
    if not resp or "data" not in resp:
        logger_access.info(f"No sessions data returned: {resp}")
        return []
    return resp.get("data", [])


def fetch_balances(session_key: str) -> Dict[str, Any]:
    endpoint = f"/api/v1/execute/paper/balances?session_key={session_key}"
    resp = make_golang_api_call(method="GET", endpoint=endpoint, data=None, base_url=GOLANG_API_BASE_URL)
    if not resp or not resp.get("success"):
        logger_access.info(f"Failed to fetch balances for {session_key}: {resp}")
        return {}
    return resp.get("data", {})


def fetch_paper_orders(session_key: str, page: int = 1, limit: int = 10000) -> List[Dict[str, Any]]:
    """Fetch paper orders for a session. Expects execute router at /api/v1/execute/paper-orders."""
    try:
        endpoint = f"/api/v1/execute/paper-orders?session_key={session_key}&page={page}&limit={limit}"
        resp = make_golang_api_call(method="GET", endpoint=endpoint, data=None, base_url=GOLANG_API_BASE_URL)
        if not resp or not resp.get("success"):
            logger_access.info(f"Failed to fetch paper orders for {session_key}: {resp}")
            return []
        data = resp.get("data")
        if isinstance(data, dict) and "items" in data:
            return data.get("items") or []
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        logger_error.error(f"fetch_paper_orders error for {session_key}: {e}")
        return []


def get_price_quote_in_usdt(exchange: str, base: str, quote: str = USDT) -> Optional[float]:
    """Get latest price for base/USDT via exchange client in PAPER_MODE.
    Returns None if unavailable.
    """
    try:
        # Dummy credentials are fine; PAPER_MODE clients don't need real keys
        acc_info = {"api_key": "paper", "secret_key": "paper", "session_key": ""}
        client = get_client_exchange(exchange_name=exchange, acc_info=acc_info, symbol=base, quote=quote, session_key="")
        if not client:
            return None
        price_data = None
        # Prefer get_price if available
        if hasattr(client, "get_price"):
            price_data = client.get_price(base, quote)
        if price_data and isinstance(price_data, dict):
            pr = price_data.get("price") or price_data.get("last") or price_data.get("lastPr")
            return to_float(pr) if pr is not None else None
        # Fallback to get_ticker
        if hasattr(client, "get_ticker"):
            ticker = client.get_ticker(base, quote)
            if ticker and isinstance(ticker, dict):
                pr = ticker.get("last") or ticker.get("lastPr")
                return to_float(pr) if pr is not None else None
    except Exception as e:
        logger_error.error(f"Price fetch error for {base}/{quote} on {exchange}: {e}")
    return None


def compute_total_usdt_value(exchange: str, balances: Dict[str, Any]) -> (float, Dict[str, float]):
    """Compute total value in USDT across balances using current market prices.
    Returns (total_value_usdt, tokens_totals_dict)
    """
    tokens: Dict[str, float] = {}
    total_usdt = 0.0

    for asset, row in balances.items():
        if not isinstance(row, dict):
            continue
        amt = to_float(row.get("total", row.get("available", 0.0)))
        tokens[asset] = amt
        if amt <= 0:
            continue
        if asset == USDT:
            total_usdt += amt
        else:
            price = get_price_quote_in_usdt(exchange, asset, USDT)
            if price is None or price <= 0:
                logger_access.info(f"Missing price for {asset}/USDT; counting as 0 for now")
                continue
            total_usdt += amt * price

    return total_usdt, tokens


def compute_total_paper_fees_usdt(exchange: str, orders: List[Dict[str, Any]]) -> float:
    """Sum paper fees in USDT across orders.
    - Uses order.fee when provided (assumed quoted in the order's quote asset)
    - Fallback: compute via compute_trade_fee using price/qty/side
    - Converts quote->USDT if needed using current quote/USDT price
    Assumption: most symbols are quoted in USDT; if not, conversion is attempted.
    """
    total_fee_usdt = 0.0
    for o in orders:
        try:
            symbol = o.get("symbol") or o.get("Symbol") or ""
            side = (o.get("side") or o.get("Side") or "").upper()
            price = to_float(o.get("avg_price") or o.get("avgPrice") or o.get("price") or o.get("Price") or 0.0)
            qty = to_float(o.get("filled_quantity") or o.get("fillQuantity") or o.get("quantity") or 0.0)
            fee_raw = to_float(o.get("fee") or o.get("Fee") or 0.0)

            if not symbol or not side or price <= 0 or qty <= 0:
                continue

            # Determine base/quote
            try:
                base, quote = split_symbol(symbol)
            except Exception:
                # Default to USDT quote if cannot split
                base, quote = symbol, USDT

            # Determine fee in quote currency
            fee_in_quote = fee_raw
            if fee_in_quote <= 0:
                fee_in_quote = compute_trade_fee(side=side, price=price, quantity=qty, fee_rate=0.0, return_currency="quote")
                # compute_trade_fee will resolve fee rate using defaults/env if 0 passed

            # Convert to USDT if quote != USDT
            if quote == USDT:
                fee_usdt = fee_in_quote
            else:
                q_price_usdt = get_price_quote_in_usdt(exchange, quote, USDT) or 0.0
                fee_usdt = fee_in_quote * q_price_usdt if q_price_usdt > 0 else 0.0

            total_fee_usdt += fee_usdt
        except Exception as e:
            logger_error.error(f"Error computing fee for order {o}: {e}")
            continue
    return total_fee_usdt


def update_session_balance(session_key: str, exchange: str) -> None:
    balances = fetch_balances(session_key)
    if not balances:
        return

    gross_balance_usdt, tokens = compute_total_usdt_value(exchange, balances)

    # Optionally subtract cumulative paper order fees
    net_balance_usdt = gross_balance_usdt
    fee_usdt_total = 0.0
    if APPLY_PAPER_ORDER_FEES_IN_BALANCE:
        orders = fetch_paper_orders(session_key=session_key, page=1, limit=10000)
        if orders:
            fee_usdt_total = compute_total_paper_fees_usdt(exchange, orders)
            net_balance_usdt = max(gross_balance_usdt - fee_usdt_total, 0.0)

    payload = {
        "session_key": session_key,
        "current_balance": float(net_balance_usdt),
        "current_tokens_value": json.dumps(tokens),
    }

    resp = make_golang_api_call(
        method="POST",
        endpoint="/api/v1/execute/paper/update-balance",
        data=payload,
        base_url=GOLANG_API_BASE_URL,
    )
    if resp and resp.get("success"):
        logger_access.info(
            f"Updated balance for {session_key}: gross={gross_balance_usdt}, fees={fee_usdt_total}, net={net_balance_usdt}"
        )
    else:
        logger_access.info(f"Failed to update balance for {session_key}: {resp}")



def run_once():
    sessions = fetch_running_sessions(page=1, limit=500)
    if not sessions:
        logger_access.info("No running paper sessions found")
        return

    for s in sessions:
        try:
            session_key = s.get("session_key") or s.get("SessionKey")
            exchange = (s.get("exchange") or s.get("Exchange") or "binance").lower()
            if not session_key:
                continue
            update_session_balance(session_key, exchange)
        except Exception as e:
            logger_error.error(f"Error processing session {s}: {e}")
            continue


def main():
    interval_sec = int(os.environ.get("UPDATE_BALANCE_INTERVAL_SEC", "30"))  # default 3 minutes
    logger_access.info(
        f"Starting update-balance cron loop, interval={interval_sec}s, base_url={GOLANG_API_BASE_URL}, apply_fees={APPLY_PAPER_ORDER_FEES_IN_BALANCE}"
    )
    while True:
        try:
            run_once()
        except Exception as e:
            logger_error.error(f"update-balance main loop error: {e}")
        time.sleep(interval_sec)


if __name__ == "__main__":
    main()