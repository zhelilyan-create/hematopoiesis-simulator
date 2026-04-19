"""
Sweep20: Equilibrium validation after progenitor apoptosis recalibration.

Root cause fixed (config only, no model changes):
  Previous: apo/div ratio for progenitors was 0.02-0.10
            → density_factor had to suppress division by 10-50x to reach target
            → any suppression destroyed differentiation or composition
  Fixed:    apo/div ratio raised to 0.40-0.50
            → density_factor needs only 0.5-0.8 correction
            → M6.4 selective (v0.12) now operates in a sane regime

New apoptosis rates (hematopoiesis_baseline.yaml):
  HSC: 0.025  MPP: 0.040  CMP: 0.040  CLP: 0.040
  Mature rates unchanged.

Grid (8 runs, IDs 518-525):
  density_gamma  in {2.0, 4.0}
  density_beta   in {0.0, 1.0}
  seed           in {42, 1}
  -> 2 x 2 x 2 = 8 runs

Fixed:
  crowding_apoptosis_rate = 0.10
  crowding_threshold      = 1.3   (M4 safety-only; expected dormant)
  niche_strength          = 4.0
  target                  = 1000
  t_max                   = 100

Success criteria:
  on_target:  |dev| <= 10%
  stable:     seed variance <= 30
  realistic:  HSC% in [5%, 40%]  AND  mature% > 10%
  M4_safety:  M4 NOT active at steady state (tail_mean < 1300)

v0.11/v0.12 reference for same gamma/beta (OLD apoptosis rates):
  gamma=2, beta=0: sweep16 ~n=1205 [M4 active thr=1.1]
  gamma=4, beta=0: sweep16 ~n=1163 [M4 active thr=1.1]
  gamma=2, beta=1: sweep18 ~n=1418 [M4 active thr=1.3]
  gamma=4, beta=1: sweep18 ~n=1319 [M4 active thr=1.3]
"""

import json
import math
import re
import subprocess
import sys

BASELINE_CONFIG    = "configs/hematopoiesis_baseline.yaml"
TARGET             = 1000
NICHE_STRENGTH     = 4.0
CROWDING_RATE      = 0.10
CROWDING_THRESHOLD = 1.3
ASYM               = 0.02
NOISE_STD          = 0.02
T_MAX              = 100

DENSITY_GAMMAS = [2.0, 4.0]
DENSITY_BETAS  = [0.0, 1.0]
SEEDS          = [42, 1]

MATURE_TYPES = {"B_cell", "T_cell", "Myeloid", "Erythroid"}
M4_THRESHOLD = CROWDING_THRESHOLD * TARGET   # 1300


