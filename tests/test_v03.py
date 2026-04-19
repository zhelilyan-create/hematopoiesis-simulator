"""Tests for v0.3: AsymmetricInheritanceRules and inheritance config parsing.

Covers (15 tests):
  AsymmetricInheritanceRules unit tests (6):
    - daughter 0 gets stemness + delta
    - daughter 1 gets stemness - delta
    - high parent stemness: daughter 0 clamped to 1.0
    - low parent stemness:  daughter 1 clamped to 0.0
    - stress_score copied unchanged to both daughters
    - division_count incremented by 1 in both daughters

  Validation (1):
    - stemness_asymmetry < 0 raises ValueError

  Config parsing (4):
    - mode: asymmetric  -> AsymmetricInheritanceRules instantiated
    - mode: symmetric   -> SymmetricInheritanceRules instantiated
    - inheritance section absent -> SymmetricInheritanceRules (backward compat)
    - unknown mode      -> ValueError

  Edge/debug case (1):
    - stemness_asymmetry = 0.0 produces numerically symmetric daughters

  Behavioural / integration (3):
    - after many divisions, stemness values diverge (mechanism propagates)
    - fixed seed produces identical results under v0.3 config
    - v0.2 config still runs correctly (backward compatibility)
"""

from pathlib import Path

import pytest
import yaml

from cell_diff_sim.cell import Cell
from cell_diff_sim.engine.ctmc import CTMCEngine
from cell_diff_sim.engine.events import DivisionEvent
from cell_diff_sim.internal_state import InternalState
from cell_diff_sim.models.hematopoiesis import HCellType, HematopoiesisModel
from cell_diff_sim.models.inheritance import (
    AsymmetricInheritanceRules,
    SymmetricInheritanceRules,
)
from cell_diff_sim.observers.recorder import Recorder
from cell_diff_sim.population import Population

ROOT = Path(__file__).parent.parent
CONFIG_V02 = ROOT / "configs" / "hematopoiesis_v02.yaml"
CONFIG_V03 = ROOT / "configs" / "hematopoiesis_v03.yaml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parent(stemness: float = 0.5, stress: float = 0.2, div: int = 3) -> Cell:
    return Cell(
        cell_type=HCellType.HSC,
        internal_state=InternalState(
            stemness_score=stemness,
            stress_score=stress,
            division_count=div,
        ),
    )


def _ev() -> DivisionEvent:
    return DivisionEvent(daughter_cell_types=(HCellType.HSC, HCellType.HSC))


# ===========================================================================
# AsymmetricInheritanceRules — unit tests
# ===========================================================================

def test_asymmetric_daughter0_gets_stemness_plus_delta():
    """Daughter 0: stemness = parent.stemness + delta (no clamping needed)."""
    rules = AsymmetricInheritanceRules(stemness_asymmetry=0.1)
    parent = _parent(stemness=0.5)
    d0 = rules.inherit(parent, 0, _ev())
    assert d0.internal_state.stemness_score == pytest.approx(0.6)


def test_asymmetric_daughter1_gets_stemness_minus_delta():
    """Daughter 1: stemness = parent.stemness - delta (no clamping needed)."""
    rules = AsymmetricInheritanceRules(stemness_asymmetry=0.1)
    parent = _parent(stemness=0.5)
    d1 = rules.inherit(parent, 1, _ev())
    assert d1.internal_state.stemness_score == pytest.approx(0.4)


def test_asymmetric_daughter0_clamped_at_one():
    """High parent stemness: daughter 0 must not exceed 1.0."""
    rules = AsymmetricInheritanceRules(stemness_asymmetry=0.1)
    parent = _parent(stemness=0.95)
    d0 = rules.inherit(parent, 0, _ev())
    assert d0.internal_state.stemness_score == pytest.approx(1.0)


def test_asymmetric_daughter1_clamped_at_zero():
    """Low parent stemness: daughter 1 must not go below 0.0."""
    rules = AsymmetricInheritanceRules(stemness_asymmetry=0.1)
    parent = _parent(stemness=0.05)
    d1 = rules.inherit(parent, 1, _ev())
    assert d1.internal_state.stemness_score == pytest.approx(0.0)


def test_asymmetric_stress_copied_unchanged():
    """stress_score is inherited symmetrically — both daughters get parent value."""
    rules = AsymmetricInheritanceRules(stemness_asymmetry=0.1)
    parent = _parent(stress=0.3)
    d0 = rules.inherit(parent, 0, _ev())
    d1 = rules.inherit(parent, 1, _ev())
    assert d0.internal_state.stress_score == pytest.approx(0.3)
    assert d1.internal_state.stress_score == pytest.approx(0.3)


