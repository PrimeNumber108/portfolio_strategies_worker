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

try:
    import requests
except Exception:
    requests = None

# Make sure our project modules are importable (logger, etc.)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../"))
sys.path.insert(0, PROJECT_ROOT)
from logger import logger_error, logger_database, logger_access
from utils import make_golang_api_call
from exchange_api_spot.user import get_client_exchange
 


def env(name: str, default: str = "") -> str:
    v = os.environ.get(name)
    return v if v is not None else default


def get_base_url() -> str:
    # Prefer GOLANG_MGMT_API_URL (used by golang_auth), fallback to legacy MGNT_API_BASE_URL
    return env("GOLANG_MGMT_API_URL", env("MGNT_API_BASE_URL", "http://localhost:8083"))


def get_session_key() -> str:
    return env("STRATEGY_SESSION_KEY", "demo_sessionkey")


def get_auth_header() -> Dict[str, str]:
    token = env("STRATEGY_JWT", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


def fetch_last_balance(base_url: str, session_key: str) -> Dict[str, Any]:
    """
    Fetch last paper orders via authenticated call using make_golang_api_call.
    Uses .env credentials (GOLANG_API_USERNAME/PASSWORD) handled by golang_auth.
    """
    endpoint = f"/api/v1/execute/paper-orders?session_key={session_key}"
    response = make_golang_api_call(
        method="GET",
        endpoint=endpoint,
        base_url=base_url,
    )

    if not response:
        return {
            "success": False,
            "error": "Failed to fetch paper orders (no response)",
            "orders": [],
            "session_key": session_key,
            "count": 0,
            "initial_balance": 1000.0,
        }

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


def get_current_price(symbol: str, exchange: str) -> float:
    """
    Get current market price for a symbol from the exchange.
    
    Args:
        symbol: Trading symbol (e.g., 'BTCUSDT')
        exchange: Exchange name
        
    Returns:
        Current price or 0.0 if unable to fetch
    """
    try:
        # Try to get exchange client to fetch current price
        logger_access.info("symbol 1: ",symbol.split("_")[0])
        # Provide dummy credentials for price fetching (public data doesn't need real credentials)
        dummy_acc_info = {
            'api_key': 'dummy_key_for_price',
            'secret_key': 'dummy_secret_for_price',
            'passphrase': ''
        }
        client = get_client_exchange(
            exchange_name=exchange,
            acc_info=dummy_acc_info,
            symbol=symbol.split("_")[0],  # Extract base symbol
            quote="USDT",
            session_key="price_check",
            paper_mode=True
        )
        
        if client and hasattr(client, 'get_price'):
            price_data = client.get_price()
            if price_data and 'price' in price_data:
                return float(price_data['price'])
        
        # Fallback: use a default current price (you can modify this)
        logger_database.info(f"Could not fetch current price for {symbol}, using default")
        return 125000.0  # Default BTC price
        
    except Exception as e:
        logger_error.error(f"Error fetching current price for {symbol}: {str(e)}")
        return 125000.0  # Default fallback price


def create_opposite_paper_order(session_key: str, symbol: str, total_qty: float, current_price: float, 
                               original_side: str, exchange: str) -> bool:
    """
    Create a paper order at current price.
    
    Args:
        session_key: Trading session key
        symbol: Trading symbol
        total_qty: Total quantity for the order
        current_price: Current market price
        original_side: Order side ('BUY' or 'SELL') - determined by sum_money_of_orders sign
        exchange: Exchange name
        
    Returns:
        True if order created successfully
    """
    try:
        if abs(total_qty) < 1e-12:
            return True  # No position to close
        
        # Use the side directly (no need to calculate opposite)
        order_side = original_side
        
        # Prepare paper order data
        paper_order = {
            "session_key": session_key,
            "symbol": symbol,
            "side": order_side,
            "order_type": "MARKET",
            "quantity": abs(total_qty),
            "price": current_price,
            "avg_price": current_price,
            "filled_quantity": abs(total_qty),
            "status": "filled",
            "exchange": exchange,
            "fee": 0.0,
            "timestamp": int(time.time() * 1000),
            "order_id": f"paper_close_{session_key}_{int(time.time())}"
        }
        
        logger_access.info(f"📝 Creating paper order: {order_side} {abs(total_qty)} {symbol} at {current_price}")
        
        # Store the paper order using Golang API
        response = make_golang_api_call(
            method="POST",
            endpoint="/api/v1/execute/paper/orders",
            data=paper_order,
            base_url=get_base_url()
        )
        
        if response and response.get("success"):
            logger_access.info(f"✅ Paper order created successfully")
            return True
        else:
            logger_error.error(f"❌ Failed to create paper order: {response}")
            return False
            
    except Exception as e:
        logger_error.error(f"❌ Error creating paper order: {str(e)}")
        return False


def compute_balance(initial_balance: float, orders: List[Dict[str, Any]], session_key: str = "") -> Dict[str, Any]:
    cash = 1000.0  # Fixed cash amount - always 1000 USDT
    positions: Dict[str, Dict[str, float]] = {}
    last_trade_price: Dict[str, float] = {}

    # Infer exchange from orders (optional)
    exchange = (orders[0].get("exchange") if orders else "binance") or "binance"

    # Calculate cash flow and positions from orders
    sum_money_of_orders = 0.0  # Total money spent/received from orders
    
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
            # Don't modify cash - keep it at 1000 USDT
            positions[sym]["qty"] += qty
            sum_money_of_orders += qty * price + fee  # Money spent on buying
        elif side == "SELL":
            # Don't modify cash - keep it at 1000 USDT
            positions[sym]["qty"] -= qty
            sum_money_of_orders -= qty * price - fee  # Money received from selling (negative)
        else:
            continue

    balances: Dict[str, Any] = {}
    
    # Calculate total quantity and opposite order value at current price
    total_position_qty = 0.0
    main_symbol = ""
    
    logger_database.info('--- Positions ---', positions)
    
    # First, calculate total quantity from all positions
    for sym, pos in positions.items():
        qty = float(pos.get("qty") or 0)
        if abs(qty) < 1e-12:
            continue
            
        main_symbol = sym  # Use the last symbol with position
        total_position_qty += qty
        
        logger_database.info(f"Position {sym}: qty={qty}")

    # Calculate sum_opposite_orders_at_current_price = total_qty * current_price
    sum_opposite_orders_at_current_price = 0.0
    current_price = 0.0
    
    if abs(total_position_qty) > 1e-12 and main_symbol:
        # Get current market price once
        
        current_price = get_current_price(main_symbol, exchange)
        logger_database.info(f"Current price for {main_symbol}: {current_price}")
        
        # Calculate: sum_qty * current_price
        sum_opposite_orders_at_current_price = abs(total_position_qty) * current_price
        
        logger_database.info(f"Total position qty: {total_position_qty}, Current price: {current_price}, Opposite value: {sum_opposite_orders_at_current_price}")

    # Create opposite paper order if there's a net position
    if abs(total_position_qty) > 1e-12 and session_key and main_symbol:
        # Determine side based on sum_money_of_orders:
        # If sum_money_of_orders is negative => side is SELL
        # If sum_money_of_orders is positive => side is BUY
        opposite_side = "BUY" if sum_money_of_orders < 0 else "SELL"
        
        create_opposite_paper_order(
            session_key=session_key,
            symbol=main_symbol,
            total_qty=abs(total_position_qty),  # Use absolute value for quantity
            current_price=current_price,
            original_side=opposite_side,  # Pass the determined side directly
            exchange=exchange
        )

    logger_database.info(f'sum_money_of_orders: {sum_money_of_orders}')
    logger_database.info(f'sum_opposite_orders_at_current_price: {sum_opposite_orders_at_current_price}')

    # Calculate total USDT value: cash - sum_money_of_orders + sum_opposite_orders_at_current_price
    total_usdt_value = cash - sum_money_of_orders + sum_opposite_orders_at_current_price
    
    balances["USDT"] = {"amount": round(total_usdt_value, 8)}
    balances["Total"] = round(total_usdt_value, 8)
    
    logger_database.info(f"Final calculation: cash({cash}) - sum_money_of_orders({sum_money_of_orders}) + sum_opposite_orders_at_current_price({sum_opposite_orders_at_current_price}) = {total_usdt_value}")
    logger_database.info(f"compute_balance: {balances}")
    
    return {
        "success": True,
        "balances": balances,
        "exchange": exchange,
        "orders_count": len(orders),
    }


def main():
    logger_access.info("Starting paper trade result checker...")
    session_key = get_session_key()
    if not session_key:
        result = {
            "success": True,
            "balances": {"USDT": {"amount": 1000.0}, "Total": 1000.0},
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
        logger_access.info("run result success 1")
        result = compute_balance(initial_balance, orders, session_key)
        logger_access.info("run result success 2")

        result.update({
            "session_key": session_key,
        })
        logger_access.info("run result success")

    except Exception as e:
        result = {
            "success": True,
            "error": str(e),
            "balances": {"USDT": {"amount": 0.0}, "Total": 0.0},
            "session_key": session_key,
        }
        logger_error.error("run result error",e.__traceback__.tb_lineno, e)


    # Single-line RESULT for Go parser
    print("RESULT: " + json.dumps(result))

if __name__ == "__main__":
    main()