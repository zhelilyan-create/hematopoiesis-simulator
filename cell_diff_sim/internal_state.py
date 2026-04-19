"""Typed internal cell state — v0.7.

InternalState holds per-cell molecular/physiological variables that
modulate event rates in state-dependent models.

v0.2 fields
-----------
stemness_score : float
    Degree of stem-cell character.  Neutral value 0.5 (midpoint of [0, 1]).
    Higher values increase division propensity and decrease differentiation.
stress_score : float
    Accumulated cellular stress (e.g. oxidative, replicative).
    Neutral value 0.0 (no stress).  Increases apoptosis propensity.
division_count : int
    Total number of divisions this cell lineage has undergone since
    the lineage founder.  Tracks replicative history.
    Neutral value 0.

v0.7 fields
-----------
epigenetic_bias : float
    Slowly changing, heritable epigenetic state that influences fate bias.
    Range [-1.0, 1.0].  Neutral value 0.0 (no bias).
    Positive values bias toward differentiation; negative toward self-renewal.
    Inherited across divisions (with optional small asymmetric shift).
    Drifts slowly toward 0.0 between events (mean-reversion).
    At neutral value 0.0 this field has zero effect on all event rates.

Neutral baseline
----------------
``InternalState()`` (all defaults) produces a modifier of exactly 1.0
for every event type in :class:`~models.rate_modulation.RateModulator`.
This is an algebraic guarantee — see rate_modulation.py for the proof.
The v0.7 ``epigenetic_bias`` field preserves this guarantee: at its neutral
value 0.0 and ``w_diff_epigenetic=0.0`` (the default weight), the epigenetic
term contributes exactly 0 to all modifier formulas.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class InternalState:
    """Per-cell internal state for state-dependent rate modulation.

    Parameters
    ----------
    stemness_score : float
        Stem-cell character in [0, 1].  Default 0.5 (neutral midpoint).
    stress_score : float
        Cellular stress >= 0.  Default 0.0 (no stress).
    division_count : int
        Replicative history >= 0.  Default 0.

    Raises
    ------
    ValueError
        If any field is out of its valid range.
    """

    stemness_score:   float = 0.5
    stress_score:     float = 0.0
    division_count:   int   = 0
    epigenetic_bias:  float = 0.0   # v0.7: heritable fate-bias memory, range [-1, 1]

    def __post_init__(self) -> None:
        if not (0.0 <= self.stemness_score <= 1.0):
            raise ValueError(
                f"stemness_score must be in [0, 1], got {self.stemness_score}"
            )
        if self.stress_score < 0.0:
            raise ValueError(
                f"stress_score must be >= 0, got {self.stress_score}"
            )
        if self.division_count < 0:
            raise ValueError(
                f"division_count must be >= 0, got {self.division_count}"
            )
        if not (-1.0 <= self.epigenetic_bias <= 1.0):
            raise ValueError(
                f"epigenetic_bias must be in [-1, 1], got {self.epigenetic_bias}"
            )
