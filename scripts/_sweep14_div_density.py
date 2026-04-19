"""
v0.8 M6.4 division-density sweep:
  Fixed: asym=0.02, noise_std=0.02, crowding_rate=0.05, t_max=100
  target_population_size in {500, 1000}
  niche_strength         in {2.0, 4.0}          (M6.2 exponent — best range from M6.2)
  density_gamma          in {1.0, 2.0, 4.0, 8.0} (M6.3+M6.4 dual correction)
  seed                   in {42, 1}              (two seeds for variance check)
  → 2 × 2 × 4 × 2 = 32 runs, run_ids 308-339

M6.4 adds division-density correction on top of M6.3:
  div_density_factor  = (target / n)^gamma   → applied to division rate
  diff_density_factor = (n / target)^gamma   → applied to diff rate (M6.3)

  Combined dual-force mechanism:
    n > target: division ↓  AND  differentiation ↑  → strong contraction
    n < target: division ↑  AND  differentiation ↓  → strong expansion
    n = target: both factors = 1 → no effect

Key insight: total population n changes only via division (+1) and apoptosis (−1).
Differentiation is cell-type transition (n unchanged). Therefore applying the
density correction to DIVISION is the primary control on total population size.
M6.3-only (diff correction) could not pin n; M6.4 (div correction) directly does.

Success criterion: |final_n - target| < 15% of target
"""
import subprocess, json, sys, re

BASELINE_CONFIG = "configs/hematopoiesis_baseline.yaml"
TARGETS         = [500, 1000]
CROWDING_RATE   = 0.05
NICHE_STRENGTHS = [2.0, 4.0]
DENSITY_GAMMAS  = [1.0, 2.0, 4.0, 8.0]
SEEDS           = [42, 1]
ASYM            = 0.02
NOISE_STD       = 0.02

MATURE_TYPES     = {"B_cell", "T_cell", "Myeloid", "Erythroid"}
PROGENITOR_TYPES = {"HSC", "MPP", "CLP", "CMP"}


