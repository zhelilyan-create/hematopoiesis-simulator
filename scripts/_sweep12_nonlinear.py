"""
v0.8 M6.2 nonlinear fate regulation sweep:
  Fixed: asym=0.02, noise_std=0.02 (M5), t_max=100
  target_population_size  = 1000
  crowding_apoptosis_rate = 0.05  (M4 baseline)
  niche_alpha             in {0.05, 0.1}    (M6.1 linear, used when niche_strength=0)
  niche_strength          in {0.0, 1.0, 2.0, 4.0}  (M6.2 nonlinear exponent k)
  seeds                   in {42, 1}
  → 2 × 4 × 2 = 16 runs, run_ids 274-289

M6.2 formula:
  underpopulated (niche>0): fate_multiplier = exp(-k * niche * stemness)
  overpopulated  (niche<0): fate_multiplier = exp(+k * |niche| * stemness)
  clamp: [0.01, 10.0]

When niche_strength=0, falls back to M6.1 linear: max(0, 1 - alpha*niche*stemness)
"""
import subprocess, json, sys, re

BASELINE_CONFIG         = "configs/hematopoiesis_baseline.yaml"
TARGET_SIZE             = 1000
CROWDING_RATE           = 0.05
NICHE_ALPHAS            = [0.05, 0.1]
NICHE_STRENGTHS         = [0.0, 1.0, 2.0, 4.0]
SEEDS                   = [42, 1]
ASYM                    = 0.02
NOISE_STD               = 0.02

MATURE_TYPES     = {"B_cell", "T_cell", "Myeloid", "Erythroid"}
PROGENITOR_TYPES = {"HSC", "MPP", "CLP", "CMP"}


