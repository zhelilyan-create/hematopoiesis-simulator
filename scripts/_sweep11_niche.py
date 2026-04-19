"""
v0.8 niche-dependent fate sweep (M6.1 validation):
  Fixed: asym=0.02, noise_std=0.02 (M5 baseline), t_max=100
  target_population_size  = 1000  (shared M4/M6.1 reference)
  crowding_apoptosis_rate in {0.01, 0.05}  (M4 strength)
  niche_alpha             in {0.0, 0.05, 0.1}  (M6.1 strength)
  seeds                   in {42, 1}
  → 2 × 3 × 2 = 12 runs, run_ids 262-273

M6.1 mechanism (v0.8.1):
  niche > 0 (underpopulated) → differentiation ↓  (cells stay stem longer)
  niche < 0 (overpopulated)  → differentiation ↑  (cells commit faster)
  division rate unchanged from baseline (vs M6 which boosted division)

Validation targets
------------------
(1) Population control   — overshoot smaller than M6; N closer to target
(2) HSC stability        — HSC pool present, not inflated
(3) Low-density behavior — reduced differentiation, NOT accelerated division
(4) Seed sensitivity     — variance across seeds stays low
"""
import subprocess, json, sys, re

BASELINE_CONFIG = "configs/hematopoiesis_baseline.yaml"
TARGET_SIZE             = 1000
CROWDING_RATES          = [0.01, 0.05]
NICHE_ALPHAS            = [0.0, 0.05, 0.1]
SEEDS                   = [42, 1]
ASYM                    = 0.02
NOISE_STD               = 0.02

MATURE_TYPES     = {"B_cell", "T_cell", "Myeloid", "Erythroid"}
PROGENITOR_TYPES = {"HSC", "MPP", "CLP", "CMP"}


