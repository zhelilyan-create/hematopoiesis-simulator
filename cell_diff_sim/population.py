"""Population container.

Holds all live cells and exposes query and mutation operations.
The engine and model mutate the population exclusively through this class.
"""

from __future__ import annotations

from typing import Iterator
from uuid import UUID

from cell_diff_sim.cell import Cell, CellType


class Population:
    """Container for all live cells in the simulation.

    Provides O(1) lookup by cell UUID and filtered views by cell type.
    The population is the single shared mutable state of the simulation;
    all mutations go through :meth:`add` and :meth:`remove`.

    Parameters
    ----------
    cells : list[Cell] | None
        Optional list of initial cells.  Defaults to an empty population.
    """

    def __init__(self, cells: list[Cell] | None = None) -> None:
        self._cells: dict[UUID, Cell] = {}
        for cell in (cells or []):
            self.add(cell)

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add(self, cell: Cell) -> None:
        """Add a cell to the population.

        Parameters
        ----------
        cell : Cell
            The cell to add.  Its ``id`` must not already be present.

        Raises
        ------
        ValueError
            If a cell with the same UUID is already in the population.
        """
        if cell.id in self._cells:
            raise ValueError(f"Cell {cell.id} is already in the population.")
        self._cells[cell.id] = cell

    def remove(self, cell_id: UUID) -> Cell:
        """Remove and return a cell by its UUID.

        Parameters
        ----------
        cell_id : UUID

        Returns
        -------
        Cell
            The removed cell.

        Raises
        ------
        KeyError
            If no cell with the given UUID exists.
        """
        return self._cells.pop(cell_id)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, cell_id: UUID) -> Cell:
        """Return a cell by UUID.

        Raises
        ------
        KeyError
            If not found.
        """
        return self._cells[cell_id]

    def by_type(self, cell_type: CellType) -> list[Cell]:
        """Return all live cells of the given cell type."""
        return [c for c in self._cells.values() if c.cell_type == cell_type]

    def snapshot(self) -> dict[CellType, int]:
        """Return a count of live cells per cell type.

        Returns
        -------
        dict[CellType, int]
            Keys are cell types present in the population; values are counts.
            Cell types with zero cells are omitted.
        """
        counts: dict[CellType, int] = {}
        for cell in self._cells.values():
            key: CellType = cell.cell_type.value if hasattr(cell.cell_type, "value") else cell.cell_type
            counts[key] = counts.get(key, 0) + 1
        return counts

    # ------------------------------------------------------------------
    # Python protocols
    # ------------------------------------------------------------------

    def __iter__(self) -> Iterator[Cell]:
        """Iterate over all live cells (order not guaranteed)."""
        return iter(list(self._cells.values()))

    def __len__(self) -> int:
        """Return total number of live cells."""
        return len(self._cells)

    def __contains__(self, cell_id: UUID) -> bool:
        """Return True if a cell with the given UUID is present."""
        return cell_id in self._cells

    def __repr__(self) -> str:
        counts = self.snapshot()
        summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        return f"Population(n={len(self)}, [{summary}])"
