import json
import time
from .constants import ORDER_FILLED, ORDER_CANCELLED, ORDER_PARTIALLY_FILLED, ORDER_NEW, ORDER_UNKNOWN

clients_dict = {}

def get_symbol_by_exchange_name(exchange_name ='', symbol ='', quote = 'USDT'):
    """
    Generates a symbol string based on the given exchange name, symbol, and quote.

    Args:
        exchange_name (str): The name of the exchange. Defaults to an empty string.
        symbol (str): The symbol of the asset. Defaults to an empty string.
        quote (str): The quote currency. Defaults to 'USDT'.

    Returns:
        str: The generated symbol string. The format depends on the exchange name:
            - If exchange_name is 'gateio', the symbol string is in the format "{symbol}_{quote}".
            - If exchange_name is 'okx', the symbol string is in the format "{symbol}-{quote}-SWAP".
            - If exchange_name is 'bitget', the symbol string is in the format "{symbol}{quote}_SPBL".
            - If exchange_name is 'bingx' or 'kucoin', the symbol string is in the format "{symbol}-{quote}".
            - Otherwise, the symbol string is in the format "{symbol}{quote}".
    """
    if exchange_name == 'gateio':
        return f"{symbol}_{quote}"
    if exchange_name == 'okx':
        return f"{symbol}-{quote}-SWAP"
    if exchange_name == 'bitget':
        return f"{symbol}{quote}_SPBL"
    if exchange_name in ['bingx', 'kucoin']:
        return f"{symbol}-{quote}"
    return f"{symbol}{quote}"


def get_quote_by_symbol(symbol):
    """
    Given a symbol, this function returns the quote currency of the symbol. 

    Args:
        symbol (str): The symbol to get the quote currency for.

    Returns:
        str: The quote currency of the symbol. If the symbol ends with 'USDT', it returns 'USDT'. 
        If the symbol ends with 'BTC', 'ETH', or 'SOL', it returns the last three characters of the symbol. 
        Otherwise, it returns an empty string.
    """
    if symbol[-4:] == 'USDT':
        return symbol[-4:]
    if symbol[-3:] in ['BTC', 'ETH', 'SOL']: 
        return symbol[-3:]
    return ""


def extract_symbols(symbol):
    """
    A function that extracts base and quote symbols from the given symbol by removing dashes, checking against 
        a list of possible quote symbols, and returning the base and quote symbols if a match is found. Otherwise, it returns None.

    Args:
        symbol (str): The symbol from which to extract base and quote symbols.

    Returns:
        Tuple[str, str]: A tuple containing the base symbol (in uppercase) and the quote symbol (in uppercase) if a match is found. 
            If no match is found, it returns (None, None).
    """
    # Remove dashes to standardize the format
    symbol = symbol.upper().replace("-", "")
    symbol = symbol.upper().replace("_", "")
    symbol = symbol.upper().replace("SPBL", "")
    standardized_symbol = symbol

    # Define possible quote symbols
    quote_symbols = ['USDT', 'BTC', 'ETH', 'SOL', 'KRW', 'USD']

    # Extract base and quote symbols
    for quote in quote_symbols:
        if standardized_symbol.endswith(quote):
            base = standardized_symbol[:-len(quote)]
            return base.upper(), quote.upper()

    # If no match found, return None
    return None, None

def exchange_scale(scale):
    """
    Calculate the price scale, quantity scale, and tick price based on the given scale dictionary.

    Args:
        scale (dict): A dictionary containing the price scale and quantity scale.

    Returns:
        tuple: A tuple containing the price scale, quantity scale, and tick price.

    Raises:
        ValueError: If the scale dictionary does not contain the required keys.
    """
    price_scale = int(scale['priceScale'])
    qty_scale = int(scale['qtyScale'])
    tick_price = 1 / (10 ** float(price_scale))
    return price_scale, qty_scale, tick_price    

