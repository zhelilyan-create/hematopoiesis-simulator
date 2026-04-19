"""
v0.8 M6.3 calibrated equilibrium sweep:
  Fixed: asym=0.02, noise_std=0.02, crowding_rate=0.05, t_max=100
  target_population_size in {500, 1000}
  niche_strength         in {1.0, 2.0, 4.0}   (M6.2 exponent)
  density_gamma          in {0.5, 1.0, 2.0}   (M6.3 power-law)
  seed = 42 only (fast scan)
  → 2 × 3 × 3 = 18 runs, run_ids 290-307

M6.3 formula (added on top of M6.2):
  density_factor = (n / target)^gamma
  n < target → diff ↓ (pulls up)
  n > target → diff ↑ (pulls down)
  → equilibrium pinned to target

Key metric: |final_n - target|  → should be < 15% of target
"""
import subprocess, json, sys, re

BASELINE_CONFIG = "configs/hematopoiesis_baseline.yaml"
TARGETS         = [500, 1000]
CROWDING_RATE   = 0.05
NICHE_STRENGTHS = [1.0, 2.0, 4.0]
DENSITY_GAMMAS  = [0.5, 1.0, 2.0]
SEED            = 42
ASYM            = 0.02
NOISE_STD       = 0.02

MATURE_TYPES     = {"B_cell", "T_cell", "Myeloid", "Erythroid"}
PROGENITOR_TYPES = {"HSC", "MPP", "CLP", "CMP"}


def run_one(target, niche_strength, density_gamma):
    cmd = [
        sys.executable, "scripts/run_sim.py",
        "--config",                        BASELINE_CONFIG,
        "--seed",                          str(SEED),
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
        print("  FAIL tgt=%d k=%.1f g=%.1f: %s" % (
            target, niche_strength, density_gamma, result.stderr[-300:]),
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

    # Bias stats
    hit = re.search(
        r"Epigenetic bias stats \(n=\d+\):\s*\n"
        r"\s+mean=([+\-]?\d+\.\d+)\s+std=(\d+\.\d+)",
        stdout,
    )
    if hit:
        m["bias_std"] = float(hit.group(2))

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
        return "on_target"    # KEY SUCCESS CRITERION
    if dev_pct <= 30:
        return "near_target"
    return "overshoot"


results = []
run_id_start = 290

header = "%4s  %5s  %5s  %5s | %6s  %7s  %6s  %5s  %5s | status" % (
    "rid", "tgt", "k", "g", "n", "tgt_dev", "dev%", "hsc%", "mat%"
)
print(header)
print("-" * len(header))

idx = 0
for target in TARGETS:
    print("--- target=%d ---" % target)
    for niche_strength in NICHE_STRENGTHS:
        for density_gamma in DENSITY_GAMMAS:
            rid    = run_id_start + idx
            idx   += 1
            stdout = run_one(target, niche_strength, density_gamma)
            m      = parse_output(stdout) if stdout else {}
            status = classify(m, target)
            results.append(dict(
                run_id=rid,
                target=target,
                niche_strength=niche_strength,
                density_gamma=density_gamma,
                seed=SEED,
                status=status,
                **m,
            ))

            n      = m.get("final_n",   "?")
            hpct   = m.get("HSC_pct",   float("nan"))
            mat    = m.get("mature_pct", float("nan"))
            tgt_d  = (n - target)       if isinstance(n, int) else float("nan")
            dev_p  = abs(tgt_d)/target*100 if isinstance(tgt_d, (int,float)) and tgt_d==tgt_d else float("nan")

            print("%4d  %5d  %5.1f  %5.1f | %6s  %+7s  %6.1f  %5.1f  %5.1f | %s" % (
                rid, target, niche_strength, density_gamma,
                str(n), str(tgt_d) if isinstance(tgt_d,int) else "?",
                dev_p, hpct, mat, status
            ))
    print()

# ==========================================================================
# Analysis
# ==========================================================================
print()
print("=" * 72)
print("M6.3 CALIBRATION ANALYSIS")
print("=" * 72)

# (1) Primary: |n - target| < 15%
on_target  = [r for r in results if r["status"] == "on_target"]
near_target = [r for r in results if r["status"] == "near_target"]
overshoot  = [r for r in results if r["status"] == "overshoot"]
errors     = [r for r in results if r["status"] in ("error","hsc_loss","collapsed")]
print("\n(1) Equilibrium accuracy:")
print("    on_target  (dev<=15%%): %d/%d" % (len(on_target),  len(results)))
print("    near_target(dev<=30%%): %d/%d" % (len(near_target), len(results)))
print("    overshoot  (dev>30%%) : %d/%d" % (len(overshoot),  len(results)))
print("    errors               : %d/%d" % (len(errors),     len(results)))

# (2) Per-gamma summary
print("\n(2) Mean |n-target|%% by density_gamma:")
print("    %5s  %8s  %8s  %8s" % ("gamma", "mean_dev%", "min_dev%", "max_dev%"))
for g in DENSITY_GAMMAS:
    rr = [r for r in results if r["density_gamma"]==g and isinstance(r.get("final_n"),int)]
    if rr:
        devs = [abs(r["final_n"]-r["target"])/r["target"]*100 for r in rr]
        print("    %5.1f  %8.1f  %8.1f  %8.1f" % (g, sum(devs)/len(devs), min(devs), max(devs)))

# (3) Best combo per target
print("\n(3) Best run per target (lowest |n-target|):")
for t in TARGETS:
    rr = [r for r in results if r["target"]==t and isinstance(r.get("final_n"),int)]
    if rr:
        best = min(rr, key=lambda r: abs(r["final_n"]-t))
        print("    target=%4d: run %d  k=%.1f g=%.1f  n=%d  dev%%=%.1f  status=%s" % (
            t, best["run_id"], best["niche_strength"], best["density_gamma"],
            best["final_n"], abs(best["final_n"]-t)/t*100, best["status"]))

# (4) M6.2 vs M6.3 comparison (at k=4, target=1000)
print("\n(4) M6.2 vs M6.3 comparison (k=4.0, target=1000, seed=42):")
print("    M6.2 (gamma=0): n=1554, dev=+554 (+55.4%%)")
m63_k4 = [r for r in results if r["target"]==1000 and r["niche_strength"]==4.0]
for r in sorted(m63_k4, key=lambda r: r["density_gamma"]):
    d = abs(r.get("final_n",9999)-1000)/1000*100
    print("    M6.3 gamma=%.1f: n=%s, dev%%=%.1f  status=%s" % (
        r["density_gamma"], r.get("final_n","?"), d, r["status"]))

# (5) HSC check
hsc_lost = [r for r in results if r.get("HSC", 1)==0 or r.get("status")=="hsc_loss"]
print("\n(5) HSC persistence: %d/18 lost HSC  %s" % (len(hsc_lost), "OK" if not hsc_lost else "FAIL"))

print()
print("JSON_START")
print(json.dumps(results))
print("JSON_END")
