"""InheritanceRules protocol and implementations — v0.7.

InheritanceRules defines how a parent cell's InternalState and CentrioleState
are propagated into each of the two daughter cells produced by a DivisionEvent.

Return type
-----------
All implementations return a :class:`DaughterState` — a small container that
bundles the daughter's ``InternalState`` and ``CentrioleState`` together.
:class:`~engine.division_handler.DivisionHandler` unpacks it and passes each
field to :func:`~engine.cell_factory.create_daughter`.

This module has no runtime imports from the rest of the package other than
the two state dataclasses, keeping it safe to import from ``base.py`` without
creating circular dependencies.

Inheritance mode summary
------------------------
+---------------------------+--------------------------------------------------+
| Class                     | Config ``mode:``                                 |
+===========================+==================================================+
| DefaultInheritanceRules   | (internal use / tests only)                      |
+---------------------------+--------------------------------------------------+
| SymmetricInheritanceRules | ``symmetric`` (default, v0.2)                    |
+---------------------------+--------------------------------------------------+
| AsymmetricInheritanceRules| ``asymmetric`` (v0.3, extended v0.6)             |
+---------------------------+--------------------------------------------------+
| CentrioleInheritanceRules | ``centriole``  (v0.4, extended v0.6)             |
+---------------------------+--------------------------------------------------+

``mode: symmetric`` and absent ``inheritance`` section are the primary
backward-compatibility paths for v0.1/v0.2/v0.3 configs.

v0.7 epigenetic inheritance
----------------------------
:class:`EpigeneticInheritanceWrapper` wraps any rule and adds a separate
epigenetic inheritance layer on top, without touching the base implementations.
When ``epigenetic.enabled`` is absent or ``False`` in the config, the wrapper
is not applied and the base rule runs unchanged.

All base implementations (Symmetric, Asymmetric, Centriole) pass the parent's
``epigenetic_bias`` through to daughters unchanged.  The wrapper then applies
the configured shift on top.  ``DefaultInheritanceRules`` returns the
structural default (``epigenetic_bias=0.0``) — by design.

Backward compatibility
----------------------
Non-centriole modes (``symmetric``, ``asymmetric``) always return
``CentrioleState(age=0)`` for both daughters.  Centriole state exists on
every ``Cell`` structurally but is inert in those modes.

``mode: asymmetric``  — abstract direct asymmetry.  A fixed ``stemness_asymmetry``
δ_s is applied to stemness.  From v0.6, an optional ``stress_asymmetry`` δ_σ
is applied to stress in the opposite direction.  Defaults to 0.0 for exact
backward compatibility.

``mode: centriole``   — mechanistic proxy: centriole age drives the stemness
shift via ``stemness_delta = factor * min(age, age_cap)``.  From v0.6, an
optional ``centriole_stress_factor`` drives a coupled stress shift via the
same centriole-age-derived delta.  Defaults to 0.0 for exact backward
compatibility.

Stress bounds convention (v0.6)
--------------------------------
- ``stress_score`` is lower-bounded at 0.0.
- There is **no upper cap** in v0.6.  Stress can grow without bound above 0.
- Asymmetric stress inheritance only prevents negative values:
  ``daughter_stress = max(0.0, parent_stress - δ_σ)``.
- The higher-stress daughter receives ``parent_stress + δ_σ`` with no
  additional clamping — its stress is always ≥ parent_stress ≥ 0.

Direction convention (v0.6)
-----------------------------
``daughter_index = 0``  →  higher stemness, **lower** stress.
``daughter_index = 1``  →  lower stemness, **higher** stress.
This convention is consistent with v0.3/v0.4 (daughter 0 was always the
higher-stemness daughter) and extends it to the stress axis.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from cell_diff_sim.centriole_state import CentrioleState
from cell_diff_sim.internal_state import InternalState

if TYPE_CHECKING:
    from cell_diff_sim.cell import Cell
    from cell_diff_sim.engine.events import DivisionEvent


# ---------------------------------------------------------------------------
# DaughterState — return type for all inherit() implementations
# ---------------------------------------------------------------------------

@dataclass
class DaughterState:
    """Container returned by :meth:`InheritanceRules.inherit`.

    Bundles the two per-daughter state objects so that
    :class:`~engine.division_handler.DivisionHandler` can unpack them and
    pass each to :func:`~engine.cell_factory.create_daughter`.

    Parameters
    ----------
    internal_state : InternalState
        Rates-relevant state (stemness, stress, division count).
    centriole_state : CentrioleState
        Centriole age.  Set to ``CentrioleState(age=0)`` by non-centriole
        implementations — inert but structurally present.
    """

    internal_state:  InternalState
    centriole_state: CentrioleState


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class InheritanceRules(Protocol):
    """Protocol: computes daughter state during cell division.

    Implementations are provided by each biological model and called
    exclusively by :class:`~engine.division_handler.DivisionHandler`.

    The ``daughter_index`` parameter (0 or 1) distinguishes the two daughters:

    - Symmetric implementations ignore it (both daughters get the same state).
    - :class:`AsymmetricInheritanceRules` uses it to determine the sign of
      the stemness and stress perturbations.
    - :class:`CentrioleInheritanceRules` uses it to assign the old vs. new
      centriole and derives the stemness and stress shifts from centriole age.

    v0.8: ``rng`` (optional, default ``None``) is the engine's numpy RNG.
    Base implementations ignore it.  :class:`EpigeneticInheritanceWrapper`
    uses it to draw per-division stochastic noise.
    """

    def inherit(
        self,
        parent: Cell,
        daughter_index: int,
        event: DivisionEvent,
        rng=None,
    ) -> DaughterState:
        """Return the state for one daughter cell.

        Parameters
        ----------
        parent : Cell
            The dividing parent cell.
        daughter_index : int
            0 or 1.
        event : DivisionEvent
            The division event (carries ``daughter_cell_types``).
        rng : numpy.random.Generator or None
            Engine RNG.  Passed through to inheritance rules that need
            stochastic sampling (e.g. :class:`EpigeneticInheritanceWrapper`).
            Base implementations ignore this parameter.

        Returns
        -------
        DaughterState
            Contains ``internal_state`` and ``centriole_state`` for this
            daughter.
        """
        ...


# ---------------------------------------------------------------------------
# Default implementation
# ---------------------------------------------------------------------------

class DefaultInheritanceRules:
    """Returns neutral defaults for every daughter.

    - ``InternalState()``  — neutral stemness, no stress, zero divisions.
    - ``CentrioleState()`` — fresh centriole (age = 0).

    Use when internal state is irrelevant to the model (e.g. all modulation
    weights = 0.0 and centriole mode disabled).
    """

    def inherit(
        self,
        parent: Cell,
        daughter_index: int,
        event: DivisionEvent,
        rng=None,
    ) -> DaughterState:
        """Return neutral DaughterState regardless of parent state."""
        return DaughterState(
            internal_state=InternalState(),
            centriole_state=CentrioleState(),
        )


# ---------------------------------------------------------------------------
# Symmetric inheritance — v0.2 / default
# ---------------------------------------------------------------------------

class SymmetricInheritanceRules:
    """Copies parent InternalState to both daughters, incrementing division_count.

    Treats both daughters identically.  CentrioleState is always set to
    ``CentrioleState(age=0)`` — centriole tracking is inactive in this mode.

    Inheritance logic
    -----------------
    - ``stemness_score``  : copied unchanged from parent
    - ``stress_score``    : copied unchanged from parent
    - ``division_count``  : parent value + 1
    - ``centriole_state`` : ``CentrioleState(age=0)`` (inert, not tracked)

    This is the primary backward-compatibility implementation for v0.1/v0.2
    configs (no ``inheritance`` section present → this class is used).
    """

    def inherit(
        self,
        parent: Cell,
        daughter_index: int,
        event: DivisionEvent,
        rng=None,
    ) -> DaughterState:
        """Return DaughterState with symmetric InternalState and inert CentrioleState."""
        s = parent.internal_state
        return DaughterState(
            internal_state=InternalState(
                stemness_score=s.stemness_score,
                stress_score=s.stress_score,
                division_count=s.division_count + 1,
                epigenetic_bias=s.epigenetic_bias,  # v0.7: pass through unchanged
            ),
            centriole_state=CentrioleState(),  # inert: age=0, not tracked
        )


# ---------------------------------------------------------------------------
# Asymmetric inheritance — v0.3 / v0.6 extension
# ---------------------------------------------------------------------------

class AsymmetricInheritanceRules:
    """Partitions stemness_score (and optionally stress_score) asymmetrically.

    Each division shifts the parent's ``stemness_score`` by a fixed ±δ_s, and
    optionally the parent's ``stress_score`` by ±δ_σ in the opposite direction
    (v0.6 extension).

    Direction convention
    --------------------
    - Daughter 0 (index 0): ``clamp(parent.stemness + δ_s, 0, 1)``
                             ``max(0.0, parent.stress  − δ_σ)``
    - Daughter 1 (index 1): ``clamp(parent.stemness − δ_s, 0, 1)``
                             ``parent.stress + δ_σ``

    Daughter 0 is always the more stem-like, lower-stress daughter.
    Daughter 1 is always the more committed, higher-stress daughter.

    Stress bounds (v0.6)
    --------------------
    - ``stress_score`` is lower-bounded at 0.0; there is no upper cap.
    - Only the lower-stress daughter (index 0) requires clamping:
      ``max(0.0, parent.stress − δ_σ)``.
    - The higher-stress daughter (index 1) receives ``parent.stress + δ_σ``,
      which is always ≥ parent.stress ≥ 0, so no clamping is needed.

    Backward compatibility
    ----------------------
    ``stress_asymmetry`` defaults to 0.0.  When 0.0, both daughters receive
    ``parent.stress_score`` unchanged — byte-for-byte identical to v0.3/v0.4/v0.5.

    ``CentrioleState`` is always set to ``CentrioleState(age=0)`` — centriole
    tracking is inactive in this mode.

    Mode comparison
    ---------------
    ``mode: asymmetric``  — abstract direct asymmetry driven by fixed per-division
    δ values.  Does not model centriole history.

    ``mode: centriole``   — mechanistic proxy where the shifts are derived from
    centriole age (see :class:`CentrioleInheritanceRules`).

    Saturation
    ----------
    Stemness lineages that repeatedly land on the high-stemness side approach
    1.0 and remain clamped there.  This is expected behaviour (bounded [0, 1]
    domain).  Stress in the high-stress lineage is unbounded above — it will
    grow with each division.

    Parameters
    ----------
    stemness_asymmetry : float
        δ_s ≥ 0.  Magnitude of the stemness perturbation per division.
    stress_asymmetry : float
        δ_σ ≥ 0.  Magnitude of the stress perturbation per division.
        Default 0.0 — no stress asymmetry (v0.3/v0.4/v0.5 behaviour).

    Raises
    ------
    ValueError
        If ``stemness_asymmetry < 0`` or ``stress_asymmetry < 0``.
    """

    def __init__(
        self,
        stemness_asymmetry: float = 0.1,
        stress_asymmetry: float = 0.0,
    ) -> None:
        if stemness_asymmetry < 0.0:
            raise ValueError(
                f"stemness_asymmetry must be >= 0, got {stemness_asymmetry}"
            )
        if stress_asymmetry < 0.0:
            raise ValueError(
                f"stress_asymmetry must be >= 0, got {stress_asymmetry}"
            )
        self._stemness_delta = stemness_asymmetry
        self._stress_delta   = stress_asymmetry

    def inherit(
        self,
        parent: Cell,
        daughter_index: int,
        event: DivisionEvent,
        rng=None,
    ) -> DaughterState:
        """Return asymmetrically perturbed DaughterState.

        Parameters
        ----------
        daughter_index : int
            0 → higher stemness, lower stress.
            1 → lower stemness, higher stress.
        rng : ignored
            Accepted for Protocol compatibility; not used by this implementation.
        """
        s    = parent.internal_state
        sign = 1 if daughter_index == 0 else -1

        new_stemness = max(0.0, min(1.0, s.stemness_score + sign * self._stemness_delta))

        # Stress moves opposite to stemness.
        # Lower-stress daughter (index 0): clamp at 0.0 (no negative stress).
        # Higher-stress daughter (index 1): no upper cap.
        if daughter_index == 0:
            new_stress = max(0.0, s.stress_score - self._stress_delta)
        else:
            new_stress = s.stress_score + self._stress_delta

        return DaughterState(
            internal_state=InternalState(
                stemness_score=new_stemness,
                stress_score=new_stress,
                division_count=s.division_count + 1,
                epigenetic_bias=s.epigenetic_bias,  # v0.7: pass through unchanged
            ),
            centriole_state=CentrioleState(),  # inert: age=0, not tracked
        )


# ---------------------------------------------------------------------------
# Centriole-driven asymmetric inheritance — v0.4 / v0.6 extension
# ---------------------------------------------------------------------------

class CentrioleInheritanceRules:
    """Centriole age drives asymmetric stemness (and optionally stress) inheritance.

    At each division:

    - Daughter 0 inherits the **old** centriole: ``CentrioleState(age = parent.age + 1)``
    - Daughter 1 inherits the **new** centriole: ``CentrioleState(age = 0)``

    The stemness shift is derived from the parent's centriole age (v0.4)::

        stemness_delta = centriole_stemness_factor * min(parent.centriole_state.age,
                                                         centriole_age_cap)

        daughter 0: stemness = clamp(parent.stemness + stemness_delta, 0, 1)
        daughter 1: stemness = clamp(parent.stemness - stemness_delta, 0, 1)

    From v0.6, an optional stress shift is derived from the same centriole age::

        stress_delta = centriole_stress_factor * min(parent.centriole_state.age,
                                                     centriole_age_cap)

        daughter 0: stress = max(0.0, parent.stress - stress_delta)
        daughter 1: stress = parent.stress + stress_delta

    Both shifts use the same ``centriole_age_cap`` — a single cap governs the
    plateau for all centriole-age-derived effects.

    Stress bounds (v0.6)
    --------------------
    - ``stress_score`` is lower-bounded at 0.0; there is no upper cap.
    - Only daughter 0 (lower-stress) requires clamping: ``max(0.0, ...)``.
    - Daughter 1 (higher-stress) receives ``parent.stress + stress_delta``,
      which is always ≥ parent.stress ≥ 0, so no clamping is needed.

    Backward compatibility
    ----------------------
    ``centriole_stress_factor`` defaults to 0.0.  When 0.0, ``stress_delta = 0``
    and both daughters receive ``parent.stress_score`` unchanged — byte-for-byte
    identical to v0.4/v0.5.

    Founder assumption
    ------------------
    Founder cells start with ``CentrioleState(age=0)``, so on the **first
    division** both deltas = 0.  Asymmetry (in both stemness and stress) only
    emerges from the second division onward.  This is an **intentional v0.4
    design assumption**, carried forward unchanged.

    Bounded effect
    --------------
    Using ``min(age, centriole_age_cap)`` prevents deltas from growing without
    bound.  Both stemness and stress asymmetry plateau once the old-centriole
    lineage reaches ``age_cap`` divisions.  Stress in the high-stress lineage
    is unbounded above (no cap on absolute level) — only the per-division
    increment is capped.

    Biological framing (kept modest)
    ---------------------------------
    Old centriole → higher stemness, lower stress is a named convention, not
    a biological claim.  The two factors (stemness, stress) are independent
    parameters — they can be set to different magnitudes.  No specific molecular
    pathway is modelled.

    Parameters
    ----------
    centriole_stemness_factor : float
        Stemness shift per unit of centriole age (up to ``centriole_age_cap``).
        Must be >= 0.
    centriole_stress_factor : float
        Stress shift per unit of centriole age (up to ``centriole_age_cap``).
        Must be >= 0.  Default 0.0 — no stress asymmetry (v0.4/v0.5 behaviour).
    centriole_age_cap : int
        Maximum centriole age that contributes to either delta.  Must be >= 1.

    Raises
    ------
    ValueError
        If ``centriole_stemness_factor < 0``, ``centriole_stress_factor < 0``,
        or ``centriole_age_cap < 1``.
    """

    def __init__(
        self,
        centriole_stemness_factor: float = 0.0,
        centriole_stress_factor:   float = 0.0,
        centriole_age_cap:         int   = 10,
    ) -> None:
        if centriole_stemness_factor < 0.0:
            raise ValueError(
                f"centriole_stemness_factor must be >= 0, "
                f"got {centriole_stemness_factor}"
            )
        if centriole_stress_factor < 0.0:
            raise ValueError(
                f"centriole_stress_factor must be >= 0, "
                f"got {centriole_stress_factor}"
            )
        if centriole_age_cap < 1:
            raise ValueError(
                f"centriole_age_cap must be >= 1, got {centriole_age_cap}"
            )
        self._stemness_factor = centriole_stemness_factor
        self._stress_factor   = centriole_stress_factor
        self._cap             = centriole_age_cap

    def inherit(
        self,
        parent: Cell,
        daughter_index: int,
        event: DivisionEvent,
        rng=None,
    ) -> DaughterState:
        """Return DaughterState with centriole-age-derived stemness and stress shifts.

        Parameters
        ----------
        daughter_index : int
            0 → old centriole (age+1), higher stemness, lower stress.
            1 → new centriole (age=0),  lower stemness, higher stress.
        rng : ignored
            Accepted for Protocol compatibility; not used by this implementation.
        """
        s  = parent.internal_state
        ca = parent.centriole_state

        # Both deltas grow linearly with centriole age up to cap, then plateau.
        effective_age   = min(ca.age, self._cap)
        stemness_delta  = self._stemness_factor * effective_age
        stress_delta    = self._stress_factor   * effective_age

        sign = 1 if daughter_index == 0 else -1
        new_stemness = max(0.0, min(1.0, s.stemness_score + sign * stemness_delta))

        # Stress moves opposite to stemness.
        # Lower-stress daughter (index 0): clamp at 0.0 (no negative stress).
        # Higher-stress daughter (index 1): no upper cap.
        if daughter_index == 0:
            new_stress = max(0.0, s.stress_score - stress_delta)
        else:
            new_stress = s.stress_score + stress_delta

        new_centriole_age = ca.age + 1 if daughter_index == 0 else 0

        return DaughterState(
            internal_state=InternalState(
                stemness_score=new_stemness,
                stress_score=new_stress,
                division_count=s.division_count + 1,
                epigenetic_bias=s.epigenetic_bias,  # v0.7: pass through unchanged
            ),
            centriole_state=CentrioleState(age=new_centriole_age),
        )


# ---------------------------------------------------------------------------
# Epigenetic inheritance wrapper — v0.7
# ---------------------------------------------------------------------------

class EpigeneticInheritanceWrapper:
    """Wraps any InheritanceRules to add a stochastic epigenetic inheritance layer.

    Applied on top of the base inheritance rules when ``epigenetic.enabled: true``
    is set in the config.  Leaves all other state fields untouched.

    Epigenetic shift convention (v0.8)
    -----------------------------------
    Per division, a shift is sampled:

        shift = asymmetry_strength + rng.normal(0, inheritance_noise_std)

    where ``asymmetry_strength`` is the deterministic directional component and
    ``inheritance_noise_std`` is the standard deviation of the stochastic
    per-division noise.  When ``rng`` is ``None`` or ``inheritance_noise_std``
    is 0.0, only the deterministic component applies.

    - Daughter 0 (higher stemness / old centriole):
      ``clip(parent.epigenetic_bias − shift, −1, 1)``
    - Daughter 1 (lower stemness / new centriole):
      ``clip(parent.epigenetic_bias + shift, −1, 1)``

    Direction: daughter 0 inherits a slightly more self-renewal-biased
    (negative) epigenetic state; daughter 1 inherits a slightly more
    differentiation-biased (positive) state.  Consistent with v0.6 convention
    (daughter 0 = higher stemness, lower stress).

    Backward compatibility
    ----------------------
    When both parameters are 0.0 (the default), shift = 0 and both daughters
    inherit the parent bias unchanged — numerically identical to the base rules
    without the wrapper.

    v0.7 → v0.8 migration
    ----------------------
    In v0.7, ``inheritance_noise`` was a **deterministic** additive value.
    In v0.8, it is reinterpreted as the **standard deviation** of a
    zero-mean Gaussian drawn once per division event.  The YAML key
    ``inheritance_noise`` is preserved for compatibility; its value now sets
    ``inheritance_noise_std``.  With ``inheritance_noise_std = 0`` the
    behaviour is identical to v0.7 with ``inheritance_noise = 0``.

    Parameters
    ----------
    base_rules : InheritanceRules
        The wrapped base implementation (Symmetric, Asymmetric, or Centriole).
    asymmetry_strength : float
        Systematic directional shift per division (>= 0).  Default 0.0.
    inheritance_noise_std : float
        Standard deviation of the stochastic per-division noise (>= 0).
        Default 0.0 — deterministic behaviour (v0.7-compatible).

    Raises
    ------
    ValueError
        If either parameter is negative.
    """

    def __init__(
        self,
        base_rules: InheritanceRules,
        asymmetry_strength:    float = 0.0,
        inheritance_noise_std: float = 0.0,
    ) -> None:
        if asymmetry_strength < 0.0:
            raise ValueError(
                f"asymmetry_strength must be >= 0, got {asymmetry_strength}"
            )
        if inheritance_noise_std < 0.0:
            raise ValueError(
                f"inheritance_noise_std must be >= 0, got {inheritance_noise_std}"
            )
        self._base      = base_rules
        self._asym      = asymmetry_strength
        self._noise_std = inheritance_noise_std

    def inherit(
        self,
        parent: Cell,
        daughter_index: int,
        event: DivisionEvent,
        rng=None,
    ) -> DaughterState:
        """Return DaughterState with base rules applied, then stochastic epigenetic shift.

        Parameters
        ----------
        daughter_index : int
            0 → bias shifted downward (more self-renewal).
            1 → bias shifted upward (more differentiation).
        rng : numpy.random.Generator or None
            Engine RNG.  When provided and ``inheritance_noise_std > 0``,
            a Gaussian noise term is sampled and added to the deterministic
            shift.  When ``None``, only ``asymmetry_strength`` applies.
        """
        ds = self._base.inherit(parent, daughter_index, event, rng)
        s  = ds.internal_state

        # Stochastic shift: deterministic component + optional Gaussian noise.
        if rng is not None and self._noise_std > 0.0:
            noise = float(rng.normal(0.0, self._noise_std))
        else:
            noise = 0.0
        total_shift = self._asym + noise

        if daughter_index == 0:
            new_bias = max(-1.0, min(1.0, parent.internal_state.epigenetic_bias - total_shift))
        else:
            new_bias = max(-1.0, min(1.0, parent.internal_state.epigenetic_bias + total_shift))

        return DaughterState(
            internal_state=InternalState(
                stemness_score=s.stemness_score,
                stress_score=s.stress_score,
                division_count=s.division_count,
                epigenetic_bias=new_bias,
            ),
            centriole_state=ds.centriole_state,
        )
