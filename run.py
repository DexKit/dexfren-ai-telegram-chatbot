from utils.logger import setup_logger
import subprocess
import os
import signal
import sys
from dotenv import load_dotenv
from ascii_art import DEXKIT_LOGO
from monitor import SystemMonitor
import threading
import time

load_dotenv()
logger = setup_logger()
system_monitor = SystemMonitor()
cleanup_executed = False

def run_bot():
    logger.info("Starting DexFren Bot...")
    try:
        required_files = [
            'config/agent_instructions.json',
            'config/youtube_videos.json',
            'config/platform_urls.json',
            'config/documentation_urls.json'
        ]
        
        for file in required_files:
            if not os.path.exists(file):
                logger.error(f"Required configuration file not found: {file}")
                return None
                
        process = subprocess.Popen(
            [sys.executable, "main.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        logger.info("Bot started successfully")
        return process
    except Exception as e:
        logger.error(f"Error starting bot: {str(e)}")
        return None

def run_frontend():
    logger.info("Starting Frontend Server...")
    try:
        process = subprocess.Popen(
            [sys.executable, "frontend/app.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )
        logger.info("Frontend started successfully")
        return process
    except Exception as e:
        logger.error(f"Error starting frontend: {str(e)}")
        return None

def cleanup(processes):
    global cleanup_executed
    
    if cleanup_executed:
        return
    
    logger.info("Stopping all services...")
    
    system_monitor.stop_monitoring()
    
    for process in processes:
        if process and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
    
    logger.info("All services stopped")
    cleanup_executed = True

def monitor_process_output(process, name):
    if process is None:
        return
        
    try:
        for line in iter(process.stdout.readline, ''):
            if line:
                if "ERROR" in line or "Error" in line:
                    logger.error(f"{name}: {line}")
                else:
                    logger.info(f"{name}: {line}")
    except Exception as e:
        logger.error(f"Error reading {name} output: {str(e)}")

def main():
    print(DEXKIT_LOGO)
    print("\n" + "="*50)
    logger.info("DexFren AI Bot System Starting")
    print("="*50 + "\n")

    processes = []
    
    def signal_handler(signum, frame):
        cleanup(processes)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        bot_process = run_bot()
        if bot_process:
            processes.append(bot_process)
            bot_monitor = threading.Thread(
                target=monitor_process_output,
                args=(bot_process, "Bot"),
                daemon=True
            )
            bot_monitor.start()

        frontend_process = run_frontend()
        if frontend_process:
            processes.append(frontend_process)
            frontend_monitor = threading.Thread(
                target=monitor_process_output,
                args=(frontend_process, "Frontend"),
                daemon=True
            )
            frontend_monitor.start()

        system_monitor.start_monitoring()

        while all(p.poll() is None for p in processes):
            time.sleep(0.1)

    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Critical error: {str(e)}")
    finally:
        cleanup(processes)

if __name__ == "__main__":
    main() 