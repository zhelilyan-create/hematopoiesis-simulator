"""
v0.10 Soft Control sweep.

Changes vs v0.9:
  M6.4: power-law (target/n)^gamma  →  exp(gamma * (target-n)/target)
  M4:   always-on crowding           →  safety-only (n > threshold*target)

Grid (54 runs, IDs 364-417):
  density_gamma     in {1.0, 2.0, 4.0}
  crowding_rate     in {0.05, 0.1, 0.2}
  crowding_threshold in {1.1, 1.2, 1.5}
  seed              in {42, 1}
  → 3 x 3 x 3 x 2 = 54 runs

Fixed: target=1000, niche_strength=4.0, asym=0.02, noise_std=0.02, t_max=100

Checks:
  (1) |final_n - target| <= 20%   (on_target, relaxed from 15%)
  (2) HSC persistence
  (3) M4 role: does it activate? (n > threshold * target?)
  (4) variance across seeds
"""

import subprocess, json, sys, re

BASELINE_CONFIG    = "configs/hematopoiesis_baseline.yaml"
TARGET             = 1000
NICHE_STRENGTH     = 4.0
DENSITY_GAMMAS     = [1.0, 2.0, 4.0]
CROWDING_RATES     = [0.05, 0.1, 0.2]
CROWDING_THRESHOLDS = [1.1, 1.2, 1.5]
SEEDS              = [42, 1]
ASYM               = 0.02
NOISE_STD          = 0.02

MATURE_TYPES     = {"B_cell", "T_cell", "Myeloid", "Erythroid"}
PROGENITOR_TYPES = {"HSC", "MPP", "CLP", "CMP"}


