import json
import os
import time
import datetime
import redis
import mysql.connector
import pymysql
from logger import logger_database
from config import MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

def get_connection():
    """
    Establishes a connection to a MySQL database with retry mechanism.

    Args:
        retries (int): Số lần thử lại khi kết nối thất bại.
        delay (int): Thời gian chờ giữa các lần thử lại (giây).

    Returns:
        tuple: Connection và cursor nếu kết nối thành công, None nếu thất bại.
    """
    retries=3 
    delay=5
    attempt = 0
    while attempt < retries:
        try:
            connection = pymysql.connect(
                host=MYSQL_HOST,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DATABASE,
                port=3306,
                connect_timeout=10  # Timeout 10 giây
            )
            cursor = connection.cursor()
            return connection, cursor
        except pymysql.MySQLError as err:
            logger_database.error(f"Database connection attempt {attempt + 1} failed: {err}")
            attempt += 1
            time.sleep(delay)  # Chờ trước khi thử lại

    logger_database.error("Failed to connect to the database after multiple attempts.")
    return None, None

def close_connection(connection, cursor):
    """
    Safely close a MySQL cursor and connection. Accepts None and logs close errors.

    Args:
        connection: The MySQL connection object or None.
        cursor: The MySQL cursor object or None.
    """
    try:
        if cursor is not None:
            try:
                cursor.close()
            except Exception as e:
                logger_database.error(f"Error closing cursor: {e}")
        if connection is not None:
            try:
                connection.close()
            except Exception as e:
                logger_database.error(f"Error closing connection: {e}")
    except Exception:
        # Ensure close never raises further exceptions
        pass

def execute_script_location(abs_paths_list):
    """
    Executes a script location in the database.

    Args:
        abs_paths_list (list): A list of absolute paths to check and insert into the database.

    Returns:
        None

    Raises:
        Exception: If there is an error connecting to the MySQL database.
    """
    try:
        connection, cursor = get_connection()
        # Check if the row exists in the database for each absolute path
        for abs_path in abs_paths_list:
            query = "SELECT COUNT(*) FROM script_locations WHERE location = %s"
            cursor.execute(query, (abs_path,))
            result = cursor.fetchone()
            if result[0] == 0:
                # If the row does not exist, insert it
                current_date = datetime.datetime.now()
                formatted_date = current_date.strftime('%Y-%m-%d %H:%M:%S')
                insert_query = """INSERT INTO script_locations (location, name, created_at, deleted_at, updated_at) 
                                    VALUES (%s, %s, %s, NULL, %s)
                                    ON DUPLICATE KEY UPDATE
                                    location = VALUES(location),
                                    updated_at = VALUES(updated_at)"""
                cursor.execute(insert_query, (abs_path, os.path.basename(abs_path), formatted_date, formatted_date))
                connection.commit()
                logger_database.info(f"Inserted: {os.path.basename(abs_path)} - {abs_path}")
        
        # Now, delete rows from the table where the location does not exist in abs_paths
        # delete_query = "DELETE FROM script_locations WHERE location NOT IN (%s)" % ', '.join(['%s'] * len(abs_paths_list))
        delete_query = f"DELETE FROM script_locations WHERE location NOT IN ({', '.join(['%s'] * len(abs_paths_list))})"

        cursor.execute(delete_query, abs_paths_list)
        # Commit the changes
        connection.commit()
        logger_database.info("Deleted rows with locations not found in the filesystem.")

        close_connection(connection, cursor)
    except Exception as err:
        logger_database.error(f"Error connecting to MySQL: {err}")
    
