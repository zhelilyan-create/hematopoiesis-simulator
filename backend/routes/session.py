"""Session routes: start, step, snapshot, stop."""
from __future__ import annotations

import uuid
from fastapi import APIRouter, HTTPException

from models.schemas import (
    StartRequest, StartResponse,
    StepRequest, StepResponse,
    SnapshotResponse, StopResponse,
    StateMetrics,
)
from models.simulation_session import SimulationSession, build_config
from utils.validators import validate_params

router = APIRouter()

# In-memory session store (MVP — single user)
sessions: dict[str, SimulationSession] = {}
MAX_SESSIONS = 50


# ---------------------------------------------------------------------------
# POST /session/start
# ---------------------------------------------------------------------------

@router.post("/session/start", response_model=StartResponse)
async def start_session(body: StartRequest):
    # Collect flat params (UI sends convenience dict)
    params = dict(body.params or {})

    # Validate
    errors, warnings = validate_params(params)
    if errors:
        raise HTTPException(status_code=400, detail={"error": errors[0], "warnings": warnings})

    # Build full config
    if body.config:
        cfg = body.config
        # Still apply flat params on top if provided
        if params:
            cfg = {**cfg}
            pd = cfg.setdefault("population_dynamics", {})
            for k in ("density_gamma", "density_beta", "niche_strength",
                      "crowding_threshold", "crowding_apoptosis_rate"):
                if k in params:
                    pd[k] = float(params[k])
            if "target_population_size" in params:
                pd["target_population_size"] = int(float(params["target_population_size"]))
    else:
        cfg = build_config(params)

    # Evict oldest session if at capacity
    global sessions
    if len(sessions) >= MAX_SESSIONS:
        oldest = next(iter(sessions))
        del sessions[oldest]

    session_id = uuid.uuid4().hex[:12]
    try:
        sessions[session_id] = SimulationSession(
            session_id=session_id,
            config=cfg,
            seed=body.seed,
            t_max=body.t_max,
            params=params,
        )
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail={"error": f"Failed to initialise simulation: {exc}",
                    "warnings": []},
        )

    return StartResponse(session_id=session_id)


# ---------------------------------------------------------------------------
# POST /session/{session_id}/step
# ---------------------------------------------------------------------------

@router.post("/session/{session_id}/step", response_model=StepResponse)
async def step_session(session_id: str, body: StepRequest):
    session = _get(session_id)
    result  = session.step(body.n_events)
    return StepResponse(
        time=result["time"],
        population=result["population"],
        states=StateMetrics(**result["states"]),
        total=result["total"],
        finished=result["finished"],
        events_executed=result["events_executed"],
    )


# ---------------------------------------------------------------------------
# GET /session/{session_id}/snapshot
# ---------------------------------------------------------------------------

@router.get("/session/{session_id}/snapshot", response_model=SnapshotResponse)
async def get_snapshot(session_id: str):
    session = _get(session_id)
    snap    = session.get_snapshot()
    return SnapshotResponse(
        session_id=snap["session_id"],
        time=snap["time"],
        population=snap["population"],
        states=StateMetrics(**snap["states"]),
        total=snap["total"],
        finished=snap["finished"],
        history=[
            {
                "time":       h["time"],
                "population": h["population"],
                "states":     StateMetrics(**h["states"]),
                "total":      h["total"],
            }
            for h in snap["history"]
        ],
    )


# ---------------------------------------------------------------------------
# POST /session/{session_id}/stop
# ---------------------------------------------------------------------------

@router.post("/session/{session_id}/stop", response_model=StopResponse)
async def stop_session(session_id: str):
    session = _get(session_id)
    session.finished = True
    summary = session.get_summary()
    return StopResponse(
        session_id=summary["session_id"],
        final_time=summary["final_time"],
        final_population=summary["final_population"],
        summary_stats=summary["summary_stats"],
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get(session_id: str) -> SimulationSession:
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return sessions[session_id]


def get_sessions() -> dict[str, SimulationSession]:
    return sessions
