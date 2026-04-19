"""Pydantic schemas for API request/response validation."""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class PopulationDynamics(BaseModel):
    target_population_size: int = 1000
    density_gamma: float = 4.0
    density_beta: float = 0.0
    niche_strength: float = 4.0
    crowding_threshold: float = 1.3
    crowding_apoptosis_rate: float = 0.1


class StartRequest(BaseModel):
    config: Optional[dict] = None          # full YAML-equivalent dict; None = use baseline
    params: Optional[dict] = None          # flat override dict (convenience)
    seed: int = 0   # 0 = random (np.random.default_rng(None)), >0 = fixed
    t_max: float = 100.0


class StepRequest(BaseModel):
    n_events: int = Field(default=500, ge=1, le=50_000)


# ---------------------------------------------------------------------------
# Response bodies
# ---------------------------------------------------------------------------

class PopulationCounts(BaseModel):
    HSC: int = 0
    MPP: int = 0
    CMP: int = 0
    CLP: int = 0
    Myeloid: int = 0
    Erythroid: int = 0
    B_cell: int = 0
    T_cell: int = 0


class StateMetrics(BaseModel):
    mean_stemness: float = 0.0
    mean_stress: float = 0.0
    mean_bias: float = 0.0


class StartResponse(BaseModel):
    session_id: str


class StepResponse(BaseModel):
    time: float
    population: dict
    states: StateMetrics
    total: int
    finished: bool
    events_executed: int


class SnapshotPoint(BaseModel):
    time: float
    population: dict
    states: StateMetrics
    total: int


class SnapshotResponse(BaseModel):
    session_id: str
    time: float
    population: dict
    states: StateMetrics
    total: int
    finished: bool
    history: list[SnapshotPoint]


class SummaryStats(BaseModel):
    mean_stemness: float
    mean_stress: float
    mean_bias: float


class StopResponse(BaseModel):
    session_id: str
    final_time: float
    final_population: dict
    summary_stats: SummaryStats


class RunRecord(BaseModel):
    id: str
    timestamp: str
    seed: int
    config_hash: str
    final_total: int
    final_population: dict
    summary: dict


class HistoryResponse(BaseModel):
    runs: list[RunRecord]


class ErrorResponse(BaseModel):
    error: str
    warnings: list[str] = []
