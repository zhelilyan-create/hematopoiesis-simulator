"""Entry point for the hematopoiesis cell differentiation simulator — v0.9.

Usage
-----
    # YAML only — identical to v0.6 behaviour
    python scripts/run_sim.py --config configs/hematopoiesis_v06.yaml --seed 42

    # Override centriole stress factor (regime comparison, same seed)
    python scripts/run_sim.py --config configs/hematopoiesis_v06.yaml --centriole-stress-factor 0.0  --seed 42
    python scripts/run_sim.py --config configs/hematopoiesis_v06.yaml --centriole-stress-factor 0.05 --seed 42

    # Switch inheritance mode (ablation)
    python scripts/run_sim.py --config configs/hematopoiesis_v06.yaml --inheritance-mode symmetric --seed 42

    # Override initial HSC count and stress accumulation
    python scripts/run_sim.py --config configs/hematopoiesis_v06.yaml --initial-hsc 50 --stress-accumulation-rate 0.02 --seed 42

    # Save plot
    python scripts/run_sim.py --config configs/hematopoiesis_v06.yaml --seed 42 --plot-out results.png

Design
------
YAML is the base source of truth.  CLI arguments override selected values
*after* the YAML is loaded, *before* the model is constructed.  Passing no
override arguments produces behaviour identical to v0.6.

WARNING
-------
All rate values in the config are PLACEHOLDER values for structural testing.
They are NOT biologically calibrated.  Do not interpret outputs as
quantitative predictions.
"""

from __future__ import annotations

