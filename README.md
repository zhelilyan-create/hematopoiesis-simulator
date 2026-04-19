# Cell Differentiation Simulator — v0.6

A minimal, modular Python simulator for hematopoiesis cell differentiation,
driven by a Gillespie engine.

> **Simulation model note (v0.5):** from v0.5 the simulator is a
> **piecewise-deterministic Markov process (PDMP)**, not a pure CTMC.
> Between stochastic events each cell's `InternalState` may drift
> deterministically.  The Gillespie algorithm is preserved; one hook is
> added.  All v0.1–v0.4 configs remain numerically identical (no-op
> fast path when `state_evolution` section is absent).

> **v0.6:** asymmetric division now redistributes both `stemness_score`
> and `stress_score`.  Daughter 0 (high-stemness) receives lower stress;
> daughter 1 (low-stemness) receives higher stress.  All v0.1–v0.5 configs
> remain numerically identical (new stress parameters default to 0.0).

> **WARNING: all rate values in `configs/` are placeholder values chosen for
> structural testing only.  They are NOT derived from experimental data.
> Do not interpret simulation outputs as quantitative biological predictions.**

---

## What this simulator does

- Models hematopoiesis as a CTMC over 8 discrete cell types
- Three event types per cell: **differentiation**, **symmetric self-renewal
  division**, **apoptosis**
- Gillespie direct method (exact stochastic simulation)
- **v0.2: state-dependent rates** — event rates are modulated by each cell's
  `InternalState` (stemness, stress, replicative history)
- **v0.2: typed `InternalState`** — `stemness_score`, `stress_score`,
  `division_count` tracked per cell and inherited across divisions
- **v0.3: asymmetric inheritance** — optional asymmetric partitioning of
  `stemness_score` at division; daughter 0 gets stemness + δ, daughter 1
  gets stemness − δ, both clamped to [0, 1]
- **v0.4: centriole-driven asymmetry** — `CentrioleState` tracks the
  replicative age of the centriole per cell; `CentrioleInheritanceRules`
  assigns the old centriole (age + 1) to daughter 0 and the new centriole
  (age = 0) to daughter 1, with stemness shift proportional to centriole age
  (bounded by a configurable cap); first division of founder cells is
  stemness-symmetric by design
- **v0.5: PDMP lifetime dynamics** — `StateEvolutionRules` implements
  deterministic per-cell `InternalState` drift between stochastic events;
  primary effect is `stress_accumulation_rate` causing stress to rise
  passively during a cell's lifetime, making event rates implicitly
  age-dependent through the existing `RateModulator` channel; time-ordering:
  propensities sampled → Δt drawn → states evolved → event applied
- **v0.6: richer asymmetric inheritance** — both `stemness_score` and
  `stress_score` are now partitioned at division; daughter 0 (old-centriole /
  high-stemness) receives lower stress, daughter 1 (new-centriole /
  low-stemness) receives higher stress; controlled by two new optional
  parameters (`stress_asymmetry`, `centriole_stress_factor`) that default
  to 0.0 for exact backward compatibility; `stress_score` is lower-bounded
  at 0.0 with no upper cap
- Deterministic reproducibility via random seed
- Time-series recording of population composition
- Basic visualization (population over time, final composition)

### Cell type hierarchy

```
HSC
└── MPP
    ├── CMP
    │   ├── Myeloid     (terminal)
    │   └── Erythroid   (terminal)
    └── CLP
        ├── B_cell      (terminal)
        └── T_cell      (terminal)
```

Terminal types have no outgoing differentiation or division events.

---

## What this simulator does NOT do

| Feature | Status |
|---|---|
| Asymmetric cell division | Implemented (v0.3/v0.4) |
| Centriole age / mother-daughter centriole tracking | Implemented (v0.4) |
| Spatial modelling | Not implemented |
| Gene regulatory network | Not implemented |
| Population-level feedback (e.g. carrying capacity) | Not implemented |
| Biologically calibrated rates | Not implemented — all rates are placeholders |

---

## v0.2 / v0.3 / v0.4 / v0.5 / v0.6: internal cell state and inheritance

Each cell carries an `InternalState` dataclass:

| Field | Default | Meaning |
|---|---|---|
| `stemness_score` | 0.5 | Stem-cell character ∈ [0, 1] |
| `stress_score` | 0.0 | Accumulated cellular stress ≥ 0 |
| `division_count` | 0 | Divisions since lineage founder ≥ 0 |

### Rate modulation formulas

