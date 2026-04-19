"""Cell dataclass — the atomic unit of the simulation.

Nothing outside this module should construct a Cell directly during division;
use engine.cell_factory.create_daughter() instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID, uuid4

from cell_diff_sim.centriole_state import CentrioleState
from cell_diff_sim.internal_state import InternalState

# ---------------------------------------------------------------------------
# CellType type alias
# ---------------------------------------------------------------------------
# CellType is intentionally a plain str alias.  Each biological model defines
# its own StrEnum whose values are strings and therefore satisfy this alias.
# This keeps Cell independent of any concrete model.
#
# Example (in models/hematopoiesis.py):
#   class HCellType(StrEnum):
#       HSC = "HSC"
#       MPP = "MPP"
#       ...
CellType = str


# ---------------------------------------------------------------------------
# Cell
# ---------------------------------------------------------------------------

@dataclass
class Cell:
    """Represents a single cell in the simulation.

    Parameters
    ----------
    cell_type : CellType
        The biological cell type (e.g. "HSC", "MPP").

        Named ``cell_type`` rather than ``state`` to prevent ambiguity with
        the several distinct state concepts planned for future versions:

        ============= ===================================================
        Field name    Planned meaning
        ============= ===================================================
        cell_type     Discrete differentiation stage (this field, v0.1)
        internal_state Molecular / protein-level state (scaffold, v0.1)
        centriole_state Centriole age and inheritance (v0.x)
        cell_cycle_state G1 / S / G2 / M phase (v0.x)
        regulatory_state Transcription-factor activity (v0.x)
        ============= ===================================================

    birth_time : float
        Simulation time at which this cell was created (hours).

    generation : int
        Number of divisions from the lineage founder (0 = founder cell).
        Used for lineage tracking and, later, for centriole-age accounting.

    parent_id : Optional[UUID]
        UUID of the parent cell, or None for founder cells.

    id : UUID
        Unique identifier, auto-assigned on construction.

    internal_state : InternalState
        Typed per-cell state introduced in v0.2.
        Holds ``stemness_score``, ``stress_score``, ``division_count``.
        Defaults to ``InternalState()`` — the neutral baseline where all
        rate modifiers equal exactly 1.0.
        Event rates are computed from this field; ``CentrioleState`` is not
        read directly by the rate computation path.

    centriole_state : CentrioleState
        Centriole age tracking introduced in v0.4.
        Defaults to ``CentrioleState(age=0)`` — a freshly formed centriole.
        Drives asymmetric stemness inheritance via
        :class:`~models.inheritance.CentrioleInheritanceRules`.
        Not read by the rate computation path.

    metadata : dict
        Arbitrary key-value store for simulation bookkeeping
        (e.g. debug flags, experiment labels).  Not used by the engine.
    """

    cell_type: CellType
    birth_time: float = 0.0
    generation: int = 0
    parent_id: Optional[UUID] = None
    id: UUID = field(default_factory=uuid4)

    # --- Typed internal state (v0.2) ---------------------------------------
    internal_state: InternalState = field(default_factory=InternalState)
    # --- Centriole state (v0.4) --------------------------------------------
    centriole_state: CentrioleState = field(default_factory=CentrioleState)
    metadata: dict = field(default_factory=dict)

    def __repr__(self) -> str:
        return (
            f"Cell(id={str(self.id)[:8]}…, "
            f"cell_type={self.cell_type!r}, "
            f"gen={self.generation}, "
            f"t={self.birth_time:.2f})"
        )
