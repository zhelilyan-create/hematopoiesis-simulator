"""History route: list of completed runs."""
from __future__ import annotations

from fastapi import APIRouter
from models.schemas import HistoryResponse
from routes.session import get_sessions

router = APIRouter()


@router.get("/runs/history", response_model=HistoryResponse)
async def get_history():
    sessions = get_sessions()
    runs = [s.get_run_record() for s in sessions.values()]
    # Most recent first
    runs.sort(key=lambda r: r["timestamp"], reverse=True)
    return HistoryResponse(runs=runs)
