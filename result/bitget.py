#!/usr/bin/env python3
"""
Bitget Result Checker (Paper/Real)
- Outputs balances map with Total or a minimal error shape
- Mirrors structure like binance.py/poloniex.py result checkers
"""
import os
import sys
import json
import time

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../"))
sys.path.insert(0, PROJECT_ROOT)

try:
    from exchange_api_spot.user import get_client_exchange
except Exception:
    get_client_exchange = None


def env(name: str, default: str = "") -> str:
    v = os.environ.get(name)
    return v if v is not None else default


def fetch_balances(client):
    if client is None:
        return {"Total": 0.0}
    try:
        raw = client.get_account_balance()
        data = (raw or {}).get("data") or {}
    except Exception:
        data = {}

    formatted = {}
    total_usd = 0.0
    for asset, info in data.items():
        try:
            amount = float((info or {}).get("total") or 0)
        except Exception:
            amount = 0.0
        if amount <= 0:
            continue
        price = 1.0 if asset == "USDT" else 0.0
        if asset != "USDT":
            try:
                tick = client.get_ticker(asset, "USDT")
                p = tick.get("last") if isinstance(tick, dict) else None
                if p is not None:
                    price = float(p)
            except Exception:
                try:
                    p = client.get_price()
                    if isinstance(p, dict):
                        pv = p.get("price")
                        if pv is not None:
                            price = float(pv)
                except Exception:
                    price = 0.0
        formatted[asset] = {"amount": amount, "price": str(price)}
        total_usd += amount * float(price)

    formatted["Total"] = total_usd
    return formatted


def main():
    api_key = env("STRATEGY_API_KEY")
    api_secret = env("STRATEGY_API_SECRET")
    passphrase = env("STRATEGY_PASSPHRASE")
    session_key = env("STRATEGY_SESSION_KEY")

    client = None
    if get_client_exchange is not None:
        try:
            client = get_client_exchange(
                exchange_name="bitget",
                acc_info={
                    "api_key": api_key,
                    "secret_key": api_secret,
                    "passphrase": passphrase,
                },
                symbol="BTC",
                quote="USDT",
                use_proxy=False,
            )
        except Exception:
            client = None

    balances = fetch_balances(client)

    result = {
        "success": True,
        "balances": balances,
        "session_id": session_key,
        "exchange": "bitget",
        "timestamp": int(time.time()),
    }

    print("\n" + "=" * 50)
    print("RESULT:")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()