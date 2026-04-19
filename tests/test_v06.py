"""Tests for v0.6: richer asymmetric inheritance (stemness + stress).

v0.6 extends both AsymmetricInheritanceRules and CentrioleInheritanceRules
so that stress_score is partitioned asymmetrically at division, not only
stemness_score.

Direction convention under test:
  daughter_index = 0  →  higher stemness, LOWER stress
  daughter_index = 1  →  lower stemness,  HIGHER stress

Stress bounds convention under test:
  - stress_score is lower-bounded at 0.0 (no negative stress).
  - There is no upper cap: daughter 1 stress can grow without bound.
  - Only daughter 0 requires clamping: max(0.0, parent.stress - delta).

Backward compatibility under test:
  - stress_asymmetry=0.0 (AsymmetricInheritanceRules default) produces
    identical output to v0.3/v0.4/v0.5.
  - centriole_stress_factor=0.0 (CentrioleInheritanceRules default) produces
    identical output to v0.4/v0.5.
  - All v0.1–v0.5 YAML configs parse without error under the v0.6 model.

Covers (16 tests):
  AsymmetricInheritanceRules — stress extension unit tests (5):
    - stress_asymmetry=0.0 → symmetric stress (backward compat)
    - daughter 0 gets lower stress by exactly delta
    - daughter 1 gets higher stress by exactly delta
    - daughter 0 stress clamped at 0.0 (no negative stress)
    - stemness and stress shift simultaneously in one inherit() call

  CentrioleInheritanceRules — stress extension unit tests (5):
    - centriole_stress_factor=0.0 → symmetric stress (backward compat)
    - daughter 0 (old centriole) gets lower stress
    - daughter 1 (new centriole) gets higher stress
    - stress delta scales linearly with centriole age up to cap
    - stress delta plateaus at centriole_age_cap (bounded increment)

  Validation (2):
    - negative stress_asymmetry raises ValueError
    - negative centriole_stress_factor raises ValueError

  Config parsing (3):
    - v0.6 YAML with centriole_stress_factor parses correctly
    - v0.5 YAML (no stress params) defaults to 0.0 under v0.6 model
    - negative centriole_stress_factor in YAML raises ValueError

  Integration / causal chain (1):
    - higher-stress daughter has higher effective apoptosis rate
"""

from pathlib import Path

import pytest
import yaml

from cell_diff_sim.cell import Cell
from cell_diff_sim.centriole_state import CentrioleState
from cell_diff_sim.engine.events import ApoptosisEvent, DivisionEvent
from cell_diff_sim.internal_state import InternalState
from cell_diff_sim.models.hematopoiesis import HCellType, HematopoiesisModel
from cell_diff_sim.models.inheritance import (
    AsymmetricInheritanceRules,
    CentrioleInheritanceRules,
)
from cell_diff_sim.population import Population

ROOT = Path(__file__).parent.parent
CONFIG_V05 = ROOT / "configs" / "hematopoiesis_v05.yaml"
CONFIG_V06 = ROOT / "configs" / "hematopoiesis_v06.yaml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ev() -> DivisionEvent:
    return DivisionEvent(daughter_cell_types=(HCellType.HSC, HCellType.HSC))


def _parent(
    stemness: float = 0.5,
    stress: float = 0.3,
    div: int = 2,
    centriole_age: int = 0,
) -> Cell:
    return Cell(
        cell_type=HCellType.HSC,
        internal_state=InternalState(
            stemness_score=stemness,
            stress_score=stress,
            division_count=div,
        ),
        centriole_state=CentrioleState(age=centriole_age),
    )


# ===========================================================================
# AsymmetricInheritanceRules — stress extension (v0.6)
# ===========================================================================

def test_asymmetric_stress_zero_is_symmetric():
    """stress_asymmetry=0.0 (default) → both daughters inherit parent stress unchanged.

    Backward compatibility: identical to v0.3/v0.4/v0.5 behaviour.
    """
    rules = AsymmetricInheritanceRules(stemness_asymmetry=0.1, stress_asymmetry=0.0)
    parent = _parent(stress=0.4)
    ds0 = rules.inherit(parent, 0, _ev())
    ds1 = rules.inherit(parent, 1, _ev())
    assert ds0.internal_state.stress_score == pytest.approx(0.4)
    assert ds1.internal_state.stress_score == pytest.approx(0.4)


def test_asymmetric_daughter0_gets_lower_stress():
    """Daughter 0 stress = parent.stress - stress_asymmetry."""
    rules = AsymmetricInheritanceRules(stemness_asymmetry=0.1, stress_asymmetry=0.05)
    parent = _parent(stress=0.3)
    ds0 = rules.inherit(parent, 0, _ev())
    assert ds0.internal_state.stress_score == pytest.approx(0.3 - 0.05)


def test_asymmetric_daughter1_gets_higher_stress():
    """Daughter 1 stress = parent.stress + stress_asymmetry (no upper cap)."""
    rules = AsymmetricInheritanceRules(stemness_asymmetry=0.1, stress_asymmetry=0.05)
    parent = _parent(stress=0.3)
    ds1 = rules.inherit(parent, 1, _ev())
    assert ds1.internal_state.stress_score == pytest.approx(0.3 + 0.05)


