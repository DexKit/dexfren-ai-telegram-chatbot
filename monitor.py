from utils.logger import setup_logger
import psutil
import os
import time
import threading

logger = setup_logger()

class SystemMonitor:
    def __init__(self):
        self.running = False
        self.monitor_thread = None

    def start_monitoring(self):
        """Inicia el monitoreo en un hilo separado"""
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        logger.info("System monitoring started")

    def stop_monitoring(self):
        """Detiene el monitoreo"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join()
        logger.info("System monitoring stopped")

    def _monitor_loop(self):
        """Loop principal de monitoreo"""
        while self.running:
            try:
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                
                bot_processes = [p for p in psutil.process_iter(['name', 'cpu_percent', 'memory_percent']) 
                               if 'python' in p.info['name'].lower()]
                
                kb_size = 0
                if os.path.exists('./knowledge_base'):
                    kb_size = sum(
                        os.path.getsize(os.path.join('./knowledge_base', f)) 
                        for f in os.listdir('./knowledge_base')
                    ) / (1024 * 1024)

                logger.info(f"System Metrics:")
                logger.info(f"├── CPU Usage: {cpu_percent}%")
                logger.info(f"├── Memory Usage: {memory.percent}%")
                logger.info(f"├── Knowledge Base Size: {kb_size:.2f} MB")
                logger.info(f"└── Active Python Processes: {len(bot_processes)}")

                for proc in bot_processes:
                    logger.info(f"    └── Process: {proc.info['name']} "
                              f"(CPU: {proc.info['cpu_percent']}%, "
                              f"Memory: {proc.info['memory_percent']:.1f}%)")

            except Exception as e:
                logger.error(f"Error in monitoring: {str(e)}")
            
            time.sleep(60)