"""Tests for v0.6.1: apply_overrides() and CLI argument handling.

v0.6.1 adds CLI parameter overrides on top of YAML configuration.
YAML remains the base source of truth; CLI overrides are applied after
YAML loading, before model construction.

All tests construct argparse.Namespace directly — no subprocess, no real
argv parsing — so they are fast, isolated, and deterministic.

Covers (14 tests):
  apply_overrides() unit tests (9):
    - no overrides → config unchanged, override list empty
    - override wins over existing YAML value
    - absent CLI arg (None) leaves YAML value intact
    - override creates a missing config section
    - initial_hsc override patches initial_population.HSC
    - inheritance_mode override patches inheritance.mode
    - centriole_stress_factor override patches correct key
    - rate modulation weight override patches correct key
    - multiple overrides all applied in one call

  Override reporting tests (2):
    - override list contains correct key=value strings
    - no overrides → override list is []

  Argparse validation (1):
    - invalid inheritance_mode value rejected with SystemExit

  Integration (2):
    - overridden config builds a working model and runs without error
    - v0.6 config + zero overrides produces reproducible results
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from scripts.run_sim import apply_overrides  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _empty_args(**kwargs) -> argparse.Namespace:
    """Build a Namespace with all override fields set to None by default.

    Pass keyword arguments to override specific fields, e.g.
    ``_empty_args(centriole_stress_factor=0.05)``.
    """
    defaults = dict(
        initial_hsc=None,
        inheritance_mode=None,
        stemness_asymmetry=None,
        stress_asymmetry=None,
        centriole_stemness_factor=None,
        centriole_stress_factor=None,
        centriole_age_cap=None,
        stress_accumulation_rate=None,
        stemness_drift_rate=None,
        w_div_stemness=None,
        w_div_stress=None,
        w_div_repl=None,
        w_diff_stemness=None,
        w_diff_stress=None,
        w_diff_repl=None,
        w_apo_stress=None,
        w_apo_repl=None,
    )
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


# ===========================================================================
# apply_overrides() unit tests
# ===========================================================================

def test_no_overrides_returns_config_unchanged():
    """All-None args → returned config is a copy equal to original; override list empty."""
    original = {"inheritance": {"mode": "centriole", "centriole_stemness_factor": 0.05}}
    cfg, overrides = apply_overrides(original, _empty_args())
    assert cfg == original
    assert overrides == []


def test_apply_overrides_does_not_mutate_original():
    """apply_overrides must never mutate the input config dict."""
    original = {"inheritance": {"mode": "centriole"}}
    original_copy = {"inheritance": {"mode": "centriole"}}
    apply_overrides(original, _empty_args(inheritance_mode="symmetric"))
    assert original == original_copy


def test_override_wins_over_yaml_value():
    """A CLI arg overrides the value already present in the YAML config."""
    original = {"inheritance": {"centriole_stress_factor": 0.02}}
    cfg, _ = apply_overrides(original, _empty_args(centriole_stress_factor=0.10))
    assert cfg["inheritance"]["centriole_stress_factor"] == pytest.approx(0.10)


def test_absent_cli_arg_leaves_yaml_value_intact():
    """A None CLI arg must not touch the existing YAML value."""
    original = {"inheritance": {"centriole_stress_factor": 0.02}}
    cfg, _ = apply_overrides(original, _empty_args())  # centriole_stress_factor=None
    assert cfg["inheritance"]["centriole_stress_factor"] == pytest.approx(0.02)


def test_override_creates_missing_section():
    """Override of a key whose section is absent from YAML creates the section."""
    original = {}  # no state_evolution section
    cfg, overrides = apply_overrides(original, _empty_args(stress_accumulation_rate=0.01))
    assert cfg["state_evolution"]["stress_accumulation_rate"] == pytest.approx(0.01)
    assert len(overrides) == 1


def test_initial_hsc_override():
    """--initial-hsc patches initial_population.HSC."""
    original = {"initial_population": {"HSC": 10}}
    cfg, overrides = apply_overrides(original, _empty_args(initial_hsc=25))
    assert cfg["initial_population"]["HSC"] == 25
    assert any("initial_population.HSC" in s for s in overrides)


def test_inheritance_mode_override():
    """--inheritance-mode patches inheritance.mode."""
    original = {"inheritance": {"mode": "centriole"}}
    cfg, overrides = apply_overrides(original, _empty_args(inheritance_mode="symmetric"))
    assert cfg["inheritance"]["mode"] == "symmetric"
    assert any("inheritance.mode" in s for s in overrides)


def test_centriole_stress_factor_override():
    """--centriole-stress-factor patches inheritance.centriole_stress_factor."""
    original = {"inheritance": {"mode": "centriole", "centriole_stress_factor": 0.02}}
    cfg, _ = apply_overrides(original, _empty_args(centriole_stress_factor=0.07))
    assert cfg["inheritance"]["centriole_stress_factor"] == pytest.approx(0.07)


def test_rate_modulation_weight_override():
    """--w-apo-stress patches state_modulation.w_apo_stress."""
    original = {"state_modulation": {"w_apo_stress": 1.0}}
    cfg, overrides = apply_overrides(original, _empty_args(w_apo_stress=2.5))
    assert cfg["state_modulation"]["w_apo_stress"] == pytest.approx(2.5)
    assert any("state_modulation.w_apo_stress" in s for s in overrides)


def test_multiple_overrides_all_applied():
    """Three simultaneous overrides must all be present in the returned config."""
    original = {}
    cfg, overrides = apply_overrides(
        original,
        _empty_args(
            inheritance_mode="asymmetric",
            stemness_asymmetry=0.15,
            stress_accumulation_rate=0.03,
        ),
    )
    assert cfg["inheritance"]["mode"] == "asymmetric"
    assert cfg["inheritance"]["stemness_asymmetry"] == pytest.approx(0.15)
    assert cfg["state_evolution"]["stress_accumulation_rate"] == pytest.approx(0.03)
    assert len(overrides) == 3


# ===========================================================================
# Override reporting tests
# ===========================================================================

def test_override_list_contains_correct_strings():
    """Each override string must include the dotted key path and the value."""
    original = {}
    _, overrides = apply_overrides(
        original,
        _empty_args(centriole_stress_factor=0.05, w_apo_stress=2.0),
    )
    keys = [s.split(" = ")[0] for s in overrides]
    assert "inheritance.centriole_stress_factor" in keys
    assert "state_modulation.w_apo_stress" in keys


def test_no_overrides_list_is_empty():
    """Zero CLI overrides → override list is exactly []."""
    _, overrides = apply_overrides({"inheritance": {"mode": "centriole"}}, _empty_args())
    assert overrides == []


# ===========================================================================
# Argparse validation
# ===========================================================================

def test_invalid_inheritance_mode_rejected(capsys):
    """--inheritance-mode with an invalid value must cause SystemExit (argparse error)."""
    from scripts.run_sim import parse_args
    with pytest.raises(SystemExit):
        parse_args.__wrapped__ if hasattr(parse_args, "__wrapped__") else None
        # Simulate passing bad argv
        sys.argv = ["run_sim.py", "--inheritance-mode", "bogus"]
        parse_args()


# ===========================================================================
# Integration tests
# ===========================================================================

def test_overridden_config_model_runs():
    """An overridden config must produce a working model that can run briefly."""
    from cell_diff_sim.cell import Cell
    from cell_diff_sim.engine.ctmc import CTMCEngine
    from cell_diff_sim.models.hematopoiesis import HCellType, HematopoiesisModel
    from cell_diff_sim.population import Population

    config = yaml.safe_load((ROOT / "configs" / "hematopoiesis_v06.yaml").read_text())
    cfg, overrides = apply_overrides(
        config,
        _empty_args(centriole_stress_factor=0.05, stress_accumulation_rate=0.01),
    )
    assert len(overrides) == 2

    model = HematopoiesisModel(cfg)
    pop = Population([Cell(cell_type=HCellType.HSC) for _ in range(5)])
    CTMCEngine(model, pop, rng_seed=0).run(t_max=5.0)  # must not raise


def test_v06_config_no_overrides_reproducible():
    """Zero overrides on v0.6 config + fixed seed → identical snapshot sequence."""
    from cell_diff_sim.cell import Cell
    from cell_diff_sim.engine.ctmc import CTMCEngine
    from cell_diff_sim.models.hematopoiesis import HCellType, HematopoiesisModel
    from cell_diff_sim.observers.recorder import Recorder
    from cell_diff_sim.population import Population

    raw = yaml.safe_load((ROOT / "configs" / "hematopoiesis_v06.yaml").read_text())

    def run_once(seed: int) -> list:
        cfg, _ = apply_overrides(raw, _empty_args())
        model = HematopoiesisModel(cfg)
        pop = Population([Cell(cell_type=HCellType.HSC) for _ in range(5)])
        rec = Recorder()
        CTMCEngine(model, pop, observers=[rec], rng_seed=seed).run(t_max=10.0)
        return [s.counts for s in rec.snapshots]

    assert run_once(99) == run_once(99)
