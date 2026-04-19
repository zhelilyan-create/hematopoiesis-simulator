"""
v0.9 Fate-Driven Division sweep.

Architecture change: DifferentiationEvent removed.  All cell-type transitions
happen through fate-driven DivisionEvent with niche-modulated weights:
  modifier = exp(-k * niche * stemness * commitment_strength)
  where commitment_strength = count of daughters != parent type.

Grid:
  target_population_size = 1000 (fixed)
  niche_strength (k)     in {1, 2, 4}
  density_gamma (gamma)  in {4, 8}
  seed                   in {1, 42}
  → 3 x 2 x 2 = 12 runs, IDs 340-351

Fixed params:
  crowding_rate = 0.05
  asym = 0.02, noise_std = 0.02
  t_max = 100

Checks:
  (1) population control:  |final_n - target| <= 15%  (on_target)
  (2) HSC persistence:     HSC > 0
  (3) composition:         mature% > 5% (not all progenitors)
  (4) transitions via division: verified structurally (DifferentiationEvent removed)
"""

import subprocess, json, sys, re

BASELINE_CONFIG = "configs/hematopoiesis_baseline.yaml"
TARGET          = 1000
CROWDING_RATE   = 0.05
NICHE_STRENGTHS = [1.0, 2.0, 4.0]
DENSITY_GAMMAS  = [4.0, 8.0]
SEEDS           = [42, 1]
ASYM            = 0.02
NOISE_STD       = 0.02

MATURE_TYPES     = {"B_cell", "T_cell", "Myeloid", "Erythroid"}
PROGENITOR_TYPES = {"HSC", "MPP", "CLP", "CMP"}