def run_one(niche_alpha, niche_strength, seed):
    cmd = [
        sys.executable, "scripts/run_sim.py",
        "--config",                        BASELINE_CONFIG,
        "--seed",                          str(seed),
        "--epigenetic-asymmetry-strength", str(ASYM),
        "--epigenetic-inheritance-noise",  str(NOISE_STD),
        "--target-population-size",        str(TARGET_SIZE),
        "--crowding-apoptosis-rate",       str(CROWDING_RATE),
        "--niche-alpha",                   str(niche_alpha),
        "--niche-strength",                str(niche_strength),
        "--track-states",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print(
            f"  FAIL alpha={niche_alpha} k={niche_strength} seed={seed}: "
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

    # Bias stats
    hit = re.search(
        r"Epigenetic bias stats \(n=\d+\):\s*\n"
        r"\s+mean=([+\-]?\d+\.\d+)\s+std=(\d+\.\d+)\s+min=[+\-]?\d+\.\d+\s+max=[+\-]?\d+\.\d+\s*\n"
        r"\s+p10=([+\-]?\d+\.\d+)\s+p50=([+\-]?\d+\.\d+)\s+p90=([+\-]?\d+\.\d+)\s*\n"
        r"\s+\|bias\|>0\.1:\s*([0-9.]+)%\s+\|bias\|>0\.2:\s*([0-9.]+)%",
        stdout,
    )
    if hit:
        m["bias_std"] = float(hit.group(2))
        m["bias_f01"] = float(hit.group(6))

    # State distributions
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
        m["tail_mean_stress"]    = float(hit.group(4))
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
    if m.get("HSC_pct", 0) > 60:
        return "stem_dominated"
    return "ok"


results = []
run_id_start = 274   # next after M6.1 sweep (262-273)

header = "%4s  %6s  %5s  %4s | %6s  %7s  %5s  %5s  %7s | status" % (
    "rid", "alpha", "k", "seed", "n", "tgt_d", "hsc%", "mat%", "stem_t"
)
print(header)
print("-" * len(header))

idx = 0
for niche_alpha in NICHE_ALPHAS:
    for niche_strength in NICHE_STRENGTHS:
        for seed in SEEDS:
            rid    = run_id_start + idx
            idx   += 1
            stdout = run_one(niche_alpha, niche_strength, seed)
            m      = parse_output(stdout) if stdout else {}
            status = classify(m)
            results.append(dict(
                run_id=rid,
                target_population_size=TARGET_SIZE,
                crowding_apoptosis_rate=CROWDING_RATE,
                niche_alpha=niche_alpha,
                niche_strength=niche_strength,
                seed=seed,
                status=status,
                **m,
            ))

            n      = m.get("final_n",         "?")
            hpct   = m.get("HSC_pct",          float("nan"))
            mat    = m.get("mature_pct",       float("nan"))
            stem_t = m.get("tail_mean_stemness", float("nan"))
            tgt_d  = (m["final_n"] - TARGET_SIZE) if isinstance(n, int) else float("nan")

            tgt_d_str = ("%+7d" % tgt_d) if isinstance(tgt_d, (int, float)) and tgt_d == tgt_d else "      ?"
            print("%4d  %6.3f  %5.1f  %4d | %6s  %7s  %5.1f  %5.1f  %+7.4f | %s" % (
                rid, niche_alpha, niche_strength, seed,
                str(n), tgt_d_str, hpct, mat, stem_t, status
            ))

    print()  # blank line between niche_alpha groups

# --------------------------------------------------------------------------
# Analysis summary
# --------------------------------------------------------------------------
print()
print("=" * 72)
print("M6.2 ANALYSIS SUMMARY (target=1000, cr=0.05)")
print("=" * 72)

# (1) Population control: mean |n-target| per niche_strength
print("\n(1) Population control — mean |n-target| by niche_strength:")
print("    %5s  %7s  %7s  %6s" % ("k", "mean_n", "|n-tgt|", "status"))
for k in NICHE_STRENGTHS:
    rr = [r for r in results if r.get("niche_strength") == k and isinstance(r.get("final_n"), int)]
    if rr:
        mean_n = sum(r["final_n"] for r in rr) / len(rr)
        mean_d = sum(abs(r["final_n"] - TARGET_SIZE) for r in rr) / len(rr)
        ok_n = sum(1 for r in rr if r["status"] == "ok")
        print("    %5.1f  %7.0f  %7.0f  %d/%d ok" % (k, mean_n, mean_d, ok_n, len(rr)))

# (2) HSC stability
hsc_lost = [r for r in results if r.get("HSC", 1) == 0 or r.get("status") == "hsc_loss"]
stem_dom  = [r for r in results if r.get("status") == "stem_dominated"]
ok_runs   = [r for r in results if r.get("status") == "ok"]
print("\n(2) HSC stability:")
print("    ok=%d  hsc_loss=%d  stem_dominated=%d  other=%d" % (
    len(ok_runs), len(hsc_lost), len(stem_dom),
    len(results) - len(ok_runs) - len(hsc_lost) - len(stem_dom)))
if results:
    hsc_range = (min(r["HSC_pct"] for r in results if "HSC_pct" in r),
                 max(r["HSC_pct"] for r in results if "HSC_pct" in r))
    print("    HSC%% range: %.1f%% - %.1f%%" % hsc_range)

# (3) Phase behavior: stem_t by niche_strength
print("\n(3) Phase behavior — mean tail stemness by niche_strength:")
for k in NICHE_STRENGTHS:
    rr = [r for r in results if r.get("niche_strength") == k and r.get("tail_mean_stemness") is not None]
    if rr:
        mean_s = sum(r["tail_mean_stemness"] for r in rr) / len(rr)
        print("    k=%.1f  mean_stemness=%.4f" % (k, mean_s))

# (4) Seed variance
print("\n(4) Seed variance |n42 - n1| by (alpha, k):")
print("    %6s  %5s  %8s  %8s" % ("alpha", "k", "M6.1_d", "M6.2_d"))
# M6.1 seed deltas (from previous sweep, cr=0.05)
M61_ref = {0.05: 156, 0.1: 479}
for alpha in NICHE_ALPHAS:
    for k in NICHE_STRENGTHS:
        r42 = next((r for r in results if r["niche_alpha"]==alpha and r["niche_strength"]==k and r["seed"]==42), None)
        r1  = next((r for r in results if r["niche_alpha"]==alpha and r["niche_strength"]==k and r["seed"]==1),  None)
        if r42 and r1 and isinstance(r42.get("final_n"), int) and isinstance(r1.get("final_n"), int):
            delta = abs(r42["final_n"] - r1["final_n"])
            ref   = M61_ref.get(alpha, "?") if k == 0.0 else "—"
            print("    %6.3f  %5.1f  %8s  %8d" % (alpha, k, ref if k==0.0 else "—", delta))

# (5) M5 active
has_bias = [r for r in results if r.get("bias_std", 0) > 0.01]
print("\n(5) M5 coexistence: %d/%d runs show bias_std > 0.01" % (len(has_bias), len(results)))

print()
print("JSON_START")
print(json.dumps(results))
print("JSON_END")