def insert_stop_strategy_tracking(key):
    """
    Inserts a new tracking action into the `tracking_actions` table in the MySQL database.

    Args:
        key (str): The key name of the tracking action.

    Returns:
        None

    Raises:
        Exception: If there is an error connecting to the MySQL database.

    """
    try:
        # Connect to the MySQL server
        connection, cursor = get_connection()
        current_date = datetime.datetime.now()
        formatted_date = current_date.strftime('%Y-%m-%d %H:%M:%S')
        insert_query = """INSERT INTO tracking_actions (key_name, action, created_at, deleted_at, updated_at) 
                            VALUES (%s, %s, %s, NULL, %s)"""
        cursor.execute(insert_query, (key, 1, formatted_date, formatted_date))
        # Commit the changes
        connection.commit()
        logger_database.info(f"Inserted: {key} stop into TrackingAction table")

        close_connection(connection, cursor)

    except Exception as err:
        logger_database.error(f"Error connecting to MySQL: {err}")    

def update_strategy_tracking_status(key, status):
    """
    Inserts a new tracking action into the `tracking_actions` table in the MySQL database.

    Args:
        key (str): The key name of the tracking action.

    Returns:
        None

    Raises:
        Exception: If there is an error connecting to the MySQL database.

    """
    try:
        # Connect to the MySQL server
        connection, cursor = get_connection()
        current_date = datetime.datetime.now()
        formatted_date = current_date.strftime('%Y-%m-%d %H:%M:%S')
        update_query =  """ UPDATE tracking_actions 
                            SET status = %s, updated_at = %s 
                            WHERE key_name = %s"""
        cursor.execute(update_query, (status, formatted_date, key))
        
        # Nếu status = 9, cập nhật thêm bảng params
        if status == 9:
            # Thực hiện truy vấn JOIN để cập nhật status trong bảng params
            update_params_query = """UPDATE params p
                                     JOIN tracking_actions t ON p.id = t.param_id
                                     SET p.status = 9
                                     WHERE t.key_name = %s"""
            cursor.execute(update_params_query, (key,))
            logger_database.info(f"Updated status in params table for key: {key}")

        # Commit the changes
        connection.commit()
        logger_database.info(f"Updated: {key} - status {status} in TrackingAction table")

    except Exception as err:
        logger_database.error(f"Error connecting to MySQL: {err}")    
    finally:
        # Đảm bảo luôn đóng kết nối và con trỏ, dù có lỗi hay không
        close_connection(connection, cursor)

    
def insert_or_update_inflow_record(exchange_name, symbol, start_time, end_time, 
                                   large_orders_buy, large_orders_sell, 
                                   medium_orders_buy, medium_orders_sell, 
                                   small_orders_buy, small_orders_sell):
    """
    Inserts or updates a record in the 'inflows' table in the MySQL database.

    Args:
        exchange_name (str): The name of the exchange.
        symbol (str): The symbol of the record.
        start_time (datetime): The start time of the record.
        end_time (datetime): The end time of the record.
        large_orders_buy (float): The large orders buy.
        large_orders_sell (float): The large orders sell.
        medium_orders_buy (float): The medium orders buy.
        medium_orders_sell (float): The medium orders sell.
        small_orders_buy (float): The small orders buy.
        small_orders_sell (float): The small orders sell.

    Returns:
        None

    Raises:
        Exception: If there is an error connecting to the MySQL database.

    """
    try:
        # Connect to the MySQL server
        connection, cursor = get_connection()
        
        # Get the current timestamp for created_at and updated_at
        current_timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Prepare the INSERT statement with ON DUPLICATE KEY UPDATE clause
        upsert_query = """
        INSERT INTO inflows (
            exchange_name, symbol, start_time, end_time, large_orders_buy, large_orders_sell, medium_orders_buy, medium_orders_sell, 
            small_orders_buy, small_orders_sell, created_at, updated_at, deleted_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        ) ON DUPLICATE KEY UPDATE
            end_time = VALUES(end_time),
            large_orders_buy = VALUES(large_orders_buy),
            large_orders_sell = VALUES(large_orders_sell),
            medium_orders_buy = VALUES(medium_orders_buy),
            medium_orders_sell = VALUES(medium_orders_sell),
            small_orders_buy = VALUES(small_orders_buy),
            small_orders_sell = VALUES(small_orders_sell),
            updated_at = VALUES(updated_at)
        """
        
        # Execute the INSERT or UPDATE statement
        cursor.execute(upsert_query, (
            exchange_name, symbol, start_time, end_time, large_orders_buy, large_orders_sell, medium_orders_buy, medium_orders_sell, 
            small_orders_buy, small_orders_sell, current_timestamp, current_timestamp, None  # Set deleted_at to None initially
        ))
        
        # Commit the transaction
        connection.commit()
        return True
    except Exception as err:
        logger_database.error(f"Error: {err}")
        return err
        
    finally:
        # Close the cursor and connection
        close_connection(connection, cursor)

