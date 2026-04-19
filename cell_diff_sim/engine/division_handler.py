"""Division orchestration.

DivisionHandler is the single place where cell division is executed.
Keeping division out of model.apply() prevents that method from becoming
a catch-all and makes the responsibility boundary explicit:

    ┌─────────────────────┬──────────────────────────────────────────┐
    │ Who decides …       │ Where the logic lives                    │
    ├─────────────────────┼──────────────────────────────────────────┤
    │ daughter cell types │ DivisionEvent.daughter_cell_types        │
    │                     │ (set by model in get_events)             │
    │ internal_state +    │ InheritanceRules.inherit() → DaughterState│
    │ centriole_state     │ (provided by model, called here)         │
    │ cell creation       │ cell_factory.create_daughter()           │
    │ population mutation │ DivisionHandler.execute() ← this file   │
    └─────────────────────┴──────────────────────────────────────────┘

Extension path
--------------
- Asymmetric division: daughter_cell_types already a 2-tuple;
  InheritanceRules.inherit(daughter_index=0/1) already has the slot.
  Only InheritanceRules needs a new implementation — this file is unchanged.
- Centriole inheritance (v0.4): handled inside InheritanceRules subclass;
  DivisionHandler unpacks DaughterState transparently.
- >2 daughters: extend DivisionEvent and add a loop here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cell_diff_sim.engine.cell_factory import create_daughter

if TYPE_CHECKING:
    from cell_diff_sim.cell import Cell
    from cell_diff_sim.engine.events import DivisionEvent
    from cell_diff_sim.models.inheritance import InheritanceRules
    from cell_diff_sim.population import Population


class DivisionHandler:
    """Orchestrates all division logic for the CTMC engine.

    A single shared instance is held by CTMCEngine and called whenever
    a DivisionEvent is selected by the Gillespie algorithm.
    """

    def execute(
        self,
        event: DivisionEvent,
        parent: Cell,
        population: Population,
        inheritance_rules: InheritanceRules,
        now: float,
        rng=None,
    ) -> None:
        """Execute a division event: remove parent, create two daughters.

        Steps
        -----
        1. Ask ``inheritance_rules`` for each daughter's internal_state.
        2. Create daughter cells via ``cell_factory.create_daughter``.
        3. Remove parent from population.
        4. Add daughters to population.

        The parent is removed *after* daughters are created so that
        lineage information (parent.id, parent.generation) is still
        accessible during step 2.

        Parameters
        ----------
        event : DivisionEvent
            Carries ``daughter_cell_types`` — a 2-tuple of CellType.
        parent : Cell
            The dividing cell; removed from population by this method.
        population : Population
            Mutated in-place.
        inheritance_rules : InheritanceRules
            Provided by the model via ``model.inheritance_rules``.
        now : float
            Current simulation time (hours); assigned as birth_time of daughters.
        rng : numpy.random.Generator or None
            Engine RNG forwarded to ``inheritance_rules.inherit()`` for
            stochastic inheritance implementations (v0.8).  Base
            implementations ignore it.
        """
        type_a, type_b = event.daughter_cell_types

        # Compute inherited state for each daughter (returns DaughterState).
        # rng is forwarded so stochastic inheritance wrappers can draw noise.
        ds_a = inheritance_rules.inherit(parent, 0, event, rng)
        ds_b = inheritance_rules.inherit(parent, 1, event, rng)

        # Construct daughters before removing parent (need parent.id, .generation)
        daughter_a = create_daughter(parent, type_a, now, ds_a.internal_state, ds_a.centriole_state)
        daughter_b = create_daughter(parent, type_b, now, ds_b.internal_state, ds_b.centriole_state)

        # Mutate population
        population.remove(parent.id)
        population.add(daughter_a)
        population.add(daughter_b)
