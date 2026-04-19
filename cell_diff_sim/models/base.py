"""Abstract interfaces for biological models.

AbstractModel is the sole contract the CTMC engine uses to interact with
any biological model.  The engine imports nothing from concrete model
modules — only from this file.

v0.5 note: AbstractModel now exposes an optional ``evolve_cell_states``
method (concrete, not abstract) that implements the deterministic drift
component of the PDMP-style extension.  The default is a no-op, so all
v0.1–v0.4 models are unaffected.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from cell_diff_sim.models.inheritance import InheritanceRules

if TYPE_CHECKING:
    from cell_diff_sim.cell import Cell, CellType
    from cell_diff_sim.engine.events import Event
    from cell_diff_sim.population import Population


class AbstractModel(ABC):
    """Abstract base class for all biological differentiation models.

    A model is responsible for five things:

    1. **Cell type catalogue** — the complete list of valid cell types
       (:attr:`cell_types`).
    2. **Event generation** — computing which events a cell can undergo
       and at what rate (:meth:`get_events`).
    3. **Event application** — mutating the population for
       :class:`~engine.events.ApoptosisEvent` (:meth:`apply`).
       (v0.9: DifferentiationEvent removed; type transitions via DivisionEvent.)
    4. **Inheritance rules** — the strategy used by
       :class:`~engine.division_handler.DivisionHandler` when creating
       daughter cells (:attr:`inheritance_rules`).
    5. **Lifetime state evolution** (v0.5, optional) — deterministic drift
       of each cell's ``InternalState`` between stochastic events
       (:meth:`evolve_cell_states`).  Default is a no-op.

    Division is intentionally **not** handled by :meth:`apply`.
    :class:`~engine.division_handler.DivisionHandler` owns all division
    logic.  This keeps :meth:`apply` small and focused.

    Implementing a new model
    ------------------------
    Subclass :class:`AbstractModel`, implement all abstract members, and
    pass an instance to :class:`~engine.ctmc.CTMCEngine`.
    Override :meth:`evolve_cell_states` to add per-cell lifetime dynamics.
    """

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def cell_types(self) -> list[CellType]:
        """Return the complete list of valid cell types for this model."""
        ...

    @property
    @abstractmethod
    def inheritance_rules(self) -> InheritanceRules:
        """Return the InheritanceRules instance used during cell division.

        The engine passes this to DivisionHandler; the model is free to
        return a different instance per call (e.g. cell-type-specific rules).
        """
        ...

    # ------------------------------------------------------------------
    # Core interface
    # ------------------------------------------------------------------

    @abstractmethod
    def get_events(
        self,
        cell: Cell,
        population: Population,
    ) -> list[tuple[float, Event]]:
        """Compute all possible events for ``cell`` with their rates.

        The ``population`` argument is provided so that models can
        implement population-dependent rates (carrying capacity, paracrine
        signals, etc.) without any changes to the engine.

        Parameters
        ----------
        cell : Cell
            The cell for which to compute events.
        population : Population
            The current full population (read-only; do not mutate here).

        Returns
        -------
        list[tuple[float, Event]]
            A flat list of ``(rate, event)`` pairs.  Rates must be
            non-negative floats.  An empty list means the cell is
            in an absorbing state (no transitions possible).
        """
        ...

    @abstractmethod
    def apply(
        self,
        event: Event,
        cell: Cell,
        population: Population,
    ) -> None:
        """Apply a non-division event to the population.

        Handles :class:`~engine.events.ApoptosisEvent` **only** (v0.9).
        DifferentiationEvent has been removed; all cell-type transitions now
        happen through DivisionEvent fate tables.

        A :class:`~engine.events.DivisionEvent` must **never** be passed
        here — it is handled exclusively by
        :class:`~engine.division_handler.DivisionHandler`.  Concrete
        implementations should raise :class:`TypeError` if a
        :class:`~engine.events.DivisionEvent` is received, to catch
        routing mistakes early.

        Parameters
        ----------
        event : Event
            The event to apply.
        cell : Cell
            The cell on which the event acts (may be mutated in-place).
        population : Population
            The population to mutate in-place.
        """
        ...

    # ------------------------------------------------------------------
    # Optional lifetime dynamics (v0.5)
    # ------------------------------------------------------------------

    def evolve_cell_states(self, population: Population, dt: float) -> None:
        """Evolve all cells' ``InternalState`` for elapsed time ``dt``.

        This method is the deterministic drift hook of the PDMP-style
        extension introduced in v0.5.  It is called by
        :class:`~engine.ctmc.CTMCEngine` on **every** Gillespie step,
        strictly in this order:

        1. Propensities computed from **pre-drift** ``InternalState``.
        2. Δt sampled from Exp(λ_total).
        3. ``evolve_cell_states(population, dt)`` called — all cells age.
        4. Selected event applied to **post-drift** state.

        This ordering is the intentional v0.5 PDMP approximation: rates are
        sampled at the old state; the event fires at the evolved state.  The
        error per step is O(Δt²).

        **Default implementation: no-op.**
        All v0.1–v0.4 models that do not override this method are
        numerically unaffected.

        Parameters
        ----------
        population : Population
            The current cell population.  May mutate ``cell.internal_state``
            on each cell.
        dt : float
            Elapsed simulation time for this Gillespie step (hours).
        """
        pass  # default no-op — preserves v0.1–v0.4 behaviour
