import json
import random
import requests
import redis
from logger import logger_error, logger_access
from config import RUNNING_STRATEGY_STATUS_PATH, TELEGRAM_TOKEN, TELEGRAM_ERROR_CHANNEL
r9 = redis.Redis(host='localhost', port=6379, decode_responses=True, db = 9)

def send_to_telegram(text, channel_id):
    """
    Sends a message to a specified Telegram channel using the provided text.

    Args:
        text (str): The text of the message to be sent.
        channel_id (str): The ID of the Telegram channel to send the message to.

    Returns:
        None
    """
    token = TELEGRAM_TOKEN
    chat_id = channel_id
    msg_type = 'sendMessage'
    msg = f'https://api.telegram.org/bot{token}/{msg_type}?chat_id={chat_id}&text={text}'
    requests.get(msg, timeout=10)

def delete_strategy_key(json_file_path,stratgey_key):
    """
    Delete a key from a JSON file.

    Args:
        json_file_path (str): The path to the JSON file.
        stratgey_key (str): The key to be deleted.

    Returns:
        None
    """
    with open(json_file_path, 'r', encoding='utf-8') as file:
        json_file = json.loads(file)
    if stratgey_key in json_file:
        json_file.pop(stratgey_key)
    with open(json_file_path, 'w', encoding='utf-8') as file:
        json.dump(json_file, file, indent=2)
        logger_access.info(json_file)


def get_kill_switch(symbol): # strategy ->
    """
    Retrieves the kill switch flag for the specified symbol.
    
    Args:
        symbol (str): The symbol for which the kill switch flag is being retrieved.
        
    Returns:
        int or bool: The kill switch flag value. If the flag is not found, generates a new key for the symbol and returns 0.
        If an exception occurs during the process, logs the error and returns 1 as a default value.
    """
    try:
        if r9.exists(str(symbol).upper()) < 1:      
            logger_access.info(f"{symbol} not exist generating new key")
            #logger
            set_kill_switch(symbol=symbol, switch_bool=0)
        flag = json.loads(r9.get(str(symbol).upper())) 
        return flag
    except Exception as e:
        logger_error.error(e, e.__traceback__.tb_lineno)
        logger_error.error(f"{e} {e.__traceback__.tb_lineno}") 
        return 1 # -> stop

    
# 0 is not kill, 1 is kill
def set_kill_switch(symbol, switch_bool): # main -> 
    """
    Sets the kill switch for a given symbol to the specified boolean value.

    Args:
        symbol (str): The symbol for which the kill switch is being set.
        bool (bool): The boolean value to set the kill switch to.

    Returns:
        bool: True if the kill switch was successfully set, False otherwise.
    """
    try:
        r9.set(name=str(symbol).upper(), value=switch_bool)  #symbol la base 
        return True # -> still running
    except Exception as e:
        #logge_error
        logger_error.error(e, e.__traceback__.tb_lineno)
        logger_error.error(f"{e} {e.__traceback__.tb_lineno}") 
        return False  # -> stop

def check_kill_switch(inventory_value, stop_loss, symbol, exchange):
    """
    Check if the inventory value is below the stop loss threshold. If it is, trigger the kill switch,
    send a message to the Telegram channel, and set the kill switch flag to 1. If the inventory value is
    above the stop loss threshold, logger_access.info a message indicating that the inventory is still normal.
    
    Parameters:
        inventory_value (float): The current value of the inventory.
        stop_loss (float): The stop loss threshold.
        symbol (str): The symbol of the inventory.
        exchange (str): The exchange where the inventory is traded.
    
    Returns:
        None
    
    Raises:
        Exception: If an error occurs during the execution of the function.
    """
    try:
        if float(inventory_value) <= stop_loss:
            logger_access.info(f"Trigger kill switch in {exchange.upper()} because {inventory_value} <= {stop_loss}")
            send_to_telegram(f"Trigger kill switch in BINANCE because {inventory_value} <= {stop_loss}", TELEGRAM_ERROR_CHANNEL)
            set_kill_switch(symbol=symbol, switch_bool=1) 
            logger_error.error(f"Trigger kill switch in {exchange.upper()} because {inventory_value} <= {stop_loss}")
        else:
            logger_access.info(f"Still normal inventory: {inventory_value} - stop loss: {stop_loss}")
    except Exception as e:
        logger_error.error(e, e.__traceback__.tb_lineno)
        logger_error.error(f"{e} {e.__traceback__.tb_lineno}") 


def read_service_statuses(key):
    """
    Read the service statuses from the RUNNING_STRATEGY_STATUS_PATH file and return the value associated with the given key.

    Parameters:
        key (str): The key to retrieve the value from the service statuses.

    Returns:
        Any: The value associated with the given key in the service statuses.
    """
    with open(RUNNING_STRATEGY_STATUS_PATH, 'r', encoding='utf-8') as file:
        data = json.load(file)
    return data[key]

def update_running_status(key_string):
    """
    Updates the running status of a given key string in the JSON file specified by RUNNING_STRATEGY_STATUS_PATH.
    
    Parameters:
        key_string (str): The key string to update the running status of.
    
    Returns:
        None
    """
    with open(RUNNING_STRATEGY_STATUS_PATH, 'r', encoding='utf-8') as file:
        data = json.load(file)
    if key_string in data:
        data[key_string] = 1
    with open(RUNNING_STRATEGY_STATUS_PATH, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=2)


def calculate_param_wash(volume_need_next_hour, round_min=5, round_max=40, frequency_min=180, frequency_max=600, capital_min=100, capital_max=800):
    """
    Calculates the optimal parameters for washing a certain volume in the next hour.
    
    Args:
        volume_need_next_hour (float): The volume of washing needed in the next hour.
        round_min (float, optional): The minimum value for the round parameter. Defaults to 5.
        round_max (float, optional): The maximum value for the round parameter. Defaults to 40.
        frequency_min (float, optional): The minimum value for the frequency parameter. Defaults to 180.
        frequency_max (float, optional): The maximum value for the frequency parameter. Defaults to 600.
        capital_min (float, optional): The minimum value for the capital parameter. Defaults to 100.
        capital_max (float, optional): The maximum value for the capital parameter. Defaults to 800.
    
    Returns:
        tuple: A tuple containing the optimal values for round_trade, frequency_trade, and capital_trade.
            Each value is an integer.
    """
    while True:
        round_trade = random.uniform(round_min, round_max)
        frequency_trade = random.uniform(frequency_min, frequency_max)
        capital_trade = random.uniform(capital_min, capital_max)
        if capital_trade * round_trade * (3600/frequency_trade) >= volume_need_next_hour:
            logger_access.info(round_trade, frequency_trade, capital_trade)
            break
    return int(round_trade), int(frequency_trade), int(capital_trade)