def inflow_get_last_row():
    """
    Retrieves the last row from the 'inflows' table in the MySQL database.

    Returns:
        dict or Exception: The last row from the 'inflows' table as a dictionary, or an Exception if an error occurs.

    Raises:
        Exception: If an error occurs while connecting to the database or executing the SQL query.
    """
    try:
        # Connect to the MySQL server
        connection, cursor = get_connection()
        
        # Prepare the SELECT statement to get the last row based on the 'id' column
        query = "SELECT * FROM inflows ORDER BY id DESC LIMIT 1"
        
        # Execute the SELECT statement
        cursor.execute(query)
        
        # Fetch the last row
        last_row = cursor.fetchone()
        
        return last_row
        
    except Exception as err:
        logger_database.error(f"Error: {err}")
        return err
        
    finally:
        # Close the cursor and connection
        close_connection(connection, cursor)
    
def insert_make_order(order):
    """
    Inserts an order into the 'make_orders' table in the MySQL database.

    Args:
        order (dict): A dictionary containing the details of the order to be inserted. It should have the following keys:
            - 'order_id' (str): The ID of the order.
            - 'exchange' (str): The exchange where the order is placed.
            - 'strategy_name' (str): The name of the strategy used to place the order.
            - 'api_key' (str): The API key used to authenticate the order.
            - 'account_id' (str): The ID of the account associated with the order.
            - 'param_id' (str): The ID of the parameters used to place the order.
            - 'symbol' (str): The symbol of the asset being traded.
            - 'note' (str): Any additional notes or comments about the order.

    Returns:
        None or Exception: If an error occurs while inserting the order, an Exception is returned. Otherwise, None is returned.

    Raises:
        Exception: If an error occurs while connecting to the database or executing the SQL query.

    Note:
        The 'created_at' and 'updated_at' columns are set to the current timestamp.
    """
    try:
        connection, cursor = get_connection()
        
        current_timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        insert_query = """
            INSERT INTO make_orders (order_id, exchange, strategy_name, api_key, account_id, param_id, symbol, note, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
        
        cursor.execute(insert_query, (order['order_id'], order['exchange'], order['strategy_name'], order['api_key'], order['account_id'], 
                                      order['param_id'], order['symbol'], order['note'], current_timestamp, current_timestamp))
        
        connection.commit()
        return True
    except Exception as err:
        logger_database.error(f"Error inserting row:{err}  {err.__traceback__.tb_lineno}")
        logger_database.error(f"Error inserting row:{order}")
        return err
        
    finally:
        close_connection(connection, cursor)

def fetch_all_make_order():
    """
    Fetches all the make orders from the database.

    Returns:
        A list of lists, where each inner list contains the following elements:
        - order_id (int): The ID of the order.
        - exchange (str): The exchange where the order was placed.
        - strategy_name (str): The name of the strategy used for the order.
        - api_key (str): The API key used for the order.
        - account_id (int): The ID of the account associated with the order.
        - param_id (int): The ID of the parameter used for the order.
        - symbol (str): The symbol of the order.
        - note (str): Additional notes about the order.

    Raises:
        mysql.connector.Error: If there is an error executing the SQL query.

    Note:
        Only orders that have not been marked as deleted are returned.

    """
    try:
        connection, cursor = get_connection()
        # current_timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # Fetch all rows that are not already marked as deleted
        select_query = """SELECT order_id, exchange, strategy_name, api_key, account_id, param_id, symbol, note 
                            FROM make_orders 
                            WHERE deleted_at IS NULL
                        """
        cursor.execute(select_query)
        result =[]
        list_make_orders = cursor.fetchall()
        for make_order in list_make_orders:
            result.append([
                        make_order[0], # order_id
                        make_order[1], # exchange
                        make_order[2], # strategy_name
                        make_order[3], # api_key
                        make_order[4], # account_id
                        make_order[5], # param_id
                        make_order[6], # symbol
                        make_order[7], # note
                    ])
        return result
    except Exception as err:
        logger_database.error(f"Error soft deleting rows: {err}")
        return err
        
    finally:
        close_connection(connection, cursor)

def soft_delete_make_order(order_id):
    """
    Soft deletes a row in the `make_orders` table by setting the `deleted_at` column to the current timestamp.

    Parameters:
        order_id (int): The ID of the order to be soft deleted.

    Returns:
        None

    Raises:
        Exception: If an error occurs during the soft deletion process.

    Notes:
        - This function retrieves a database connection and cursor using the `get_connection()` function.
        - The current timestamp is obtained using `datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')`.
        - The `UPDATE` query is executed using the `cursor.execute()` method.
        - The `connection.commit()` method is called to commit the changes to the database.
        - If an error occurs during the soft deletion process, the error is logged using the `logger_database.error()` method.
        - The `close_connection()` function is called to close the database connection and cursor.

    """
    try:
        connection, cursor = get_connection()
        current_timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
       
        update_query = "UPDATE make_orders SET deleted_at = %s WHERE order_id = %s"
        cursor.execute(update_query, (current_timestamp, order_id))
        logger_database.info(f"Soft deleted row with id {order_id} successfully.")
        connection.commit()
        return True
    except Exception as err:
        logger_database.error(f"orderID {order_id}")
        logger_database.error(f"Error soft deleting rows: {err}")
        return err
        
    finally:
        close_connection(connection, cursor)

def insert_final_order(order):
    """
    Inserts a final order into the database.

    Args:
        order (dict): A dictionary containing the order details.

    Returns:
        None if the insertion is successful, otherwise an error message.
    """
    try:
        connection, cursor = get_connection()
        # convert datetime to miliseconds
        if order['orderCreateTime'] is not None and len(str(order['orderCreateTime'])) == 10:
            order['orderCreateTime'] = int(order['orderCreateTime']) * 1000
        if order['orderUpdateTime'] is not None and len(str(order['orderUpdateTime'])) == 10:
            order['orderUpdateTime'] = int(order['orderUpdateTime']) * 1000


        current_timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        insert_query = """
            INSERT INTO final_orders (order_id, symbol, symbol_norm, exchange, strategy_name, api_key, account_id, param_id, client_order_id, 
                quantity, status, price, side, filled_price, filled_size, order_type, fee, order_create_time, order_update_time, 
                created_at, updated_at, note)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

        symbol_norm = ""
        if 'symbol' in order:
            symbol_norm = order['symbol'].replace('-', '').replace('_', '').upper()

        cursor.execute(insert_query, (order['orderId'], order['symbol'], symbol_norm, order['exchange'], order['strategyName'], order['apiKey'], 
                                      order['accountId'], order['paramId'], order['clientOrderId'], order['quantity'], 
                                      str(order['status']).upper(), order['price'], str(order['side']).upper(), order['fillPrice'], 
                                      order['fillQuantity'], str(order['orderType']).upper(), order['fee'], order['orderCreateTime'], 
                                      order['orderUpdateTime'], current_timestamp, current_timestamp, order['note']))
        connection.commit()
        return None

    except Exception as err:
        logger_database.error(f"order {order}")
        logger_database.error(f"Error inserting row:{err}")
        return err

    finally:
        close_connection(connection, cursor)
        
