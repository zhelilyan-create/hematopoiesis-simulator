"""Hematopoiesis Simulator — Desktop Launcher

PyInstaller entry point.
Starts the FastAPI backend in a thread and opens the browser.

Usage (development):
    python launcher.py

Usage (built exe — double click):
    dist/HematopoiesisSim/HematopoiesisSim.exe
"""
from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser

# ── Resolve base directory ────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    # PyInstaller one-dir: all extracted files are in sys._MEIPASS
    BASE_DIR = sys._MEIPASS
else:
    # Normal Python run: launcher.py is in the project root
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Ensure project root and backend/ are importable before any other imports
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "backend"))

HOST = "127.0.0.1"
PORT = 8000
URL  = f"http://{HOST}:{PORT}"


def _open_browser() -> None:
    """Wait for uvicorn to bind, then open the default browser."""
    time.sleep(2.5)
    webbrowser.open(URL)


def main() -> None:
    print("=" * 60)
    print("  Hematopoiesis Simulator  v0.1.0  —  Desktop")
    print("=" * 60)
    print(f"  Server : {URL}")
    print("  Browser opens automatically in ~3 seconds")
    print("  Press Ctrl+C to stop")
    print("=" * 60)

    # Open browser in background thread (uvicorn starts first)
    threading.Thread(target=_open_browser, daemon=True).start()

    # Import here (after sys.path is set up correctly)
    import uvicorn
    from desktop_app import app  # registers static file routes on top of app.py

    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="warning",   # suppress INFO noise; use "info" to debug
    )


if __name__ == "__main__":
    main()
