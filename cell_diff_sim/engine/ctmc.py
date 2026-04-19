"""Simulation engine — Gillespie direct method with PDMP drift hook (v0.5).

This module is intentionally model-agnostic.  All biological knowledge
lives in AbstractModel; this file only knows about:
  - how to collect propensities from a model
  - how to sample the next event time
  - how to evolve per-cell states between events (v0.5 PDMP hook)
  - how to dispatch to the correct handler
  - how to notify observers

Simulation model note (v0.5)
-----------------------------
From v0.5 onward the engine supports a **piecewise-deterministic Markov
process (PDMP)** in addition to the pure CTMC.  Between stochastic events,
each cell's ``InternalState`` may drift deterministically via
``model.evolve_cell_states(population, dt)``.  For models that do not
override this method (including all v0.1–v0.4 models) the call is a no-op
and the algorithm reduces to the standard Gillespie CTMC.

Algorithm (one step)
--------------------
1. Collect propensities
   For each cell c: ask model.get_events(c, population) → [(rate, event)]
   Build flat list of (rate, event, cell) triples.
   **Rates are sampled from the pre-drift InternalState.**

2. Compute total rate
   λ_total = Σ rates
   If λ_total == 0: population is in an absorbing state → halt.

3. Sample time to next event
   Δt ~ Exponential(λ_total)
   Advance t ← t + Δt

4. Evolve cell states  [PDMP hook, v0.5]
   model.evolve_cell_states(population, Δt)
   All cells' InternalState is updated deterministically.
   Default: no-op (v0.1–v0.4 configs unchanged).

5. Select event
   Draw one (rate, event, cell) with probability ∝ rate.
   **Event is applied to the post-drift state.**

6. Dispatch
   DivisionEvent  → DivisionHandler.execute(...)
   ApoptosisEvent → model.apply(event, cell, population)

   v0.9: DifferentiationEvent removed; all type transitions are through
   DivisionEvent fate tables.

7. Notify observers
   For each observer: observer.on_step(t, population)

Extension path
--------------
- Next Reaction Method (Gibson-Bruck) for large populations: swap the
  _collect_propensities + sampling logic entirely within this file;
  nothing outside changes.
- Additional event types: add one isinstance branch to _dispatch().
"""

from __future__ import annotations

from cell_diff_sim.engine.division_handler import DivisionHandler
from cell_diff_sim.engine.events import (
    ApoptosisEvent,
    DivisionEvent,
    Event,
)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cell_diff_sim.cell import Cell
    from cell_diff_sim.models.base import AbstractModel
    from cell_diff_sim.observers.recorder import Recorder
    from cell_diff_sim.population import Population

    # Type alias — only meaningful for type checkers; not evaluated at runtime
    _Propensity = tuple[float, Event, Cell]