def run_one(gamma, crowding_rate, threshold, seed):
    cmd = [
        sys.executable, "scripts/run_sim.py",
        "--config",                        BASELINE_CONFIG,
        "--seed",                          str(seed),
        "--epigenetic-asymmetry-strength", str(ASYM),
        "--epigenetic-inheritance-noise",  str(NOISE_STD),
        "--target-population-size",        str(TARGET),
        "--crowding-apoptosis-rate",       str(crowding_rate),
        "--crowding-threshold",            str(threshold),
        "--niche-strength",                str(NICHE_STRENGTH),
        "--density-gamma",                 str(gamma),
        "--track-states",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print("  FAIL g=%.1f cr=%.2f thr=%.1f seed=%d: %s" % (
            gamma, crowding_rate, threshold, seed, result.stderr[-200:]),
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
    if dev_pct <= 20:
        return "on_target"
    if dev_pct <= 40:
        return "near_target"
    return "overshoot"


results = []
run_id_start = 364

header = "%4s  %5s  %5s  %5s  %4s | %6s  %7s  %6s  %5s  %5s | status" % (
    "rid", "g", "cr", "thr", "seed", "n", "dev", "dev%", "hsc%", "mat%"
)
print(header)
print("-" * len(header))

idx = 0
for gamma in DENSITY_GAMMAS:
    print("--- gamma=%.1f ---" % gamma)
    for crowding_rate in CROWDING_RATES:
        for threshold in CROWDING_THRESHOLDS:
            for seed in SEEDS:
                rid    = run_id_start + idx
                idx   += 1
                stdout = run_one(gamma, crowding_rate, threshold, seed)
                m      = parse_output(stdout) if stdout else {}
                status = classify(m)

                n     = m.get("final_n",    "?")
                hpct  = m.get("HSC_pct",    float("nan"))
                mat   = m.get("mature_pct", float("nan"))
                tgt_d = (n - TARGET) if isinstance(n, int) else float("nan")
                dev_p = abs(tgt_d)/TARGET*100 if isinstance(tgt_d, (int,float)) and str(tgt_d) != "nan" else float("nan")

                # Detect if M4 safety valve would have been active
                m4_active = isinstance(n, int) and n > threshold * TARGET

                results.append(dict(
                    run_id=rid, target=TARGET,
                    density_gamma=gamma,
                    crowding_apoptosis_rate=crowding_rate,
                    crowding_threshold=threshold,
                    seed=seed, status=status, m4_active=m4_active,
                    **m,
                ))

                print("%4d  %5.1f  %5.2f  %5.1f  %4d | %6s  %+7s  %6.1f  %5.1f  %5.1f | %s%s" % (
                    rid, gamma, crowding_rate, threshold, seed,
                    str(n), str(tgt_d) if isinstance(tgt_d,int) else "?",
                    dev_p, hpct, mat, status,
                    " [M4!]" if m4_active else ""
                ))
        print()
    print()

# ===========================================================================
print()
print("=" * 76)
print("v0.10 SOFT CONTROL ANALYSIS (exp M6.4 + threshold M4)")
print("=" * 76)

on_target   = [r for r in results if r["status"] == "on_target"]
near_target = [r for r in results if r["status"] == "near_target"]
overshoot   = [r for r in results if r["status"] == "overshoot"]
errors      = [r for r in results if r["status"] in ("error","hsc_loss","collapsed")]
m4_fired    = [r for r in results if r.get("m4_active")]

print("\n(1) Equilibrium accuracy (|dev| <= 20%%):")
print("    on_target  (dev<=20%%): %d/%d" % (len(on_target),  len(results)))
print("    near_target(dev<=40%%): %d/%d" % (len(near_target), len(results)))
print("    overshoot  (dev>40%%) : %d/%d" % (len(overshoot),  len(results)))
print("    errors               : %d/%d" % (len(errors),     len(results)))
print("    M4 safety fired      : %d/%d" % (len(m4_fired),   len(results)))

print("\n(2) Mean dev%% by density_gamma (all cr, thr, seeds):")
print("    %5s  %8s  %8s  %8s  %6s" % ("gamma", "mean_dev%", "min_dev%", "max_dev%", "on_tgt"))
for g in DENSITY_GAMMAS:
    rr = [r for r in results if r["density_gamma"]==g and isinstance(r.get("final_n"),int)]
    if rr:
        devs = [abs(r["final_n"]-TARGET)/TARGET*100 for r in rr]
        n_on = sum(1 for r in rr if r["status"]=="on_target")
        print("    %5.1f  %8.1f  %8.1f  %8.1f  %d/%d" % (
            g, sum(devs)/len(devs), min(devs), max(devs), n_on, len(rr)))

print("\n(3) Effect of crowding_threshold on M4 activation rate:")
for thr in CROWDING_THRESHOLDS:
    rr   = [r for r in results if r["crowding_threshold"]==thr]
    fired = [r for r in rr if r.get("m4_active")]
    print("    threshold=%.1f: M4 active in %d/%d runs" % (thr, len(fired), len(rr)))

print("\n(4) Seed variance |n_42 - n_1| by (gamma, cr, thr):")
print("    %5s  %5s  %5s  %8s" % ("gamma", "cr", "thr", "|n42-n1|"))
for g in DENSITY_GAMMAS:
    for cr in CROWDING_RATES:
        for thr in CROWDING_THRESHOLDS:
            r42 = next((r for r in results if r["density_gamma"]==g and
                        r["crowding_apoptosis_rate"]==cr and
                        r["crowding_threshold"]==thr and r["seed"]==42), None)
            r1  = next((r for r in results if r["density_gamma"]==g and
                        r["crowding_apoptosis_rate"]==cr and
                        r["crowding_threshold"]==thr and r["seed"]==1),  None)
            if (r42 and r1 and isinstance(r42.get("final_n"),int)
                    and isinstance(r1.get("final_n"),int)):
                delta = abs(r42["final_n"] - r1["final_n"])
                print("    %5.1f  %5.2f  %5.1f  %8d" % (g, cr, thr, delta))

print("\n(5) HSC persistence:")
hsc_lost = [r for r in results if r.get("HSC",1)==0 or r.get("status")=="hsc_loss"]
print("    Lost HSC: %d/%d  %s" % (len(hsc_lost), len(results), "OK" if not hsc_lost else "FAIL"))

print("\n(6) Best run (lowest |n-target|):")
rr = [r for r in results if isinstance(r.get("final_n"),int)]
if rr:
    best = min(rr, key=lambda r: abs(r["final_n"]-TARGET))
    print("    run %d  g=%.1f cr=%.2f thr=%.1f seed=%d  n=%d  dev%%=%.1f  M4=%s  mature%%=%.1f" % (
        best["run_id"], best["density_gamma"], best["crowding_apoptosis_rate"],
        best["crowding_threshold"], best["seed"], best["final_n"],
        abs(best["final_n"]-TARGET)/TARGET*100,
        "active" if best.get("m4_active") else "inactive",
        best.get("mature_pct", float("nan"))))

print("\n(7) v0.9 vs v0.10 comparison (target=1000, seed=42):")
print("    v0.9 power-law gamma=8:   n=1069  dev=+6.9%%  (sweep14 run 338)")
print("    v0.9 power-law gamma=16:  n=1061  dev=+6.1%%  (sweep15b run 358)")
r_new = next((r for r in results if r["density_gamma"]==4.0 and r["seed"]==42), None)
if r_new and isinstance(r_new.get("final_n"),int):
    d = (r_new["final_n"]-TARGET)/TARGET*100
    print("    v0.10 exp   gamma=4.0:   n=%d  dev=%+.1f%%  M4=%s" % (
        r_new["final_n"], d, "active" if r_new.get("m4_active") else "inactive"))
r_g2 = next((r for r in results if r["density_gamma"]==2.0 and r["seed"]==42), None)
if r_g2 and isinstance(r_g2.get("final_n"),int):
    d = (r_g2["final_n"]-TARGET)/TARGET*100
    print("    v0.10 exp   gamma=2.0:   n=%d  dev=%+.1f%%  M4=%s" % (
        r_g2["final_n"], d, "active" if r_g2.get("m4_active") else "inactive"))

print()
print("JSON_START")
print(json.dumps(results))
print("JSON_END")