def run_one(gamma: float, beta: float, seed: int) -> str | None:
    cmd = [
        sys.executable, "scripts/run_sim.py",
        "--config",                        BASELINE_CONFIG,
        "--seed",                          str(seed),
        "--epigenetic-asymmetry-strength", str(ASYM),
        "--epigenetic-inheritance-noise",  str(NOISE_STD),
        "--target-population-size",        str(TARGET),
        "--crowding-apoptosis-rate",       str(CROWDING_RATE),
        "--crowding-threshold",            str(CROWDING_THRESHOLD),
        "--niche-strength",                str(NICHE_STRENGTH),
        "--density-gamma",                 str(gamma),
        "--density-beta",                  str(beta),
        "--t-max",                         str(T_MAX),
        "--track-states",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print("  FAIL g=%.1f b=%.1f seed=%d: %s" % (
            gamma, beta, seed, result.stderr[-300:]), file=sys.stderr)
        return None
    return result.stdout


def parse_output(stdout: str) -> dict:
    m: dict = {}
    hit = re.search(r"Final population\s+\(n=(\d+)", stdout)
    if hit:
        m["final_n"] = int(hit.group(1))

    cell_counts: dict = {}
    cell_pcts: dict   = {}
    for line in stdout.splitlines():
        hit = re.match(r"\s+(\w+)\s+(\d+)\s+\(\s*([0-9.]+)%\)", line)
        if hit:
            cell_counts[hit.group(1)] = int(hit.group(2))
            cell_pcts[hit.group(1)]   = float(hit.group(3))

    if cell_counts:
        for ct in ["HSC","MPP","CLP","CMP","B_cell","T_cell","Myeloid","Erythroid"]:
            m[ct]          = cell_counts.get(ct, 0)
            m[f"{ct}_pct"] = cell_pcts.get(ct, 0.0)
        total = m.get("final_n", sum(cell_counts.values()))
        if total:
            m["mature_pct"] = round(
                100 * sum(cell_counts.get(t, 0) for t in MATURE_TYPES) / total, 1)
            m["HSC_pct"]    = cell_pcts.get("HSC", 0.0)

    hit = re.search(
        r"State distributions.*?:\s*\n"
        r"\s+mean_stemness\s*:\s*([+\-]?\d+\.\d+)\s+/\s+([+\-]?\d+\.\d+)\s*\n"
        r"\s+mean_stress\s*:\s*([+\-]?\d+\.\d+)\s+/\s+([+\-]?\d+\.\d+)\s*\n"
        r"\s+mean_bias\s*:\s*([+\-]?\d+\.\d+)\s+/\s+([+\-]?\d+\.\d+)\s*\n"
        r"\s+mean_pop_size\s*:\s*(\d+)\s+/\s+([0-9.]+)",
        stdout,
    )
    if hit:
        m["tail_mean_pop_size"] = float(hit.group(8))

    return m


def classify(m: dict) -> tuple[str, bool]:
    if not m or "final_n" not in m:
        return "error", False
    if m.get("HSC", 1) == 0:
        return "hsc_loss", False
    n = m["final_n"]
    dev = abs(n - TARGET) / TARGET
    if dev <= 0.10:
        status = "on_target"
    elif dev <= 0.20:
        status = "near_target"
    elif dev <= 0.40:
        status = "far"
    else:
        status = "overshoot"
    tail     = m.get("tail_mean_pop_size")
    m4_at_ss = (tail > M4_THRESHOLD) if tail is not None else (n > M4_THRESHOLD)
    return status, m4_at_ss


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

results: list[dict] = []
RUN_START = 518

hdr = "%4s  %5s  %5s  %4s | %6s  %7s  %6s  %5s  %5s  %6s | status" % (
    "rid", "g", "beta", "seed", "n", "dev", "dev%", "hsc%", "mat%", "tail_n")
print(hdr)
print("-" * len(hdr))

idx = 0
for gamma in DENSITY_GAMMAS:
    print("--- gamma=%.1f ---" % gamma)
    for beta in DENSITY_BETAS:
        for seed in SEEDS:
            rid    = RUN_START + idx
            idx   += 1
            stdout = run_one(gamma, beta, seed)
            m      = parse_output(stdout) if stdout else {}
            status, m4_at_ss = classify(m)

            n     = m.get("final_n",           "?")
            hpct  = m.get("HSC_pct",           float("nan"))
            mat   = m.get("mature_pct",         float("nan"))
            tail  = m.get("tail_mean_pop_size", float("nan"))
            tgt_d = (n - TARGET) if isinstance(n, int) else float("nan")
            dev_p = abs(tgt_d) / TARGET * 100 if isinstance(n, int) else float("nan")

            results.append(dict(
                run_id=rid, gamma=gamma, beta=beta, seed=seed,
                status=status, m4_at_ss=m4_at_ss, **m,
            ))

            print("%4d  %5.1f  %5.1f  %4d | %6s  %+7s  %6.1f  %5.1f  %5.1f  %6.0f | %s%s" % (
                rid, gamma, beta, seed,
                str(n),
                str(tgt_d) if isinstance(n, int) else "?",
                dev_p,
                hpct if not math.isnan(hpct) else -1,
                mat  if not math.isnan(mat)  else -1,
                tail if not math.isnan(tail) else -1,
                status,
                " [M4!]" if m4_at_ss else "",
            ))
        print()
    print()


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

valid     = [r for r in results if isinstance(r.get("final_n"), int)]
on_target = [r for r in valid if r["status"] == "on_target"]
m4_active = [r for r in results if r.get("m4_at_ss")]

print()
print("=" * 76)
print("SWEEP20 ANALYSIS  Recalibrated progenitor apoptosis + v0.12 selective")
print("=" * 76)

print("\n(1) Summary:")
print("    on_target  (dev<=10%%): %d/%d" % (len(on_target), len(results)))
print("    M4 active at SS       : %d/%d" % (len(m4_active), len(results)))

# --- (A) All runs ---
print("\n(A) All runs:")
print("    %4s  %5s  %5s  %4s  %6s  %6s  %5s  %5s  %6s  %s" % (
    "rid","g","beta","seed","n","dev%","hsc%","mat%","tail_n","M4_SS"))
for r in sorted(valid, key=lambda x: abs(x["final_n"] - TARGET)):
    dev_p = abs(r["final_n"] - TARGET) / TARGET * 100
    tail  = r.get("tail_mean_pop_size", float("nan"))
    print("    %4d  %5.1f  %5.1f  %4d  %6d  %6.1f  %5.1f  %5.1f  %6.0f  %s" % (
        r["run_id"], r["gamma"], r["beta"], r["seed"],
        r["final_n"], dev_p,
        r.get("HSC_pct", float("nan")), r.get("mature_pct", float("nan")),
        tail if not math.isnan(tail) else -1,
        "active" if r.get("m4_at_ss") else "OFF"))

# --- (B) Sweet spot ---
print("\n(B) Runs satisfying all criteria (dev<=10%%, HSC 5-40%%, mature>10%%, M4 off):")
sweet = [r for r in valid
         if abs(r["final_n"]-TARGET)/TARGET <= 0.10
         and 5.0 <= r.get("HSC_pct", 0) <= 40.0
         and r.get("mature_pct", 0) > 10.0
         and not r.get("m4_at_ss")]
if sweet:
    print("    %4s  %5s  %5s  %4s  %6s  %6s  %5s  %5s" % (
        "rid","g","beta","seed","n","dev%","hsc%","mat%"))
    for r in sweet:
        print("    %4d  %5.1f  %5.1f  %4d  %6d  %6.1f  %5.1f  %5.1f" % (
            r["run_id"], r["gamma"], r["beta"], r["seed"],
            r["final_n"], abs(r["final_n"]-TARGET)/TARGET*100,
            r.get("HSC_pct", float("nan")), r.get("mature_pct", float("nan"))))
else:
    print("    NONE — check individual criteria below.")
    for r in sorted(valid, key=lambda x: abs(x["final_n"]-TARGET))[:4]:
        dev_p = abs(r["final_n"]-TARGET)/TARGET*100
        fails = []
        if dev_p > 10.0:                              fails.append("dev=%.1f%%" % dev_p)
        if not (5.0 <= r.get("HSC_pct",0) <= 40.0):  fails.append("HSC%%=%.1f" % r.get("HSC_pct",0))
        if r.get("mature_pct",0) <= 10.0:             fails.append("mat%%=%.1f" % r.get("mature_pct",0))
        if r.get("m4_at_ss"):                         fails.append("M4_active")
        print("    g=%.1f b=%.1f seed=%d: n=%d  FAIL: %s" % (
            r["gamma"], r["beta"], r["seed"], r["final_n"], ", ".join(fails)))

# --- (C) Seed variance ---
print("\n(C) Seed variance |n42 - n1|:")
print("    %5s  %5s  %8s" % ("g","beta","|n42-n1|"))
for gamma in DENSITY_GAMMAS:
    for beta in DENSITY_BETAS:
        r42 = next((r for r in results if r["gamma"]==gamma and r["beta"]==beta
                    and r["seed"]==42), None)
        r1  = next((r for r in results if r["gamma"]==gamma and r["beta"]==beta
                    and r["seed"]==1), None)
        if r42 and r1 and isinstance(r42.get("final_n"),int) and isinstance(r1.get("final_n"),int):
            print("    %5.1f  %5.1f  %8d" % (gamma, beta, abs(r42["final_n"]-r1["final_n"])))

# --- (D) Composition snapshot ---
print("\n(D) Population composition (seed=42):")
print("    %5s  %5s  %6s  %5s  %5s  %5s  %5s  %5s" % (
    "g","beta","n","HSC%","MPP%","CMP%","CLP%","mat%"))
for gamma in DENSITY_GAMMAS:
    for beta in DENSITY_BETAS:
        r = next((r for r in results if r["gamma"]==gamma and r["beta"]==beta
                  and r["seed"]==42), None)
        if r and isinstance(r.get("final_n"), int):
            print("    %5.1f  %5.1f  %6d  %5.1f  %5.1f  %5.1f  %5.1f  %5.1f" % (
                gamma, beta, r["final_n"],
                r.get("HSC_pct",0), r.get("MPP_pct",0),
                r.get("CMP_pct",0), r.get("CLP_pct",0),
                r.get("mature_pct",0)))

# --- (E) Verdict ---
print()
print("=" * 76)
print("VERDICT")
print("=" * 76)

if sweet:
    by_key: dict = {}
    for r in sweet:
        by_key.setdefault((r["gamma"],r["beta"]), []).append(r)
    both = {k:v for k,v in by_key.items() if len(v)==2}
    if both:
        best_key = min(both, key=lambda k: sum(abs(r["final_n"]-TARGET) for r in both[k]))
        g, b = best_key
        rr = both[best_key]
        mean_dev = sum(abs(r["final_n"]-TARGET)/TARGET*100 for r in rr)/2
        print()
        print("SUCCESS: Both seeds on_target with all criteria met.")
        print("  Best: gamma=%.1f  beta=%.1f  mean_dev=%.1f%%  M4=OFF" % (g, b, mean_dev))
        print()
        print("  Recommended baseline:")
        print("    density_gamma:           %.1f" % g)
        print("    density_beta:            %.1f" % b)
        print("    crowding_apoptosis_rate: 0.10")
        print("    crowding_threshold:      1.3")
        print("    HSC apo:  0.025  MPP/CMP/CLP apo: 0.040")
    else:
        best = min(sweet, key=lambda r: abs(r["final_n"]-TARGET))
        print()
        print("PARTIAL: on_target achieved but not both seeds.")
        print("  Best: g=%.1f b=%.1f seed=%d n=%d dev=%.1f%%" % (
            best["gamma"], best["beta"], best["seed"], best["final_n"],
            abs(best["final_n"]-TARGET)/TARGET*100))
        print("  Try expanding grid: beta in {0.5, 1.0, 1.5}.")
else:
    best = min(valid, key=lambda r: abs(r["final_n"]-TARGET)) if valid else None
    if best:
        dev_p = abs(best["final_n"]-TARGET)/TARGET*100
        print()
        print("NOT YET: no run meets all criteria.")
        print("  Best n=%d dev=%.1f%% HSC%%=%.1f mat%%=%.1f M4=%s" % (
            best["final_n"], dev_p,
            best.get("HSC_pct",0), best.get("mature_pct",0),
            "active" if best.get("m4_at_ss") else "OFF"))
        print()
        # Diagnose which criterion fails
        if dev_p > 10:
            # Is equilibrium above or below target?
            mean_n = sum(r["final_n"] for r in valid)/len(valid)
            if mean_n > TARGET:
                print("  Equilibrium still above target (mean n=%.0f)." % mean_n)
                print("  Options: raise apo further, or lower threshold so M4 co-regulates.")
            else:
                print("  Equilibrium below target — apoptosis too aggressive.")
                print("  Reduce progenitor apo rates (e.g. HSC: 0.025 -> 0.015).")
        else:
            print("  Composition criterion fails — check HSC% and mature%.")

print()
print("JSON_START")
print(json.dumps(results, default=str))
print("JSON_END")