Event rates are multiplied by state-dependent modifiers:

```
modifier_div  = 1.0 + w_div_stemness*(stemness−0.5)
                    − w_div_stress*stress
                    − w_div_repl*division_count

modifier_diff = 1.0 − w_diff_stemness*(stemness−0.5)
                    + w_diff_stress*stress
                    + w_diff_repl*division_count

modifier_apo  = 1.0 + w_apo_stress*stress
                    + w_apo_repl*division_count

effective_rate = base_rate × clamp(modifier, min_factor, max_factor)
```

**Algebraic guarantee:** at neutral `InternalState()` (stemness=0.5, stress=0,
div_count=0) all modifiers equal exactly 1.0 for any weight values.

**Biological interpretation:**
- Higher stemness → more division, less differentiation
- Higher stress → less division, more differentiation, more apoptosis
- More past divisions → less division, more differentiation, more apoptosis

All weights are configurable in the `state_modulation` YAML section.
Set all weights to 0.0 (or omit the section entirely) to disable modulation.

Each cell also carries a `CentrioleState` (v0.4):

| Field | Default | Meaning |
|---|---|---|
| `age` | 0 | Replicative age of the centriole (division cycles) |

### Lifetime dynamics (v0.5)

`StateEvolutionRules` applies deterministic drift to every cell's `InternalState`
on each Gillespie step. The rules are linear and interpretable:

```
stress_score(t + Δt)   = clamp(stress_score(t)   + stress_accumulation_rate × Δt,  0, ∞)
stemness_score(t + Δt) = clamp(stemness_score(t) + stemness_drift_rate      × Δt,  0, 1)
division_count         = unchanged  (updated only at division)
```

**Time-ordering assumption (PDMP convention):**
1. Propensities computed from **pre-drift** `InternalState`
2. Δt sampled from Exp(λ)
3. All cells evolved by Δt
4. Selected event applied to **post-drift** state

This is the explicit-Euler PDMP approximation; error per step is O(Δt²).

**Primary effect:** `stress_accumulation_rate > 0` — stress rises passively
during a cell's lifetime. Through `RateModulator` this raises the apoptosis
rate (and lowers division/differentiation rates) for older cells, making the
model implicitly age-aware without any change to the Gillespie algorithm.

**Edge/debug option:** `stemness_drift_rate` (signed, default `0.0`) is
supported but is not the primary v0.5 mechanism.

```yaml
# v0.5 config section
state_evolution:
  stress_accumulation_rate: 0.01   # NON-CALIBRATED: stress per hour
  stemness_drift_rate: 0.0         # NON-CALIBRATED: 0.0 = no drift (default)
```

Omit the section entirely (or set both rates to `0.0`) to disable evolution
and get v0.4-identical behaviour.

### Inheritance (v0.2 / v0.3 / v0.4 / v0.6)

Three implementations, selected by the `inheritance` YAML section:

**`SymmetricInheritanceRules`** (default, v0.2):
- `stemness_score` and `stress_score` are copied unchanged to both daughters
- `division_count` is incremented by 1 in both daughters

**`AsymmetricInheritanceRules`** (v0.3, extended v0.6; enabled by `mode: asymmetric`):
- Daughter 0: `stemness = clamp(parent.stemness + δ_s, 0, 1)`;
  `stress = max(0.0, parent.stress − δ_σ)` ← lower stress (v0.6)
- Daughter 1: `stemness = clamp(parent.stemness − δ_s, 0, 1)`;
  `stress = parent.stress + δ_σ` ← higher stress, no upper cap (v0.6)
- `division_count` is incremented by 1 in both daughters
- δ_s set by `stemness_asymmetry`; δ_σ set by `stress_asymmetry` (default `0.0`)

**`CentrioleInheritanceRules`** (v0.4, extended v0.6; enabled by `mode: centriole`):
- Daughter 0 inherits the **old** centriole: `CentrioleState(age = parent.age + 1)`
- Daughter 1 inherits the **new** centriole: `CentrioleState(age = 0)`
- `effective_age = min(parent.centriole_age, centriole_age_cap)`
- `stemness_delta = centriole_stemness_factor × effective_age`
- `stress_delta   = centriole_stress_factor   × effective_age` ← (v0.6)
- Daughter 0: `stemness = clamp(parent.stemness + stemness_delta, 0, 1)` (higher);
  `stress = max(0.0, parent.stress − stress_delta)` (lower)
- Daughter 1: `stemness = clamp(parent.stemness − stemness_delta, 0, 1)` (lower);
  `stress = parent.stress + stress_delta` (higher, no upper cap)
