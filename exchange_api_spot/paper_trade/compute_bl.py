# compute_bl.py
# Balance computation for paper trading without creating opposite orders.
# Fees: BUY fee charged in base asset; SELL fee charged in quote asset.

from typing import Dict, Tuple
import os

BalanceRow = Dict[str, float]
Balances = Dict[str, BalanceRow]


def _ensure_asset(balances: Balances, asset: str) -> BalanceRow:
    if asset not in balances:
        balances[asset] = {
            "asset": asset,
            "available": 0.0,
            "locked": 0.0,
            "total": 0.0,
        }
    return balances[asset]


def _recompute_total(row: BalanceRow) -> None:
    row["total"] = float(row.get("available", 0.0)) + float(row.get("locked", 0.0))


def _norm_side(side: str) -> str:
    return str(side).upper()


def split_symbol(symbol: str) -> Tuple[str, str]:
    """
    Utility to split common spot symbols into base/quote.
    Extend known_quotes as needed for your venue.
    """
    known_quotes = ("USDT", "USD", "BUSD", "USDC", "BTC", "ETH", "BNB")
    for q in known_quotes:
        if symbol.endswith(q):
            return symbol[:-len(q)], q
    raise ValueError(f"Cannot split symbol: {symbol}. Provide base/quote explicitly.")


def _effective_fee_rate(fee_rate: float) -> float:
    """
    Resolve effective fee rate with sensible defaults:
    - If caller passes <= 0, use PAPER_TRADE_FEE_RATE env if set, else 0.001 (0.1%).
    """
    try:
        fr = float(fee_rate)
    except Exception:
        fr = 0.0
    if fr <= 0:
        fr_env = os.environ.get("PAPER_TRADE_FEE_RATE", "0.001")
        try:
            fr = float(fr_env)
        except Exception:
            fr = 0.001
        if fr <= 0:
            fr = 0.001
    return fr


def compute_post_trade_balances(
    balances: Balances,
    side: str,
    base_asset: str,
    quote_asset: str,
    price: float,
    quantity: float,
    fee_rate: float = 0.001,
) -> Balances:
    """
    Mutates and returns balances using immediate-fill semantics.
    - BUY: deduct quote by price*qty, credit base by qty - (qty*fee_rate)
    - SELL: deduct base by qty, credit quote by price*qty - (price*qty*fee_rate)
    """
    if not isinstance(balances, dict):
        raise ValueError("balances must be a dict: {asset: {available, locked, total}}")

    side = _norm_side(side)
    price = float(price)
    qty = float(quantity)
    fee_rate = _effective_fee_rate(fee_rate)

    base = _ensure_asset(balances, base_asset)
    quote = _ensure_asset(balances, quote_asset)

    if side == "BUY":
        cost = price * qty
        if quote["available"] + 1e-12 < cost:
            raise ValueError(f"Insufficient {quote_asset}: need {cost}, have {quote['available']}")
        quote["available"] -= cost

        fee_base = qty * fee_rate  # fee in base on BUY
        base["available"] += max(qty - fee_base, 0.0)

    elif side == "SELL":
        if base["available"] + 1e-12 < qty:
            raise ValueError(f"Insufficient {base_asset}: need {qty}, have {base['available']}")
        base["available"] -= qty

        gross = price * qty
        fee_quote = gross * fee_rate  # fee in quote on SELL
        quote["available"] += max(gross - fee_quote, 0.0)

    else:
        raise ValueError("side must be 'BUY' or 'SELL'")

    _recompute_total(base)
    _recompute_total(quote)
    return balances


def compute_trade_fee(
    side: str,
    price: float,
    quantity: float,
    fee_rate: float = 0.001,
    return_currency: str = "quote",
) -> float:
    """
    Compute the trade fee amount for an immediate-fill paper trade.

    - BUY: fee is charged in base; in quote terms it's (qty * fee_rate * price)
    - SELL: fee is charged in quote; in quote terms it's (price * qty * fee_rate)

    Args:
        side: "BUY" or "SELL"
        price: execution price
        quantity: executed quantity
        fee_rate: taker fee rate (fraction)
        return_currency: "quote" or "base". If "quote", always returns the fee valued in quote.

    Returns:
        float: fee amount in the requested currency.
    """
    s = _norm_side(side)
    p = float(price)
    q = float(quantity)
    fr = _effective_fee_rate(fee_rate)

    if s == "BUY":
        fee_base = q * fr
        fee_quote = fee_base * p
        return fee_quote if return_currency.lower() == "quote" else fee_base
    elif s == "SELL":
        gross = p * q
        fee_quote = gross * fr
        # No base-denominated fee for SELL in this model; return 0 if requested.
        return fee_quote if return_currency.lower() == "quote" else 0.0
    else:
        raise ValueError("side must be 'BUY' or 'SELL'")