import argparse
import copy
from pathlib import Path


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a hematopoiesis cell differentiation simulation.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # --- General run parameters ---------------------------------------------
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/hematopoiesis_v06.yaml"),
        help="Path to the YAML configuration file.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility. Omit for random behaviour.",
    )
    parser.add_argument(
        "--t-max",
        type=float,
        default=100.0,
        help="Maximum simulation time (hours).",
    )
    parser.add_argument(
        "--plot-out",
        type=Path,
        default=None,
        metavar="PATH",
        help="Save a summary figure to this file (PNG, PDF, SVG, …). "
             "Requires matplotlib.",
    )
    parser.add_argument(
        "--initial-hsc",
        type=int,
        default=None,
        metavar="N",
        help="Override initial HSC count from YAML.",
    )

    # --- Inheritance mode ----------------------------------------------------
    parser.add_argument(
        "--inheritance-mode",
        type=str,
        default=None,
        choices=["symmetric", "asymmetric", "centriole"],
        metavar="MODE",
        help="Override inheritance.mode. Choices: symmetric, asymmetric, centriole.",
    )

    # --- Abstract asymmetric inheritance parameters -------------------------
    parser.add_argument(
        "--stemness-asymmetry",
        type=float,
        default=None,
        metavar="DELTA",
        help="Override inheritance.stemness_asymmetry (>= 0).",
    )
    parser.add_argument(
        "--stress-asymmetry",
        type=float,
        default=None,
        metavar="DELTA",
        help="Override inheritance.stress_asymmetry (>= 0). v0.6 extension.",
    )

    # --- Centriole parameters -----------------------------------------------
    parser.add_argument(
        "--centriole-stemness-factor",
        type=float,
        default=None,
        metavar="F",
        help="Override inheritance.centriole_stemness_factor (>= 0).",
    )
    parser.add_argument(
        "--centriole-stress-factor",
        type=float,
        default=None,
        metavar="F",
        help="Override inheritance.centriole_stress_factor (>= 0). v0.6 extension.",
    )
    parser.add_argument(
        "--centriole-age-cap",
        type=int,
        default=None,
        metavar="N",
        help="Override inheritance.centriole_age_cap (>= 1).",
    )

    # --- State evolution parameters -----------------------------------------
    parser.add_argument(
        "--stress-accumulation-rate",
        type=float,
        default=None,
        metavar="R",
        help="Override state_evolution.stress_accumulation_rate (>= 0).",
    )
    parser.add_argument(
        "--stemness-drift-rate",
        type=float,
        default=None,
        metavar="R",
        help="Override state_evolution.stemness_drift_rate (signed).",
    )

    # --- Rate modulation weights --------------------------------------------
    parser.add_argument(
        "--w-div-stemness",
        type=float,
        default=None,
        metavar="W",
        help="Override state_modulation.w_div_stemness.",
    )
    parser.add_argument(
        "--w-div-stress",
        type=float,
        default=None,
        metavar="W",
        help="Override state_modulation.w_div_stress.",
    )
    parser.add_argument(
        "--w-div-repl",
        type=float,
        default=None,
        metavar="W",
        help="Override state_modulation.w_div_repl.",
    )
    parser.add_argument(
        "--w-diff-stemness",
        type=float,
        default=None,
        metavar="W",
        help="Override state_modulation.w_diff_stemness.",
    )
    parser.add_argument(
        "--w-diff-stress",
        type=float,
        default=None,
        metavar="W",
        help="Override state_modulation.w_diff_stress.",
    )
    parser.add_argument(
        "--w-diff-repl",
        type=float,
        default=None,
        metavar="W",
        help="Override state_modulation.w_diff_repl.",
    )
    parser.add_argument(
        "--w-apo-stress",
        type=float,
        default=None,
        metavar="W",
        help="Override state_modulation.w_apo_stress.",
    )
    parser.add_argument(
        "--w-apo-repl",
        type=float,
        default=None,
        metavar="W",
        help="Override state_modulation.w_apo_repl.",
    )
    parser.add_argument(
        "--w-diff-epigenetic",
        type=float,
        default=None,
        metavar="W",
        help="Override state_modulation.w_diff_epigenetic. v0.7 extension.",
    )
    parser.add_argument(
        "--w-lineage-epigenetic",
        type=float,
        default=None,
        metavar="W",
        help="Override state_modulation.w_lineage_epigenetic. v0.7 lineage-selection bias.",
    )
    parser.add_argument(
        "--epigenetic-inheritance-noise",
        type=float,
        default=None,
        metavar="F",
        help="Override epigenetic.inheritance_noise (v0.8: std of per-division "
             "Gaussian noise). v0.7 epigenetic layer.",
    )
    parser.add_argument(
        "--epigenetic-asymmetry-strength",
        type=float,
        default=None,
        metavar="F",
        help="Override epigenetic.asymmetry_strength. v0.7 epigenetic layer.",
    )

    # --- Population dynamics (v0.8 M4 + M6) ----------------------------------
    parser.add_argument(
        "--target-population-size",
        type=int,
        default=None,
        metavar="N",
        help="Override population_dynamics.target_population_size. "
             "Shared reference for M4 (crowding apoptosis) and M6 (niche bias). v0.8.",
    )
    parser.add_argument(
        "--crowding-apoptosis-rate",
        type=float,
        default=None,
        metavar="R",
        help="Override population_dynamics.crowding_apoptosis_rate. "
             "Rate coefficient for crowding pressure above target size (M4). v0.8.",
    )
    parser.add_argument(
        "--niche-strength",
        type=float,
        default=None,
        metavar="K",
        help="Override population_dynamics.niche_strength. "
             "v0.9 M6.2: per-fate weight modifier = exp(-k*niche*stemness*commitment). "
             "k=0 disables niche modulation.",
    )
    parser.add_argument(
        "--density-gamma",
        type=float,
        default=None,
        metavar="G",
        help="Override population_dynamics.density_gamma. "
             "M6.4 (v0.11): hybrid controller exp term. "
             "density_factor = exp(gamma*(target-n)/target) * (target/n)^beta. "
             "Typical range 0–4.",
    )
    parser.add_argument(
        "--density-beta",
        type=float,
        default=None,
        metavar="B",
        help="Override population_dynamics.density_beta. "
             "M6.4 (v0.11): hybrid controller power-law anchor term. "
             "density_factor = exp(gamma*delta) * (target/n)^beta. "
             "beta=0 -> pure exp (v0.10). beta>0 anchors equilibrium at target. "
             "Typical range 0–4.",
    )
    parser.add_argument(
        "--crowding-threshold",
        type=float,
        default=None,
        metavar="T",
        help="Override population_dynamics.crowding_threshold. "
             "M4 safety apoptosis activates only when n > T*target. "
             "Default 1.2 (120%% of target). v0.10.",
    )

    # --- State tracking -------------------------------------------------------
    parser.add_argument(
        "--track-states",
        action="store_true",
        default=False,
        help="Track and report per-step mean stemness/stress/bias distributions. v0.8.",
    )

    return parser.parse_args()


