import datetime
from math import ceil
import pandas as pd

def convert_time(timestamp_ms):
    """
    Convert a timestamp in milliseconds to a formatted time string.

    Args:
        timestamp_ms (int): The timestamp in milliseconds.

    Returns:
        str: The formatted time string in the format "YYYY-MM-DD HH:MM:SS".
    """
    timestamp_s = timestamp_ms / 1000
    dt = datetime.datetime.fromtimestamp(timestamp_s)
    formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
    return formatted_time


def convert_to_datetime_index(date_str):
    """
    Converts a given date string to a datetime index.

    Args:
        date_str (str): The date string to be converted, in the format '%d/%m/%Y %H:%M'.

    Returns:
        pd.DatetimeIndex: A pandas DatetimeIndex object containing the converted datetime.
    """
    dt = pd.to_datetime(date_str, format='%d/%m/%Y %H:%M')
    df = pd.DataFrame(index=[dt])
    print(df)
    return df.index


def calculate_gap_hours(ts1, ts2):
    """
    Calculate the gap in hours between two timestamps.

    Args:
        ts1 (int): The first timestamp in milliseconds.
        ts2 (int): The second timestamp in milliseconds.

    Returns:
        int: The gap in hours between the two timestamps.

    This function calculates the difference in seconds between two timestamps,
    converts it to hours, and rounds up to the nearest whole number. The input
    timestamps are assumed to be in milliseconds and are converted to seconds
    before the calculation. The function returns the gap in hours between the
    two timestamps.
    """
    # Convert milliseconds to seconds
    ts1_seconds = ts1
    ts2_seconds = ts2
    if len(str(int(ts1))) == 13:
        ts1_seconds = int(ts1 / 1000)
    if len(str(int(ts2))) == 13:
        ts2_seconds = int(ts2 / 1000)

    # Calculate the difference in seconds
    difference_seconds = abs(ts2_seconds - ts1_seconds)

    # Convert the difference to hours
    difference_hours = ceil(difference_seconds / 3600.0)

    return difference_hours