def run_one(crowding_rate, niche_alpha, seed):
    cmd = [
        sys.executable, "scripts/run_sim.py",
        "--config",                        BASELINE_CONFIG,
        "--seed",                          str(seed),
        "--epigenetic-asymmetry-strength", str(ASYM),
        "--epigenetic-inheritance-noise",  str(NOISE_STD),
        "--target-population-size",        str(TARGET_SIZE),
        "--crowding-apoptosis-rate",       str(crowding_rate),
        "--niche-alpha",                   str(niche_alpha),
        "--track-states",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print(
            f"  FAIL cr={crowding_rate} alpha={niche_alpha} seed={seed}: "
            f"{result.stderr[-300:]}",
            file=sys.stderr,
        )
        return None
    return result.stdout


def parse_output(stdout):
    m = {}

    hit = re.search(r"Final population\s+\(n=(\d+)", stdout)
    if hit:
        m["final_n"] = int(hit.group(1))

    hit = re.search(r"Events recorded\s*:\s*(\d+)", stdout)
    if hit:
        m["n_events"] = int(hit.group(1))

    cell_counts, cell_pcts = {}, {}
    for line in stdout.splitlines():
        hit = re.match(r"\s+(\w+)\s+(\d+)\s+\(\s*([0-9.]+)%\)", line)
        if hit:
            cell_counts[hit.group(1)] = int(hit.group(2))
            cell_pcts[hit.group(1)]   = float(hit.group(3))

    if cell_counts:
        for ct in ["HSC", "MPP", "CLP", "CMP", "B_cell", "T_cell", "Myeloid", "Erythroid"]:
            m[ct]          = cell_counts.get(ct, 0)
            m[f"{ct}_pct"] = cell_pcts.get(ct, 0.0)
        total = m.get("final_n", sum(cell_counts.values()))
        if total:
            m["mature_pct"]     = round(100 * sum(cell_counts.get(t, 0) for t in MATURE_TYPES) / total, 1)
            m["progenitor_pct"] = round(100 * sum(cell_counts.get(t, 0) for t in PROGENITOR_TYPES) / total, 1)
        mpp = m.get("MPP", 1)
        m["hsc_mpp_ratio"] = round(m["HSC"] / mpp, 3) if mpp else None

    # Epigenetic bias stats
    hit = re.search(
        r"Epigenetic bias stats \(n=\d+\):\s*\n"
        r"\s+mean=([+\-]?\d+\.\d+)\s+std=(\d+\.\d+)\s+min=[+\-]?\d+\.\d+\s+max=[+\-]?\d+\.\d+\s*\n"
        r"\s+p10=([+\-]?\d+\.\d+)\s+p50=([+\-]?\d+\.\d+)\s+p90=([+\-]?\d+\.\d+)\s*\n"
        r"\s+\|bias\|>0\.1:\s*([0-9.]+)%\s+\|bias\|>0\.2:\s*([0-9.]+)%",
        stdout,
    )
    if hit:
        m["bias_std"]  = float(hit.group(2))
        m["bias_f01"]  = float(hit.group(6))
        m["bias_f02"]  = float(hit.group(7))

    # State distribution summary (--track-states)
    hit = re.search(
        r"State distributions.*?:\s*\n"
        r"\s+mean_stemness\s*:\s*([+\-]?\d+\.\d+)\s+/\s+([+\-]?\d+\.\d+)\s*\n"
        r"\s+mean_stress\s*:\s*([+\-]?\d+\.\d+)\s+/\s+([+\-]?\d+\.\d+)\s*\n"
        r"\s+mean_bias\s*:\s*([+\-]?\d+\.\d+)\s+/\s+([+\-]?\d+\.\d+)\s*\n"
        r"\s+mean_pop_size\s*:\s*(\d+)\s+/\s+([0-9.]+)",
        stdout,
    )
    if hit:
        m["final_mean_stemness"] = float(hit.group(1))
        m["tail_mean_stemness"]  = float(hit.group(2))
        m["final_mean_stress"]   = float(hit.group(3))
        m["tail_mean_stress"]    = float(hit.group(4))
        m["final_mean_bias"]     = float(hit.group(5))
        m["tail_mean_bias"]      = float(hit.group(6))
        m["tail_mean_pop_size"]  = float(hit.group(8))

    return m


def classify(m):
    if not m or "final_n" not in m:
        return "error"
    if m.get("HSC", 1) == 0:
        return "hsc_loss"
    if m.get("final_n", 0) < 100:
        return "collapsed"
    if m.get("final_n", 0) < 300:
        return "growth_suppressed"
    if m.get("HSC_pct", 0) > 50 or (m.get("hsc_mpp_ratio") or 0) > 2.0:
        return "too_stem_heavy"
    return "ok"


results = []
run_id_start = 262   # next after M6 sweep (250-261)

header = (
    f"{'rid':>4}  {'cr':>5}  {'alpha':>6}  {'seed':>4} | "
    f"{'n':>6}  {'tgt_d':>7}  {'hsc%':>5}  {'mpp%':>5}  {'mat%':>5} | "
    f"{'stem_t':>7}  {'stress_t':>8}  {'bstd':>6} | status"
)
print(header)
print("-" * len(header))

idx = 0
for crowding_rate in CROWDING_RATES:
    for niche_alpha in NICHE_ALPHAS:
        for seed in SEEDS:
            rid    = run_id_start + idx
            idx   += 1
            stdout = run_one(crowding_rate, niche_alpha, seed)
            m      = parse_output(stdout) if stdout else {}
            status = classify(m)
            results.append(dict(
                run_id=rid,
                target_population_size=TARGET_SIZE,
                crowding_apoptosis_rate=crowding_rate,
                niche_alpha=niche_alpha,
                seed=seed,
                status=status,
                **m,
            ))

            n     = m.get("final_n",          "?")
            hpct  = m.get("HSC_pct",           float("nan"))
            mpct  = m.get("MPP_pct",           float("nan"))
            mat   = m.get("mature_pct",        float("nan"))
            stem_t = m.get("tail_mean_stemness", float("nan"))
            str_t  = m.get("tail_mean_stress",   float("nan"))
            bstd   = m.get("bias_std",           float("nan"))
            # deviation from target
            tgt_d  = (m["final_n"] - TARGET_SIZE) if isinstance(n, int) else float("nan")

            print(
                f"{rid:>4}  {crowding_rate:>5.2f}  {niche_alpha:>6.3f}  {seed:>4} | "
                f"{n:>6}  {tgt_d:>+7}  {hpct:>5.1f}  {mpct:>5.1f}  {mat:>5.1f} | "
                f"{stem_t:>+7.4f}  {str_t:>+8.4f}  {bstd:>6.4f} | {status}"
            )

    print()  # blank line between crowding_rate groups

# --------------------------------------------------------------------------
# Validation summary
# --------------------------------------------------------------------------
print()
print("=" * 70)
print("VALIDATION SUMMARY")
print("=" * 70)

# (1) HSC persistence
hsc_lost = [r for r in results if r.get("HSC", 1) == 0 or r.get("status") == "hsc_loss"]
ok_str  = "OK"  if not hsc_lost else "FAILURES: " + str([r['run_id'] for r in hsc_lost])
print(f"\n(1) HSC persistence: {len(hsc_lost)}/{len(results)} runs lost HSC pool  {ok_str}")

# (2) Population control: does higher niche_alpha reduce |n - target|?
print("\n(2) Population control (mean |final_n - target| by niche_alpha):")
for alpha in NICHE_ALPHAS:
    runs_a = [r for r in results if r.get("niche_alpha") == alpha and isinstance(r.get("final_n"), int)]
    if runs_a:
        mean_dev = sum(abs(r["final_n"] - TARGET_SIZE) for r in runs_a) / len(runs_a)
        print(f"    niche_alpha={alpha:.3f}  mean |n-target| = {mean_dev:.1f}  "
              f"(n={len(runs_a)} runs)")

# (3) Hierarchy: HSC% not collapsed, not too stem-heavy
collapsed = [r for r in results if r.get("status") in ("collapsed", "hsc_loss", "error")]
stem_heavy = [r for r in results if r.get("status") == "too_stem_heavy"]
ok_runs = [r for r in results if r.get("status") == "ok"]
print(f"\n(3) Hierarchy:")
print(f"    ok={len(ok_runs)}  collapsed/hsc_loss={len(collapsed)}  "
      f"too_stem_heavy={len(stem_heavy)}")

# (4) M5 interaction: bias_std present in all runs (stochastic noise active)
has_bias = [r for r in results if r.get("bias_std", 0) > 0.01]
m5_ok = "OK" if len(has_bias) == len(results) else "WARNING: some runs may have lost noise"
print(f"\n(4) M5 interaction: {len(has_bias)}/{len(results)} runs show bias_std > 0.01  {m5_ok}")

print()
print("JSON_START")
print(json.dumps(results))
print("JSON_END")
