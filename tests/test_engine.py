"""Tests for the CTMC engine and full simulation behavior.

Covers:
- zero-rate event exclusion from propensities
- terminal cell types produce no differentiation or division events
- deterministic reproducibility with a fixed seed
- different seeds produce different results
- t_max stopping: engine.time <= t_max after run
- initial snapshot: NOT recorded automatically
- manual initial snapshot: recorded correctly at t=0
- get_events returns only positive rates
"""

from pathlib import Path

import pytest
import yaml

from cell_diff_sim.cell import Cell
from cell_diff_sim.engine.ctmc import CTMCEngine
from cell_diff_sim.engine.events import DifferentiationEvent, DivisionEvent
from cell_diff_sim.models.hematopoiesis import HCellType, HematopoiesisModel
from cell_diff_sim.observers.recorder import Recorder
from cell_diff_sim.population import Population

ROOT = Path(__file__).parent.parent
CONFIG_PATH = ROOT / "configs" / "hematopoiesis_v01.yaml"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text())


@pytest.fixture
def model(config) -> HematopoiesisModel:
    return HematopoiesisModel(config)


def _make_engine(
    config: dict,
    seed: int = 0,
    n_hsc: int = 5,
) -> tuple[CTMCEngine, Recorder]:
    m = HematopoiesisModel(config)
    pop = Population([Cell(cell_type=HCellType.HSC) for _ in range(n_hsc)])
    rec = Recorder()
    engine = CTMCEngine(m, pop, observers=[rec], rng_seed=seed)
    return engine, rec


# ---------------------------------------------------------------------------
# Zero-rate event exclusion
# ---------------------------------------------------------------------------

def test_get_events_all_rates_positive(model):
    """get_events() must never return a zero-rate event."""
    pop = Population([Cell(cell_type=HCellType.HSC)])
    cell = next(iter(pop))
    for rate, _ in model.get_events(cell, pop):
        assert rate > 0.0, f"Zero-rate event found: rate={rate}"


def test_get_events_rates_are_finite(model):
    """All rates must be finite (no inf, no nan)."""
    import math
    pop = Population([Cell(cell_type=HCellType.HSC)])
    cell = next(iter(pop))
    for rate, _ in model.get_events(cell, pop):
        assert math.isfinite(rate)


# ---------------------------------------------------------------------------
# Terminal cell types
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ct", [
    HCellType.Myeloid,
    HCellType.Erythroid,
    HCellType.B_cell,
    HCellType.T_cell,
])
def test_terminal_has_no_differentiation_event(model, ct):
    pop = Population([Cell(cell_type=ct)])
    cell = next(iter(pop))
    event_types = [type(ev) for _, ev in model.get_events(cell, pop)]
    assert DifferentiationEvent not in event_types


@pytest.mark.parametrize("ct", [
    HCellType.Myeloid,
    HCellType.Erythroid,
    HCellType.B_cell,
    HCellType.T_cell,
])
def test_terminal_has_no_division_event(model, ct):
    pop = Population([Cell(cell_type=ct)])
    cell = next(iter(pop))
    event_types = [type(ev) for _, ev in model.get_events(cell, pop)]
    assert DivisionEvent not in event_types


# ---------------------------------------------------------------------------
# Deterministic reproducibility
# ---------------------------------------------------------------------------

def test_same_seed_produces_identical_runs(config):
    e1, r1 = _make_engine(config, seed=99)
    e1.run(t_max=10.0)

    e2, r2 = _make_engine(config, seed=99)
    e2.run(t_max=10.0)

    assert len(r1) == len(r2)
    for s1, s2 in zip(r1.snapshots, r2.snapshots):
        assert s1.time == pytest.approx(s2.time)
        assert s1.counts == s2.counts


def test_different_seeds_produce_different_runs(config):
    e1, r1 = _make_engine(config, seed=1)
    e1.run(t_max=30.0)

    e2, r2 = _make_engine(config, seed=2)
    e2.run(t_max=30.0)

    # Vanishingly unlikely to be equal
    assert r1.snapshots[-1].counts != r2.snapshots[-1].counts


# ---------------------------------------------------------------------------
# t_max stopping
# ---------------------------------------------------------------------------

def test_engine_time_does_not_exceed_tmax(config):
    t_max = 15.0
    engine, _ = _make_engine(config, seed=0)
    engine.run(t_max=t_max)
    assert engine.time <= t_max


def test_engine_time_at_tmax_when_time_limited(config):
    """When the run completes due to t_max (not extinction), time == t_max."""
    # Use a large population so extinction is very unlikely
    engine, _ = _make_engine(config, seed=42, n_hsc=20)
    engine.run(t_max=50.0)
    assert engine.time == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# Initial snapshot behaviour
# ---------------------------------------------------------------------------

def test_initial_snapshot_not_recorded_automatically(config):
    """Observers are called only after events; t=0 is never auto-recorded."""
    engine, rec = _make_engine(config, seed=0)
    engine.run(t_max=5.0)

    assert len(rec) > 0, "expected at least one event"
    assert rec.snapshots[0].time > 0.0, (
        "first snapshot should be after first event, not at t=0"
    )


def test_manual_initial_snapshot_recorded_at_t0(config):
    """Caller can manually record t=0 before run(); first snapshot is t=0."""
    m = HematopoiesisModel(config)
    pop = Population([Cell(cell_type=HCellType.HSC) for _ in range(5)])
    rec = Recorder()

    rec.on_step(0.0, pop)   # manual initial snapshot

    engine = CTMCEngine(m, pop, observers=[rec], rng_seed=0)
    engine.run(t_max=5.0)

    assert rec.snapshots[0].time == pytest.approx(0.0)
    assert rec.snapshots[0].total == 5


def test_manual_initial_snapshot_shows_correct_composition(config):
    m = HematopoiesisModel(config)
    pop = Population([
        Cell(cell_type=HCellType.HSC),
        Cell(cell_type=HCellType.MPP),
    ])
    rec = Recorder()
    rec.on_step(0.0, pop)

    CTMCEngine(m, pop, observers=[rec], rng_seed=0).run(t_max=0.001)

    assert rec.snapshots[0].counts.get("HSC", 0) == 1
    assert rec.snapshots[0].counts.get("MPP", 0) == 1
