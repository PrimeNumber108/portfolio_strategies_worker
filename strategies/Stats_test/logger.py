# logger properties
import os
import logging
from logging.handlers import TimedRotatingFileHandler
from config import LOGGER_PATH #, LOGGER_PATH_GLOBAL, LOGGER_PATH_ERROR, LOGGER_PATH_JOBS, LOGGER_PATH_WARNING
current_directory = os.getcwd()
current_dir = os.path.basename(current_directory)

FORMAT = '[%(asctime)-15s][%(filename)s:%(lineno)d][%(levelname)s] %(message)s'
loggers = {}

if not os.path.exists("logger"):
    os.mkdir("logger")

class SizeAndTimedRotatingFileHandler(TimedRotatingFileHandler):
    """_summary_

    Args:
        TimedRotatingFileHandler (_type_): _description_
    """
    def __init__(self, filename, when='midnight', interval=1, backupCount=7, maxBytes=5*1024*1024, encoding=None, delay=False, utc=False, atTime=None):
        """_summary_

        Args:
            filename (_type_): _description_
            when (str, optional): _description_. Defaults to 'midnight'.
            interval (int, optional): _description_. Defaults to 1.
            backupCount (int, optional): _description_. Defaults to 7.
            maxBytes (_type_, optional): _description_. Defaults to 5*1024*1024.
            encoding (_type_, optional): _description_. Defaults to None.
            delay (bool, optional): _description_. Defaults to False.
            utc (bool, optional): _description_. Defaults to False.
            atTime (_type_, optional): _description_. Defaults to None.
        """
        # Gọi hàm khởi tạo của TimedRotatingFileHandler
        super().__init__(filename, when=when, interval=interval, backupCount=backupCount, encoding=encoding, delay=delay, utc=utc, atTime=atTime)
        self.maxBytes = maxBytes

    def shouldRollover(self, record):
        """_summary_

        Args:
            record (_type_): _description_

        Returns:
            _type_: _description_
        """
        
        # Kiểm tra điều kiện quay vòng theo thời gian
        
        if super().shouldRollover(record):
            return True
        
        # Kiểm tra điều kiện quay vòng theo kích thước
        if self.stream is None:  # Nếu chưa mở file
            self.stream = self._open()
        
        if os.stat(self.baseFilename).st_size >= self.maxBytes:
            return True

        return False


def setup_logger(name, log_file, level=logging.DEBUG):
    """
    This function sets up a logger with the given name and log file.
    """
    name = f"{current_dir}_{name}" 
    if loggers.get(name):
        return loggers.get(name)
   
    formatter = logging.Formatter(FORMAT)
    handler = SizeAndTimedRotatingFileHandler(
                        filename=log_file,
                        when="midnight",        # Xoay vòng theo ngày
                        maxBytes=100*1024*1024,  # Giới hạn kích thước file là 10 MB
                        backupCount=3           # Giữ lại 7 file log cũ
                    )
    # handler = RotatingFileHandler(log_file, mode='a', when='midnight', maxBytes=50*1024*1024,
    #                                  backupCount=10, encoding=None, delay=0)
    # handler = TimedRotatingFileHandler(log_file, when='midnight', backupCount=5)
    handler.setFormatter(formatter)
    handler.setLevel(level)
    logger2 = logging.getLogger(name)
    logger2.setLevel(level)
    logger2.addHandler(handler)
    loggers[name] = logger2
    return logger2

def setup_logger_global(name, log_file, level=logging.DEBUG):
    """
    Setup a global logger with the given name and log file.

    Parameters:
        name (str): The name of the logger.
        log_file (str): The path to the log file.
        level (int, optional): The logging level. Defaults to logging.DEBUG.

    Returns:
        logger: The logger object.
    """
    return setup_logger(name, LOGGER_PATH +log_file, level)

logger = setup_logger("global", './logger/assess.log')
logger_access = logger
logger_database = setup_logger("database", './logger/database.log')
logger_poloniex = setup_logger("poloniex_private", './logger/poloniex.log')
logger_error= setup_logger("error", './logger/error.log')
