import logging
import os
from datetime import datetime

def setup_logger():
    logger = logging.getLogger('DexFren')
    
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if not os.path.exists('logs'):
        os.makedirs('logs')
    daily_file = os.path.join('logs', f'dexfren_{datetime.now().strftime("%Y%m%d")}.log')
    file_handler = logging.FileHandler(daily_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger 