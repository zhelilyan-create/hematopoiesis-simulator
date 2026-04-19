"""Tests for v0.5: StateEvolutionParams, StateEvolutionRules, and PDMP integration.

v0.5 converts the simulator from a pure CTMC to a PDMP (piecewise-deterministic
Markov process).  Between stochastic events, each cell's InternalState drifts
deterministically.  The Gillespie algorithm is unchanged; one hook is added.

Time-ordering assumption under test:
  1. Propensities sampled from pre-drift state.
  2. dt sampled.
  3. All cells evolved by dt (evolve_cell_states).
  4. Selected event applied to post-drift state.

Covers (15 tests):
  StateEvolutionRules unit tests (7):
    - zero rates produce no change
    - stress accumulates at correct rate
    - stemness drifts downward (negative rate)
    - stemness drifts upward (positive rate)
    - stemness ceiling clamped at 1.0
    - stemness floor clamped at 0.0
    - division_count not affected by evolution

  StateEvolutionParams validation (1):
    - negative stress_accumulation_rate raises ValueError

  Config parsing (3):
    - state_evolution section present -> StateEvolutionRules with correct params
    - state_evolution section absent  -> is_noop == True (no drift)
    - negative stress rate in config  -> ValueError propagated

  Engine / integration (3):
    - stress increases during a simulation with non-zero accumulation rate
    - v0.5 config produces reproducible results with fixed seed
    - v0.4 config still runs correctly with v0.5 model (backward compat)

  Causal chain (1):
    - accumulated stress raises effective apoptosis rate (via RateModulator)
"""

from pathlib import Path

import pytest
import yaml

from cell_diff_sim.cell import Cell
from cell_diff_sim.engine.ctmc import CTMCEngine
from cell_diff_sim.internal_state import InternalState
from cell_diff_sim.models.hematopoiesis import HCellType, HematopoiesisModel
from cell_diff_sim.models.state_evolution import StateEvolutionParams, StateEvolutionRules
from cell_diff_sim.observers.recorder import Recorder
from cell_diff_sim.population import Population

ROOT = Path(__file__).parent.parent
CONFIG_V04 = ROOT / "configs" / "hematopoiesis_v04.yaml"
CONFIG_V05 = ROOT / "configs" / "hematopoiesis_v05.yaml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _state(stemness: float = 0.5, stress: float = 0.0, div: int = 0) -> InternalState:
    return InternalState(stemness_score=stemness, stress_score=stress, division_count=div)


def _rules(stress_rate: float = 0.0, stemness_rate: float = 0.0) -> StateEvolutionRules:
    return StateEvolutionRules(
        StateEvolutionParams(
            stress_accumulation_rate=stress_rate,
            stemness_drift_rate=stemness_rate,
        )
    )


# ===========================================================================
# StateEvolutionRules — unit tests
# ===========================================================================

def test_zero_rates_produce_no_change():
    """Both rates = 0 → evolve() returns state numerically equal to input."""
    rules = _rules(stress_rate=0.0, stemness_rate=0.0)
    s = _state(stemness=0.6, stress=0.2, div=3)
    result = rules.evolve(s, dt=10.0)
    assert result.stemness_score  == pytest.approx(0.6)
    assert result.stress_score    == pytest.approx(0.2)
    assert result.division_count  == 3


def test_stress_accumulates_at_correct_rate():
    """stress_score increases by stress_accumulation_rate × dt."""
    rules = _rules(stress_rate=0.05)
    s = _state(stress=0.0)
    result = rules.evolve(s, dt=4.0)
    assert result.stress_score == pytest.approx(0.05 * 4.0)  # = 0.2


def test_stemness_drifts_downward():
    """Negative stemness_drift_rate decreases stemness_score by |rate| × dt."""
    rules = _rules(stemness_rate=-0.02)
    s = _state(stemness=0.6)
    result = rules.evolve(s, dt=5.0)
    assert result.stemness_score == pytest.approx(0.6 - 0.02 * 5.0)  # = 0.5


def test_stemness_drifts_upward():
    """Positive stemness_drift_rate increases stemness_score by rate × dt."""
    rules = _rules(stemness_rate=0.03)
    s = _state(stemness=0.4)
    result = rules.evolve(s, dt=3.0)
    assert result.stemness_score == pytest.approx(0.4 + 0.03 * 3.0)  # = 0.49


def test_stemness_ceiling_clamped_at_one():
    """Upward drift cannot push stemness_score above 1.0."""
    rules = _rules(stemness_rate=0.1)
    s = _state(stemness=0.95)
    result = rules.evolve(s, dt=10.0)
    assert result.stemness_score == pytest.approx(1.0)


def test_stemness_floor_clamped_at_zero():
    """Downward drift cannot push stemness_score below 0.0."""
    rules = _rules(stemness_rate=-0.1)
    s = _state(stemness=0.05)
    result = rules.evolve(s, dt=10.0)
    assert result.stemness_score == pytest.approx(0.0)


def test_division_count_not_affected_by_evolution():
    """evolve() never changes division_count — that is a division-time update."""
    rules = _rules(stress_rate=0.1, stemness_rate=-0.01)
    s = _state(div=7)
    result = rules.evolve(s, dt=100.0)
    assert result.division_count == 7


# ===========================================================================
# StateEvolutionParams validation
# ===========================================================================

def test_negative_stress_accumulation_rate_raises():
    """stress_accumulation_rate < 0 must raise ValueError."""
    with pytest.raises(ValueError, match="stress_accumulation_rate"):
        StateEvolutionParams(stress_accumulation_rate=-0.01)


