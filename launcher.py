"""Hematopoiesis Simulator — Desktop Launcher

PyInstaller entry point.
Starts the FastAPI backend on 127.0.0.1:8000 and opens the browser.

Usage (development):
    python launcher.py

Usage (built exe):
    Double-click HematopoiesisSim.exe  (or run from the dist/ folder)
"""
from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser

# ── Resolve base directory ────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    # PyInstaller one-dir: extracted files live in sys._MEIPASS
    BASE_DIR = sys._MEIPASS
else:
    # Normal Python run from project root
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Put both project root and backend on sys.path before any imports
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "backend"))

HOST = "127.0.0.1"
PORT = 8000
URL  = f"http://{HOST}:{PORT}"


def _open_browser() -> None:
    """Wait for uvicorn to bind, then open the default browser."""
    time.sleep(2.5)
    webbrowser.open(URL)


if __name__ == "__main__":
    print(f"[Launcher] Hematopoiesis Simulator starting at {URL}")
    print("[Launcher] The browser will open automatically in a few seconds…")

    # Open browser in background thread so uvicorn can start first
    threading.Thread(target=_open_browser, daemon=True).start()

    import uvicorn
    from desktop_app import app  # import object directly — avoids string-based lookup

    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="warning",   # suppress INFO noise; set "info" to debug
    )
