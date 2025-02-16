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

def run_bot():
    """Inicia el proceso del bot"""
    logger.info("🤖 Starting DexFren Bot...")
    try:
        process = subprocess.Popen(
            [sys.executable, "main.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Redirigir stderr a stdout
            universal_newlines=True,
            bufsize=1,
            env={**os.environ, 'PYTHONUNBUFFERED': '1'}  # Forzar salida sin buffer
        )
        logger.info("✅ Bot started successfully")
        return process
    except Exception as e:
        logger.error(f"❌ Error starting bot: {str(e)}")
        return None

def run_frontend():
    """Inicia el proceso del frontend"""
    logger.info("🌐 Starting Frontend Server...")
    try:
        process = subprocess.Popen(
            [sys.executable, "frontend/app.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )
        logger.info("✅ Frontend started successfully")
        return process
    except Exception as e:
        logger.error(f"❌ Error starting frontend: {str(e)}")
        return None

def cleanup(processes):
    """Limpia los procesos al cerrar"""
    logger.info("\n🛑 Stopping services...")
    for process in processes:
        if process:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
    system_monitor.stop_monitoring()
    logger.info("✅ All services stopped")

def monitor_process_output(process, name):
    """Monitor and log process output"""
    while True:
        try:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                line = line.strip()
                if line:  # Solo loguear si hay contenido
                    if "ERROR" in line.upper():
                        logger.error(f"{name}: {line}")
                    else:
                        logger.info(f"{name}: {line}")
        except Exception as e:
            logger.error(f"Error reading {name} output: {str(e)}")
            break

def main():
    print(DEXKIT_LOGO)
    print("\n" + "="*50)
    logger.info("DexFren AI Bot System Starting")
    print("="*50 + "\n")

    processes = []
    try:
        # Iniciar bot
        bot_process = run_bot()
        if bot_process:
            processes.append(bot_process)
            # Monitor bot output in a separate thread
            bot_monitor = threading.Thread(
                target=monitor_process_output,
                args=(bot_process, "Bot"),
                daemon=True
            )
            bot_monitor.start()

        # Iniciar frontend
        frontend_process = run_frontend()
        if frontend_process:
            processes.append(frontend_process)
            # Monitor frontend output in a separate thread
            frontend_monitor = threading.Thread(
                target=monitor_process_output,
                args=(frontend_process, "Frontend"),
                daemon=True
            )
            frontend_monitor.start()

        # Iniciar monitoreo del sistema
        system_monitor.start_monitoring()

        # Mantener el script corriendo y procesar salida
        while all(p.poll() is None for p in processes):
            time.sleep(0.1)  # Pequeña pausa para no consumir CPU

    except KeyboardInterrupt:
        logger.info("\n⚡ Received interrupt signal")
    except Exception as e:
        logger.error(f"Critical error: {str(e)}")
    finally:
        cleanup(processes)

if __name__ == "__main__":
    main() 