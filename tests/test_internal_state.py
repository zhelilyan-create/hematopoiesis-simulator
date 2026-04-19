"""Tests for InternalState, RateModulator, and SymmetricInheritanceRules.

Covers:
- InternalState: valid construction and __post_init__ validation
- RateModulator: neutral state -> all factors = 1.0
- RateModulator: all-zero weights -> factors = 1.0 for any state
- RateModulator: factor direction (higher stemness -> more division, etc.)
- SymmetricInheritanceRules: copies scores, increments division_count
- Backward compatibility: v0.1 config still runs with v0.2 model
- Reproducibility: fixed seed still gives identical runs
"""

from pathlib import Path

import pytest
import yaml

from cell_diff_sim.cell import Cell
from cell_diff_sim.engine.ctmc import CTMCEngine
from cell_diff_sim.engine.events import DivisionEvent
from cell_diff_sim.internal_state import InternalState
from cell_diff_sim.models.hematopoiesis import HCellType, HematopoiesisModel
from cell_diff_sim.models.inheritance import SymmetricInheritanceRules
from cell_diff_sim.models.rate_modulation import ModulationParams, RateModulator
from cell_diff_sim.observers.recorder import Recorder
from cell_diff_sim.population import Population

ROOT = Path(__file__).parent.parent
CONFIG_V01 = ROOT / "configs" / "hematopoiesis_v01.yaml"
CONFIG_V02 = ROOT / "configs" / "hematopoiesis_v02.yaml"


# ===========================================================================
# InternalState: construction and validation
# ===========================================================================

def test_internal_state_defaults():
    s = InternalState()
    assert s.stemness_score == pytest.approx(0.5)
    assert s.stress_score   == pytest.approx(0.0)
    assert s.division_count == 0


def test_internal_state_boundary_values():
    """Boundary values 0.0 and 1.0 for stemness must be accepted."""
    InternalState(stemness_score=0.0)
    InternalState(stemness_score=1.0)


def test_internal_state_stemness_below_zero_raises():
    with pytest.raises(ValueError, match="stemness_score"):
        InternalState(stemness_score=-0.01)


def test_internal_state_stemness_above_one_raises():
    with pytest.raises(ValueError, match="stemness_score"):
        InternalState(stemness_score=1.01)


def test_internal_state_negative_stress_raises():
    with pytest.raises(ValueError, match="stress_score"):
        InternalState(stress_score=-0.1)


def test_internal_state_negative_division_count_raises():
    with pytest.raises(ValueError, match="division_count"):
        InternalState(division_count=-1)


# ===========================================================================
# RateModulator: neutral state gives factor = 1.0
# ===========================================================================

def _modulator_with_nonzero_weights() -> RateModulator:
    """A modulator with nonzero weights to exercise the formulas."""
    return RateModulator(ModulationParams(
        w_div_stemness=1.0,  w_div_stress=0.5,   w_div_repl=0.005,
        w_diff_stemness=1.0, w_diff_stress=0.2,  w_diff_repl=0.005,
        w_apo_stress=1.0,    w_apo_repl=0.005,
    ))


def test_neutral_state_division_factor_is_one():
    mod = _modulator_with_nonzero_weights()
    assert mod.division_factor(InternalState()) == pytest.approx(1.0)


def test_neutral_state_differentiation_factor_is_one():
    mod = _modulator_with_nonzero_weights()
    assert mod.differentiation_factor(InternalState()) == pytest.approx(1.0)


def test_neutral_state_apoptosis_factor_is_one():
    mod = _modulator_with_nonzero_weights()
    assert mod.apoptosis_factor(InternalState()) == pytest.approx(1.0)


# ===========================================================================
# RateModulator: all-zero weights -> factor = 1.0 for ANY state
# ===========================================================================

def test_zero_weights_division_factor_is_one():
    mod = RateModulator(ModulationParams())   # all weights = 0.0
    extreme = InternalState(stemness_score=1.0, stress_score=10.0, division_count=100)
    assert mod.division_factor(extreme) == pytest.approx(1.0)


