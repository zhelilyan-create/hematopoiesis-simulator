"""Factory function for creating daughter cells during division.

This is the single construction path for cells produced by division.
Direct instantiation of Cell() during division is intentionally avoided
so that lineage bookkeeping (id, generation, parent_id) is always correct.

Called exclusively by DivisionHandler — never by models or the engine loop.
"""

from __future__ import annotations

from uuid import uuid4

from cell_diff_sim.cell import Cell, CellType
from cell_diff_sim.centriole_state import CentrioleState
from cell_diff_sim.internal_state import InternalState


def create_daughter(
    parent: Cell,
    cell_type: CellType,
    birth_time: float,
    internal_state: InternalState,
    centriole_state: CentrioleState,
) -> Cell:
    """Create a single daughter cell inheriting lineage from a parent.

    Parameters
    ----------
    parent : Cell
        The dividing parent cell.  Its ``id`` becomes the daughter's
        ``parent_id``; its ``generation`` is incremented by 1.
    cell_type : CellType
        The cell type of the new daughter (determined by DivisionEvent).
    birth_time : float
        Current simulation time (hours).
    internal_state : InternalState
        Pre-computed internal state from ``DaughterState.internal_state``.
    centriole_state : CentrioleState
        Pre-computed centriole state from ``DaughterState.centriole_state``.

    Returns
    -------
    Cell
        A new Cell with a fresh UUID, incremented generation, and
        ``parent_id`` set to the parent's UUID.

    Notes
    -----
    ``metadata`` is always initialised to ``{}`` for daughters.
    Any metadata that should propagate across divisions must be handled
    in ``InheritanceRules`` via the state objects.
    """
    return Cell(
        cell_type=cell_type,
        birth_time=birth_time,
        generation=parent.generation + 1,
        parent_id=parent.id,
        id=uuid4(),
        internal_state=internal_state,
        centriole_state=centriole_state,
        metadata={},
    )
