"""Desktop wrapper for the FastAPI app.

Extends app.py with static-file serving so the backend also acts as the
web server for the bundled frontend.  Import this module (not app.py)
when running the desktop .exe.

Path resolution works in three modes:
  1. Normal dev run  : __file__ is in backend/, project root is one level up.
  2. PyInstaller exe : sys._MEIPASS contains the extracted bundle.
  3. pytest / CI     : same as mode 1.
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

# ── Resolve project root ──────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    # Running inside a PyInstaller one-dir bundle
    _BASE = Path(sys._MEIPASS)
else:
    # Normal Python: this file lives in backend/, project root is one up
    _BASE = Path(__file__).parent.parent

# Ensure both project root and backend/ are importable
sys.path.insert(0, str(_BASE))
sys.path.insert(0, str(_BASE / "backend"))

# ── Import the existing FastAPI app (all API routes already registered) ───────
from app import app  # noqa: E402

from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.responses import FileResponse   # noqa: E402

_FRONTEND = _BASE / "frontend" / "public"   # index.html, App.jsx, logo.png
_HELP     = _BASE / "Help_page"             # help.html (and any other assets)

# ── Serve index.html at root ──────────────────────────────────────────────────
# Registered AFTER API routers → only acts as fallback for GET /
@app.get("/", include_in_schema=False)
async def _serve_index() -> FileResponse:
    return FileResponse(str(_FRONTEND / "index.html"))

# ── Mount /Help_page → Help_page/ directory ───────────────────────────────────
if _HELP.exists():
    app.mount("/Help_page", StaticFiles(directory=str(_HELP)), name="help")

# ── Mount / → frontend/public/ (App.jsx, logo.png, etc.) ─────────────────────
# StaticFiles acts as a catch-all fallback; explicit route handlers above
# take priority because FastAPI evaluates routes before mounts.
if _FRONTEND.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND)), name="frontend")
