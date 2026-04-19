"""Internal-state evolution rules for cell lifetime dynamics — v0.7.

Implements the deterministic drift component of the PDMP-style extension
introduced in v0.5.

Simulation model clarification
-------------------------------
From v0.5 onward the simulator is **no longer a pure CTMC**.  It is a
**piecewise-deterministic Markov process (PDMP)**: each cell's
``InternalState`` drifts deterministically between stochastic events.
The Gillespie algorithm is preserved; one lightweight hook is added.

Between consecutive stochastic events, each cell's ``InternalState``
evolves according to simple linear rules::

    stress_score(t + Δt)     = clamp(stress_score(t)   + stress_accumulation_rate × Δt,  0, ∞)
    stemness_score(t + Δt)   = clamp(stemness_score(t) + stemness_drift_rate      × Δt,  0, 1)
    epigenetic_bias(t + Δt)  = clamp(epigenetic_bias(t) × max(0, 1 − epigenetic_drift_rate × Δt), −1, 1)
    division_count           = unchanged  (updated only at division)

The epigenetic drift rule is a **mean-reversion toward 0**: bias decays
multiplicatively toward the neutral value.  With ``epigenetic_drift_rate = 0``
(the default) ``epigenetic_bias`` is unchanged between events — identical to
pre-v0.7 behaviour (v0.7 adds the field but defaults to a noop).

Time-ordering assumption (v0.5 PDMP convention)
-------------------------------------------------
In each Gillespie step:

1. Propensities are computed from the **pre-drift** ``InternalState``.
2. Δt is sampled from Exp(λ_total).
3. All cells' states are evolved deterministically by Δt.
4. The selected event is applied to the **post-drift** state.

This is the standard explicit-Euler PDMP approximation; the error in
event-rate sampling is O(Δt²) per step.

Primary effect (v0.5 baseline)
-------------------------------
``stress_accumulation_rate > 0`` models passive stress accumulation
during a cell's lifetime.  Because
:class:`~models.rate_modulation.RateModulator` translates higher stress
into higher apoptosis rates (and lower division / differentiation rates),
older cells experience effectively age-dependent event rates without any
change to the Gillespie algorithm itself.

Edge / debug option
--------------------
``stemness_drift_rate`` (signed, default ``0.0``) is supported but is
**not** the primary v0.5 mechanism.  A negative value models progressive
loss of stem character with age.  This option is provided for exploration
only; do not over-interpret results produced with non-zero stemness drift.

Biological framing (kept modest)
----------------------------------
These are phenomenological linear drift rules, not mechanistic models.
Parameters are NOT derived from experimental data and are NOT biologically
calibrated.  Do not interpret simulation outputs as quantitative
biological predictions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cell_diff_sim.internal_state import InternalState


@dataclass
class StateEvolutionParams:
    """Parameters governing per-cell lifetime state dynamics (v0.5).

    Both parameters default to ``0.0``, which disables evolution entirely
    and preserves exact v0.1–v0.4 behaviour.

    Parameters
    ----------
    stress_accumulation_rate : float
        Rate at which ``stress_score`` increases per unit simulation time
        (hours⁻¹).  Must be ≥ 0.  Stress only accumulates in v0.5; stress
        relief is not modelled.  Set to ``0.0`` to disable.
    stemness_drift_rate : float
        Rate at which ``stemness_score`` drifts per unit simulation time
        (hours⁻¹).  May be negative (downward drift — progressive loss of
        stem character) or positive (upward drift).  Defaults to ``0.0``
        (no drift).  This is an **edge/debug option**; the primary v0.5
        mechanism is ``stress_accumulation_rate``.
    """

    stress_accumulation_rate: float = 0.0
    stemness_drift_rate:      float = 0.0
    epigenetic_drift_rate:    float = 0.0   # v0.7: mean-reversion rate for epigenetic_bias

    def __post_init__(self) -> None:
        if self.stress_accumulation_rate < 0.0:
            raise ValueError(
                f"stress_accumulation_rate must be >= 0, "
                f"got {self.stress_accumulation_rate}. "
                "Stress can only accumulate or remain flat in v0.5; "
                "stress relief is not yet modelled."
            )
        if self.epigenetic_drift_rate < 0.0:
            raise ValueError(
                f"epigenetic_drift_rate must be >= 0, "
                f"got {self.epigenetic_drift_rate}."
            )


class StateEvolutionRules:
    """Applies deterministic lifetime drift to a cell's ``InternalState``.

    This is the deterministic component of the PDMP-style extension
    introduced in v0.5.  The class is stateless with respect to individual
    cells: the same rules apply uniformly to every cell regardless of type,
    lineage, or generation.

    Parameters
    ----------
    params : StateEvolutionParams
        Evolution parameters.  If both rates are ``0.0`` (the default),
        :meth:`evolve` is effectively a no-op and :attr:`is_noop` returns
        ``True``.
    """

    def __init__(self, params: StateEvolutionParams) -> None:
        self._params = params

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_noop(self) -> bool:
        """True when all evolution rates are zero — identical to pre-v0.5 behaviour.

        Used as a fast path by
        :meth:`~models.hematopoiesis.HematopoiesisModel.evolve_cell_states`
        to skip population iteration on every Gillespie step when evolution
        is disabled (e.g. all v0.1–v0.4 configs).

        v0.7: also checks ``epigenetic_drift_rate``.  When the epigenetic
        section is absent (or ``drift_rate: 0.0``) and the other rates are
        also zero, the fast path is preserved.
        """
        return (
            self._params.stress_accumulation_rate == 0.0
            and self._params.stemness_drift_rate == 0.0
            and self._params.epigenetic_drift_rate == 0.0
        )

    # ------------------------------------------------------------------
    # Core method
    # ------------------------------------------------------------------

    def evolve(self, state: InternalState, dt: float) -> InternalState:
        """Return a new ``InternalState`` after deterministic drift over ``dt``.

        **Time-ordering note:** this method is called *after* Δt is sampled
        and *before* the selected event is applied — see module docstring for
        the full PDMP step ordering.

        Parameters
        ----------
        state : InternalState
            Current per-cell state before the drift step.
        dt : float
            Elapsed simulation time (hours).  Must be ≥ 0.

        Returns
        -------
        InternalState
            New state with updated ``stress_score`` and ``stemness_score``.
            ``division_count`` is never modified here; it is updated only
            at division time by the inheritance rules.
        """
        from cell_diff_sim.internal_state import InternalState  # local avoids cycle

        new_stress = max(
            0.0,
            state.stress_score + self._params.stress_accumulation_rate * dt,
        )
        new_stemness = max(
            0.0,
            min(
                1.0,
                state.stemness_score + self._params.stemness_drift_rate * dt,
            ),
        )
        # v0.7: epigenetic mean-reversion toward 0.
        # decay factor in [0, 1] prevents sign-flipping for large dt.
        decay = max(0.0, 1.0 - self._params.epigenetic_drift_rate * dt)
        new_epigenetic_bias = max(-1.0, min(1.0, state.epigenetic_bias * decay))
        return InternalState(
            stemness_score=new_stemness,
            stress_score=new_stress,
            division_count=state.division_count,
            epigenetic_bias=new_epigenetic_bias,
        )
