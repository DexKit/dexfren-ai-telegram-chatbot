import os
import time
import subprocess
import signal
import sys
import shutil
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    filename='bot_monitor.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def clean_cache():
    """Clean cache and knowledge base"""
    try:
        directories = [
            './knowledge_base',
            './__pycache__',
            './knowledge/__pycache__',
            './frontend/__pycache__'
        ]
        
        for directory in directories:
            if os.path.exists(directory):
                shutil.rmtree(directory)
                logging.info(f"Cleaned directory: {directory}")
    except Exception as e:
        logging.error(f"Error cleaning cache: {str(e)}")

def rebuild_knowledge_base():
    """Rebuild knowledge base"""
    try:
        result = subprocess.run([sys.executable, 'build_knowledge_base.py'], 
                              capture_output=True, 
                              text=True)
        if result.returncode == 0:
            logging.info("Knowledge base rebuilt successfully")
        else:
            logging.error(f"Error rebuilding knowledge base: {result.stderr}")
    except Exception as e:
        logging.error(f"Error executing build_knowledge_base.py: {str(e)}")

def is_process_running(process):
    """Check if the process is running"""
    if process is None:
        return False
    return process.poll() is None

def restart_bot():
    """Restart the bot completely"""
    try:
        clean_cache()
        rebuild_knowledge_base()
        process = subprocess.Popen([sys.executable, 'run.py'])
        logging.info("Bot restarted successfully")
        return process
    except Exception as e:
        logging.error(f"Error restarting bot: {str(e)}")
        return None

def main():
    bot_process = None
    last_restart = 0
    
    while True:
        current_time = time.time()
        
        # If the process does not exist or is not running
        if not is_process_running(bot_process):
            # Avoid too frequent restarts
            if current_time - last_restart > 10:
                logging.warning("Bot crashed, starting recovery...")
                bot_process = restart_bot()
                last_restart = current_time
        
        time.sleep(10)  # Check every 10 seconds

if __name__ == "__main__":
    main() 