def test_asymmetric_stress_clamped_at_zero():
    """Daughter 0 stress is clamped at 0.0 — stress cannot be negative."""
    rules = AsymmetricInheritanceRules(stemness_asymmetry=0.1, stress_asymmetry=0.5)
    parent = _parent(stress=0.1)  # 0.1 - 0.5 would be -0.4 without clamping
    ds0 = rules.inherit(parent, 0, _ev())
    assert ds0.internal_state.stress_score == pytest.approx(0.0)


def test_asymmetric_stemness_and_stress_shift_simultaneously():
    """A single inherit() call shifts both stemness and stress in the correct directions."""
    rules = AsymmetricInheritanceRules(stemness_asymmetry=0.1, stress_asymmetry=0.05)
    parent = _parent(stemness=0.5, stress=0.3)

    ds0 = rules.inherit(parent, 0, _ev())
    ds1 = rules.inherit(parent, 1, _ev())

    # Daughter 0: higher stemness, lower stress
    assert ds0.internal_state.stemness_score == pytest.approx(0.5 + 0.1)
    assert ds0.internal_state.stress_score   == pytest.approx(0.3 - 0.05)

    # Daughter 1: lower stemness, higher stress
    assert ds1.internal_state.stemness_score == pytest.approx(0.5 - 0.1)
    assert ds1.internal_state.stress_score   == pytest.approx(0.3 + 0.05)


# ===========================================================================
# CentrioleInheritanceRules — stress extension (v0.6)
# ===========================================================================

def test_centriole_stress_factor_zero_is_symmetric():
    """centriole_stress_factor=0.0 (default) → both daughters inherit parent stress unchanged.

    Backward compatibility: identical to v0.4/v0.5 behaviour.
    """
    rules = CentrioleInheritanceRules(
        centriole_stemness_factor=0.05,
        centriole_stress_factor=0.0,
        centriole_age_cap=10,
    )
    parent = _parent(stress=0.4, centriole_age=5)
    ds0 = rules.inherit(parent, 0, _ev())
    ds1 = rules.inherit(parent, 1, _ev())
    assert ds0.internal_state.stress_score == pytest.approx(0.4)
    assert ds1.internal_state.stress_score == pytest.approx(0.4)


def test_centriole_daughter0_gets_lower_stress():
    """Daughter 0 (old centriole) receives parent.stress - stress_delta."""
    rules = CentrioleInheritanceRules(
        centriole_stemness_factor=0.05,
        centriole_stress_factor=0.1,
        centriole_age_cap=10,
    )
    parent = _parent(stress=0.5, centriole_age=3)
    # stress_delta = 0.1 * min(3, 10) = 0.3
    ds0 = rules.inherit(parent, 0, _ev())
    assert ds0.internal_state.stress_score == pytest.approx(0.5 - 0.1 * 3)


def test_centriole_daughter1_gets_higher_stress():
    """Daughter 1 (new centriole) receives parent.stress + stress_delta (no upper cap)."""
    rules = CentrioleInheritanceRules(
        centriole_stemness_factor=0.05,
        centriole_stress_factor=0.1,
        centriole_age_cap=10,
    )
    parent = _parent(stress=0.5, centriole_age=3)
    # stress_delta = 0.1 * min(3, 10) = 0.3
    ds1 = rules.inherit(parent, 1, _ev())
    assert ds1.internal_state.stress_score == pytest.approx(0.5 + 0.1 * 3)


def test_centriole_stress_delta_scales_linearly_with_age():
    """stress_delta = centriole_stress_factor * centriole_age, linearly up to cap."""
    factor = 0.1
    rules = CentrioleInheritanceRules(
        centriole_stemness_factor=0.0,
        centriole_stress_factor=factor,
        centriole_age_cap=10,
    )
    for age in (1, 3, 5, 9):
        parent = _parent(stress=1.0, centriole_age=age)
        ds0 = rules.inherit(parent, 0, _ev())
        ds1 = rules.inherit(parent, 1, _ev())
        expected_delta = factor * age
        assert ds0.internal_state.stress_score == pytest.approx(1.0 - expected_delta)
        assert ds1.internal_state.stress_score == pytest.approx(1.0 + expected_delta)


def test_centriole_stress_delta_is_capped():
    """stress_delta plateaus at centriole_age_cap — per-division increment is bounded."""
    cap    = 5
    factor = 0.1
    rules = CentrioleInheritanceRules(
        centriole_stemness_factor=0.0,
        centriole_stress_factor=factor,
        centriole_age_cap=cap,
    )
    parent_at_cap    = _parent(stress=1.0, centriole_age=cap)
    parent_above_cap = _parent(stress=1.0, centriole_age=cap + 3)

    ds_at_cap    = rules.inherit(parent_at_cap,    1, _ev())
    ds_above_cap = rules.inherit(parent_above_cap, 1, _ev())

    # Both should produce the same stress delta (plateau at cap)
    assert ds_at_cap.internal_state.stress_score == pytest.approx(
        ds_above_cap.internal_state.stress_score
    )
    # And the delta should equal factor * cap
    assert ds_at_cap.internal_state.stress_score == pytest.approx(1.0 + factor * cap)