# ---------------------------------------------------------------------------
# Config override logic
# ---------------------------------------------------------------------------

def apply_overrides(
    config: dict,
    args: argparse.Namespace,
) -> tuple[dict, list[str]]:
    """Apply CLI overrides to a config dict, returning a patched copy.

    Parameters
    ----------
    config : dict
        The config dict loaded from YAML.  **Not mutated** — a deep copy is
        made before any override is applied.
    args : argparse.Namespace
        Parsed CLI arguments.  Any argument whose value is ``None`` is
        treated as "not supplied" and produces no override.

    Returns
    -------
    patched_config : dict
        A deep copy of ``config`` with CLI overrides applied.
    overrides : list[str]
        Human-readable description of every override that was applied, in
        the order they were applied.  Empty if no overrides were requested.

    Design notes
    ------------
    - YAML is the base source of truth.  This function only *patches*; it
      never replaces the full config.
    - ``dict.setdefault()`` is used to create missing sections (e.g. a YAML
      without a ``state_evolution`` section can still receive an override for
      ``stress_accumulation_rate``).
    - All validation (negative rates, unknown modes, etc.) is delegated to
      ``HematopoiesisModel.__init__`` as it always was — this function does
      not re-validate.
    """
    cfg = copy.deepcopy(config)
    overrides: list[str] = []

    def _set(section: str, key: str, value: object) -> None:
        cfg.setdefault(section, {})[key] = value
        overrides.append(f"{section}.{key} = {value!r}")

    # --- General run parameters (non-section) --------------------------------
    if args.initial_hsc is not None:
        cfg.setdefault("initial_population", {})["HSC"] = args.initial_hsc
        overrides.append(f"initial_population.HSC = {args.initial_hsc!r}")

    # --- Inheritance ---------------------------------------------------------
    if args.inheritance_mode is not None:
        _set("inheritance", "mode", args.inheritance_mode)
    if args.stemness_asymmetry is not None:
        _set("inheritance", "stemness_asymmetry", args.stemness_asymmetry)
    if args.stress_asymmetry is not None:
        _set("inheritance", "stress_asymmetry", args.stress_asymmetry)
    if args.centriole_stemness_factor is not None:
        _set("inheritance", "centriole_stemness_factor", args.centriole_stemness_factor)
    if args.centriole_stress_factor is not None:
        _set("inheritance", "centriole_stress_factor", args.centriole_stress_factor)
    if args.centriole_age_cap is not None:
        _set("inheritance", "centriole_age_cap", args.centriole_age_cap)

    # --- State evolution -----------------------------------------------------
    if args.stress_accumulation_rate is not None:
        _set("state_evolution", "stress_accumulation_rate", args.stress_accumulation_rate)
    if args.stemness_drift_rate is not None:
        _set("state_evolution", "stemness_drift_rate", args.stemness_drift_rate)

    # --- Rate modulation weights ---------------------------------------------
    if args.w_div_stemness is not None:
        _set("state_modulation", "w_div_stemness", args.w_div_stemness)
    if args.w_div_stress is not None:
        _set("state_modulation", "w_div_stress", args.w_div_stress)
    if args.w_div_repl is not None:
        _set("state_modulation", "w_div_repl", args.w_div_repl)
    if args.w_diff_stemness is not None:
        _set("state_modulation", "w_diff_stemness", args.w_diff_stemness)
    if args.w_diff_stress is not None:
        _set("state_modulation", "w_diff_stress", args.w_diff_stress)
    if args.w_diff_repl is not None:
        _set("state_modulation", "w_diff_repl", args.w_diff_repl)
    if args.w_apo_stress is not None:
        _set("state_modulation", "w_apo_stress", args.w_apo_stress)
    if args.w_apo_repl is not None:
        _set("state_modulation", "w_apo_repl", args.w_apo_repl)
    if args.w_diff_epigenetic is not None:
        _set("state_modulation", "w_diff_epigenetic", args.w_diff_epigenetic)
    if args.w_lineage_epigenetic is not None:
        _set("state_modulation", "w_lineage_epigenetic", args.w_lineage_epigenetic)
    if args.epigenetic_inheritance_noise is not None:
        cfg.setdefault("epigenetic", {})["enabled"] = True
        _set("epigenetic", "inheritance_noise", args.epigenetic_inheritance_noise)
    if args.epigenetic_asymmetry_strength is not None:
        cfg.setdefault("epigenetic", {})["enabled"] = True
        _set("epigenetic", "asymmetry_strength", args.epigenetic_asymmetry_strength)

    # --- Population dynamics (v0.8 M4 + M6) ----------------------------------
    if args.target_population_size is not None:
        _set("population_dynamics", "target_population_size", args.target_population_size)
    if args.crowding_apoptosis_rate is not None:
        _set("population_dynamics", "crowding_apoptosis_rate", args.crowding_apoptosis_rate)
    if args.niche_strength is not None:
        _set("population_dynamics", "niche_strength", args.niche_strength)
    if args.density_gamma is not None:
        _set("population_dynamics", "density_gamma", args.density_gamma)
    if args.density_beta is not None:
        _set("population_dynamics", "density_beta", args.density_beta)
    if args.crowding_threshold is not None:
        _set("population_dynamics", "crowding_threshold", args.crowding_threshold)

    return cfg, overrides


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_separator() -> None:
    print("=" * 60)


