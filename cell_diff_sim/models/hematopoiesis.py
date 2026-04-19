"""Hematopoiesis differentiation model — v0.12 (selective density control).

Implements AbstractModel for the 8-state hematopoiesis tree:

    HSC
    └── MPP
        ├── CMP
        │   ├── Myeloid     (terminal)
        │   └── Erythroid   (terminal)
        └── CLP
            ├── B_cell      (terminal)
            └── T_cell      (terminal)

v0.9 changes from v0.8
-----------------------
**Fate-driven division (decision-based lineage branching):**

- ``DifferentiationEvent`` is removed entirely.  All cell-type transitions
  now happen exclusively through ``DivisionEvent``.
- Division fates are defined per cell type in the ``division_fates`` config
  section.  Each fate specifies a pair of daughter cell types and a base
  weight (unnormalised probability).
- Before selecting a fate, weights are modulated by the niche signal (M6.2
  generalised to per-fate commitment strength):

      niche             = 1 − n / target
      commitment        = count of daughters ≠ parent type
      modifier          = exp(−k · niche · stemness · commitment)
      weight_eff        = base_weight × modifier

  Underpopulation (niche > 0) suppresses commitment;
  overpopulation  (niche < 0) enhances commitment.

- All weights are normalised before use.  The total division rate per cell
  remains ``effective_div = base_div × div_factor × density_factor`` (M6.4),
  unchanged from v0.8.

- Terminal cell types (zero division rate, no fate table) can only undergo
  apoptosis.  ``get_events()`` emits no division events for them.

v0.12 changes from v0.11
-----------------------
**M6.5: Selective density control (structural fix):**

- In v0.11 the density factor was applied globally to ``effective_div``,
  which scales ALL fates equally — including committed (differentiating)
  ones.  This caused a structural collapse: suppressing committed division
  reduces mature-cell production, weakens the apoptosis sink, and lets
  the equilibrium float far above target despite strong density factors.

- In v0.12 the density factor is applied **only to self-renewal fates**
  (commitment == 0, i.e. both daughters == parent type).  Committed fates
  (asymmetric or fully differentiated) are emitted at the base rate,
  preserving the differentiation flux and mature-cell apoptosis sink.

  Per-fate application::

      commitment = number of daughters != parent_type
      if commitment == 0:
          rate_i = base_rate_i * density_factor   # self-renewal suppressed
      else:
          rate_i = base_rate_i                    # committed fates intact

  The hybrid density formula is **unchanged** from v0.11::

      delta          = (target - n) / target
      density_factor = exp(gamma * delta) * (target / n) ** beta
      density_factor = clamp(density_factor, 0.01, 10.0)

  This is not a parameter-tuning step; it is an architectural correction
  that aligns the density signal with its intended biological meaning:
  *niche occupancy limits stem-cell self-renewal, not lineage output*.

v0.11 changes (carried forward)
-----------------------
**Hybrid density controller (M6.4 upgrade):**

  ``gamma`` drives smooth exponential recovery (symmetric around n=target).
  ``beta`` is the power-law anchor term (asymmetric; v0.11).
  When beta=0: reduces to v0.10 pure-exp.  When gamma=0: pure PL (v0.9).

New config key: ``population_dynamics.density_beta``.
New CLI flag:   ``--density-beta``.

v0.10 changes (carried forward)
-----------------------
M4: safety-only crowding apoptosis (fires above crowding_threshold * target).
M6.4: soft exponential division controller (now extended with beta anchor).

v0.8 changes (carried forward)
-----------------------
M4: density-dependent apoptosis.
M5: stochastic epigenetic inheritance (per-division Gaussian noise).
M6.2: niche-dependent fate modulation (now generalised to per-fate weights).
M6.4: population-size control via division scaling.

v0.7 changes (carried forward)
-----------------------
Epigenetic memory layer: heritable ``epigenetic_bias`` field.
Centered bias signal (bias_eff = bias − mean_pop_bias).

v0.5 behaviour (carried forward)
----------------------------------
PDMP: deterministic drift between stochastic events.

Rates are loaded from a config dict matching
``configs/hematopoiesis_baseline.yaml`` or any compatible YAML.
"""

from __future__ import annotations

import math
from dataclasses import replace as _dc_replace
from enum import Enum
from typing import TYPE_CHECKING

from cell_diff_sim.engine.events import (
    ApoptosisEvent,
    DivisionEvent,
)
from cell_diff_sim.models.base import AbstractModel
from cell_diff_sim.models.inheritance import (
    AsymmetricInheritanceRules,
    CentrioleInheritanceRules,
    EpigeneticInheritanceWrapper,
    InheritanceRules,
    SymmetricInheritanceRules,
)
from cell_diff_sim.models.rate_modulation import ModulationParams, RateModulator
from cell_diff_sim.models.state_evolution import StateEvolutionParams, StateEvolutionRules