# ===========================================================================
# Validation
# ===========================================================================

def test_negative_stress_asymmetry_raises():
    """stress_asymmetry < 0 must raise ValueError."""
    with pytest.raises(ValueError, match="stress_asymmetry"):
        AsymmetricInheritanceRules(stemness_asymmetry=0.1, stress_asymmetry=-0.05)


def test_negative_centriole_stress_factor_raises():
    """centriole_stress_factor < 0 must raise ValueError."""
    with pytest.raises(ValueError, match="centriole_stress_factor"):
        CentrioleInheritanceRules(
            centriole_stemness_factor=0.05,
            centriole_stress_factor=-0.01,
            centriole_age_cap=10,
        )


# ===========================================================================
# Config parsing
# ===========================================================================

def test_v06_config_parses_centriole_stress_factor():
    """v0.6 YAML with centriole_stress_factor must reach CentrioleInheritanceRules correctly.

    Verified by calling inherit() and checking the stress split.
    """
    config = yaml.safe_load(CONFIG_V06.read_text())
    model = HematopoiesisModel(config)

    rules = model.inheritance_rules
    assert isinstance(rules, CentrioleInheritanceRules)

    # Confirm the stress factor is non-zero (v0.6 config sets it to 0.02)
    parent = _parent(stress=0.4, centriole_age=5)
    ds0 = rules.inherit(parent, 0, _ev())
    ds1 = rules.inherit(parent, 1, _ev())

    # Daughter 0 must have lower stress than parent (factor=0.02, age=5 → delta=0.1)
    assert ds0.internal_state.stress_score < parent.internal_state.stress_score
    # Daughter 1 must have higher stress than parent
    assert ds1.internal_state.stress_score > parent.internal_state.stress_score


def test_v05_config_absent_stress_params_default_to_zero():
    """v0.5 YAML (no centriole_stress_factor) parses under v0.6 model; stress symmetric.

    Verifies exact backward compatibility: missing key → 0.0 → no stress asymmetry.
    """
    config = yaml.safe_load(CONFIG_V05.read_text())
    model = HematopoiesisModel(config)

    rules = model.inheritance_rules
    assert isinstance(rules, CentrioleInheritanceRules)

    parent = _parent(stress=0.4, centriole_age=5)
    ds0 = rules.inherit(parent, 0, _ev())
    ds1 = rules.inherit(parent, 1, _ev())

    # Both daughters must receive the exact parent stress (no asymmetry)
    assert ds0.internal_state.stress_score == pytest.approx(parent.internal_state.stress_score)
    assert ds1.internal_state.stress_score == pytest.approx(parent.internal_state.stress_score)


def test_negative_centriole_stress_factor_in_config_raises():
    """Negative centriole_stress_factor in YAML must propagate as ValueError at parse time."""
    config = {
        "inheritance": {
            "mode": "centriole",
            "centriole_stemness_factor": 0.05,
            "centriole_stress_factor": -0.01,
            "centriole_age_cap": 10,
        }
    }
    with pytest.raises(ValueError, match="centriole_stress_factor"):
        HematopoiesisModel(config)


# ===========================================================================
# Integration / causal chain
# ===========================================================================

def test_v06_higher_stress_daughter_has_higher_apoptosis_rate():
    """After division, the higher-stress daughter has a higher effective apoptosis rate.

    Simulates the causal chain:
      centriole_stress_factor > 0
      → daughter 1 (new centriole) inherits parent.stress + stress_delta
      → RateModulator maps higher stress_score to higher apoptosis factor
      → effective apoptosis rate is higher for the high-stress daughter

    Tested deterministically via get_events(), no engine run needed.
    """
    config = yaml.safe_load(CONFIG_V06.read_text())
    model = HematopoiesisModel(config)

    # Parent with meaningful centriole age so stress_delta > 0
    parent = _parent(stemness=0.5, stress=0.3, centriole_age=5)
    pop = Population([parent])

    rules = model.inheritance_rules
    ds0 = rules.inherit(parent, 0, _ev())  # lower stress daughter
    ds1 = rules.inherit(parent, 1, _ev())  # higher stress daughter

    # Confirm stress ordering is as expected
    assert ds0.internal_state.stress_score < ds1.internal_state.stress_score

    cell_low_stress = Cell(
        cell_type=HCellType.HSC,
        internal_state=ds0.internal_state,
    )
    cell_high_stress = Cell(
        cell_type=HCellType.HSC,
        internal_state=ds1.internal_state,
    )

    apo_low  = [r for r, ev in model.get_events(cell_low_stress,  pop) if isinstance(ev, ApoptosisEvent)]
    apo_high = [r for r, ev in model.get_events(cell_high_stress, pop) if isinstance(ev, ApoptosisEvent)]

    assert sum(apo_high) > sum(apo_low), (
        "high-stress daughter (daughter 1) should have higher effective apoptosis rate"
    )