def price_rounding_scale(price, symbol, quote, exchange, r):
    """
    Rounds the given price based on the scale retrieved from Redis.

    Args:
        price (float): The price to be rounded.
        symbol (str): The symbol used to retrieve the scale from Redis.
        quote (str): The quote used to retrieve the scale from Redis.
        exchange (str): The exchange used to retrieve the scale from Redis.
        redis (Redis): The Redis client used to retrieve the scale.

    Returns:
        float or None: The rounded price based on the scale retrieved from Redis.
                       If the scale is not found in Redis, returns None.
    """
    if r.get(f'{symbol}_{quote}_{str(exchange).lower()}_scale') is not None:
        scale = json.loads(r.get(f'{symbol}_{quote}_{str(exchange).lower()}_scale'))       
        price_scale, _ = int(scale["priceScale"]), int(scale["qtyScale"])
        return round(float(price), price_scale)
    return float(price)

def quantity_rounding_scale(quantity, symbol, quote, exchange, r):
    """
    Calculates the rounded quantity based on the specified symbol, quote, exchange, and quantity.
    
    Args:
        quantity (float): The quantity to be rounded.
        symbol (str): The symbol used to retrieve the scale from Redis.
        quote (str): The quote used to retrieve the scale from Redis.
        exchange (str): The exchange used to retrieve the scale from Redis.
        redis (Redis): The Redis client used to retrieve the scale.
    
    Returns:
        float: The rounded quantity based on the scale retrieved from Redis.
              If the scale is not found in Redis, returns None.
    """
    if r.get(f'{symbol}_{quote}_{str(exchange).lower()}_scale') is not None:
        scale = json.loads(r.get(f'{symbol}_{quote}_{str(exchange).lower()}_scale'))       
        _, qty_scale = int(scale["priceScale"]), int(scale["qtyScale"])
        return round(float(quantity), qty_scale)
    return float(quantity)

def get_candle_data_info(symbol_redis, exchange_name, r, interval = '1h'):
    """
    A function that retrieves candle data information from the Redis cache or the exchange API.

    Args:
        symbol_redis (str): The symbol of the candle data in Redis.
        exchange_name (str): The name of the exchange.
        r (Redis): The Redis client.
        interval (str, optional): The time interval for the candle data. Defaults to '1h'.

    Returns:
        dict: A dictionary containing the candle data information.

    """
    now = int(time.time()*1000)
    if r.exists(f'{symbol_redis}_{exchange_name}_candle_{interval}') < 1:
        return None
    candles = json.loads(r.get(f'{symbol_redis}_{exchange_name}_candle_{interval}'))
    ts = float(candles['ts'])
    if now - ts >= 3000:
        return None
    return candles

FILLED_LIST_STATUS = ["full_fill", "full-fill", "FILLED", "closed", "filled", "fills","finished", "finish", "Filled"]
PARTITAL_FILLED_LIST_STATUS = ['partial_fill', 'partially_filled', 'PARTIALLY_FILLED', 'partial', 'PARTIAL', 'partial-filled', 'PartiallyFilled']
NEW_LIST_STATUS = ['open', 'OPEN', "new", "NEW","PENDING", "pending", 'live', 'created', 'submitted','canceling']
CANCELED_LIST_STATUS = ["cancelled", "CANCELLED", "cancel", "CANCEL", "canceled", "CANCELED",'canceled', 'partial-canceled',"Cancelled"]

def convert_order_status(order_details_status):
    """
    Converts an order status from a specific exchange's format to a standardized format.

    Args:
        order_details_status (str): The order status from the exchange.

    Returns:
        str: The standardized order status. It can be one of the following: "FILLED", "PARTIALLY_FILLED", "NEW", "CANCELED", or "UNKNOWN".
    """
    order_status = None
    if order_details_status in FILLED_LIST_STATUS:
        order_status = ORDER_FILLED
    elif order_details_status in PARTITAL_FILLED_LIST_STATUS:
        order_status = ORDER_PARTIALLY_FILLED
    elif order_details_status in NEW_LIST_STATUS:
        order_status = ORDER_NEW
    elif order_details_status in CANCELED_LIST_STATUS:
        order_status = ORDER_CANCELLED
    else:
        order_status = ORDER_UNKNOWN
    return order_status
    
        