- `division_count` is incremented symmetrically
- **Founder assumption:** founder cells start with `age = 0`, so the first
  division always has both deltas = 0 and is fully symmetric. Asymmetry only
  emerges from the second division onward.
- `centriole_age_cap ≥ 1` bounds the per-division increment for both deltas;
  effect plateaus once the old-centriole lineage reaches `age_cap` divisions.

**Stress bounds convention (v0.6):**
- `stress_score` is lower-bounded at 0.0; there is **no upper cap**.
- Asymmetric inheritance only prevents negative stress values (daughter 0 clamping).
- The higher-stress daughter's stress can grow without bound across divisions.

**Saturation:** stemness lineages approach `0.0` or `1.0` and remain clamped.
Stress in the high-stress lineage is unbounded above — only the per-division
increment is capped, not the absolute level.

**Biological framing (kept modest):** `CentrioleInheritanceRules` is a minimal
mechanistic proxy. Old centriole → higher stemness, lower stress is a named
convention, not a biological claim. The two factors are independent parameters.
No specific molecular pathway is modelled.

```yaml
# v0.3 config section
inheritance:
  mode: asymmetric
  stemness_asymmetry: 0.1

# v0.4 config section (stress_asymmetry absent → 0.0, identical to v0.3)
inheritance:
  mode: centriole
  centriole_stemness_factor: 0.05   # NON-CALIBRATED
  centriole_age_cap: 10             # NON-CALIBRATED

# v0.6 config section
inheritance:
  mode: centriole
  centriole_stemness_factor: 0.05   # NON-CALIBRATED
  centriole_stress_factor:   0.02   # NON-CALIBRATED: small measurable stress asymmetry
  centriole_age_cap: 10             # NON-CALIBRATED
```

Omit the section entirely, or set `mode: symmetric`, to get v0.2-identical
behaviour.  Omit `stress_asymmetry` / `centriole_stress_factor` to get
v0.4/v0.5-identical stress inheritance.

### Backward compatibility

The v0.1/v0.2 configs have no `inheritance` section → `SymmetricInheritanceRules`
is used → **numerically identical to v0.2**.
The v0.1 config also has no `state_modulation` section → all weights = 0.0 →
**numerically identical to v0.1**.
All non-centriole modes set `CentrioleState(age=0)` on daughters; since
`get_events()` never reads `centriole_state`, rates are unaffected — v0.1/v0.2/v0.3
configs are numerically identical under v0.4.
Configs without a `state_evolution` section have both rates = `0.0`; the
`is_noop` fast path skips population iteration — v0.1–v0.4 configs are
numerically identical under v0.5.

---

## Requirements

```
Python >= 3.10
numpy >= 1.26
pandas >= 2.0
pyyaml >= 6.0
matplotlib >= 3.5   (optional, for --plot-out)
pytest >= 7.4       (optional, for tests)
```

Install:

```bash
pip install numpy pandas pyyaml
pip install matplotlib          # optional, for visualization
pip install pytest              # optional, for tests
```

---

## How to run

### Basic simulation (v0.6 config, fixed seed)

```bash
python scripts/run_sim.py --config configs/hematopoiesis_v06.yaml --seed 42
```

### v0.6.1: regime comparison using CLI overrides (same seed, different stress factor)

```bash
# Stress asymmetry off
python scripts/run_sim.py --config configs/hematopoiesis_v06.yaml --centriole-stress-factor 0.0  --seed 42

# Stress asymmetry on (small)
python scripts/run_sim.py --config configs/hematopoiesis_v06.yaml --centriole-stress-factor 0.05 --seed 42

# Stress asymmetry on (larger)
python scripts/run_sim.py --config configs/hematopoiesis_v06.yaml --centriole-stress-factor 0.10 --seed 42
```

### v0.6.1: ablation — remove all asymmetry

```bash
python scripts/run_sim.py --config configs/hematopoiesis_v06.yaml --inheritance-mode symmetric --seed 42
```

### v0.6.1: override initial population and stress accumulation

```bash
python scripts/run_sim.py --config configs/hematopoiesis_v06.yaml \
    --initial-hsc 50 --stress-accumulation-rate 0.02 --seed 42
```

### v0.6.1: override abstract asymmetric parameters

```bash
python scripts/run_sim.py --config configs/hematopoiesis_v06.yaml \
    --inheritance-mode asymmetric --stemness-asymmetry 0.15 --stress-asymmetry 0.08 --seed 42
```

