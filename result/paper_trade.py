#!/usr/bin/env python3
"""
Paper Trade Result Checker
- Computes balances for a paper session by reading session data from management API
- Emits a single-line RESULT: {json} compatible with Go parser

Result format:
{
  "success": true,
  "balances": { "Cash": 1000.0, "BTCUSDT": {"qty": 0.12, "price": 65000, "value": 7800}, "Total": 8800.0 },
  "exchange": "binance",
  "orders_count": 3,
  "session_key": "paper_xxx"
}
"""
import os
import json
import sys
import time
from typing import Dict, Any, List, Tuple
from logger import logger_error, logger_database

try:
    import requests
except Exception:
    requests = None

# Make sure our project modules are importable (logger, etc.)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../"))
sys.path.insert(0, PROJECT_ROOT)


def env(name: str, default: str = "") -> str:
    v = os.environ.get(name)
    return v if v is not None else default


def get_base_url() -> str:
    return env("MGNT_API_BASE_URL", "http://localhost:8083")


def get_session_key() -> str:
    return env("STRATEGY_SESSION_KEY", "")


def get_auth_header() -> Dict[str, str]:
    token = env("STRATEGY_JWT", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


def fetch_last_balance(base_url: str, session_key: str) -> Dict[str, Any]:
    """
    Fetches orders for paper session and returns them with initial balance.
    Calls the new paper-orders endpoint.
    """
    url = f"{base_url}/api/v1/execute/paper-orders"
    params = {"session_key": session_key}
    headers = {"Content-Type": "application/json"}
    headers.update(get_auth_header())

    if requests is None:
        import urllib.request, urllib.parse
        final_url = f"{url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(final_url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            response = json.loads(resp.read().decode("utf-8"))
    else:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        response = r.json()
    
    # Transform response to expected format
    return {
        "success": response.get("success", False),
        "initial_balance": 1000.0,  # Fixed initial balance for paper trading
        "orders": response.get("data", []),
        "session_key": response.get("session_key", session_key),
        "count": response.get("count", 0)
    }


def parse_symbol(symbol: str) -> Tuple[str, str, str]:
    s = (symbol or '').strip().upper()
    if '/' in s:
        base, quote = s.split('/', 1)
        return base, quote, f"{base}/{quote}"
    for q in ("USDT", "USD", "USDC", "BUSD", "BTC", "ETH"):
        if s.endswith(q):
            base = s[:-len(q)]
            return base, q, f"{base}{q}"
    return s or 'BTC', 'USDT', f"{(s or 'BTC')}USDT"


def compute_balance(initial_balance: float, orders: List[Dict[str, Any]]) -> Dict[str, Any]:
    cash = float(initial_balance or 0)
    positions: Dict[str, Dict[str, float]] = {}
    last_trade_price: Dict[str, float] = {}

    # Infer exchange from orders (optional)
    exchange = (orders[0].get("exchange") if orders else "binance") or "binance"

    for o in orders:
        sym = (o.get("symbol") or "").upper()
        side = (o.get("side") or o.get("Side") or "").upper()
        qty = float(o.get("filled_quantity") or o.get("quantity") or 0)
        price = float(o.get("avg_price") or o.get("price") or 0)
        fee = float(o.get("fee") or 0)

        if price > 0:
            last_trade_price[sym] = price

        if sym not in positions:
            positions[sym] = {"qty": 0.0}

        if side == "BUY":
            cash -= qty * price + fee
            positions[sym]["qty"] += qty
        elif side == "SELL":
            cash += qty * price - fee
            positions[sym]["qty"] -= qty
        else:
            continue

    balances: Dict[str, Any] = {}
    inventory_value = 0.0

    for sym, pos in positions.items():
        qty = float(pos.get("qty") or 0)
        if abs(qty) < 1e-12:
            continue
        price = last_trade_price.get(sym, 0.0)
        value = qty * price
        inventory_value += value
        balances[sym] = {"qty": qty, "price": price, "value": value}

    total = cash + inventory_value
    balances["Cash"] = round(cash, 8)
    balances["Total"] = round(total, 8)

    return {
        "success": True,
        "balances": balances,
        "exchange": exchange,
        "orders_count": len(orders),
    }


def main():
    session_key = get_session_key()
    if not session_key:
        result = {
            "success": True,
            "balances": {"Cash": 1000.0, "Total": 1000.0},
            "warning": "Missing STRATEGY_SESSION_KEY; using defaults",
        }
        print("RESULT: " + json.dumps(result))
        return

    base_url = get_base_url()

    try:
        payload = fetch_last_balance(base_url, session_key)
        
        if not payload.get("success"):
            raise RuntimeError(payload)
        initial_balance = float(payload.get("initial_balance") or 0)
        orders = payload.get("orders") or []
        result = compute_balance(initial_balance, orders)
        result.update({
            "session_key": session_key,
        })
        logger_database.info("run result success")

    except Exception as e:
        result = {
            "success": True,
            "error": str(e),
            "balances": {"Cash": 0.0, "Total": 0.0},
            "session_key": session_key,
        }
        logger_database.info("run result error")


    # Single-line RESULT for Go parser
    print("RESULT: " + json.dumps(result))

if __name__ == "__main__":
    main()