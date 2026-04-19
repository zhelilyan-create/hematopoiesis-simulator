"""
v0.9 recalibration sweep.

In v0.9 all cell-type transitions go through division fates.  M6.4 suppresses
division when n > target, which ALSO suppresses mature-cell production (the
natural apoptosis sink).  This shifts equilibrium to higher n vs v0.8.

Fix: increase crowding_apoptosis_rate to compensate for the reduced mature-cell
apoptosis.  Also probe higher density_gamma.

Grid:
  target_population_size = 1000 (fixed)
  crowding_apoptosis_rate in {0.1, 0.2, 0.3}
  density_gamma           in {8.0, 16.0}
  niche_strength          = 4.0 (best from sweep15)
  seed                    in {42, 1}
  -> 3 x 2 x 2 = 12 runs, IDs 352-363

Root cause explanation:
  v0.8: differentiation events (type-switch) were NOT suppressed by M6.4.
         Mature cells accumulated even when division was slowed.
  v0.9: ALL type transitions through division fates.  M6.4 also slows
         mature-cell production -> reduced apoptosis sink -> higher eq.n.
  Fix:  stronger crowding apoptosis compensates for lower mature-cell sink.
"""

import subprocess, json, sys, re

BASELINE_CONFIG  = "configs/hematopoiesis_baseline.yaml"
TARGET           = 1000
CROWDING_RATES   = [0.1, 0.2, 0.3]
DENSITY_GAMMAS   = [8.0, 16.0]
NICHE_STRENGTH   = 4.0
SEEDS            = [42, 1]
ASYM             = 0.02
NOISE_STD        = 0.02

MATURE_TYPES     = {"B_cell", "T_cell", "Myeloid", "Erythroid"}
PROGENITOR_TYPES = {"HSC", "MPP", "CLP", "CMP"}