### v0.6.1: disable stress effect on rates (weight ablation)

```bash
python scripts/run_sim.py --config configs/hematopoiesis_v06.yaml \
    --w-apo-stress 0.0 --w-div-stress 0.0 --seed 42
```

### Save a summary figure

```bash
python scripts/run_sim.py --config configs/hematopoiesis_v06.yaml --seed 42 --plot-out results.png
```

### Earlier version configs (still fully supported)

```bash
python scripts/run_sim.py --config configs/hematopoiesis_v05.yaml --seed 42
python scripts/run_sim.py --config configs/hematopoiesis_v04.yaml --seed 42
python scripts/run_sim.py --config configs/hematopoiesis_v03.yaml --seed 42
python scripts/run_sim.py --config configs/hematopoiesis_v02.yaml --seed 42
python scripts/run_sim.py --config configs/hematopoiesis_v01.yaml --seed 42
```

### CLI reference (v0.6.1)

| Argument | Type | Default | Overrides |
|---|---|---|---|
| `--config` | path | `configs/hematopoiesis_v06.yaml` | Config file path |
| `--seed` | int | None (random) | RNG seed |
| `--t-max` | float | 100.0 | Max simulation time (h) |
| `--plot-out` | path | None | Output figure path |
| `--initial-hsc` | int | None | `initial_population.HSC` |
| `--inheritance-mode` | str | None | `inheritance.mode` |
| `--stemness-asymmetry` | float | None | `inheritance.stemness_asymmetry` |
| `--stress-asymmetry` | float | None | `inheritance.stress_asymmetry` |
| `--centriole-stemness-factor` | float | None | `inheritance.centriole_stemness_factor` |
| `--centriole-stress-factor` | float | None | `inheritance.centriole_stress_factor` |
| `--centriole-age-cap` | int | None | `inheritance.centriole_age_cap` |
| `--stress-accumulation-rate` | float | None | `state_evolution.stress_accumulation_rate` |
| `--stemness-drift-rate` | float | None | `state_evolution.stemness_drift_rate` |
| `--w-div-stemness` | float | None | `state_modulation.w_div_stemness` |
| `--w-div-stress` | float | None | `state_modulation.w_div_stress` |
| `--w-div-repl` | float | None | `state_modulation.w_div_repl` |
| `--w-diff-stemness` | float | None | `state_modulation.w_diff_stemness` |
| `--w-diff-stress` | float | None | `state_modulation.w_diff_stress` |
| `--w-diff-repl` | float | None | `state_modulation.w_diff_repl` |
| `--w-apo-stress` | float | None | `state_modulation.w_apo_stress` |
| `--w-apo-repl` | float | None | `state_modulation.w_apo_repl` |

All override arguments default to `None`. When `None`, the YAML value is used unchanged.
Passing no override arguments produces output identical to v0.6.

### Example output (v0.1 config, seed 42)

```
============================================================
HEMATOPOIESIS SIMULATION  v0.6.1  [NON-CALIBRATED RATES]
============================================================
  Config : configs/hematopoiesis_v01.yaml
  Seed   : 42
  t_max  : 100.0 h

Initial population  (n=10, t=0 h):
    HSC               10  (100.0%)

Simulation ended at t = 100.0000 h
Events recorded : 3947

Final population  (n=2155, t=100.00 h):
    B_cell           101  ( 4.7%)
    CLP              200  ( 9.3%)
    CMP              183  ( 8.5%)
    Erythroid         73  ( 3.4%)
    HSC              581  (27.0%)
    MPP              827  (38.4%)
    Myeloid           78  ( 3.6%)
    T_cell           112  ( 5.2%)
============================================================
```

---

## Run the test suite

```bash
pytest tests/
```

Tests cover:

- Config parsing — valid, negative rates, `None` targets, unknown cell types
- Population consistency — size changes after apoptosis, differentiation, division
- Engine behaviour — deterministic reproducibility, `t_max` stopping,
  initial snapshot semantics, zero-rate event exclusion,
  terminal cell type event constraints
- **v0.2**: `InternalState` validation, neutral-state modifiers = 1.0,
  zero-weight modulation, factor directions, `SymmetricInheritanceRules`,
  state-dependent rate directions, backward compatibility, reproducibility
- **v0.3**: `AsymmetricInheritanceRules` unit tests, clamping, config parsing,
  unknown-mode guard, zero-δ edge case, stemness divergence, reproducibility,
  backward compatibility with v0.2 config
