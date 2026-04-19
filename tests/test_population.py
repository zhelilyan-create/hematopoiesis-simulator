"""Tests for population consistency after each event type.

Verifies that:
- apoptosis removes exactly one cell
- differentiation preserves population size and changes cell_type in-place
- division removes parent and adds two daughters (net +1)
- daughter cells have correct lineage fields
- Population.add() rejects duplicate UUIDs
- model.apply() rejects DivisionEvent
"""

import pytest

from cell_diff_sim.cell import Cell
from cell_diff_sim.engine.division_handler import DivisionHandler
from cell_diff_sim.engine.events import ApoptosisEvent, DifferentiationEvent, DivisionEvent
from cell_diff_sim.models.hematopoiesis import HCellType, HematopoiesisModel
from cell_diff_sim.models.inheritance import DefaultInheritanceRules
from cell_diff_sim.population import Population


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cell(ct: HCellType = HCellType.HSC) -> Cell:
    return Cell(cell_type=ct)


def _model() -> HematopoiesisModel:
    return HematopoiesisModel({})


# ---------------------------------------------------------------------------
# Apoptosis
# ---------------------------------------------------------------------------

def test_apoptosis_reduces_size_by_one():
    c = _cell()
    pop = Population([c])
    _model().apply(ApoptosisEvent(), c, pop)
    assert len(pop) == 0


def test_apoptosis_removes_correct_cell():
    c1 = _cell(HCellType.HSC)
    c2 = _cell(HCellType.MPP)
    pop = Population([c1, c2])
    _model().apply(ApoptosisEvent(), c1, pop)
    assert len(pop) == 1
    assert c1.id not in pop
    assert c2.id in pop


# ---------------------------------------------------------------------------
# Differentiation
# ---------------------------------------------------------------------------

def test_differentiation_preserves_size():
    c = _cell(HCellType.HSC)
    pop = Population([c])
    _model().apply(DifferentiationEvent(target_cell_type=HCellType.MPP), c, pop)
    assert len(pop) == 1


def test_differentiation_changes_cell_type_in_place():
    c = _cell(HCellType.HSC)
    cell_id = c.id
    pop = Population([c])
    _model().apply(DifferentiationEvent(target_cell_type=HCellType.MPP), c, pop)
    # Same object, same UUID, new cell_type
    assert c.cell_type == HCellType.MPP
    assert c.id == cell_id
    assert cell_id in pop


def test_differentiation_does_not_change_generation():
    c = _cell(HCellType.HSC)
    c.generation = 3
    pop = Population([c])
    _model().apply(DifferentiationEvent(target_cell_type=HCellType.MPP), c, pop)
    assert c.generation == 3


# ---------------------------------------------------------------------------
# Division
# ---------------------------------------------------------------------------

def _divide(parent: Cell, daughter_type: HCellType = HCellType.HSC) -> Population:
    pop = Population([parent])
    handler = DivisionHandler()
    rules = DefaultInheritanceRules()
    ev = DivisionEvent(daughter_cell_types=(daughter_type, daughter_type))
    handler.execute(ev, parent, pop, rules, now=1.0)
    return pop


def test_division_increases_size_by_one():
    c = _cell()
    pop = _divide(c)
    assert len(pop) == 2


def test_division_removes_parent():
    c = _cell()
    pop = _divide(c)
    assert c.id not in pop


def test_division_daughters_have_correct_type():
    c = _cell(HCellType.HSC)
    pop = _divide(c, HCellType.HSC)
    for daughter in pop:
        assert daughter.cell_type == HCellType.HSC


def test_division_daughters_increment_generation():
    c = _cell()
    c.generation = 2
    pop = _divide(c)
    for daughter in pop:
        assert daughter.generation == 3


def test_division_daughters_have_parent_id():
    c = _cell()
    pop = _divide(c)
    for daughter in pop:
        assert daughter.parent_id == c.id


def test_division_daughters_have_birth_time():
    c = _cell()
    pop = Population([c])
    handler = DivisionHandler()
    rules = DefaultInheritanceRules()
    ev = DivisionEvent(daughter_cell_types=(HCellType.HSC, HCellType.HSC))
    handler.execute(ev, c, pop, rules, now=7.5)
    for daughter in pop:
        assert daughter.birth_time == pytest.approx(7.5)


def test_division_daughters_have_distinct_ids():
    c = _cell()
    pop = _divide(c)
    ids = [d.id for d in pop]
    assert ids[0] != ids[1]


# ---------------------------------------------------------------------------
# Population guard: duplicate UUID
# ---------------------------------------------------------------------------

def test_add_duplicate_raises():
    c = _cell()
    pop = Population([c])
    with pytest.raises(ValueError, match="already in the population"):
        pop.add(c)


# ---------------------------------------------------------------------------
# model.apply() guard: DivisionEvent must not be routed here
# ---------------------------------------------------------------------------

def test_apply_division_event_raises_type_error():
    c = _cell()
    pop = Population([c])
    ev = DivisionEvent(daughter_cell_types=(HCellType.HSC, HCellType.HSC))
    with pytest.raises(TypeError, match="DivisionEvent"):
        _model().apply(ev, c, pop)