def test_asymmetric_division_count_incremented():
    """division_count increments by 1 in both daughters."""
    rules = AsymmetricInheritanceRules(stemness_asymmetry=0.1)
    parent = _parent(div=7)
    d0 = rules.inherit(parent, 0, _ev())
    d1 = rules.inherit(parent, 1, _ev())
    assert d0.internal_state.division_count == 8
    assert d1.internal_state.division_count == 8


# ===========================================================================
# Validation
# ===========================================================================

def test_negative_stemness_asymmetry_raises():
    with pytest.raises(ValueError, match="stemness_asymmetry"):
        AsymmetricInheritanceRules(stemness_asymmetry=-0.01)


# ===========================================================================
# Config parsing
# ===========================================================================

def test_config_mode_asymmetric_instantiates_correct_rules():
    config = {"inheritance": {"mode": "asymmetric", "stemness_asymmetry": 0.1}}
    model = HematopoiesisModel(config)
    assert isinstance(model.inheritance_rules, AsymmetricInheritanceRules)


def test_config_mode_symmetric_instantiates_correct_rules():
    config = {"inheritance": {"mode": "symmetric"}}
    model = HematopoiesisModel(config)
    assert isinstance(model.inheritance_rules, SymmetricInheritanceRules)


def test_config_no_inheritance_section_defaults_to_symmetric():
    """Absent inheritance section -> SymmetricInheritanceRules (v0.2 compat)."""
    model = HematopoiesisModel({})
    assert isinstance(model.inheritance_rules, SymmetricInheritanceRules)


def test_config_unknown_mode_raises():
    config = {"inheritance": {"mode": "random"}}
    with pytest.raises(ValueError, match="Unknown inheritance mode"):
        HematopoiesisModel(config)


# ===========================================================================
# Edge / debug case: stemness_asymmetry = 0.0
# ===========================================================================

def test_zero_asymmetry_produces_symmetric_daughters():
    """stemness_asymmetry=0.0 is legal; daughters have identical stemness."""
    rules = AsymmetricInheritanceRules(stemness_asymmetry=0.0)
    parent = _parent(stemness=0.6)
    d0 = rules.inherit(parent, 0, _ev())
    d1 = rules.inherit(parent, 1, _ev())
    assert d0.internal_state.stemness_score == pytest.approx(0.6)
    assert d1.internal_state.stemness_score == pytest.approx(0.6)


# ===========================================================================
# Behavioural / integration
# ===========================================================================

def test_stemness_diverges_under_repeated_asymmetric_division():
    """After many asymmetric divisions the population must contain cells
    with stemness higher AND lower than the founder's stemness.

    Strategy: simulate long enough that multiple divisions occur, then
    confirm the stemness range in the final population is wider than zero.
    We don't assert exact values — just that the mechanism propagates.
    """
    config = yaml.safe_load(CONFIG_V03.read_text())
    model = HematopoiesisModel(config)
    # Use a single founder at neutral stemness so divergence is symmetric
    founder = Cell(
        cell_type=HCellType.HSC,
        internal_state=InternalState(stemness_score=0.5),
    )
    pop = Population([founder])
    rec = Recorder()
    engine = CTMCEngine(model, pop, observers=[rec], rng_seed=0)
    engine.run(t_max=50.0)

    stemness_values = [c.internal_state.stemness_score for c in pop]
    assert len(stemness_values) > 1, "population went extinct — increase t_max or n"
    assert max(stemness_values) > 0.5, "no high-stemness lineage found"
    assert min(stemness_values) < 0.5, "no low-stemness lineage found"


def test_v03_config_reproducible_with_fixed_seed():
    """Fixed seed must produce identical runs under v0.3 config."""
    config = yaml.safe_load(CONFIG_V03.read_text())

    def run_once(seed: int) -> list:
        m = HematopoiesisModel(config)
        pop = Population([Cell(cell_type=HCellType.HSC) for _ in range(5)])
        rec = Recorder()
        CTMCEngine(m, pop, observers=[rec], rng_seed=seed).run(t_max=10.0)
        return [s.counts for s in rec.snapshots]

    assert run_once(13) == run_once(13)


def test_v02_config_still_runs_with_v03_model():
    """v0.2 config (no inheritance section) must run without errors."""
    config = yaml.safe_load(CONFIG_V02.read_text())
    model = HematopoiesisModel(config)
    assert isinstance(model.inheritance_rules, SymmetricInheritanceRules)

    pop = Population([Cell(cell_type=HCellType.HSC) for _ in range(5)])
    rec = Recorder()
    engine = CTMCEngine(model, pop, observers=[rec], rng_seed=0)
    engine.run(t_max=5.0)
    assert engine.time <= 5.0
    assert len(rec) > 0
