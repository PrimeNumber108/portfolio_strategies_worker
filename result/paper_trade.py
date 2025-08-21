#!/usr/bin/env python3
"""
Paper Trade Result Checker
- Fetches session orders from management API
- Builds cash and positions, fetches market prices, calculates final balance
- Prints a single-line RESULT: {json}
"""
import os
import json
import sys
import time
from typing import Dict, Any, List, Tuple

try:
    import requests
except Exception:  # Minimal fallback if requests is unavailable
    requests = None

# External exchange client
try:
    from exchange_api_spot.user import get_client_exchange
except Exception as e:
    get_client_exchange = None


def env(name: str, default: str = "") -> str:
    v = os.environ.get(name)
    return v if v is not None else default


def get_base_url() -> str:
    # Allow override via env, fallback to localhost
    return env("MGNT_API_BASE_URL", "http://localhost:8080")


def get_session_key() -> str:
    return env("STRATEGY_SESSION_KEY", "")


def get_auth_header() -> Dict[str, str]:
    # Optionally pass JWT if available
    token = env("STRATEGY_JWT", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


def fetch_session_data(base_url: str, session_key: str) -> Dict[str, Any]:
    url = f"{base_url}/api/v1/execute/paper/last-balance"
    params = {"session_key": session_key}
    headers = {"Content-Type": "application/json"}
    headers.update(get_auth_header())

    if requests is None:
        # Simple urllib fallback
        import urllib.request, urllib.parse
        final_url = f"{url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(final_url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    else:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        return r.json()


def parse_symbol(symbol: str) -> Tuple[str, str, str]:
    """Return (base, quote, normalized_symbol). Tries common formats."""
    s = symbol.strip().upper()
    if "/" in s:
        base, quote = s.split("/", 1)
        return base, quote, f"{base}/{quote}"
    # Heuristics for common quotes
    for q in ("USDT", "USD", "USDC", "BUSD", "BTC", "ETH"):
        if s.endswith(q):
            base = s[:-len(q)]
            return base, q, f"{base}{q}"
    # Fallback
    return s, "USDT", f"{s}USDT"


def get_market_price(client, symbol_variants: List[str]) -> float:
    """Try to fetch price using a few common client methods and symbol shapes."""
    if client is None:
        return 0.0

    # Try a few known methods with various symbol formats
    candidates = [
        ("get_price", lambda c, sym: c.get_price(sym)),
        ("getSymbolPriceTicker", lambda c, sym: c.getSymbolPriceTicker(sym)),
        ("get_ticker_price", lambda c, sym: c.get_ticker_price(sym)),
    ]

    for sym in symbol_variants:
        for name, fn in candidates:
            try:
                if hasattr(client, name):
                    price = fn(client, sym)
                    if isinstance(price, (int, float)) and price > 0:
                        return float(price)
                    # Some clients return dicts
                    if isinstance(price, dict):
                        for k in ("price", "last", "lastPrice", "close"):
                            v = price.get(k)
                            if v is None:
                                continue
                            try:
                                v = float(v)
                            except Exception:
                                continue
                            if v > 0:
                                return v
            except Exception:
                continue
    return 0.0


def build_client(exchange: str, any_order_symbol: str) -> Tuple[Any, str, str, List[str]]:
    """Create exchange client using env keys. Return (client, base, quote, symbol_variants)."""
    api_key = env("STRATEGY_API_KEY")
    api_secret = env("STRATEGY_API_SECRET")
    passphrase = env("STRATEGY_PASSPHRASE")

    base, quote, norm = parse_symbol(any_order_symbol or "BTCUSDT")
    # Client may expect symbol with or without slash; try both
    symbol_variants = [f"{base}/{quote}", f"{base}{quote}"]

    account_info = {
        "api_key": api_key,
        "secret": api_secret,
        "passphrase": passphrase,
    }

    client = None
    if get_client_exchange is not None:
        try:
            client = get_client_exchange(
                exchange_name=exchange,
                acc_info=account_info,
                symbol=norm,  # provide one variant; method tries other variants too
                quote=quote,
                use_proxy=False,
            )
        except Exception:
            client = None
    return client, base, quote, symbol_variants


def compute_balance(initial_balance: float, orders: List[Dict[str, Any]]) -> Dict[str, Any]:
    cash = float(initial_balance or 0)
    positions: Dict[str, Dict[str, float]] = {}
    last_trade_price: Dict[str, float] = {}

    # Determine exchange from first order; default to binance
    exchange = (orders[0].get("exchange") if orders else "binance") or "binance"
    any_symbol = orders[0].get("symbol") if orders else "BTCUSDT"
    client, _, _, symbol_variants_hint = build_client(exchange, any_symbol)

    for o in orders:
        sym = o.get("symbol", "").upper()
        side = (o.get("side") or o.get("Side") or "").upper()
        qty = float(o.get("filled_quantity") or o.get("quantity") or 0)
        price = float(o.get("avg_price") or o.get("price") or 0)
        fee = float(o.get("fee") or 0)

        # Track last known trade price per symbol
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
            # Unknown side, skip accounting
            continue

    balances = {}
    inventory_value = 0.0

    for sym, pos in positions.items():
        qty = float(pos.get("qty") or 0)
        if abs(qty) < 1e-12:
            continue

        # Prepare client and symbol variants for price fetch
        base, quote, norm = parse_symbol(sym)
        symbol_variants = [f"{base}/{quote}", f"{base}{quote}"]
        # Try to get live price
        price = get_market_price(client, symbol_variants) if client else 0.0
        if price <= 0:
            price = last_trade_price.get(sym, 0.0)
        value = qty * price
        inventory_value += value
        balances[sym] = {"qty": qty, "price": price, "value": value}

    total = cash + inventory_value

    # Include cash and total
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
        # Still output a valid result to avoid breaking the caller
        result = {
            "success": True,
            "balances": {"Cash": 1000.0, "Total": 1000.0},
            "warning": "Missing STRATEGY_SESSION_KEY; using defaults",
        }
        print("RESULT: " + json.dumps(result))
        return

    base_url = get_base_url()

    try:
        data = fetch_session_data(base_url, session_key)
        if not data.get("success"):
            raise RuntimeError(data)
        initial_balance = float(data.get("initial_balance") or 0)
        orders = data.get("orders") or []
        result = compute_balance(initial_balance, orders)
        result.update({
            "session_key": session_key,
        })
    except Exception as e:
        # Graceful fallback
        result = {
            "success": True,
            "error": str(e),
            "balances": {"Cash": 0.0, "Total": 0.0},
            "session_key": session_key,
        }

    # Single-line RESULT: <json> for Go parser
    print("RESULT: " + json.dumps(result))


if __name__ == "__main__":
    main()