# ===========================================================================
# Config parsing
# ===========================================================================

def test_state_evolution_section_parsed():
    """Non-zero params in YAML must reach StateEvolutionRules correctly."""
    config = {
        "state_evolution": {
            "stress_accumulation_rate": 0.05,
            "stemness_drift_rate": -0.002,
        }
    }
    model = HematopoiesisModel(config)
    assert not model.evolution_rules.is_noop
    # Verify the rates were absorbed by evolving a known state
    s = _state(stemness=0.5, stress=0.0)
    result = model.evolution_rules.evolve(s, dt=2.0)
    assert result.stress_score   == pytest.approx(0.05 * 2.0)
    assert result.stemness_score == pytest.approx(0.5 + (-0.002) * 2.0)


def test_state_evolution_absent_is_noop():
    """Missing state_evolution section → is_noop == True (no drift)."""
    model = HematopoiesisModel({})
    assert model.evolution_rules.is_noop


def test_negative_stress_rate_in_config_raises():
    """Negative stress_accumulation_rate in config must propagate as ValueError."""
    config = {"state_evolution": {"stress_accumulation_rate": -0.1}}
    with pytest.raises(ValueError, match="stress_accumulation_rate"):
        HematopoiesisModel(config)


# ===========================================================================
# Engine / integration
# ===========================================================================

def test_stress_increases_during_simulation():
    """After running with stress_accumulation_rate > 0, at least one cell
    must have accumulated non-zero stress.

    Uses a long run so that multiple Gillespie steps occur and stress
    has time to build up.  The exact amount is stochastic, but any
    surviving cell must have stress > 0.
    """
    config = yaml.safe_load(CONFIG_V05.read_text())
    model = HematopoiesisModel(config)

    founder = Cell(
        cell_type=HCellType.HSC,
        internal_state=InternalState(stemness_score=0.5, stress_score=0.0),
    )
    pop = Population([founder])
    rec = Recorder()
    CTMCEngine(model, pop, observers=[rec], rng_seed=0).run(t_max=50.0)

    surviving_cells = list(pop)
    assert len(surviving_cells) > 0, "population went extinct — increase t_max"
    stress_values = [c.internal_state.stress_score for c in surviving_cells]
    assert max(stress_values) > 0.0, "no stress accumulated despite non-zero rate"


def test_v05_config_reproducible_with_fixed_seed():
    """Fixed seed must produce identical runs under v0.5 config."""
    config = yaml.safe_load(CONFIG_V05.read_text())

    def run_once(seed: int) -> list:
        m = HematopoiesisModel(config)
        pop = Population([Cell(cell_type=HCellType.HSC) for _ in range(5)])
        rec = Recorder()
        CTMCEngine(m, pop, observers=[rec], rng_seed=seed).run(t_max=10.0)
        return [s.counts for s in rec.snapshots]

    assert run_once(55) == run_once(55)


def test_v04_config_still_runs_with_v05_model():
    """v0.4 config (no state_evolution section) must run identically under
    the v0.5 model — evolve_cell_states must be a true no-op.

    Verifies backward compatibility: two runs with the same seed produce
    identical snapshot sequences.
    """
    config = yaml.safe_load(CONFIG_V04.read_text())

    def run_once(seed: int) -> list:
        m = HematopoiesisModel(config)
        assert m.evolution_rules.is_noop, "v0.4 config should produce is_noop=True"
        pop = Population([Cell(cell_type=HCellType.HSC) for _ in range(5)])
        rec = Recorder()
        CTMCEngine(m, pop, observers=[rec], rng_seed=seed).run(t_max=10.0)
        return [s.counts for s in rec.snapshots]

    assert run_once(7) == run_once(7)


# ===========================================================================
# Causal chain: accumulated stress raises apoptosis rate
# ===========================================================================

def test_stress_accumulation_increases_apoptosis_rate():
    """Cells with higher stress must have a higher effective apoptosis rate.

    Simulates the causal chain:
      stress_accumulation_rate > 0
      → stress_score rises during lifetime
      → RateModulator maps higher stress to higher apoptosis factor
      → effective apoptosis rate is higher for aged cells

    Tested by comparing get_events() apoptosis rates between a fresh cell
    (stress = 0.0) and an aged cell (stress evolved for 50 h).
    """
    config = yaml.safe_load(CONFIG_V05.read_text())
    model = HematopoiesisModel(config)
    pop = Population([Cell(cell_type=HCellType.HSC)])

    # Fresh cell: stress = 0.0 (as born)
    fresh_cell = Cell(
        cell_type=HCellType.HSC,
        internal_state=InternalState(stemness_score=0.5, stress_score=0.0),
    )

    # Aged cell: evolve stress for 50 h using the model's own evolution rules
    aged_state = model.evolution_rules.evolve(
        InternalState(stemness_score=0.5, stress_score=0.0),
        dt=50.0,
    )
    aged_cell = Cell(
        cell_type=HCellType.HSC,
        internal_state=aged_state,
    )

    from cell_diff_sim.engine.events import ApoptosisEvent
    apo_fresh = [r for r, ev in model.get_events(fresh_cell, pop) if isinstance(ev, ApoptosisEvent)]
    apo_aged  = [r for r, ev in model.get_events(aged_cell,  pop) if isinstance(ev, ApoptosisEvent)]

    assert sum(apo_aged) > sum(apo_fresh), (
        "aged cell (higher stress) should have higher apoptosis rate than fresh cell"
    )
