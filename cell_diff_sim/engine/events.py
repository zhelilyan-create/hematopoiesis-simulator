"""Event type hierarchy for the CTMC simulation.

Events are immutable value objects produced by the model (via get_events)
and consumed by the engine's dispatch logic in CTMCEngine.

Design rules
------------
- Events carry *what should happen*, not *how*.
- Events are frozen dataclasses — hashable, comparable, loggable.
- DivisionEvent is NEVER passed to model.apply(); it goes to DivisionHandler.
- Adding a new event type = add a subclass here + one dispatch branch in ctmc.py.

v0.9 note: DifferentiationEvent has been removed.  Cell type transitions now
happen exclusively through DivisionEvent (fate-driven division).  The
``daughter_cell_types`` tuple carries the fate decision; daughters can be of
different types, implementing asymmetric and commitment-driving divisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cell_diff_sim.cell import CellType


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Event:
    """Abstract base for all simulation events.

    All concrete events must inherit from this class.  The class itself
    carries no data — it exists as a common type for type hints and
    isinstance() dispatch in the engine.
    """


# ---------------------------------------------------------------------------
# Concrete events
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DivisionEvent(Event):
    """A cell divides into two daughter cells, each with a (possibly distinct) type.

    Handled by: ``DivisionHandler.execute()``  — **never** by ``model.apply()``.

    Parameters
    ----------
    daughter_cell_types : tuple[CellType, CellType]
        Cell types of the two daughter cells, in order (daughter 0, daughter 1).
        The two elements may be identical (symmetric division) or different
        (asymmetric / commitment division).  The fate is chosen stochastically
        by the model in ``get_events()`` via niche-weighted fate tables.

    Notes
    -----
    From v0.9, all cell-type transitions happen through this event.
    ``DifferentiationEvent`` has been removed: lineage commitment is encoded
    in the fate table (``division_fates`` config section) and modulated at
    runtime by the niche signal.
    """

    daughter_cell_types: tuple[CellType, CellType]


@dataclass(frozen=True)
class ApoptosisEvent(Event):
    """A cell undergoes programmed cell death and is removed from the population.

    Handled by: ``model.apply()``
    """
