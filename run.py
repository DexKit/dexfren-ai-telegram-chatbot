import subprocess
import threading
import time
import os
import signal
import sys
from dotenv import load_dotenv

load_dotenv()

def run_bot():
    print("🤖 Starting DexFren Bot...")
    try:
        bot_process = subprocess.Popen([sys.executable, "main.py"])
        return bot_process
    except Exception as e:
        print(f"❌ Error starting bot: {str(e)}")
        return None

def run_frontend():
    print("🌐 Starting Frontend...")
    try:
        frontend_process = subprocess.Popen([sys.executable, "frontend/app.py"])
        return frontend_process
    except Exception as e:
        print(f"❌ Error starting frontend: {str(e)}")
        return None

def check_environment():
    required_vars = ['TELEGRAM_BOT_TOKEN', 'OPENAI_API_KEY']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print("❌ Error: Missing environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        return False
    return True

def cleanup(processes):
    print("\n🛑 Stopping services...")
    for process in processes:
        if process:
            process.terminate()
            process.wait()
    print("✅ Services stopped correctly")

def main():
    print("""
╔═══════════════════════════════════════╗
║           DexFren AI Bot              ║
║            Admin System               ║
╚═══════════════════════════════════════╝
    """)

    if not check_environment():
        sys.exit(1)

    processes = []
    try:
        bot_process = run_bot()
        if bot_process:
            processes.append(bot_process)
            time.sleep(2)
        
        frontend_process = run_frontend()
        if frontend_process:
            processes.append(frontend_process)
        
        print("""
✅ Services started correctly:
   🤖 Bot: http://localhost:5000
   🌐 Frontend: http://localhost:5001

📝 Press Ctrl+C to stop all services
        """)

        while all(p.poll() is None for p in processes):
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n⚡ Received interrupt signal...")
    finally:
        cleanup(processes)

if __name__ == "__main__":
    main() 