def test_zero_weights_differentiation_factor_is_one():
    mod = RateModulator(ModulationParams())
    extreme = InternalState(stemness_score=0.0, stress_score=5.0, division_count=50)
    assert mod.differentiation_factor(extreme) == pytest.approx(1.0)


def test_zero_weights_apoptosis_factor_is_one():
    mod = RateModulator(ModulationParams())
    extreme = InternalState(stress_score=100.0, division_count=200)
    assert mod.apoptosis_factor(extreme) == pytest.approx(1.0)


# ===========================================================================
# RateModulator: factor directions
# ===========================================================================

def test_higher_stemness_increases_division_factor():
    mod = _modulator_with_nonzero_weights()
    low  = InternalState(stemness_score=0.2)
    high = InternalState(stemness_score=0.8)
    assert mod.division_factor(high) > mod.division_factor(low)


def test_higher_stemness_decreases_differentiation_factor():
    mod = _modulator_with_nonzero_weights()
    low  = InternalState(stemness_score=0.2)
    high = InternalState(stemness_score=0.8)
    assert mod.differentiation_factor(high) < mod.differentiation_factor(low)


def test_higher_stress_increases_apoptosis_factor():
    mod = _modulator_with_nonzero_weights()
    low  = InternalState(stress_score=0.1)
    high = InternalState(stress_score=2.0)
    assert mod.apoptosis_factor(high) > mod.apoptosis_factor(low)


def test_higher_stress_decreases_division_factor():
    mod = _modulator_with_nonzero_weights()
    low  = InternalState(stress_score=0.0)
    high = InternalState(stress_score=1.0)
    assert mod.division_factor(high) < mod.division_factor(low)


def test_higher_division_count_decreases_division_factor():
    mod = _modulator_with_nonzero_weights()
    few  = InternalState(division_count=0)
    many = InternalState(division_count=100)
    assert mod.division_factor(many) < mod.division_factor(few)


def test_factor_clamp_applied():
    """Very extreme state must still be within [min_factor, max_factor]."""
    params = ModulationParams(w_apo_stress=10.0, min_factor=0.1, max_factor=5.0)
    mod = RateModulator(params)
    extreme = InternalState(stress_score=100.0)
    assert mod.apoptosis_factor(extreme) == pytest.approx(5.0)


# ===========================================================================
# SymmetricInheritanceRules
# ===========================================================================

def _make_parent(stemness: float = 0.7, stress: float = 0.3, div: int = 4) -> Cell:
    c = Cell(
        cell_type=HCellType.HSC,
        internal_state=InternalState(
            stemness_score=stemness,
            stress_score=stress,
            division_count=div,
        ),
    )
    return c


def test_symmetric_rules_copies_stemness():
    parent = _make_parent(stemness=0.7)
    rules = SymmetricInheritanceRules()
    ev = DivisionEvent(daughter_cell_types=(HCellType.HSC, HCellType.HSC))
    daughter_state = rules.inherit(parent, 0, ev)
    assert daughter_state.internal_state.stemness_score == pytest.approx(0.7)


def test_symmetric_rules_copies_stress():
    parent = _make_parent(stress=0.3)
    rules = SymmetricInheritanceRules()
    ev = DivisionEvent(daughter_cell_types=(HCellType.HSC, HCellType.HSC))
    daughter_state = rules.inherit(parent, 0, ev)
    assert daughter_state.internal_state.stress_score == pytest.approx(0.3)


def test_symmetric_rules_increments_division_count():
    parent = _make_parent(div=4)
    rules = SymmetricInheritanceRules()
    ev = DivisionEvent(daughter_cell_types=(HCellType.HSC, HCellType.HSC))
    d0 = rules.inherit(parent, 0, ev)
    d1 = rules.inherit(parent, 1, ev)
    assert d0.internal_state.division_count == 5
    assert d1.internal_state.division_count == 5


def test_symmetric_rules_both_daughters_equal():
    """daughter_index is ignored — both daughters get identical state."""
    parent = _make_parent()
    rules = SymmetricInheritanceRules()
    ev = DivisionEvent(daughter_cell_types=(HCellType.HSC, HCellType.HSC))
    d0 = rules.inherit(parent, 0, ev)
    d1 = rules.inherit(parent, 1, ev)
    assert d0.internal_state.stemness_score == d1.internal_state.stemness_score
    assert d0.internal_state.stress_score   == d1.internal_state.stress_score
    assert d0.internal_state.division_count == d1.internal_state.division_count