def run_one(target, niche_strength, density_gamma, seed):
    cmd = [
        sys.executable, "scripts/run_sim.py",
        "--config",                        BASELINE_CONFIG,
        "--seed",                          str(seed),
        "--epigenetic-asymmetry-strength", str(ASYM),
        "--epigenetic-inheritance-noise",  str(NOISE_STD),
        "--target-population-size",        str(target),
        "--crowding-apoptosis-rate",       str(CROWDING_RATE),
        "--niche-strength",                str(niche_strength),
        "--density-gamma",                 str(density_gamma),
        "--track-states",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print("  FAIL tgt=%d k=%.1f g=%.1f seed=%d: %s" % (
            target, niche_strength, density_gamma, seed, result.stderr[-300:]),
            file=sys.stderr)
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
            m["mature_pct"]     = round(100 * sum(cell_counts.get(t, 0) for t in MATURE_TYPES)     / total, 1)
            m["progenitor_pct"] = round(100 * sum(cell_counts.get(t, 0) for t in PROGENITOR_TYPES) / total, 1)
        mpp = m.get("MPP", 1)
        m["hsc_mpp_ratio"] = round(m["HSC"] / mpp, 3) if mpp else None

    hit = re.search(
        r"Epigenetic bias stats \(n=\d+\):\s*\n"
        r"\s+mean=([+\-]?\d+\.\d+)\s+std=(\d+\.\d+)",
        stdout,
    )
    if hit:
        m["bias_std"] = float(hit.group(2))

    hit = re.search(
        r"State distributions.*?:\s*\n"
        r"\s+mean_stemness\s*:\s*([+\-]?\d+\.\d+)\s+/\s+([+\-]?\d+\.\d+)\s*\n"
        r"\s+mean_stress\s*:\s*([+\-]?\d+\.\d+)\s+/\s+([+\-]?\d+\.\d+)\s*\n"
        r"\s+mean_bias\s*:\s*([+\-]?\d+\.\d+)\s+/\s+([+\-]?\d+\.\d+)\s*\n"
        r"\s+mean_pop_size\s*:\s*(\d+)\s+/\s+([0-9.]+)",
        stdout,
    )
    if hit:
        m["tail_mean_stemness"] = float(hit.group(2))
        m["tail_mean_pop_size"] = float(hit.group(8))

    return m


def classify(m, target):
    if not m or "final_n" not in m:
        return "error"
    if m.get("HSC", 1) == 0:
        return "hsc_loss"
    n = m["final_n"]
    if n < 50:
        return "collapsed"
    dev_pct = abs(n - target) / target * 100
    if dev_pct <= 15:
        return "on_target"
    if dev_pct <= 30:
        return "near_target"
    return "overshoot"


results = []
run_id_start = 308

header = "%4s  %5s  %5s  %5s  %4s | %6s  %7s  %6s  %5s  %5s | status" % (
    "rid", "tgt", "k", "g", "seed", "n", "tgt_dev", "dev%", "hsc%", "mat%"
)
print(header)
print("-" * len(header))

idx = 0
for target in TARGETS:
    print("--- target=%d ---" % target)
    for niche_strength in NICHE_STRENGTHS:
        for density_gamma in DENSITY_GAMMAS:
            for seed in SEEDS:
                rid    = run_id_start + idx
                idx   += 1
                stdout = run_one(target, niche_strength, density_gamma, seed)
                m      = parse_output(stdout) if stdout else {}
                status = classify(m, target)
                results.append(dict(
                    run_id=rid,
                    target=target,
                    niche_strength=niche_strength,
                    density_gamma=density_gamma,
                    seed=seed,
                    status=status,
                    **m,
                ))

                n      = m.get("final_n",   "?")
                hpct   = m.get("HSC_pct",   float("nan"))
                mat    = m.get("mature_pct", float("nan"))
                tgt_d  = (n - target)       if isinstance(n, int) else float("nan")
                dev_p  = abs(tgt_d)/target*100 if isinstance(tgt_d, (int,float)) and tgt_d==tgt_d else float("nan")

                print("%4d  %5d  %5.1f  %5.1f  %4d | %6s  %+7s  %6.1f  %5.1f  %5.1f | %s" % (
                    rid, target, niche_strength, density_gamma, seed,
                    str(n), str(tgt_d) if isinstance(tgt_d,int) else "?",
                    dev_p, hpct, mat, status
                ))
        print()
    print()

# ==========================================================================
# Analysis
# ==========================================================================
print()
print("=" * 76)
print("M6.4 DIVISION-DENSITY CALIBRATION ANALYSIS")
print("=" * 76)

# (1) Primary: |n - target| < 15%
on_target   = [r for r in results if r["status"] == "on_target"]
near_target = [r for r in results if r["status"] == "near_target"]
overshoot   = [r for r in results if r["status"] == "overshoot"]
errors      = [r for r in results if r["status"] in ("error","hsc_loss","collapsed")]
print("\n(1) Equilibrium accuracy:")
print("    on_target  (dev<=15%%): %d/%d" % (len(on_target),  len(results)))
print("    near_target(dev<=30%%): %d/%d" % (len(near_target), len(results)))
print("    overshoot  (dev>30%%) : %d/%d" % (len(overshoot),  len(results)))
print("    errors               : %d/%d" % (len(errors),     len(results)))

# (2) Per-gamma mean deviation
print("\n(2) Mean |n-target|%% by density_gamma (both targets combined):")
print("    %5s  %8s  %8s  %8s  %6s" % ("gamma", "mean_dev%", "min_dev%", "max_dev%", "on_tgt"))
for g in DENSITY_GAMMAS:
    rr = [r for r in results if r["density_gamma"]==g and isinstance(r.get("final_n"),int)]
    if rr:
        devs = [abs(r["final_n"]-r["target"])/r["target"]*100 for r in rr]
        n_on = sum(1 for r in rr if r["status"]=="on_target")
        print("    %5.1f  %8.1f  %8.1f  %8.1f  %d/%d" % (
            g, sum(devs)/len(devs), min(devs), max(devs), n_on, len(rr)))

# (3) Per-target best combo
print("\n(3) Best run per target (lowest |n-target|):")
for t in TARGETS:
    rr = [r for r in results if r["target"]==t and isinstance(r.get("final_n"),int)]
    if rr:
        best = min(rr, key=lambda r: abs(r["final_n"]-t))
        print("    target=%4d: run %d  k=%.1f g=%.1f seed=%d  n=%d  dev%%=%.1f  status=%s" % (
            t, best["run_id"], best["niche_strength"], best["density_gamma"],
            best["seed"], best["final_n"], abs(best["final_n"]-t)/t*100, best["status"]))

# (4) Progression: M6.2 → M6.3 → M6.4 (at k=4, target=1000, seed=42)
print("\n(4) Progression comparison (k=4.0, target=1000, seed=42):")
print("    M6.2 (no density):   n=1554, dev=+55.4%%")
print("    M6.3 gamma=2.0 (diff only): n=1326, dev=+32.6%%")
m64_k4 = [r for r in results if r["target"]==1000 and r["niche_strength"]==4.0 and r["seed"]==42]
for r in sorted(m64_k4, key=lambda r: r["density_gamma"]):
    d = (r.get("final_n",9999)-1000)/1000*100
    print("    M6.4 gamma=%.1f (div+diff): n=%s, dev%%=%+.1f  status=%s" % (
        r["density_gamma"], r.get("final_n","?"), d, r["status"]))

# (5) Seed variance
print("\n(5) Seed variance |n_42 - n_1| by (k, gamma):")
print("    %5s  %5s  %8s" % ("k", "gamma", "|n42-n1|"))
for k in NICHE_STRENGTHS:
    for g in DENSITY_GAMMAS:
        for t in TARGETS:
            r42 = next((r for r in results if r["target"]==t and r["niche_strength"]==k
                        and r["density_gamma"]==g and r["seed"]==42), None)
            r1  = next((r for r in results if r["target"]==t and r["niche_strength"]==k
                        and r["density_gamma"]==g and r["seed"]==1),  None)
            if (r42 and r1 and isinstance(r42.get("final_n"),int)
                    and isinstance(r1.get("final_n"),int)):
                delta = abs(r42["final_n"] - r1["final_n"])
                print("    %5.1f  %5.1f  tgt=%4d  %8d" % (k, g, t, delta))

# (6) HSC check
hsc_lost = [r for r in results if r.get("HSC", 1)==0 or r.get("status")=="hsc_loss"]
print("\n(6) HSC persistence: %d/%d lost HSC  %s" % (
    len(hsc_lost), len(results), "OK" if not hsc_lost else "FAIL"))

# (7) HSC% at on-target runs
if on_target:
    hsc_pcts = [r["HSC_pct"] for r in on_target if "HSC_pct" in r]
    mat_pcts  = [r["mature_pct"] for r in on_target if "mature_pct" in r]
    print("\n(7) Composition at on-target runs:")
    print("    HSC%%: %.1f - %.1f (mean %.1f)" % (min(hsc_pcts), max(hsc_pcts),
        sum(hsc_pcts)/len(hsc_pcts)))
    print("    Mature%%: %.1f - %.1f (mean %.1f)" % (min(mat_pcts), max(mat_pcts),
        sum(mat_pcts)/len(mat_pcts)))

print()
print("JSON_START")
print(json.dumps(results))
print("JSON_END")
