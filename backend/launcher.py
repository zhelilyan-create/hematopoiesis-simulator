import os
import sys
import subprocess
import time
import webbrowser
from pathlib import Path

def main():
    """Запустить сервер и открыть браузер"""
    
    # Определить путь к текущей директории
    backend_dir = Path(__file__).parent
    
    print("=" * 60)
    print("🧬 Hematopoiesis Simulator - Desktop Version")
    print("=" * 60)
    print()
    print("⏳ Starting server...")
    
    # Запустить uvicorn сервер
    # используем desktop_app из текущей папки
    try:
        
        server_process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "desktop_app:app", 
             "--host", "127.0.0.1", "--port", "8000"],
            cwd=str(backend_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        
        print("⏳ Waiting for server to start (2-3 seconds)...")
        time.sleep(3)
        
        
        print("🌐 Opening browser...")
        webbrowser.open("http://127.0.0.1:8000")
        
        print()
        print("✅ Server is running on http://127.0.0.1:8000")
        print("📖 Press Ctrl+C to stop the server")
        print()
        
        
        server_process.wait()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print()
        print("Troubleshooting:")
        print("1. Check if port 8000 is available")
        print("2. Check if all dependencies are installed")
        print("3. Try running: pip install -r requirements.txt")
        sys.exit(1)

if __name__ == "__main__":
    main()