# ===========================================================================
# State-dependent rates change in expected direction (integration test)
# ===========================================================================

def test_state_dependent_diff_rate_increases_with_low_stemness():
    """A cell with low stemness should have a higher differentiation rate."""
    config = yaml.safe_load(CONFIG_V02.read_text())
    model = HematopoiesisModel(config)

    pop = Population([Cell(cell_type=HCellType.HSC)])

    # High-stemness cell
    cell_high = Cell(
        cell_type=HCellType.HSC,
        internal_state=InternalState(stemness_score=0.9),
    )
    # Low-stemness cell
    cell_low = Cell(
        cell_type=HCellType.HSC,
        internal_state=InternalState(stemness_score=0.1),
    )

    diff_events_high = [
        rate for rate, ev in model.get_events(cell_high, pop)
        if isinstance(ev, type(ev)) and ev.__class__.__name__ == "DifferentiationEvent"
    ]
    diff_events_low = [
        rate for rate, ev in model.get_events(cell_low, pop)
        if isinstance(ev, type(ev)) and ev.__class__.__name__ == "DifferentiationEvent"
    ]

    assert sum(diff_events_low) > sum(diff_events_high)


def test_state_dependent_apo_rate_increases_with_stress():
    """A cell under stress should have a higher apoptosis rate."""
    config = yaml.safe_load(CONFIG_V02.read_text())
    model = HematopoiesisModel(config)
    pop = Population([Cell(cell_type=HCellType.HSC)])

    cell_low_stress  = Cell(cell_type=HCellType.HSC, internal_state=InternalState(stress_score=0.0))
    cell_high_stress = Cell(cell_type=HCellType.HSC, internal_state=InternalState(stress_score=2.0))

    from cell_diff_sim.engine.events import ApoptosisEvent
    apo_low  = [r for r, ev in model.get_events(cell_low_stress,  pop) if isinstance(ev, ApoptosisEvent)]
    apo_high = [r for r, ev in model.get_events(cell_high_stress, pop) if isinstance(ev, ApoptosisEvent)]

    assert sum(apo_high) > sum(apo_low)


# ===========================================================================
# Backward compatibility: v0.1 config still runs with v0.2 model
# ===========================================================================

def test_v01_config_runs_with_v02_model():
    """v0.1 YAML (no state_modulation) must run without errors."""
    config = yaml.safe_load(CONFIG_V01.read_text())
    model = HematopoiesisModel(config)
    pop = Population([Cell(cell_type=HCellType.HSC) for _ in range(5)])
    rec = Recorder()
    engine = CTMCEngine(model, pop, observers=[rec], rng_seed=0)
    engine.run(t_max=5.0)
    assert engine.time <= 5.0
    assert len(rec) > 0


def test_v01_config_same_results_as_before():
    """v0.1 config with v0.2 model must give same final composition
    as two identical seeds (deterministic, not comparing to v0.1 output)."""
    config = yaml.safe_load(CONFIG_V01.read_text())

    def run_once(seed: int) -> dict:
        m = HematopoiesisModel(config)
        pop = Population([Cell(cell_type=HCellType.HSC) for _ in range(10)])
        rec = Recorder()
        CTMCEngine(m, pop, observers=[rec], rng_seed=seed).run(t_max=10.0)
        return rec.snapshots[-1].counts

    assert run_once(42) == run_once(42)


# ===========================================================================
# Reproducibility: fixed seed still gives identical runs under v0.2
# ===========================================================================

def test_v02_same_seed_reproducible():
    config = yaml.safe_load(CONFIG_V02.read_text())

    def run_once(seed: int) -> list:
        m = HematopoiesisModel(config)
        pop = Population([Cell(cell_type=HCellType.HSC) for _ in range(5)])
        rec = Recorder()
        CTMCEngine(m, pop, observers=[rec], rng_seed=seed).run(t_max=10.0)
        return [s.counts for s in rec.snapshots]

    assert run_once(7) == run_once(7)