if TYPE_CHECKING:
    from cell_diff_sim.cell import Cell, CellType
    from cell_diff_sim.engine.events import Event
    from cell_diff_sim.population import Population


# ---------------------------------------------------------------------------
# Cell type enum
# ---------------------------------------------------------------------------

class HCellType(str, Enum):
    """Cell types in the hematopoiesis model.

    Inherits from ``str`` so each value is a plain string and satisfies
    the ``CellType = str`` alias defined in :mod:`cell`.
    Compatible with Python 3.10+ (StrEnum requires 3.11).
    """

    HSC       = "HSC"
    MPP       = "MPP"
    CMP       = "CMP"
    CLP       = "CLP"
    Myeloid   = "Myeloid"
    Erythroid = "Erythroid"
    B_cell    = "B_cell"
    T_cell    = "T_cell"


# Cell types that cannot differentiate further (terminal / mature)
_TERMINAL: frozenset[HCellType] = frozenset({
    HCellType.Myeloid,
    HCellType.Erythroid,
    HCellType.B_cell,
    HCellType.T_cell,
})


# ---------------------------------------------------------------------------
# Rate table types
# ---------------------------------------------------------------------------

# scalar rate per cell type
_ScalarRates = dict[HCellType, float]

# division_fates[source] = [(daughters_tuple, base_weight), ...]
_FateEntry  = tuple[tuple[HCellType, HCellType], float]
_DivFates   = dict[HCellType, list[_FateEntry]]


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class HematopoiesisModel(AbstractModel):
    """v0.9 hematopoiesis model: fate-driven division.

    All cell-type transitions happen through DivisionEvent.  The
    ``division_fates`` config section defines weighted fate choices per cell
    type; the niche signal (M6.2) modulates per-fate weights at runtime.

    .. warning::
        All rate values are **placeholder values for structural testing only**.
        They are NOT biologically calibrated.  Do not interpret simulation
        outputs as quantitative predictions.

    Parameters
    ----------
    config : dict
        Parsed YAML config dict.  Key sections:
        ``division_fates``, ``division_rates``, ``apoptosis_rates``.
        Optional: ``state_modulation``, ``inheritance``, ``state_evolution``,
        ``epigenetic``, ``population_dynamics``.
    """

    def __init__(self, config: dict) -> None:
        self._config = config

        # Placeholder — overwritten by _parse_config()
        self._inheritance_rules: InheritanceRules = SymmetricInheritanceRules()

        # Rate tables — populated by _parse_config()
        self._division_rates:  _ScalarRates = {}
        self._apoptosis_rates: _ScalarRates = {}

        # v0.9: fate tables — populated by _parse_config()
        # division_fates[cell_type] = [(daughters_tuple, base_weight), ...]
        self._division_fates: _DivFates = {}

        # Rate modulator — populated by _parse_config()
        self._modulator: RateModulator = RateModulator(ModulationParams())

        # Lifetime state evolution rules (v0.5)
        self._evolution_rules: StateEvolutionRules = StateEvolutionRules(
            StateEvolutionParams()
        )

        # v0.7: population mean-bias cache for centered epigenetic signal.
        self._mean_bias_cached: float = 0.0
        self._mean_bias_stale: bool   = True

        # v0.8 M4: density-dependent apoptosis (safety-only from v0.10).
        # Active only when n > crowding_threshold * target (runaway guard).
        self._target_population_size: int   = 0
        self._crowding_apoptosis_rate: float = 0.0
        self._crowding_threshold: float      = 1.2   # M4 activates above this ratio

        # v0.8/v0.9 M6.2: niche strength k for per-fate weight modulation.
        # modifier = exp(-k * niche * stemness * commitment_strength)
        self._niche_strength: float = 0.0

        # v0.12 M6.4 + M6.5: hybrid density controller (formula) +
        # selective application (per-fate commitment gate).
        #
        # Formula (unchanged from v0.11):
        #   density_factor = exp(gamma * delta) * (target / n) ** beta
        #   delta = (target - n) / target
        #   clamped to [0.01, 10.0]
        #
        # Application (v0.12 change):
        #   commitment == 0 fates: rate *= density_factor  (self-renewal only)
        #   commitment >  0 fates: rate unchanged          (committed preserved)
        #
        # When beta=0: exp-only term.  When gamma=0: PL-only term.
        self._density_gamma: float = 0.0
        self._density_beta:  float = 0.0

        self._parse_config(config)

    # ------------------------------------------------------------------
    # AbstractModel interface
    # ------------------------------------------------------------------

    @property
    def cell_types(self) -> list[CellType]:
        return list(HCellType)

    @property
    def inheritance_rules(self) -> InheritanceRules:
        return self._inheritance_rules

    def get_events(
        self,
        cell: Cell,
        population: Population,
    ) -> list[tuple[float, Event]]:
        """Return all possible events for ``cell`` with their rates.

        v0.9 architecture
        -----------------
        **No DifferentiationEvent is emitted.**  All cell-type transitions
        happen through DivisionEvent.  ``division_fates`` defines one or more
        fate pairs per cell type; each fate is emitted as a separate
        DivisionEvent with rate = ``effective_div * norm_weight_i``.

        Fate weight modulation (M6.2 generalised):
          niche      = 1 − n / target
          commitment = count of daughters ≠ parent type
          modifier   = exp(−k · niche · stemness · commitment)
          weight_eff = base_weight × modifier
        Then weights are normalised so sum = 1; rates sum to effective_div.

        M6.4 + M6.5 selective density controller (v0.12):
          delta          = (target - n) / target
          density_factor = exp(gamma * delta) * (target / n) ** beta
          density_factor = clamp(density_factor, 0.01, 10.0)

          Applied per fate (NOT to effective_div globally):
            commitment == 0 -> rate_i *= density_factor   (self-renewal only)
            commitment >  0 -> rate_i unchanged            (committed fates)

          Preserves differentiation flux and mature-cell apoptosis sink.

        M4 safety-only crowding apoptosis (v0.10):
          Activates only when n > crowding_threshold · target.
          Handles runaway growth; inactive in normal operation.

        Parameters
        ----------
        cell : Cell
        population : Population

        Returns
        -------
        list[tuple[float, Event]]
        """
        events: list[tuple[float, Event]] = []
        ct: HCellType = cell.cell_type  # type: ignore[assignment]
        state = cell.internal_state

        # v0.7: centered epigenetic bias — computed once per Gillespie step.
        if self._mean_bias_stale:
            n_pop = len(population)
            self._mean_bias_cached = (
                sum(c.internal_state.epigenetic_bias for c in population) / n_pop
                if n_pop else 0.0
            )
            self._mean_bias_stale = False

        # State-dependent division multiplier (v0.2 RateModulator).
        div_factor = self._modulator.division_factor(state)
        apo_factor = self._modulator.apoptosis_factor(state)

        # Cached population count (used in both division and apoptosis blocks).
        _n = len(population)

        # --- Fate-driven division ----------------------------------------
        base_div = self._division_rates.get(ct, 0.0)
        effective_div = base_div * div_factor

        # M6.4: hybrid density formula (v0.11) — computed here, NOT applied
        # globally to effective_div.  M6.5 (below) applies it per-fate.
        #   delta          = (target - n) / target
        #   density_factor = exp(gamma * delta) * (target / n) ** beta
        #   clamped to [0.01, 10.0]
        #   _n_safe guards against zero-pop divide in the power-law term.
        _density_factor = 1.0
        if self._target_population_size > 0 and (
            self._density_gamma > 0.0 or self._density_beta > 0.0
        ):
            _n_safe = max(1, _n)
            _delta  = (self._target_population_size - _n) / self._target_population_size
            _f_exp  = math.exp(self._density_gamma * _delta) if self._density_gamma > 0.0 else 1.0
            _f_pl   = (self._target_population_size / _n_safe) ** self._density_beta \
                      if self._density_beta > 0.0 else 1.0
            _density_factor = max(0.01, min(10.0, _f_exp * _f_pl))

        if effective_div > 0.0:
            fates = self._division_fates.get(ct)
            if fates:
                # Compute niche signal for M6.2 per-fate weight modulation.
                # niche > 0: underpopulated → suppress commitment (high-commitment
                #            fates get modifier < 1)
                # niche < 0: overpopulated  → enhance commitment (modifier > 1)
                _k = self._niche_strength
                if _k > 0.0 and self._target_population_size > 0:
                    _niche = 1.0 - _n / self._target_population_size
                else:
                    _niche = 0.0

                # Compute niche-modulated weights and per-fate commitment counts.
                # commitment = number of daughters != parent cell type.
                # Both stored in parallel lists for M6.5 selective application.
                eff_weights: list[float] = []
                commitments: list[int]   = []
                for (daughters, base_w) in fates:
                    commitment = sum(1 for d in daughters if d != ct)
                    commitments.append(commitment)
                    if _k > 0.0 and self._target_population_size > 0:
                        modifier = math.exp(
                            -_k * _niche * state.stemness_score * commitment
                        )
                        modifier = max(1e-6, min(1e6, modifier))
                    else:
                        modifier = 1.0
                    eff_weights.append(base_w * modifier)

                total_w = sum(eff_weights)
                if total_w > 0.0:
                    inv_total = effective_div / total_w
                    for (daughters, _), w, c in zip(fates, eff_weights, commitments):
                        # M6.5: selective density control (v0.12).
                        # Suppresses ONLY self-renewal fates (c == 0).
                        # Committed fates (c > 0) bypass density control,
                        # preserving differentiation flux and the mature-cell
                        # apoptosis sink that anchors total population size.
                        rate = w * inv_total * (_density_factor if c == 0 else 1.0)
                        if rate > 0.0:
                            events.append((rate, DivisionEvent(daughter_cell_types=daughters)))
            else:
                # No fates defined for this type: symmetric self-renewal fallback.
                # Self-renewal by definition — density factor applied.
                events.append((
                    effective_div * _density_factor,
                    DivisionEvent(daughter_cell_types=(ct, ct)),
                ))

        # --- Apoptosis -------------------------------------------------------
        base_apo = self._apoptosis_rates.get(ct, 0.0)
        effective_apo = base_apo * apo_factor

        # M4: safety-only crowding apoptosis (v0.10).
        # Active only when n > crowding_threshold * target (runaway guard).
        # In normal operation (n ≤ threshold * target) this term is zero;
        # M6.4 exponential controller handles regulation.
        if self._target_population_size > 0:
            _ratio = _n / self._target_population_size
            if _ratio > self._crowding_threshold:
                effective_apo += self._crowding_apoptosis_rate * (
                    _ratio - self._crowding_threshold
                )

        if effective_apo > 0.0:
            events.append((effective_apo, ApoptosisEvent()))

        return events

    def apply(
        self,
        event: Event,
        cell: Cell,
        population: Population,
    ) -> None:
        """Apply a non-division event to the population.

        v0.9: only ApoptosisEvent is handled here.  DifferentiationEvent has
        been removed — all cell-type transitions happen inside DivisionEvent.
        Receiving a DivisionEvent here is a routing error and raises TypeError.

        Parameters
        ----------
        event : Event
        cell : Cell
        population : Population
        """
        if isinstance(event, ApoptosisEvent):
            population.remove(cell.id)
        elif isinstance(event, DivisionEvent):
            raise TypeError(
                "HematopoiesisModel.apply() must not receive a DivisionEvent. "
                "Division is handled exclusively by DivisionHandler."
            )
        else:
            raise TypeError(
                f"HematopoiesisModel.apply() received unknown event type: "
                f"{type(event).__name__}"
            )

    # ------------------------------------------------------------------
    # Config parsing
    # ------------------------------------------------------------------

    def _parse_config(self, config: dict) -> None:
        """Parse the YAML config dict into rate tables and rules.

        v0.9: parses ``division_fates`` (new) instead of
        ``differentiation_rates`` (removed).

        Parameters
        ----------
        config : dict
            Parsed YAML.

        Raises
        ------
        ValueError
            If any rate or weight value is negative, or if a cell-type string
            is not a valid HCellType member.
        """
        # --- Division rates (scalar, per cell type) -------------------------
        raw_div: dict = config.get("division_rates", {})
        for ct_str, rate in raw_div.items():
            r = float(rate)
            if r < 0.0:
                raise ValueError(f"Negative division rate for {ct_str}: {r}")
            self._division_rates[HCellType(ct_str)] = r

        # --- Apoptosis rates ------------------------------------------------
        raw_apo: dict = config.get("apoptosis_rates", {})
        for ct_str, rate in raw_apo.items():
            r = float(rate)
            if r < 0.0:
                raise ValueError(f"Negative apoptosis rate for {ct_str}: {r}")
            self._apoptosis_rates[HCellType(ct_str)] = r

        # --- v0.9: Division fate tables ------------------------------------
        # division_fates[source] = [(daughters_tuple, base_weight), ...]
        # Weights are stored un-normalised; normalisation happens per-call
        # in get_events() after niche modulation.
        raw_fates: dict = config.get("division_fates", {})
        for src_str, fate_list in raw_fates.items():
            src = HCellType(src_str)
            if fate_list is None:
                continue
            parsed: list[_FateEntry] = []
            for entry in fate_list:
                weight = float(entry["weight"])
                if weight < 0.0:
                    raise ValueError(
                        f"Negative fate weight for {src_str}: {weight}"
                    )
                d_raw = entry["daughters"]
                d0 = HCellType(d_raw[0])
                d1 = HCellType(d_raw[1])
                parsed.append(((d0, d1), weight))
            self._division_fates[src] = parsed

        # --- State modulation (v0.2, optional) -----------------------------
        raw_mod: dict = config.get("state_modulation", {})
        if raw_mod:
            params = ModulationParams(**{k: float(v) for k, v in raw_mod.items()})
            self._modulator = RateModulator(params)

        # --- Inheritance rules (v0.3+, optional) ---------------------------
        raw_inh: dict = config.get("inheritance", {})
        mode: str = raw_inh.get("mode", "symmetric")

        if mode == "symmetric":
            self._inheritance_rules = SymmetricInheritanceRules()
        elif mode == "asymmetric":
            delta        = float(raw_inh.get("stemness_asymmetry", 0.0))
            stress_delta = float(raw_inh.get("stress_asymmetry", 0.0))
            self._inheritance_rules = AsymmetricInheritanceRules(
                stemness_asymmetry=delta,
                stress_asymmetry=stress_delta,
            )
        elif mode == "centriole":
            factor        = float(raw_inh.get("centriole_stemness_factor", 0.0))
            stress_factor = float(raw_inh.get("centriole_stress_factor", 0.0))
            cap           = int(raw_inh.get("centriole_age_cap", 10))
            self._inheritance_rules = CentrioleInheritanceRules(
                centriole_stemness_factor=factor,
                centriole_stress_factor=stress_factor,
                centriole_age_cap=cap,
            )
        else:
            raise ValueError(
                f"Unknown inheritance mode: {mode!r}. "
                "Expected 'symmetric', 'asymmetric', or 'centriole'."
            )

        # --- Lifetime state evolution (v0.5, optional) ----------------------
        raw_evo: dict = config.get("state_evolution", {})
        stress_rate   = float(raw_evo.get("stress_accumulation_rate", 0.0)) if raw_evo else 0.0
        stemness_rate = float(raw_evo.get("stemness_drift_rate", 0.0))       if raw_evo else 0.0

        # --- Epigenetic memory layer (v0.7/v0.8, optional) ------------------
        raw_epi: dict = config.get("epigenetic", {})
        epi_enabled   = bool(raw_epi.get("enabled", False)) if raw_epi else False
        epi_noise_std = float(raw_epi.get("inheritance_noise",  0.0)) if raw_epi else 0.0
        epi_asym      = float(raw_epi.get("asymmetry_strength", 0.0)) if raw_epi else 0.0
        epi_drift     = float(raw_epi.get("drift_rate",         0.0)) if raw_epi else 0.0

        self._evolution_rules = StateEvolutionRules(
            StateEvolutionParams(
                stress_accumulation_rate=stress_rate,
                stemness_drift_rate=stemness_rate,
                epigenetic_drift_rate=epi_drift,
            )
        )

        if epi_enabled:
            self._inheritance_rules = EpigeneticInheritanceWrapper(
                self._inheritance_rules,
                asymmetry_strength=epi_asym,
                inheritance_noise_std=epi_noise_std,
            )

        # --- Population dynamics: M4 (safety) + M6.2 (per-fate) + M6.4 (soft) --
        raw_pop: dict = config.get("population_dynamics", {})
        if raw_pop:
            self._target_population_size  = int(raw_pop.get("target_population_size",   0))
            self._crowding_apoptosis_rate = float(raw_pop.get("crowding_apoptosis_rate", 0.0))
            self._crowding_threshold      = float(raw_pop.get("crowding_threshold",       1.2))
            self._niche_strength          = float(raw_pop.get("niche_strength",           0.0))
            self._density_gamma           = float(raw_pop.get("density_gamma",            0.0))
            self._density_beta            = float(raw_pop.get("density_beta",             0.0))

    # ------------------------------------------------------------------
    # Lifetime dynamics (v0.5 PDMP hook)
    # ------------------------------------------------------------------

    @property
    def evolution_rules(self) -> StateEvolutionRules:
        return self._evolution_rules

    def evolve_cell_states(self, population: Population, dt: float) -> None:
        """Evolve all cells' ``InternalState`` for elapsed time ``dt``.

        Implements the deterministic drift component of the PDMP extension.
        Called by :class:`~engine.ctmc.CTMCEngine` on every Gillespie step.
        """
        # Invalidate mean-bias cache — biases change after each drift step.
        self._mean_bias_stale = True

        if self._evolution_rules.is_noop:
            return
        for cell in population:
            cell.internal_state = self._evolution_rules.evolve(
                cell.internal_state, dt
            )