- **v0.4**: `CentrioleState` validation, `CentrioleInheritanceRules` unit tests
  (old/new centriole age, stemness shift, first-division symmetry, clamping,
  symmetric stress/division_count), validation guards, config parsing, age-cap
  plateau, reproducibility, backward compatibility with v0.3 config
- **v0.5**: `StateEvolutionRules` unit tests (zero rates, stress accumulation,
  stemness drift, clamping, division_count immunity), validation guard, config
  parsing, stress increases during simulation, reproducibility, backward
  compatibility with v0.4 config, causal chain (stress → apoptosis rate)
- **v0.6.1**: `apply_overrides()` unit tests (no overrides, override wins, absent
  arg leaves YAML intact, creates missing section, initial_hsc, inheritance_mode,
  centriole_stress_factor, modulation weight, multiple overrides), reporting tests
  (correct strings, empty list), argparse validation (invalid mode rejected),
  integration (overridden config runs, zero-overrides reproducibility)
- **v0.6**: `AsymmetricInheritanceRules` stress extension (zero stress_asymmetry
  is symmetric, daughter 0 lower stress, daughter 1 higher stress, floor clamp,
  simultaneous stemness+stress shift), `CentrioleInheritanceRules` stress
  extension (zero factor symmetric, daughter 0/1 stress directions, linear
  scaling, age-cap plateau), validation guards, config parsing (v0.6 YAML,
  v0.5 YAML backward compat, negative factor raises), causal chain
  (high-stress daughter → higher apoptosis rate)

---

## Project structure

```
cell_diff_sim/
  cell.py                 Cell dataclass + CellType alias
  internal_state.py       InternalState dataclass (v0.2)
  centriole_state.py      CentrioleState dataclass (v0.4)
  population.py           Population container
  models/
    base.py               AbstractModel interface (+ evolve_cell_states no-op, v0.5)
    inheritance.py        InheritanceRules protocol + Default + Symmetric + Asymmetric + Centriole (v0.4/v0.6)
    rate_modulation.py    ModulationParams + RateModulator (v0.2)
    state_evolution.py    StateEvolutionParams + StateEvolutionRules (v0.5)
    hematopoiesis.py      Hematopoiesis model (8 states, PDMP, configurable inheritance + evolution, v0.6)
  engine/
    events.py             DifferentiationEvent, DivisionEvent, ApoptosisEvent
    cell_factory.py       create_daughter() — sole construction path for daughters
    division_handler.py   DivisionHandler — division orchestration
    ctmc.py               Gillespie engine with PDMP drift hook (v0.5)
  observers/
    recorder.py           Recorder + Snapshot — time-series recording
  analysis/
    plots.py              plot_population_over_time, plot_final_composition
configs/
  hematopoiesis_v01.yaml  v0.1 rates (PLACEHOLDER — NOT CALIBRATED, no modulation)
  hematopoiesis_v02.yaml  v0.2 rates (PLACEHOLDER — NOT CALIBRATED, with modulation)
  hematopoiesis_v03.yaml  v0.3 rates (PLACEHOLDER — NOT CALIBRATED, asymmetric inheritance)
  hematopoiesis_v04.yaml  v0.4 rates (PLACEHOLDER — NOT CALIBRATED, centriole inheritance)
  hematopoiesis_v05.yaml  v0.5 rates (PLACEHOLDER — NOT CALIBRATED, PDMP stress accumulation)
  hematopoiesis_v06.yaml  v0.6 rates (PLACEHOLDER — NOT CALIBRATED, richer asymmetric inheritance)
scripts/
  run_sim.py              Entry point + apply_overrides() (v0.6.1)
tests/
  test_config.py          Config parsing tests
  test_population.py      Population consistency tests
  test_engine.py          Engine behaviour tests
  test_internal_state.py  InternalState + RateModulator + SymmetricInheritance (v0.2)
  test_v03.py             AsymmetricInheritanceRules + inheritance config parsing (v0.3)
  test_v04.py             CentrioleState + CentrioleInheritanceRules + config parsing (v0.4)
  test_v05.py             StateEvolutionRules + PDMP integration + causal chain (v0.5)
  test_v06.py             Richer asymmetric inheritance (stemness + stress) + causal chain (v0.6)
  test_cli.py             apply_overrides() unit tests + argparse validation + integration (v0.6.1)
```

---

## v0.7 design (planned)

1. **CLI parameter overrides** — allow overriding key config parameters
   (e.g. rates, inheritance factors) from the command line without editing YAML.