def _print_composition(counts: dict, total: int, indent: int = 4) -> None:
    pad = " " * indent
    for ct in sorted(counts):
        n = counts[ct]
        pct = 100.0 * n / total if total else 0.0
        print(f"{pad}{ct:<14} {n:>6}  ({pct:5.1f}%)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    import yaml

    from cell_diff_sim.cell import Cell
    from cell_diff_sim.engine.ctmc import CTMCEngine
    from cell_diff_sim.models.hematopoiesis import HCellType, HematopoiesisModel
    from cell_diff_sim.observers.recorder import Recorder
    from cell_diff_sim.population import Population

    args = parse_args()

    # --- Load config ---------------------------------------------------------
    raw_config = yaml.safe_load(args.config.read_text())

    # --- Apply CLI overrides (YAML is unchanged; a patched copy is returned) -
    config, overrides = apply_overrides(raw_config, args)

    # --- Build model ---------------------------------------------------------
    model = HematopoiesisModel(config)

    # --- Build initial population --------------------------------------------
    initial_counts: dict = config.get("initial_population", {"HSC": 10})
    initial_cells: list[Cell] = [
        Cell(cell_type=HCellType(ct_str))
        for ct_str, n in initial_counts.items()
        for _ in range(n)
    ]
    population = Population(initial_cells)
    n_initial = len(population)

    # --- Attach recorder and record t=0 snapshot ----------------------------
    recorder = Recorder(track_states=args.track_states)
    recorder.on_step(0.0, population)

    # --- Print header --------------------------------------------------------
    _print_separator()
    print("HEMATOPOIESIS SIMULATION  v0.9  [NON-CALIBRATED RATES]")
    _print_separator()
    print(f"  Config : {args.config}")
    print(f"  Seed   : {args.seed}")
    print(f"  t_max  : {args.t_max} h")
    if overrides:
        print(f"  Overrides ({len(overrides)}):")
        for line in overrides:
            print(f"    {line}")
    else:
        print("  Overrides : none")
    print(f"\nInitial population  (n={n_initial}, t=0 h):")
    _print_composition(population.snapshot(), n_initial)

    # --- Run -----------------------------------------------------------------
    engine = CTMCEngine(model, population, observers=[recorder], rng_seed=args.seed)
    engine.run(t_max=args.t_max)

    # --- Report --------------------------------------------------------------
    n_final = len(population)
    final_snapshot = population.snapshot()
    n_events = len(recorder) - 1   # subtract the manual t=0 entry

    print(f"\nSimulation ended at t = {engine.time:.4f} h")
    print(f"Events recorded : {n_events}")
    print(f"\nFinal population  (n={n_final}, t={engine.time:.2f} h):")
    _print_composition(final_snapshot, n_final)
    _print_separator()

    # --- Epigenetic bias statistics ------------------------------------------
    import statistics
    biases = [cell.internal_state.epigenetic_bias for cell in population]
    if biases:
        n_b  = len(biases)
        mean = statistics.mean(biases)
        std  = statistics.stdev(biases) if n_b > 1 else 0.0
        mn   = min(biases)
        mx   = max(biases)
        sorted_b = sorted(biases)
        def _pct(p):
            idx = max(0, min(n_b - 1, int(p / 100 * n_b)))
            return sorted_b[idx]
        p10 = _pct(10)
        p50 = _pct(50)
        p90 = _pct(90)
        f01 = 100.0 * sum(1 for b in biases if abs(b) > 0.1) / n_b
        f02 = 100.0 * sum(1 for b in biases if abs(b) > 0.2) / n_b
        print(f"Epigenetic bias stats (n={n_b}):")
        print(f"  mean={mean:+.4f}  std={std:.4f}  min={mn:+.4f}  max={mx:+.4f}")
        print(f"  p10={p10:+.4f}  p50={p50:+.4f}  p90={p90:+.4f}")
        print(f"  |bias|>0.1: {f01:.1f}%   |bias|>0.2: {f02:.1f}%")

    # --- State distribution summary (v0.8, optional) ------------------------
    if args.track_states and n_final > 0:
        cells_final = list(population)
        n_f = len(cells_final)
        m_stem  = sum(c.internal_state.stemness_score  for c in cells_final) / n_f
        m_stress = sum(c.internal_state.stress_score   for c in cells_final) / n_f
        m_bias  = sum(c.internal_state.epigenetic_bias for c in cells_final) / n_f
        # Time-series summary from recorder (subsample last 20% of events)
        snaps = recorder.snapshots
        tail_start = max(0, int(0.8 * len(snaps)))
        tail_snaps = snaps[tail_start:]
        if tail_snaps and tail_snaps[0].mean_stemness is not None:
            ts_stem   = [s.mean_stemness  for s in tail_snaps if s.mean_stemness  is not None]
            ts_stress = [s.mean_stress    for s in tail_snaps if s.mean_stress    is not None]
            ts_bias   = [s.mean_bias      for s in tail_snaps if s.mean_bias      is not None]
            ts_size   = [s.total          for s in tail_snaps]
            mean_ts_stem   = sum(ts_stem)   / len(ts_stem)   if ts_stem   else float("nan")
            mean_ts_stress = sum(ts_stress) / len(ts_stress) if ts_stress else float("nan")
            mean_ts_bias   = sum(ts_bias)   / len(ts_bias)   if ts_bias   else float("nan")
            mean_ts_size   = sum(ts_size)   / len(ts_size)   if ts_size   else float("nan")
            print(f"State distributions (final snapshot / tail-20% mean):")
            print(f"  mean_stemness  : {m_stem:+.4f}  /  {mean_ts_stem:+.4f}")
            print(f"  mean_stress    : {m_stress:+.4f}  /  {mean_ts_stress:+.4f}")
            print(f"  mean_bias      : {m_bias:+.4f}  /  {mean_ts_bias:+.4f}")
            print(f"  mean_pop_size  : {n_f}  /  {mean_ts_size:.1f}")
        else:
            print(f"State distributions (final):")
            print(f"  mean_stemness  : {m_stem:+.4f}")
            print(f"  mean_stress    : {m_stress:+.4f}")
            print(f"  mean_bias      : {m_bias:+.4f}")

    _print_separator()

    # --- Optional plot -------------------------------------------------------
    if args.plot_out is not None:
        try:
            from cell_diff_sim.analysis.plots import save_summary_figure
            df = recorder.to_dataframe()
            save_summary_figure(df, str(args.plot_out), t_max=args.t_max)
            print(f"Figure saved to: {args.plot_out}")
        except Exception as e:
            print(f"Plotting failed: {type(e).__name__}: {e}")
            raise


if __name__ == "__main__":
    main()
