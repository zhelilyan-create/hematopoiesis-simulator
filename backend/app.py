"""FastAPI application entry point.

Run:
    cd backend
    uvicorn app:app --reload --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.session import router as session_router
from routes.export  import router as export_router
from routes.history import router as history_router

app = FastAPI(
    title="Hematopoiesis Simulator API",
    description="Hematopoiesis Simulator",
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# CORS — allow React dev server (port 3000) and file:// origin
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # MVP: open; tighten for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(session_router)
app.include_router(export_router)
app.include_router(history_router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