def run_one(niche_strength, density_gamma, seed):
    cmd = [
        sys.executable, "scripts/run_sim.py",
        "--config",                        BASELINE_CONFIG,
        "--seed",                          str(seed),
        "--epigenetic-asymmetry-strength", str(ASYM),
        "--epigenetic-inheritance-noise",  str(NOISE_STD),
        "--target-population-size",        str(TARGET),
        "--crowding-apoptosis-rate",       str(CROWDING_RATE),
        "--niche-strength",                str(niche_strength),
        "--density-gamma",                 str(density_gamma),
        "--track-states",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print("  FAIL k=%.1f g=%.1f seed=%d: %s" % (
            niche_strength, density_gamma, seed, result.stderr[-300:]),
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
run_id_start = 340

header = "%4s  %5s  %5s  %4s | %6s  %7s  %6s  %5s  %5s | status" % (
    "rid", "k", "g", "seed", "n", "tgt_dev", "dev%", "hsc%", "mat%"
)
print(header)
print("-" * len(header))

idx = 0
for niche_strength in NICHE_STRENGTHS:
    print("--- k=%.1f ---" % niche_strength)
    for density_gamma in DENSITY_GAMMAS:
        for seed in SEEDS:
            rid    = run_id_start + idx
            idx   += 1
            stdout = run_one(niche_strength, density_gamma, seed)
            m      = parse_output(stdout) if stdout else {}
            status = classify(m)
            results.append(dict(
                run_id=rid,
                target=TARGET,
                niche_strength=niche_strength,
                density_gamma=density_gamma,
                seed=seed,
                status=status,
                **m,
            ))

            n      = m.get("final_n",   "?")
            hpct   = m.get("HSC_pct",   float("nan"))
            mat    = m.get("mature_pct", float("nan"))
            tgt_d  = (n - TARGET)       if isinstance(n, int) else float("nan")
            dev_p  = abs(tgt_d)/TARGET*100 if isinstance(tgt_d, (int,float)) and tgt_d==tgt_d else float("nan")

            print("%4d  %5.1f  %5.1f  %4d | %6s  %+7s  %6.1f  %5.1f  %5.1f | %s" % (
                rid, niche_strength, density_gamma, seed,
                str(n), str(tgt_d) if isinstance(tgt_d,int) else "?",
                dev_p, hpct, mat, status
            ))
    print()

# ===========================================================================
# Analysis
# ===========================================================================
print()
print("=" * 72)
print("v0.9 FATE-DRIVEN DIVISION — SWEEP ANALYSIS")
print("=" * 72)

on_target   = [r for r in results if r["status"] == "on_target"]
near_target = [r for r in results if r["status"] == "near_target"]
overshoot   = [r for r in results if r["status"] == "overshoot"]
errors      = [r for r in results if r["status"] in ("error","hsc_loss","collapsed")]

print("\n(1) Equilibrium accuracy (target=%d):" % TARGET)
print("    on_target  (dev<=15%%): %d/%d" % (len(on_target),  len(results)))
print("    near_target(dev<=30%%): %d/%d" % (len(near_target), len(results)))
print("    overshoot  (dev>30%%) : %d/%d" % (len(overshoot),  len(results)))
print("    errors               : %d/%d" % (len(errors),     len(results)))

print("\n(2) Mean |n-target|%% by (k, gamma):")
print("    %5s  %5s  %8s  %8s  %8s  %6s" % ("k", "gamma", "mean_dev%", "min_dev%", "max_dev%", "on_tgt"))
for k in NICHE_STRENGTHS:
    for g in DENSITY_GAMMAS:
        rr = [r for r in results if r["niche_strength"]==k and r["density_gamma"]==g
              and isinstance(r.get("final_n"),int)]
        if rr:
            devs = [abs(r["final_n"]-TARGET)/TARGET*100 for r in rr]
            n_on = sum(1 for r in rr if r["status"]=="on_target")
            print("    %5.1f  %5.1f  %8.1f  %8.1f  %8.1f  %d/%d" % (
                k, g, sum(devs)/len(devs), min(devs), max(devs), n_on, len(rr)))

print("\n(3) Best run (lowest |n-target|):")
rr = [r for r in results if isinstance(r.get("final_n"),int)]
if rr:
    best = min(rr, key=lambda r: abs(r["final_n"]-TARGET))
    print("    run %d  k=%.1f g=%.1f seed=%d  n=%d  dev%%=%.1f  status=%s" % (
        best["run_id"], best["niche_strength"], best["density_gamma"],
        best["seed"], best["final_n"], abs(best["final_n"]-TARGET)/TARGET*100,
        best["status"]))

print("\n(4) Seed variance |n_42 - n_1| by (k, gamma):")
print("    %5s  %5s  %8s" % ("k", "gamma", "|n42-n1|"))
for k in NICHE_STRENGTHS:
    for g in DENSITY_GAMMAS:
        r42 = next((r for r in results if r["niche_strength"]==k and r["density_gamma"]==g and r["seed"]==42), None)
        r1  = next((r for r in results if r["niche_strength"]==k and r["density_gamma"]==g and r["seed"]==1),  None)
        if (r42 and r1 and isinstance(r42.get("final_n"),int) and isinstance(r1.get("final_n"),int)):
            print("    %5.1f  %5.1f  %8d" % (k, g, abs(r42["final_n"]-r1["final_n"])))

print("\n(5) HSC persistence:")
hsc_lost = [r for r in results if r.get("HSC", 1)==0 or r.get("status")=="hsc_loss"]
print("    Lost HSC: %d/%d  %s" % (len(hsc_lost), len(results), "OK" if not hsc_lost else "FAIL"))

print("\n(6) Composition at on-target runs:")
if on_target:
    hsc_pcts = [r["HSC_pct"] for r in on_target if "HSC_pct" in r]
    mat_pcts  = [r["mature_pct"] for r in on_target if "mature_pct" in r]
    if hsc_pcts:
        print("    HSC%%:    %.1f - %.1f (mean %.1f)" % (min(hsc_pcts), max(hsc_pcts), sum(hsc_pcts)/len(hsc_pcts)))
    if mat_pcts:
        print("    Mature%%: %.1f - %.1f (mean %.1f)" % (min(mat_pcts), max(mat_pcts), sum(mat_pcts)/len(mat_pcts)))
else:
    print("    (no on_target runs — check overshoot)")

print("\n(7) Architecture verification:")
print("    DifferentiationEvent: REMOVED (v0.9)")
print("    Cell-type transitions: ONLY via DivisionEvent fate tables")
print("    Fate weight formula:   exp(-k * niche * stemness * commitment)")
print("    Total div rate:        base_div * div_factor * (target/n)^gamma")

print("\n(8) v0.8 baseline comparison (k=4, gamma=8, target=1000, seed=42):")
print("    v0.8 (diff events):    n=1069  dev=+6.9%%  (sweep14 run 338)")
r_new = next((r for r in results if r["niche_strength"]==4.0 and r["density_gamma"]==8.0 and r["seed"]==42), None)
if r_new and isinstance(r_new.get("final_n"),int):
    d = (r_new["final_n"]-TARGET)/TARGET*100
    print("    v0.9 (fate-driven):    n=%d  dev=%+.1f%%  status=%s" % (
        r_new["final_n"], d, r_new["status"]))
    print("    mature%% old: ~42.6%%  mature%% new: %.1f%%" % r_new.get("mature_pct", float("nan")))

print()
print("JSON_START")
print(json.dumps(results))
print("JSON_END")
