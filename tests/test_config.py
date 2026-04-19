"""Tests for config parsing in HematopoiesisModel._parse_config().

Covers: valid config, negative rates, None targets, unknown cell types,
and empty config.
"""

import pytest
from cell_diff_sim.models.hematopoiesis import HCellType, HematopoiesisModel


# ---------------------------------------------------------------------------
# Valid config
# ---------------------------------------------------------------------------

def test_parse_diff_rates():
    config = {"differentiation_rates": {"HSC": {"MPP": 0.01}}}
    model = HematopoiesisModel(config)
    assert HCellType.HSC in model._diff_rates
    assert model._diff_rates[HCellType.HSC][HCellType.MPP] == pytest.approx(0.01)


def test_parse_division_rates():
    config = {"division_rates": {"HSC": 0.05, "MPP": 0.10}}
    model = HematopoiesisModel(config)
    assert model._division_rates[HCellType.HSC] == pytest.approx(0.05)
    assert model._division_rates[HCellType.MPP] == pytest.approx(0.10)


def test_parse_apoptosis_rates():
    config = {"apoptosis_rates": {"HSC": 0.001}}
    model = HematopoiesisModel(config)
    assert model._apoptosis_rates[HCellType.HSC] == pytest.approx(0.001)


def test_zero_rate_accepted():
    """Zero is a valid rate — means the event simply never fires."""
    config = {"division_rates": {"Myeloid": 0.0}}
    model = HematopoiesisModel(config)
    assert model._division_rates[HCellType.Myeloid] == 0.0


def test_empty_config_no_crash():
    """Missing all sections → all tables empty → λ=0 → clean halt."""
    model = HematopoiesisModel({})
    assert model._diff_rates == {}
    assert model._division_rates == {}
    assert model._apoptosis_rates == {}


# ---------------------------------------------------------------------------
# Negative rate validation (Fix A)
# ---------------------------------------------------------------------------

def test_negative_diff_rate_raises():
    with pytest.raises(ValueError, match="Negative differentiation rate"):
        HematopoiesisModel({"differentiation_rates": {"HSC": {"MPP": -0.01}}})


def test_negative_division_rate_raises():
    with pytest.raises(ValueError, match="Negative division rate"):
        HematopoiesisModel({"division_rates": {"HSC": -0.05}})


def test_negative_apoptosis_rate_raises():
    with pytest.raises(ValueError, match="Negative apoptosis rate"):
        HematopoiesisModel({"apoptosis_rates": {"HSC": -0.001}})


# ---------------------------------------------------------------------------
# None targets guard (Fix B)
# ---------------------------------------------------------------------------

def test_none_diff_targets_no_crash():
    """YAML `HSC:` with no sub-keys is parsed as None; must not crash."""
    model = HematopoiesisModel({"differentiation_rates": {"HSC": None}})
    # HSC silently skipped — no diff targets registered
    assert HCellType.HSC not in model._diff_rates


def test_none_diff_targets_other_keys_still_parsed():
    """Only the None entry is skipped; other valid entries are parsed."""
    config = {
        "differentiation_rates": {
            "HSC": None,
            "MPP": {"CMP": 0.02},
        }
    }
    model = HematopoiesisModel(config)
    assert HCellType.HSC not in model._diff_rates
    assert HCellType.MPP in model._diff_rates
    assert model._diff_rates[HCellType.MPP][HCellType.CMP] == pytest.approx(0.02)


# ---------------------------------------------------------------------------
# Unknown cell-type key
# ---------------------------------------------------------------------------

def test_unknown_cell_type_in_division_raises():
    with pytest.raises(ValueError):
        HematopoiesisModel({"division_rates": {"NOTACELL": 0.05}})


def test_unknown_cell_type_in_diff_raises():
    with pytest.raises(ValueError):
        HematopoiesisModel({"differentiation_rates": {"HSC": {"NOTACELL": 0.01}}})