class CTMCEngine:
    """Gillespie direct-method simulation engine.

    Parameters
    ----------
    model : AbstractModel
        The biological model.  Provides event rates, apply logic, and
        inheritance rules.
    population : Population
        Initial cell population.  Mutated in-place during simulation.
    observers : list[Recorder] | None
        Optional observers notified after every event.
    rng_seed : int | None
        Random seed for reproducibility.  Pass an integer for deterministic
        runs; leave as None for random behaviour.
    """

    def __init__(
        self,
        model: AbstractModel,
        population: Population,
        observers: list[Recorder] | None = None,
        rng_seed: int | None = None,
    ) -> None:
        self.model = model
        self.population = population
        self.observers: list[Recorder] = observers or []
        self._division_handler = DivisionHandler()
        self._rng_seed = rng_seed
        self._rng = None  # initialised lazily in run() to avoid top-level numpy import
        self._time: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def time(self) -> float:
        """Current simulation time (hours)."""
        return self._time

    def run(self, t_max: float) -> None:
        """Run the simulation until ``t_max`` or population extinction.

        Step ordering per Gillespie step (v0.5 PDMP convention):

          1. Collect all per-cell propensities from **pre-drift** state.
          2. If none exist (extinct / absorbing state) → stop.
          3. Sample Δt ~ Exp(λ_total).  If t + Δt > t_max → stop without
             applying the event (the next event lies outside the window).
          4. Advance time by Δt.
          5. **Evolve all cells' states by Δt** (PDMP drift hook, v0.5).
             For models without lifetime dynamics this is a no-op.
          6. Select and dispatch one event to the **post-drift** state.
          7. Notify observers.

        Parameters
        ----------
        t_max : float
            Maximum simulation time (hours).

        Notes
        -----
        **Initial state is not recorded automatically.**
        Observers are notified only after each event, so the population at
        t=0 is never written to the recorder.  If you need the initial
        snapshot, call ``recorder.on_step(0.0, population)`` before calling
        ``run()``.

        **Final snapshot is at the last event, not at t_max.**
        When the next event time exceeds ``t_max``, the loop stops without
        dispatching that event.  The last recorded snapshot therefore has
        ``time < t_max`` (or ``= t_max`` if the run was exactly time-limited).
        """
        import numpy as np  # deferred so scaffold is importable without numpy
        self._rng = np.random.default_rng(self._rng_seed)

        while self._time < t_max:
            propensities = self._collect_propensities()

            if not propensities:
                break  # population extinct or fully absorbing

            rates = [p[0] for p in propensities]
            total = sum(rates)

            if total == 0.0:
                break

            # --- Time advance -----------------------------------------------
            dt = self._rng.exponential(1.0 / total)
            if self._time + dt > t_max:
                self._time = t_max
                break  # next event falls outside the observation window

            self._time += dt

            # --- PDMP drift hook (v0.5) --------------------------------------
            # Rates were sampled from the pre-drift state (step 1 above).
            # All cells' InternalState is now evolved deterministically by dt.
            # The selected event will be applied to the post-drift state.
            # Default implementation is a no-op → v0.1–v0.4 behaviour exact.
            self.model.evolve_cell_states(self.population, dt)

            # --- Event selection and dispatch --------------------------------
            _, event, cell = self._sample_next_event(propensities)
            self._dispatch(event, cell)

            # --- Notify observers --------------------------------------------
            self._notify_observers()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _collect_propensities(self) -> list[_Propensity]:
        """Build a flat list of (rate, event, cell) for every live cell.

        Iterates over the population and calls ``model.get_events`` for each
        cell.  Zero-rate events are excluded by the model.

        Returns
        -------
        list[tuple[float, Event, Cell]]
        """
        propensities: list = []
        for cell in self.population:
            for rate, event in self.model.get_events(cell, self.population):
                propensities.append((rate, event, cell))
        return propensities

    def _sample_next_event(
        self,
        propensities: list[_Propensity],
    ) -> tuple[float, Event, Cell]:
        """Select one event proportional to its rate.

        Parameters
        ----------
        propensities : list[tuple[float, Event, Cell]]
            Non-empty list of all possible (rate, event, cell) triples.

        Returns
        -------
        tuple[float, Event, Cell]
            The selected triple.
        """
        rates = [p[0] for p in propensities]
        total = sum(rates)
        probs = [r / total for r in rates]
        idx = int(self._rng.choice(len(propensities), p=probs))
        return propensities[idx]

    def _dispatch(self, event: Event, cell: Cell) -> None:
        """Route a selected event to its handler.

        Dispatch table
        --------------
        DivisionEvent  → DivisionHandler.execute()
        ApoptosisEvent → model.apply()
        (DifferentiationEvent removed in v0.9)

        Parameters
        ----------
        event : Event
        cell : Cell
        """
        if isinstance(event, DivisionEvent):
            self._division_handler.execute(
                event,
                cell,
                self.population,
                self.model.inheritance_rules,
                self._time,
                self._rng,   # v0.8: forwarded to stochastic inheritance rules
            )
        else:
            self.model.apply(event, cell, self.population)

    def _notify_observers(self) -> None:
        """Call on_step() on all registered observers."""
        for observer in self.observers:
            observer.on_step(self._time, self.population)
