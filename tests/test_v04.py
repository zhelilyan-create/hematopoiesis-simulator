"""Tests for v0.4: CentrioleState, CentrioleInheritanceRules, and config parsing.

Covers (19 tests):
  CentrioleState validation (2):
    - default age = 0
    - negative age raises ValueError

  CentrioleInheritanceRules unit tests (9):
    - daughter 0 inherits old centriole (age + 1)
    - daughter 1 inherits new centriole (age = 0)
    - daughter 0 stemness increases by delta
    - daughter 1 stemness decreases by delta
    - first division (parent age = 0) is stemness-symmetric
    - daughter 0 stemness clamped at 1.0
    - daughter 1 stemness clamped at 0.0
    - stress_score copied unchanged to both daughters
    - division_count incremented by 1 in both daughters

  Validation (2):
    - centriole_stemness_factor < 0 raises ValueError
    - centriole_age_cap = 0 raises ValueError

  Config parsing (3):
    - mode: centriole -> CentrioleInheritanceRules instantiated
    - absent params -> CentrioleInheritanceRules created with defaults (no error)
    - centriole_age_cap = 0 in config raises ValueError

  Age-cap capping (1):
    - delta plateaus once centriole age exceeds the cap

  Integration (2):
    - v0.4 config produces reproducible results with fixed seed
    - v0.3 config still runs correctly with v0.4 model
"""

from pathlib import Path

import pytest
import yaml

from cell_diff_sim.cell import Cell
from cell_diff_sim.centriole_state import CentrioleState
from cell_diff_sim.engine.ctmc import CTMCEngine
from cell_diff_sim.engine.events import DivisionEvent
from cell_diff_sim.internal_state import InternalState
from cell_diff_sim.models.hematopoiesis import HCellType, HematopoiesisModel
from cell_diff_sim.models.inheritance import (
    AsymmetricInheritanceRules,
    CentrioleInheritanceRules,
)
from cell_diff_sim.observers.recorder import Recorder
from cell_diff_sim.population import Population

ROOT = Path(__file__).parent.parent
CONFIG_V03 = ROOT / "configs" / "hematopoiesis_v03.yaml"
CONFIG_V04 = ROOT / "configs" / "hematopoiesis_v04.yaml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parent_with_centriole_age(
    centriole_age: int,
    stemness: float = 0.5,
    stress: float = 0.2,
    div: int = 3,
) -> Cell:
    """Create a parent cell with the given centriole age and internal state."""
    return Cell(
        cell_type=HCellType.HSC,
        internal_state=InternalState(
            stemness_score=stemness,
            stress_score=stress,
            division_count=div,
        ),
        centriole_state=CentrioleState(age=centriole_age),
    )


def _ev() -> DivisionEvent:
    return DivisionEvent(daughter_cell_types=(HCellType.HSC, HCellType.HSC))


# ===========================================================================
# CentrioleState: construction and validation
# ===========================================================================

def test_centriole_state_defaults():
    """Default CentrioleState has age = 0."""
    cs = CentrioleState()
    assert cs.age == 0


def test_centriole_state_negative_age_raises():
    """Negative centriole age must be rejected."""
    with pytest.raises(ValueError, match="age"):
        CentrioleState(age=-1)


# ===========================================================================
# CentrioleInheritanceRules — unit tests
# ===========================================================================

def test_centriole_daughter0_gets_old_centriole():
    """Daughter 0 inherits the old centriole: age = parent.age + 1."""
    rules = CentrioleInheritanceRules(centriole_stemness_factor=0.1, centriole_age_cap=10)
    parent = _parent_with_centriole_age(3)
    ds = rules.inherit(parent, 0, _ev())
    assert ds.centriole_state.age == 4


def test_centriole_daughter1_gets_new_centriole():
    """Daughter 1 inherits the new centriole: age = 0."""
    rules = CentrioleInheritanceRules(centriole_stemness_factor=0.1, centriole_age_cap=10)
    parent = _parent_with_centriole_age(3)
    ds = rules.inherit(parent, 1, _ev())
    assert ds.centriole_state.age == 0


