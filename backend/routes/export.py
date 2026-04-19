"""Export routes: PDF."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from utils.pdf_exporter import generate_pdf
from routes.session import get_sessions

router = APIRouter()


@router.get("/session/{session_id}/export/pdf")
async def export_pdf(session_id: str):
    sessions = get_sessions()
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    session = sessions[session_id]
    snap    = session.get_snapshot()
    summary = session.get_summary()

    session_data = {
        "session_id":       session_id,
        "seed":             session.seed,
        "t_max":            session.t_max,
        "final_time":       summary["final_time"],
        "params":           session.params,
        "final_population": summary["final_population"],
        "summary_stats":    summary["summary_stats"],
        "per_type_stats":   summary.get("per_type_stats", {}),
        "history":          snap["history"],
    }

    pdf_bytes = generate_pdf(session_data)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="hema_report_{session_id}.pdf"'
        },
    )
