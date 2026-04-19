"""Rate modulation by internal cell state — v0.7.

RateModulator computes multiplicative modifiers for the three event
types (division, differentiation, apoptosis) from a cell's InternalState.

Formulas
--------
All modifiers are centred on the neutral InternalState (stemness=0.5,
stress=0.0, division_count=0) so that modifier = 1.0 at neutral state
for every weight value::

    modifier_div  = 1.0 + w_div_stemness*(stemness-0.5)
                        - w_div_stress*stress
                        - w_div_repl*division_count

    modifier_diff = 1.0 - w_diff_stemness*(stemness-0.5)
                        + w_diff_stress*stress
                        + w_diff_repl*division_count
                        + w_diff_epigenetic*epigenetic_bias   # v0.7

    modifier_apo  = 1.0 + w_apo_stress*stress
                        + w_apo_repl*division_count

    effective_rate = base_rate * clamp(modifier, min_factor, max_factor)

Neutral-state proof
-------------------
Substituting stemness=0.5, stress=0.0, division_count=0, epigenetic_bias=0.0::

    modifier_div  = 1.0 + w*(0.5-0.5) - w*0.0 - w*0           = 1.0  (any w)
    modifier_diff = 1.0 - w*(0.5-0.5) + w*0.0 + w*0 + w_e*0.0 = 1.0  (any w_e)
    modifier_apo  = 1.0 + w*0.0 + w*0                          = 1.0  (any w)

v0.7 epigenetic term:  at ``epigenetic_bias=0.0`` the term ``w_diff_epigenetic*0.0=0``.
At default ``w_diff_epigenetic=0.0`` the term is always 0 regardless of bias.
Both paths guarantee exact backward compatibility.

Interpretation
--------------
Higher stemness         → more division, less differentiation
Higher stress           → less division, more differentiation, more apoptosis
Higher divisions        → less division, more differentiation, more apoptosis
Higher epigenetic_bias  → more differentiation  (v0.7, only when w > 0)
Lower  epigenetic_bias  → less differentiation  (v0.7, only when w > 0)

.. warning::
    All default weight values are NON-CALIBRATED placeholders.
    Set all weights to 0.0 to disable modulation entirely (v0.1 behaviour).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cell_diff_sim.internal_state import InternalState


# ---------------------------------------------------------------------------
# ModulationParams
# ---------------------------------------------------------------------------

@dataclass
class ModulationParams:
    """Non-negative weights for state-dependent rate modulation.

    All weights default to ``0.0`` so that v0.2 code with a v0.1 config
    (which has no ``state_modulation`` section) behaves identically to v0.1.

    Parameters
    ----------
    w_div_stemness : float
        Weight: stemness boost on division rate.
    w_div_stress : float
        Weight: stress penalty on division rate.
    w_div_repl : float
        Weight: replicative-history penalty on division rate.
    w_diff_stemness : float
        Weight: stemness suppression of differentiation rate.
    w_diff_stress : float
        Weight: stress promotion of differentiation rate.
    w_diff_repl : float
        Weight: replicative-history promotion of differentiation rate.
    w_apo_stress : float
        Weight: stress promotion of apoptosis rate.
    w_apo_repl : float
        Weight: replicative-history promotion of apoptosis rate.
    min_factor : float
        Lower clamp bound applied to all computed modifiers (default 0.1).
    max_factor : float
        Upper clamp bound applied to all computed modifiers (default 5.0).
    """

    w_div_stemness:       float = 0.0
    w_div_stress:         float = 0.0
    w_div_repl:           float = 0.0
    w_diff_stemness:      float = 0.0
    w_diff_stress:        float = 0.0
    w_diff_repl:          float = 0.0
    w_apo_stress:         float = 0.0
    w_apo_repl:           float = 0.0
    w_diff_epigenetic:    float = 0.0   # v0.7: epigenetic bias on differentiation rate
    w_lineage_epigenetic: float = 0.0   # v0.7: epigenetic bias on lineage selection
    min_factor:           float = 0.1
    max_factor:           float = 5.0


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


# ---------------------------------------------------------------------------
# RateModulator
# ---------------------------------------------------------------------------

class RateModulator:
    """Computes event-rate multipliers from a cell's :class:`~cell_diff_sim.internal_state.InternalState`.

    Parameters
    ----------
    params : ModulationParams
        Weight configuration, typically loaded from the ``state_modulation``
        section of a YAML config.
    """

    def __init__(self, params: ModulationParams) -> None:
        self._p = params

    def division_factor(self, state: InternalState) -> float:
        """Multiplicative modifier for the division rate.

        Higher stemness and lower stress/replication history → larger modifier.
        """
        p = self._p
        raw = (
            1.0
            + p.w_div_stemness * (state.stemness_score - 0.5)
            - p.w_div_stress   * state.stress_score
            - p.w_div_repl     * state.division_count
        )
        return _clamp(raw, p.min_factor, p.max_factor)

    def differentiation_factor(self, state: InternalState) -> float:
        """Multiplicative modifier for the differentiation rate.

        Lower stemness and higher stress/replication history → larger modifier.
        """
        p = self._p
        raw = (
            1.0
            - p.w_diff_stemness    * (state.stemness_score - 0.5)
            + p.w_diff_stress      * state.stress_score
            + p.w_diff_repl        * state.division_count
            + p.w_diff_epigenetic  * state.epigenetic_bias  # v0.7
        )
        return _clamp(raw, p.min_factor, p.max_factor)

    def apoptosis_factor(self, state: InternalState) -> float:
        """Multiplicative modifier for the apoptosis rate.

        Higher stress and replication history → larger modifier.
        """
        p = self._p
        raw = (
            1.0
            + p.w_apo_stress * state.stress_score
            + p.w_apo_repl   * state.division_count
        )
        return _clamp(raw, p.min_factor, p.max_factor)

    @property
    def lineage_epigenetic_weight(self) -> float:
        """Weight for epigenetic bias on lineage selection (v0.7).

        Returns ``w_lineage_epigenetic`` from the underlying
        :class:`ModulationParams`.  At 0.0 (default) lineage selection is
        identical to v0.6 behaviour.
        """
        return self._p.w_lineage_epigenetic
