import os
import sys
sys.path.append(os.getcwd())
import time
import json
import random
import string 
from math import floor, log10
from inspect import currentframe
from dotenv import load_dotenv
import redis
from database_mm import insert_error_logger, update_strategy_tracking_status
from logger import logger_database, logger_error, logger_access
r1 = redis.Redis(host='localhost', port=6379, decode_responses=True, db=1) # manage make_order
r2 = redis.Redis(host='localhost', port=6379, decode_responses=True, db=2) # manage apikey - exchange
r7 = redis.Redis(host='localhost', port=6379, decode_responses=True, db=7) # manage run_key strategy
r8 = redis.Redis(host='localhost', port=6379, decode_responses=True, db=8) # manage symbol skew
r9 = redis.Redis(host='localhost', port=6379, decode_responses=True, db=9) # manage symbol skill_switch

#1: BINANCE_FUTURE
#2: BINGX_FUTURE
#3: BYBIT_FUTURE
#4: OKX_FUTURE

# Get the mode and test mode from environment variables
load_dotenv()
mode = os.getenv('MODE')
mode_test = os.getenv('MODE_TEST')
mode_encrypt = os.getenv('MODE_ENCRYPT')
if mode_encrypt is None:
    mode_encrypt = False


def find_exp(number) -> int:
    """
    Find the exponent of a given number.

    Args:
        number (float): The number for which to find the exponent.

    Returns:
        int: The exponent of the given number.

    """
    base10 = log10(abs(number))
    return abs(floor(base10))

def get_precision_from_real_number(number):
    """
    Calculates the precision of a given real number.

    Args:
        number (float): The real number for which to calculate the precision.

    Returns:
        int: The precision of the given real number. If the number is an integer, the function returns the negative of the number
          of digits in the integer part. Otherwise, it returns the exponent of the number.
    """
    number = float(number)
    if number % 1 ==0:
        count =0
        while number > 1:
            number =number //10
            count +=1
        return -count
    precision = find_exp(number)
    return precision

def generate_random_string():
    """
    Generates a random string consisting of 8 random characters from the set of uppercase letters and digits,
    followed by the current timestamp in milliseconds.

    Returns:
        str: The generated random string.

    """
    time_stamp = int(time.time() * 1000)
    # Tạo danh sách các ký tự từ A đến z và các số từ 0 đến 9
    characters = string.ascii_letters + string.digits
    # Tạo chuỗi ngẫu nhiên gồm 8 ký tự từ danh sách trên
    random_string = ''.join(random.choice(characters) for _ in range(10)) + str(time_stamp)
    return random_string

def clamp(value_compare, min_value, max_value):
    """
    Clamps a value within a specified range.

    Args:
        value_compare (int): The value to be compared and clamped.
        min_value (int): The minimum value of the range.
        max_value (int): The maximum value of the range.

    Returns:
        int: The clamped value within the specified range.
    """
    return max(float(min_value), min(float(value_compare), float(max_value)))

def load_json(path):
    """
    Load and return the JSON data from the file specified by the given path.
    
    Parameters:
        path (str): The path to the JSON file to load.
        
    Returns:
        dict: The JSON data loaded from the file.
        None: If the file does not exist or an error occurs during loading.
    """
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger_error.error(e)
        return None
    
def save_json(path, data):
    """
    Saves the given data to a JSON file at the specified path.

    Parameters:
        path (str): The path to the JSON file.
        data (dict or list): The data to be saved as JSON.

    Returns:
        bool: True if the data was successfully saved, False otherwise.
    """
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
            return True
    except Exception as e:
        logger_error.error(e)
        return False
    
def update_run_key_status(key, status):
    """
    Updates the run key status in the Redis database.

    Parameters:
        key (str): The key to update the status for.
        status (int): The new status to set for the key.

    Returns:
        bool: True if the status was successfully updated, False otherwise.
    """
    if mode == "terminal" or key == "terminal":
        return True

    current_status = r7.get(key)
    # confirm key started
    if status == 1:
        # key status must be starting before convert to started
        if int(current_status) != 0:
            logger_database.error("key status must be starting before convert to started")
            return False
    # confirm key stopped
    elif status == 9:
        # key status must be stopping before convert to stopped
        if int(current_status) != 8:
            logger_database.error("key status must be stopping before convert to stopped")
            return False
    elif status == 8:
        if int(current_status) >= 8:
            logger_database.warning("No need to set current status to 8")
            return False
    r7.set(key, status)
    update_strategy_tracking_status(key, status)
    return True

def get_run_key_status(run_key):
    """
    Retrieves the current status of a run key from the Redis database.

    Parameters:
        run_key (str): The key to retrieve the status for.

    Returns:
        int: The current status of the run key. If the key does not exist, returns 8.
    """
    run_status = 1
    if mode in ['staging', 'production', 'prod', 'admin', 'dev']:
        run_status = r7.get(run_key)
        if run_status  is None:
            run_status = 8
        else:
            run_status = int(run_status)
    return run_status

def delete_run_key(key):
    """
    Deletes a run key from the Redis database.

    Parameters:
        key (str): The key to delete.

    Returns:
        bool: True if the key was successfully deleted, False otherwise.
    """
    if mode == "terminal" or key == "terminal":
        return True
    return r7.delete(key)

def get_line_number():
    """
    Gets the line number of the calling code.

    Returns:
        int: The line number of the calling code.
    """
    cf = currentframe()
    return cf.f_back.f_lineno

def update_key_and_insert_error_log(run_key, symbol_raw, line_number,exchange_name,file_name, error_message):
    """
    Updates a run key and inserts an error log.

    Parameters:
        run_key (str): The key to update.
        symbol_raw (str): The selected symbol.
        exchange_name (str): The name of the exchange.
        file_name (str): The name of the file.
        error_message (str): The error message to log.

    Returns:
        bool: True if the operation was successful.
    """
    if run_key != "terminal":
        status_run_key = get_run_key_status(run_key)
    else:
        status_run_key = "terminal"
    info2 = f"{file_name} {line_number} - {symbol_raw} - {exchange_name} \
            {error_message}  {run_key} -- {status_run_key}"
    logger_error.error(info2)
    insert_error_logger(file_name = file_name, line = get_line_number(),content = info2)
    return True