def test_centriole_daughter0_stemness_increases():
    """Daughter 0 gets stemness = parent.stemness + delta."""
    # parent age=2, factor=0.1 → delta = 0.1 * min(2, 10) = 0.2
    rules = CentrioleInheritanceRules(centriole_stemness_factor=0.1, centriole_age_cap=10)
    parent = _parent_with_centriole_age(2, stemness=0.5)
    ds = rules.inherit(parent, 0, _ev())
    assert ds.internal_state.stemness_score == pytest.approx(0.7)


def test_centriole_daughter1_stemness_decreases():
    """Daughter 1 gets stemness = parent.stemness - delta."""
    # parent age=2, factor=0.1 → delta = 0.2
    rules = CentrioleInheritanceRules(centriole_stemness_factor=0.1, centriole_age_cap=10)
    parent = _parent_with_centriole_age(2, stemness=0.5)
    ds = rules.inherit(parent, 1, _ev())
    assert ds.internal_state.stemness_score == pytest.approx(0.3)


def test_centriole_first_division_symmetric():
    """Parent centriole age=0 → delta=0 → both daughters get identical stemness.

    This is the intentional v0.4 founder assumption: first division of a founder
    cell is always stemness-symmetric because delta = factor * min(0, cap) = 0.
    """
    rules = CentrioleInheritanceRules(centriole_stemness_factor=0.1, centriole_age_cap=10)
    parent = _parent_with_centriole_age(0, stemness=0.5)
    ds0 = rules.inherit(parent, 0, _ev())
    ds1 = rules.inherit(parent, 1, _ev())
    assert ds0.internal_state.stemness_score == pytest.approx(
        ds1.internal_state.stemness_score
    )


def test_centriole_daughter0_stemness_clamped_at_one():
    """High parent stemness + large delta: daughter 0 must not exceed 1.0."""
    # parent age=5, factor=0.1 → delta = 0.5; 0.95 + 0.5 = 1.45 → clamped to 1.0
    rules = CentrioleInheritanceRules(centriole_stemness_factor=0.1, centriole_age_cap=10)
    parent = _parent_with_centriole_age(5, stemness=0.95)
    ds = rules.inherit(parent, 0, _ev())
    assert ds.internal_state.stemness_score == pytest.approx(1.0)


def test_centriole_daughter1_stemness_clamped_at_zero():
    """Low parent stemness + large delta: daughter 1 must not go below 0.0."""
    # parent age=5, factor=0.1 → delta = 0.5; 0.05 - 0.5 = -0.45 → clamped to 0.0
    rules = CentrioleInheritanceRules(centriole_stemness_factor=0.1, centriole_age_cap=10)
    parent = _parent_with_centriole_age(5, stemness=0.05)
    ds = rules.inherit(parent, 1, _ev())
    assert ds.internal_state.stemness_score == pytest.approx(0.0)


def test_centriole_stress_copied_unchanged():
    """stress_score is inherited symmetrically — both daughters get parent value."""
    rules = CentrioleInheritanceRules(centriole_stemness_factor=0.1, centriole_age_cap=10)
    parent = _parent_with_centriole_age(1, stress=0.4)
    ds0 = rules.inherit(parent, 0, _ev())
    ds1 = rules.inherit(parent, 1, _ev())
    assert ds0.internal_state.stress_score == pytest.approx(0.4)
    assert ds1.internal_state.stress_score == pytest.approx(0.4)


def test_centriole_division_count_incremented():
    """division_count is incremented by 1 in both daughters."""
    rules = CentrioleInheritanceRules(centriole_stemness_factor=0.0, centriole_age_cap=10)
    parent = _parent_with_centriole_age(0, div=5)
    ds0 = rules.inherit(parent, 0, _ev())
    ds1 = rules.inherit(parent, 1, _ev())
    assert ds0.internal_state.division_count == 6
    assert ds1.internal_state.division_count == 6