def run_one(crowding_rate, density_gamma, seed):
    cmd = [
        sys.executable, "scripts/run_sim.py",
        "--config",                        BASELINE_CONFIG,
        "--seed",                          str(seed),
        "--epigenetic-asymmetry-strength", str(ASYM),
        "--epigenetic-inheritance-noise",  str(NOISE_STD),
        "--target-population-size",        str(TARGET),
        "--crowding-apoptosis-rate",       str(crowding_rate),
        "--niche-strength",                str(NICHE_STRENGTH),
        "--density-gamma",                 str(density_gamma),
        "--track-states",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print("  FAIL cr=%.2f g=%.0f seed=%d: %s" % (
            crowding_rate, density_gamma, seed, result.stderr[-300:]),
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


def classify(m):
    if not m or "final_n" not in m:
        return "error"
    if m.get("HSC", 1) == 0:
        return "hsc_loss"
    n = m["final_n"]
    if n < 50:
        return "collapsed"
    dev_pct = abs(n - TARGET) / TARGET * 100
    if dev_pct <= 15:
        return "on_target"
    if dev_pct <= 30:
        return "near_target"
    return "overshoot"


results = []
run_id_start = 352

header = "%4s  %5s  %6s  %4s | %6s  %7s  %6s  %5s  %5s | status" % (
    "rid", "cr", "gamma", "seed", "n", "tgt_dev", "dev%", "hsc%", "mat%"
)
print(header)
print("-" * len(header))

idx = 0
for crowding_rate in CROWDING_RATES:
    print("--- crowding_rate=%.2f ---" % crowding_rate)
    for density_gamma in DENSITY_GAMMAS:
        for seed in SEEDS:
            rid    = run_id_start + idx
            idx   += 1
            stdout = run_one(crowding_rate, density_gamma, seed)
            m      = parse_output(stdout) if stdout else {}
            status = classify(m)
            results.append(dict(
                run_id=rid,
                target=TARGET,
                niche_strength=NICHE_STRENGTH,
                crowding_apoptosis_rate=crowding_rate,
                density_gamma=density_gamma,
                seed=seed,
                status=status,
                **m,
            ))

            n     = m.get("final_n",    "?")
            hpct  = m.get("HSC_pct",    float("nan"))
            mat   = m.get("mature_pct", float("nan"))
            tgt_d = (n - TARGET) if isinstance(n, int) else float("nan")
            dev_p = abs(tgt_d)/TARGET*100 if isinstance(tgt_d, (int,float)) and str(tgt_d) != "nan" else float("nan")

            print("%4d  %5.2f  %6.1f  %4d | %6s  %+7s  %6.1f  %5.1f  %5.1f | %s" % (
                rid, crowding_rate, density_gamma, seed,
                str(n), str(tgt_d) if isinstance(tgt_d,int) else "?",
                dev_p, hpct, mat, status
            ))
    print()

# ===========================================================================
print()
print("=" * 72)
print("v0.9 RECALIBRATION ANALYSIS")
print("=" * 72)

on_target   = [r for r in results if r["status"] == "on_target"]
near_target = [r for r in results if r["status"] == "near_target"]
errors      = [r for r in results if r["status"] in ("error","hsc_loss","collapsed")]

print("\n(1) Equilibrium accuracy:")
print("    on_target  (dev<=15%%): %d/%d" % (len(on_target), len(results)))
print("    near_target(dev<=30%%): %d/%d" % (len(near_target), len(results)))
print("    errors:                %d/%d" % (len(errors), len(results)))

print("\n(2) Mean dev%% by crowding_rate:")
print("    %5s  %6s  %8s  %8s  %6s" % ("cr", "gamma", "mean_dev%", "min_dev%", "on_tgt"))
for cr in CROWDING_RATES:
    for g in DENSITY_GAMMAS:
        rr = [r for r in results if r["crowding_apoptosis_rate"]==cr and r["density_gamma"]==g
              and isinstance(r.get("final_n"),int)]
        if rr:
            devs = [abs(r["final_n"]-TARGET)/TARGET*100 for r in rr]
            n_on = sum(1 for r in rr if r["status"]=="on_target")
            print("    %5.2f  %6.1f  %8.1f  %8.1f  %d/%d" % (
                cr, g, sum(devs)/len(devs), min(devs), n_on, len(rr)))

print("\n(3) HSC persistence:")
hsc_lost = [r for r in results if r.get("HSC", 1)==0 or r.get("status")=="hsc_loss"]
print("    Lost HSC: %d/%d  %s" % (len(hsc_lost), len(results), "OK" if not hsc_lost else "FAIL"))

print("\n(4) Composition at on-target runs:")
if on_target:
    hsc_p = [r["HSC_pct"] for r in on_target if "HSC_pct" in r]
    mat_p = [r["mature_pct"] for r in on_target if "mature_pct" in r]
    if hsc_p:
        print("    HSC%%:    %.1f - %.1f (mean %.1f)" % (min(hsc_p), max(hsc_p), sum(hsc_p)/len(hsc_p)))
    if mat_p:
        print("    Mature%%: %.1f - %.1f (mean %.1f)" % (min(mat_p), max(mat_p), sum(mat_p)/len(mat_p)))
else:
    print("    No on_target runs")

print("\n(5) Best run:")
rr = [r for r in results if isinstance(r.get("final_n"),int)]
if rr:
    best = min(rr, key=lambda r: abs(r["final_n"]-TARGET))
    print("    run %d  cr=%.2f g=%.0f seed=%d  n=%d  dev%%=%.1f  status=%s  mature%%=%.1f" % (
        best["run_id"], best["crowding_apoptosis_rate"], best["density_gamma"],
        best["seed"], best["final_n"], abs(best["final_n"]-TARGET)/TARGET*100,
        best["status"], best.get("mature_pct", float("nan"))))

print()
print("JSON_START")
print(json.dumps(results))
print("JSON_END")
