"""SimulationSession — step-by-step Gillespie engine wrapper.

Implements the same algorithm as CTMCEngine.run() but exposes a step(n_events)
method so the API can run the simulation in batches and stream results back.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Path: backend lives one level below the project root.
# In a PyInstaller frozen bundle __file__-based resolution is unreliable
# (the module may be stored relative to a different pathex entry).
# sys._MEIPASS is always the correct bundle root in that case.
# ---------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    # PyInstaller one-dir: extracted files live in sys._MEIPASS (_internal/)
    _PROJECT_ROOT = Path(sys._MEIPASS)
else:
    _BACKEND_DIR = Path(__file__).parent.parent
    _PROJECT_ROOT = _BACKEND_DIR.parent
sys.path.insert(0, str(_PROJECT_ROOT))

import yaml
from cell_diff_sim.cell import Cell
from cell_diff_sim.engine.division_handler import DivisionHandler
from cell_diff_sim.engine.events import DivisionEvent
from cell_diff_sim.models.hematopoiesis import HCellType, HematopoiesisModel
from cell_diff_sim.observers.recorder import Recorder
from cell_diff_sim.population import Population

ALL_TYPES = ["HSC", "MPP", "CMP", "CLP", "Myeloid", "Erythroid", "B_cell", "T_cell"]
MPP_MPP_WEIGHT    = 0.05
BASELINE_YAML     = _PROJECT_ROOT / "configs" / "hematopoiesis_baseline.yaml"
RECORD_INTERVAL   = 0.1            # snapshot every 0.1 simulated hours (6 minutes)


def _load_baseline() -> dict:
    with open(BASELINE_YAML, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def build_config(params: dict) -> dict:
    """Merge UI flat params dict on top of the baseline YAML config.

    Handles every parameter the frontend can send so that UI controls
    actually affect the simulation.  Sections applied in order:
      division fates → division/apoptosis rates → population dynamics
      → state evolution → state modulation → inheritance → epigenetic
    """
    cfg = _load_baseline()

    # ── Division fates ────────────────────────────────────────────────────────
    # Prefer explicit per-fate arrays (use_custom_division_fates=true);
    # fall back to the single self_renewal_weight scalar.
    if "division_fates_hsc" in params:
        w0, w1, w2 = [float(x) for x in params["division_fates_hsc"]]
        cfg["division_fates"]["HSC"] = [
            {"daughters": ["HSC", "HSC"], "weight": w0},
            {"daughters": ["HSC", "MPP"], "weight": w1},
            {"daughters": ["MPP", "MPP"], "weight": w2},
        ]
    else:
        sr       = float(params.get("self_renewal_weight", 0.825))
        hsc_asym = round(1.0 - sr - MPP_MPP_WEIGHT, 10)
        cfg["division_fates"]["HSC"] = [
            {"daughters": ["HSC", "HSC"], "weight": sr},
            {"daughters": ["HSC", "MPP"], "weight": hsc_asym},
            {"daughters": ["MPP", "MPP"], "weight": MPP_MPP_WEIGHT},
        ]

    if "division_fates_mpp" in params:
        w0, w1, w2, w3, w4 = [float(x) for x in params["division_fates_mpp"]]
        cfg["division_fates"]["MPP"] = [
            {"daughters": ["MPP", "MPP"], "weight": w0},
            {"daughters": ["MPP", "CMP"], "weight": w1},
            {"daughters": ["MPP", "CLP"], "weight": w2},
            {"daughters": ["CMP", "CMP"], "weight": w3},
            {"daughters": ["CLP", "CLP"], "weight": w4},
        ]

    # ── Division / apoptosis rates (per-type dicts) ───────────────────────────
    if "division_rates" in params:
        cfg.setdefault("division_rates", {}).update(
            {k: float(v) for k, v in params["division_rates"].items()}
        )
    if "apoptosis_rates" in params:
        cfg.setdefault("apoptosis_rates", {}).update(
            {k: float(v) for k, v in params["apoptosis_rates"].items()}
        )

    # ── Population dynamics ───────────────────────────────────────────────────
    pd_sec = cfg.setdefault("population_dynamics", {})
    if "target_population_size"  in params: pd_sec["target_population_size"]  = int(float(params["target_population_size"]))
    if "density_gamma"           in params: pd_sec["density_gamma"]           = float(params["density_gamma"])
    if "density_beta"            in params: pd_sec["density_beta"]            = float(params["density_beta"])
    if "niche_strength"          in params: pd_sec["niche_strength"]          = float(params["niche_strength"])
    if "crowding_threshold"      in params: pd_sec["crowding_threshold"]      = float(params["crowding_threshold"])
    if "crowding_apoptosis_rate" in params: pd_sec["crowding_apoptosis_rate"] = float(params["crowding_apoptosis_rate"])

    # Target population toggle — when disabled, zero all density regulation
    if not params.get("enable_target_population", True):
        pd_sec["density_gamma"]          = 0.0
        pd_sec["density_beta"]           = 0.0
        pd_sec["niche_strength"]         = 0.0
        pd_sec["target_population_size"] = 999_999  # effectively unlimited

    # ── State evolution (lifetime dynamics) ───────────────────────────────────
    ev_sec = cfg.setdefault("state_evolution", {})
    if "stress_accumulation_rate" in params: ev_sec["stress_accumulation_rate"] = float(params["stress_accumulation_rate"])
    if "stemness_drift_rate"      in params: ev_sec["stemness_drift_rate"]      = float(params["stemness_drift_rate"])

    # ── State modulation weights ──────────────────────────────────────────────
    sm_sec = cfg.setdefault("state_modulation", {})
    for k in ("w_div_stemness", "w_div_stress", "w_div_repl",
              "w_div_epigenetic",
              "w_apo_stress",   "w_apo_repl",
              "min_factor",     "max_factor"):
        if k in params:
            sm_sec[k] = float(params[k])

    # ── Inheritance rules ─────────────────────────────────────────────────────
    inh_sec = cfg.setdefault("inheritance", {})
    if "inheritance_mode"   in params: inh_sec["mode"]                     = str(params["inheritance_mode"])
    # Centriole-specific params
    if "stemness_factor"    in params: inh_sec["centriole_stemness_factor"] = float(params["stemness_factor"])
    if "stress_factor"      in params: inh_sec["centriole_stress_factor"]   = float(params["stress_factor"])
    if "age_cap"            in params: inh_sec["centriole_age_cap"]         = int(params["age_cap"])
    # Asymmetric-specific params
    if "stemness_asymmetry" in params: inh_sec["stemness_asymmetry"]        = float(params["stemness_asymmetry"])
    if "stress_asymmetry"   in params: inh_sec["stress_asymmetry"]          = float(params["stress_asymmetry"])

    # ── Epigenetic memory ─────────────────────────────────────────────────────
    epi_sec = cfg.setdefault("epigenetic", {})
    if "epigenetic_enabled"  in params: epi_sec["enabled"]            = bool(params["epigenetic_enabled"])
    if "inheritance_noise"   in params: epi_sec["inheritance_noise"]   = float(params["inheritance_noise"])
    if "asymmetry_strength"  in params: epi_sec["asymmetry_strength"]  = float(params["asymmetry_strength"])
    if "drift_rate"          in params: epi_sec["drift_rate"]          = float(params["drift_rate"])

    return cfg


class SimulationSession:
    """Holds one running simulation; supports step-by-step execution."""

    def __init__(
        self,
        session_id: str,
        config: dict,
        seed: int,
        t_max: float,
        params: dict,
    ) -> None:
        self.session_id  = session_id
        self.config      = config
        self.params      = params
        self.seed        = seed
        self.t_max       = t_max
        self.time        = 0.0
        self.finished    = False
        self.created_at  = datetime.now(timezone.utc)

        # Build simulation objects
        self.model = HematopoiesisModel(config)
        initial_counts: dict = config.get("initial_population", {"HSC": 10})
        cells = [
            Cell(cell_type=HCellType(ct))
            for ct, n in initial_counts.items()
            for _ in range(n)
        ]
        self.population        = Population(cells)
        self.recorder          = Recorder(track_states=True)
        self._next_record_t    = 0.0          # first grid point starts at t=0
        self.recorder.on_step(0.0, self.population)
        self._next_record_t    = RECORD_INTERVAL  # next grid point after t=0
        effective_seed = seed if seed > 0 else None
        self._division_handler = DivisionHandler()
        self._rng = np.random.default_rng(effective_seed)

    # ------------------------------------------------------------------
    # Core step
    # ------------------------------------------------------------------

    def step(self, n_events: int) -> dict:
        """Run up to n_events Gillespie steps; return current state dict."""
        if self.finished:
            return self._build_result(events_executed=0)

        events_done = 0
        for _ in range(n_events):
            if self.time >= self.t_max:
                self.finished = True
                break

            # 1. Collect propensities
            propensities: list = []
            for cell in self.population:
                for rate, event in self.model.get_events(cell, self.population):
                    propensities.append((rate, event, cell))

            if not propensities:
                self.finished = True
                break

            rates = [p[0] for p in propensities]
            total = sum(rates)
            if total == 0.0:
                self.finished = True
                break

            # 2. Time advance
            dt = self._rng.exponential(1.0 / total)
            if self.time + dt > self.t_max:
                self.time = self.t_max
                self.finished = True
                # Flush any remaining grid points up to t_max
                while self._next_record_t <= self.t_max:
                    self.recorder.on_step(self._next_record_t, self.population)
                    self._next_record_t += RECORD_INTERVAL
                break

            self.time += dt

            # 3. PDMP drift hook
            self.model.evolve_cell_states(self.population, dt)

            # 4. Select & dispatch event
            probs = [r / total for r in rates]
            idx   = int(self._rng.choice(len(propensities), p=probs))
            _, event, cell = propensities[idx]

            if isinstance(event, DivisionEvent):
                self._division_handler.execute(
                    event, cell, self.population,
                    self.model.inheritance_rules,
                    self.time, self._rng,
                )
            else:
                self.model.apply(event, cell, self.population)

            # 5. Record at uniform grid points (t=0.1, 0.2, 0.3, ...)
            #    Population is constant between Gillespie events, so recording
            #    the current population at the grid timestamp is exact.
            while self._next_record_t <= self.time:
                self.recorder.on_step(self._next_record_t, self.population)
                self._next_record_t += RECORD_INTERVAL
            events_done += 1

        return self._build_result(events_executed=events_done)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _current_states(self) -> dict:
        cells = list(self.population)
        n = len(cells)
        if n == 0:
            return {"mean_stemness": 0.0, "mean_stress": 0.0, "mean_bias": 0.0}
        return {
            "mean_stemness": round(sum(c.internal_state.stemness_score  for c in cells) / n, 4),
            "mean_stress":   round(sum(c.internal_state.stress_score    for c in cells) / n, 4),
            "mean_bias":     round(sum(c.internal_state.epigenetic_bias for c in cells) / n, 4),
        }

    def _current_population(self) -> dict:
        snap = self.population.snapshot()
        return {ct: snap.get(ct, 0) for ct in ALL_TYPES}

    def _build_result(self, events_executed: int) -> dict:
        pop = self._current_population()
        return {
            "time":             round(self.time, 4),
            "population":       pop,
            "states":           self._current_states(),
            "total":            sum(pop.values()),
            "finished":         self.finished,
            "events_executed":  events_executed,
        }

    def get_snapshot(self) -> dict:
        """Return current state + full history."""
        history = []
        for snap in self.recorder.snapshots:
            counts = {ct: snap.counts.get(ct, 0) for ct in ALL_TYPES}
            history.append({
                "time":       round(snap.time, 4),
                "population": counts,
                "states": {
                    "mean_stemness": round(snap.mean_stemness or 0.0, 4),
                    "mean_stress":   round(snap.mean_stress   or 0.0, 4),
                    "mean_bias":     round(snap.mean_bias     or 0.0, 4),
                },
                "total": snap.total,
            })
        pop = self._current_population()
        return {
            "session_id": self.session_id,
            "time":       round(self.time, 4),
            "population": pop,
            "states":     self._current_states(),
            "total":      sum(pop.values()),
            "finished":   self.finished,
            "history":    history,
        }

    def get_per_type_stats(self) -> dict:
        """Return mean stemness / stress / bias grouped by cell type."""
        from collections import defaultdict
        buckets: dict[str, list] = defaultdict(list)
        for cell in self.population:
            buckets[cell.cell_type.name].append(cell)
        result: dict = {}
        for ct, cells in buckets.items():
            n = len(cells)
            result[ct] = {
                "mean_stemness": round(sum(c.internal_state.stemness_score  for c in cells) / n, 4),
                "mean_stress":   round(sum(c.internal_state.stress_score    for c in cells) / n, 4),
                "mean_bias":     round(sum(c.internal_state.epigenetic_bias for c in cells) / n, 4),
            }
        return result

    def get_summary(self) -> dict:
        pop = self._current_population()
        return {
            "session_id":       self.session_id,
            "final_time":       round(self.time, 4),
            "final_population": pop,
            "summary_stats":    self._current_states(),
            "per_type_stats":   self.get_per_type_stats(),
        }

    def get_run_record(self) -> dict:
        import hashlib, json
        cfg_hash = hashlib.md5(
            json.dumps(self.params, sort_keys=True).encode()
        ).hexdigest()[:8]
        pop = self._current_population()
        return {
            "id":               self.session_id,
            "timestamp":        self.created_at.isoformat(),
            "seed":             self.seed,
            "config_hash":      cfg_hash,
            "final_total":      sum(pop.values()),
            "final_population": pop,
            "summary": self._current_states(),
        }