# ===========================================================================
# Validation
# ===========================================================================

def test_centriole_factor_negative_raises():
    """centriole_stemness_factor < 0 must raise ValueError."""
    with pytest.raises(ValueError, match="centriole_stemness_factor"):
        CentrioleInheritanceRules(centriole_stemness_factor=-0.01)


def test_centriole_age_cap_zero_raises():
    """centriole_age_cap = 0 must raise ValueError (would silently disable effect)."""
    with pytest.raises(ValueError, match="centriole_age_cap"):
        CentrioleInheritanceRules(centriole_age_cap=0)


# ===========================================================================
# Config parsing
# ===========================================================================

def test_config_mode_centriole_instantiates_correct_rules():
    """mode: centriole in config must create CentrioleInheritanceRules."""
    config = {
        "inheritance": {
            "mode": "centriole",
            "centriole_stemness_factor": 0.05,
            "centriole_age_cap": 10,
        }
    }
    model = HematopoiesisModel(config)
    assert isinstance(model.inheritance_rules, CentrioleInheritanceRules)


def test_config_centriole_absent_params_use_defaults():
    """mode: centriole with no factor/cap must not raise — defaults are used."""
    config = {"inheritance": {"mode": "centriole"}}
    model = HematopoiesisModel(config)
    assert isinstance(model.inheritance_rules, CentrioleInheritanceRules)


def test_config_centriole_age_cap_zero_raises():
    """centriole_age_cap: 0 in config must propagate as ValueError."""
    config = {"inheritance": {"mode": "centriole", "centriole_age_cap": 0}}
    with pytest.raises(ValueError, match="centriole_age_cap"):
        HematopoiesisModel(config)


# ===========================================================================
# Age-cap capping: delta plateaus once centriole age exceeds the cap
# ===========================================================================

def test_centriole_age_cap_limits_delta():
    """Delta must not grow beyond factor * cap even for very old centrioles."""
    rules = CentrioleInheritanceRules(centriole_stemness_factor=0.1, centriole_age_cap=3)
    # At the cap: delta = 0.1 * min(3, 3) = 0.3
    parent_at_cap    = _parent_with_centriole_age(3,  stemness=0.5)
    # Above the cap: delta = 0.1 * min(10, 3) = 0.3 (same)
    parent_above_cap = _parent_with_centriole_age(10, stemness=0.5)
    ds_at_cap    = rules.inherit(parent_at_cap,    0, _ev())
    ds_above_cap = rules.inherit(parent_above_cap, 0, _ev())
    assert ds_at_cap.internal_state.stemness_score == pytest.approx(
        ds_above_cap.internal_state.stemness_score
    )


# ===========================================================================
# Integration
# ===========================================================================

def test_v04_config_reproducible_with_fixed_seed():
    """Fixed seed must produce identical runs under v0.4 config."""
    config = yaml.safe_load(CONFIG_V04.read_text())

    def run_once(seed: int) -> list:
        m = HematopoiesisModel(config)
        pop = Population([Cell(cell_type=HCellType.HSC) for _ in range(5)])
        rec = Recorder()
        CTMCEngine(m, pop, observers=[rec], rng_seed=seed).run(t_max=10.0)
        return [s.counts for s in rec.snapshots]

    assert run_once(21) == run_once(21)


def test_v03_config_still_runs_with_v04_model():
    """v0.3 config (mode: asymmetric) must still run correctly under v0.4 model."""
    config = yaml.safe_load(CONFIG_V03.read_text())
    model = HematopoiesisModel(config)
    assert isinstance(model.inheritance_rules, AsymmetricInheritanceRules)

    pop = Population([Cell(cell_type=HCellType.HSC) for _ in range(5)])
    rec = Recorder()
    engine = CTMCEngine(model, pop, observers=[rec], rng_seed=0)
    engine.run(t_max=5.0)
    assert engine.time <= 5.0
    assert len(rec) > 0