def insert_inventory_value(inventory):
    """
    Inserts an inventory value into the 'inventory_values' table in the MySQL database.

    Args:
        inventory (dict): A dictionary containing the inventory details. It should have the following keys:
            - 'exchange_name' (str): The name of the exchange.
            - 'base_symbol' (str): The base symbol.
            - 'quote_symbol' (str): The quote symbol.
            - 'quote' (float): The quote value.
            - 'base' (float): The base value.
            - 'inventory' (float): The inventory value.
            - 'price' (float): The price value.
            - 'quote_price' (float): The quote price value.

    Returns:
        None if the insertion is successful, otherwise an error message.

    Raises:
        Exception: If there is an error inserting the row into the database.

    """
    try:
        connection, cursor = get_connection()
        
        current_timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        current_unix_timestamp = int(time.time())
        insert_query = """
            INSERT INTO inventory_values (exchange_name, base_symbol, quote_symbol, quote, base, inventory, price, quote_price, 
                created_at, updated_at, time_stamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
        
        cursor.execute(insert_query, (inventory['exchange_name'], inventory['base_symbol'], inventory['quote_symbol'], inventory['quote'], 
                                      inventory['base'], inventory['inventory'], inventory['price'], inventory['quote_price'], 
                                      current_timestamp, current_timestamp, current_unix_timestamp))
        
        connection.commit()
        return True
    except Exception as err:
        logger_database.error(f"Error inserting row: {err}")
        return err
        
    finally:
        close_connection(connection, cursor)

def insert_volume_snapshots(snapshot):
    """
    Inserts a snapshot into the volume_snapshots table based on the provided snapshot data.

    Args:
        snapshot (dict): The snapshot data containing 'time_stamp', 'strategy_name', 'exchange', 'base_symbol', 'quote_symbol', 
                         'price', 'quote_price', 'base_volume', 'quote_volume', 'usd_volume', 'created_at', 'updated_at'.

    Returns:
        None if successful, otherwise returns an error message.
    """
    try:
        connection, cursor = get_connection()
        
        # current_timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Prepare the SELECT statement to get the last row based on the 'id' column
        query = f"""SELECT * 
                    FROM volume_snapshots 
                    WHERE strategy_name = '{snapshot['strategy_name']}' AND exchange = '{snapshot['exchange']}' 
                        AND base_symbol = '{snapshot['base_symbol']}' AND quote_symbol = '{snapshot['quote_symbol']}' 
                    ORDER BY id DESC LIMIT 1"""
        
        # Execute the SELECT statement
        cursor.execute(query)
        
        # Fetch the last row
        last_row = cursor.fetchone()
        if last_row is None or int(last_row[4]) < snapshot['time_stamp']:
            insert_query = """
                INSERT INTO volume_snapshots (time_stamp, strategy_name, exchange, base_symbol, quote_symbol, price, quote_price, 
                    base_volume, quote_volume, usd_volume, created_at, updated_at)
                VALUES ( %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
            cursor.execute(insert_query, (snapshot['time_stamp'], snapshot['strategy_name'], snapshot['exchange'], snapshot['base_symbol'], 
                                          snapshot['quote_symbol'], snapshot['price'], snapshot['quote_price'], snapshot['base_volume'], 
                                          snapshot['quote_volume'], snapshot['usd_volume'], snapshot['created_at'], snapshot['updated_at'] ))
        else: 
            update_query = """
                UPDATE volume_snapshots 
                SET price = %s, quote_price = %s, base_volume = base_volume + %s, 
                    quote_volume = quote_volume + %s, usd_volume = usd_volume + %s, updated_at = %s
                WHERE time_stamp = %s AND strategy_name = %s AND exchange = %s AND base_symbol = %s AND quote_symbol = %s
                """
            cursor.execute(update_query, (snapshot['price'], snapshot['quote_price'], snapshot['base_volume'], snapshot['quote_volume'], 
                                          snapshot['usd_volume'], snapshot['updated_at'], snapshot['time_stamp'], snapshot['strategy_name'], 
                                          snapshot['exchange'], snapshot['base_symbol'], snapshot['quote_symbol']))
        
        connection.commit()
        return None
        
    except Exception as err:
        logger_database.error(f"Error inserting row: {err}")
        return err
        
    finally:
        close_connection(connection, cursor)

def insert_volume_snapshots_v2(snapshot):
    """
    Inserts a snapshot into the volume_snapshots table based on the provided snapshot data.
    Handles concurrent updates safely and ensures correct logic for time-independent updates.
    """
    try:
        connection, cursor = get_connection()

        # Lock the table to prevent race conditions during concurrent updates
        cursor.execute("LOCK TABLES volume_snapshots WRITE")

        # Check for an existing record with matching keys and time_stamp
        query = f"""
            SELECT * 
            FROM volume_snapshots 
            WHERE strategy_name = %s AND exchange = %s 
                AND base_symbol = %s AND quote_symbol = %s 
                AND time_stamp = %s
        """

        cursor.execute(query, (
            snapshot['strategy_name'],
            snapshot['exchange'],
            snapshot['base_symbol'],
            snapshot['quote_symbol'],
            snapshot['time_stamp']
        ))

        existing_row = cursor.fetchone()

        if existing_row is None:
            # Insert a new snapshot if no matching record exists
            insert_query = """
                INSERT INTO volume_snapshots (time_stamp, strategy_name, exchange, base_symbol, quote_symbol, price, quote_price, 
                    base_volume, quote_volume, usd_volume, created_at, updated_at)
                VALUES ( %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(insert_query, (
                snapshot['time_stamp'],
                snapshot['strategy_name'],
                snapshot['exchange'],
                snapshot['base_symbol'],
                snapshot['quote_symbol'],
                snapshot['price'],
                snapshot['quote_price'],
                snapshot['base_volume'],
                snapshot['quote_volume'],
                snapshot['usd_volume'],
                snapshot['created_at'],
                snapshot['updated_at']
            ))
        else:
            # Update the existing snapshot if a matching record exists
            update_query = """
                UPDATE volume_snapshots 
                SET price = %s, quote_price = %s, base_volume = base_volume + %s, 
                    quote_volume = quote_volume + %s, usd_volume = usd_volume + %s, updated_at = %s
                WHERE id = %s
            """
            cursor.execute(update_query, (
                snapshot['price'],
                snapshot['quote_price'],
                snapshot['base_volume'],
                snapshot['quote_volume'],
                snapshot['usd_volume'],
                snapshot['updated_at'],
                existing_row[0]  # Use the primary key ID of the existing row
            ))

        connection.commit()
        return None

    except Exception as err:
        logger_database.error(f"Error inserting row: {err}")
        return err

    finally:
        # Unlock the table to allow other transactions
        cursor.execute("UNLOCK TABLES")
        close_connection(connection, cursor)

def calculate_volume_snapshots(list_strategy, exchange, base_symbol, quote_symbol, from_time):
    """
    Calculate the total wash volume for a given list of strategies, exchange, base symbol, quote symbol, and from time.
    
    Args:
        list_strategy (List[str]): A list of strategy names.
        exchange (str): The exchange name.
        base_symbol (str): The base symbol.
        quote_symbol (str): The quote symbol.
        from_time (str): The starting time in the format 'YYYY-MM-DD HH:MM:SS'.
        
    Returns:
        float or Exception: The total wash volume if successful, or an Exception object if an error occurs.
    """
    try:
        connection, cursor = get_connection()
        wash_volume = 0
        
        if isinstance(list_strategy, str):
            list_strategy = [list_strategy]
        elif isinstance(list_strategy, list):
            list_strategy = list_strategy
        else:
            raise ValueError("strategy_name must be a string or a list.")
        
        if len(list_strategy) == 0:
            query = f"""SELECT * FROM volume_snapshots 
                        WHERE exchange = '{exchange}' AND base_symbol = '{base_symbol}' 
                            AND quote_symbol = '{quote_symbol}' AND time_stamp >= '{from_time}' 
                        ORDER BY id DESC"""
            # Execute the SELECT statement
            cursor.execute(query)
            list_volume_snapshots = cursor.fetchall()

            for volume_snapshot in list_volume_snapshots:
                usd_volume = volume_snapshot[-1]
                wash_volume += float(usd_volume)
        else:
            for strategy_name in list_strategy:
                # Prepare the SELECT statement to get the last row based on the 'id' column
                query = f"""SELECT * FROM volume_snapshots 
                            WHERE strategy_name LIKE '%{strategy_name.lower()}%' AND exchange = '{exchange}'
                                AND base_symbol = '{base_symbol}' AND quote_symbol = '{quote_symbol}' AND time_stamp >= '{from_time}' 
                            ORDER BY id DESC"""
                # Execute the SELECT statement
                cursor.execute(query)
                list_volume_snapshots = cursor.fetchall()
                for volume_snapshot in list_volume_snapshots:
                    usd_volume = volume_snapshot[-1]
                    wash_volume += float(usd_volume)
                logger_database.info(f"wash volume of {strategy_name} - {exchange} - {base_symbol} - {quote_symbol} - {from_time}: {wash_volume}")
        return wash_volume
        
    except Exception as err:
        logger_database.error(f"Error inserting row:{err}")
        return err
        
    finally:
        close_connection(connection, cursor)

def calculate_volume_snapshots_v2(list_strategy, exchange, base_symbol, quote_symbol, from_time, to_time):
    """
    Calculate the total wash volume for a given list of strategies, exchange, base symbol, quote symbol, and from time.
    
    Args:
        list_strategy (List[str]): A list of strategy names.
        exchange (str): The exchange name.
        base_symbol (str): The base symbol.
        quote_symbol (str): The quote symbol.
        from_time (str): The starting time in the format 'YYYY-MM-DD HH:MM:SS'.
        
    Returns:
        float or Exception: The total wash volume if successful, or an Exception object if an error occurs.
    """
    try:
        connection, cursor = get_connection()
        cursor = connection.cursor()
        wash_volume = 0
        if len(list_strategy) == 0:
            query = f"""SELECT * FROM volume_snapshots 
                        WHERE exchange = '{exchange}' AND base_symbol = '{base_symbol}' 
                            AND quote_symbol = '{quote_symbol}' AND time_stamp >= '{from_time}' AND time_stamp <= '{to_time}' 
                        ORDER BY id DESC"""
            # Execute the SELECT statement
            cursor.execute(query)
            list_volume_snapshots = cursor.fetchall()
            for volume_snapshot in list_volume_snapshots:
                usd_volume = volume_snapshot[-1]
                wash_volume += float(usd_volume)
        else:
            for strategy_name in list_strategy:
                # Prepare the SELECT statement to get the last row based on the 'id' column
                query = f"""SELECT * FROM volume_snapshots 
                            WHERE strategy_name LIKE '%{strategy_name.lower()}%' AND exchange = '{exchange}'
                                AND base_symbol = '{base_symbol}' AND quote_symbol = '{quote_symbol}' AND time_stamp >= '{from_time}' AND time_stamp <= '{to_time}' 
                            ORDER BY id DESC"""
                # Execute the SELECT statement
                cursor.execute(query)
                list_volume_snapshots = cursor.fetchall()

                for volume_snapshot in list_volume_snapshots:
                    usd_volume = volume_snapshot[-1]
                    wash_volume += float(usd_volume)
                logger_database.info(f"wash volume of {strategy_name} - {exchange} - {base_symbol} - {quote_symbol} - {from_time}: {wash_volume}")
        return wash_volume
        
    except Exception as err:
        logger_database.error(f"Error inserting row:{err}")
        return err
        
    finally:
        close_connection(connection, cursor)
    
def insert_error_max_eat(order):
    """
    Inserts an error_max_eat record into the database.

    Args:
        order (dict): A dictionary containing the following keys:
            - order_id (str): The ID of the order.
            - exchange (str): The exchange where the order was placed.
            - strategy_name (str): The name of the strategy.
            - api_key (str): The API key used for the order.
            - account_id (str): The ID of the account.
            - base_symbol (str): The base symbol of the order.
            - exchange_symbol (str): The exchange symbol of the order.
            - price (float): The price of the order.
            - side (str): The side of the order.
            - quantity (float): The quantity of the order.

    Returns:
        None: If the record is successfully inserted.

    Raises:
        Exception: If there is an error inserting the row.

    """
    try:
        connection, cursor = get_connection()
        
        current_unix_timestamp = int(time.time())
        current_timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        insert_query = """
            INSERT INTO error_max_eats (order_id, exchange, strategy_name, api_key, account_id, base_symbol, exchange_symbol, 
                price, side, quantity, created_at, updated_at, time_stamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
        
        cursor.execute(insert_query, (order['order_id'], order['exchange'], order['strategy_name'], order['api_key'], order['account_id'], 
                                      order['base_symbol'], order['exchange_symbol'], order['price'], order['side'], order['quantity'], 
                                      current_timestamp, current_timestamp, current_unix_timestamp))
        
        connection.commit()
        logger_database.info("max_eat inserted successfully.")
        return None
    except Exception as err:
        logger_database.error(f"Error inserting row:{err}")
        return err
        
    finally:
        close_connection(connection, cursor)
    
def fetch_param_by_id(param_id):
    """
    Fetches a parameter from the database by its ID.

    Parameters:
        id (int): The ID of the parameter to be fetched.

    Returns:
        dict or None: The fetched parameter as a dictionary if it exists, otherwise None.

    Raises:
        mysql.connector.Error: If there is an error executing the SQL query.
    """
    try:
        connection, cursor = get_connection()
        select_query = """SELECT content FROM params WHERE id = %s and deleted_at IS NULL"""
        cursor.execute(select_query, (param_id,))
        result = cursor.fetchone()
        if result is not None and len(result) > 0:
            result = json.loads(result[0])
            return result
        return None
    except Exception as err:
        logger_database.error(f"Error fetching row: {err}")
        return err
        
    finally:
        close_connection(connection, cursor)

def insert_error_logger(file_name, line, content):
    """
    Inserts an error_logger record into the database.

    Args:
        file_name (str): The name of the file where the error occurred.
        line (int): The line number where the error occurred.
        content (str): The content of the error.

    Returns:
        None: If the record is successfully inserted.

    Raises:
        Exception: If there is an error inserting the row.

    """
    try:
        connection, cursor = get_connection()
        
        current_timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        insert_query = """
            INSERT INTO error_loggers (file_name, line, content, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s)
            """
        cursor.execute(insert_query, (file_name, line, content, current_timestamp, current_timestamp))
        
        connection.commit()
        logger_database.info("error inserted successfully.")
        return None
    except Exception as err:
        logger_database.error(f"Error inserting row:{err}")
        return err
        
    finally:
        close_connection(connection, cursor)
        
def insert_assets_snapshot(base_symbol, contents):
    try:
        connection, cursor = get_connection()
        
        current_timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        current_unix_timestamp = int(time.time())
        insert_query = """
            INSERT INTO assets_snap_shot (base_symbol, contents, created_at, updated_at, time_stamp)
            VALUES (%s, %s, %s, %s, %s)
            """
        
        cursor.execute(insert_query, (base_symbol, contents, current_timestamp, current_timestamp, current_unix_timestamp))
        
        connection.commit()
        return True
    except Exception as err:
        logger_database.error(f"Error inserting row: {err}")
        return err
        
    finally:
        close_connection(connection, cursor)


def insert_dex_snapshot(base_symbol, contents):
    try:
        connection, cursor = get_connection()
        
        current_timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        current_unix_timestamp = int(time.time())
        insert_query = """
            INSERT INTO dex_infos_snapshots (base_symbol, contents, created_at, updated_at, time_stamp)
            VALUES (%s, %s, %s, %s, %s)
            """
        
        cursor.execute(insert_query, (base_symbol, contents, current_timestamp, current_timestamp, current_unix_timestamp))
        
        connection.commit()
        return True
    except Exception as err:
        logger_database.error(f"Error inserting row: {err}")
        return err
        
    finally:
        close_connection(connection, cursor)


    