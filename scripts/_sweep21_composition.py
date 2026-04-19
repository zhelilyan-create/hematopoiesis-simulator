"""
Sweep21: HSC self-renewal weight scan (composition correction).

Background:
  Sweep20 achieved stable population size (dev 3-6%, M4 OFF) but composition
  is imbalanced: HSC%=5-7%, mature%=50-60%.
  Root cause: excessive commitment from HSC due to low SR weight (0.70).

  Strategy: raise HSC SR weight ONLY (composition-only correction).
  No changes to rates, density controller, or niche parameters.

Grid (6 runs, IDs 526-531):
  hsc_sr_weight in {0.80, 0.825, 0.85}
  seed          in {42, 1}
  -> 3 x 2 = 6 runs

Derived weights (sum = 1.0 enforced):
  SR=0.80:  [HSC,HSC]=0.800  [HSC,MPP]=0.150  [MPP,MPP]=0.050
  SR=0.825: [HSC,HSC]=0.825  [HSC,MPP]=0.125  [MPP,MPP]=0.050
  SR=0.85:  [HSC,HSC]=0.850  [HSC,MPP]=0.100  [MPP,MPP]=0.050

Fixed (sweep20 best config):
  density_gamma          = 4.0
  density_beta           = 0.0
  crowding_threshold     = 1.3
  crowding_apoptosis_rate= 0.10
  niche_strength         = 4.0
  target                 = 1000
  t_max                  = 100

Success criteria:
  on_target  : |dev| <= 10%
  HSC range  : 10% <= HSC% <= 20%
  mature range: mature% in [30%, 45%]
  M4 safety  : M4 NOT active at SS (tail_mean < 1300)
  hierarchy  : all compartments present (MPP, CMP, CLP, mature > 0)
"""

import copy
import json
import math
import os
import re
import subprocess
import sys
import tempfile

import yaml

BASELINE_CONFIG     = "configs/hematopoiesis_baseline.yaml"
TARGET              = 1000
DENSITY_GAMMA       = 4.0
DENSITY_BETA        = 0.0
CROWDING_RATE       = 0.10
CROWDING_THRESHOLD  = 1.3
NICHE_STRENGTH      = 4.0
ASYM                = 0.02
NOISE_STD           = 0.02
T_MAX               = 100

# MPP,MPP fixed; asymmetric takes the remainder
MPP_MPP_WEIGHT = 0.05

SR_WEIGHTS = [0.80, 0.825, 0.85]
SEEDS      = [42, 1]

MATURE_TYPES = {"B_cell", "T_cell", "Myeloid", "Erythroid"}
M4_THRESHOLD = CROWDING_THRESHOLD * TARGET   # 1300


def make_config(sr_weight: float) -> dict:
    """Load baseline and patch HSC division_fates only."""
    with open(BASELINE_CONFIG, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    hsc_asym = round(1.0 - sr_weight - MPP_MPP_WEIGHT, 10)
    cfg["division_fates"]["HSC"] = [
        {"daughters": ["HSC", "HSC"], "weight": sr_weight},
        {"daughters": ["HSC", "MPP"], "weight": hsc_asym},
        {"daughters": ["MPP", "MPP"], "weight": MPP_MPP_WEIGHT},
    ]
    return cfg


def run_one(sr_weight: float, seed: int) -> str | None:
    cfg = make_config(sr_weight)
    # Write temp YAML
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".yaml", prefix="sweep21_")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            yaml.dump(cfg, fh, default_flow_style=False, allow_unicode=True)
        cmd = [
            sys.executable, "scripts/run_sim.py",
            "--config",                        tmp_path,
            "--seed",                          str(seed),
            "--epigenetic-asymmetry-strength", str(ASYM),
            "--epigenetic-inheritance-noise",  str(NOISE_STD),
            "--target-population-size",        str(TARGET),
            "--crowding-apoptosis-rate",       str(CROWDING_RATE),
            "--crowding-threshold",            str(CROWDING_THRESHOLD),
            "--niche-strength",                str(NICHE_STRENGTH),
            "--density-gamma",                 str(DENSITY_GAMMA),
            "--density-beta",                  str(DENSITY_BETA),
            "--t-max",                         str(T_MAX),
            "--track-states",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print("  FAIL sr=%.3f seed=%d: %s" % (
                sr_weight, seed, result.stderr[-300:]), file=sys.stderr)
            return None
        return result.stdout
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


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
RUN_START = 526

hdr = "%4s  %6s  %4s | %6s  %7s  %6s  %5s  %5s  %5s  %6s | status" % (
    "rid", "sr_w", "seed", "n", "dev", "dev%", "hsc%", "mpp%", "mat%", "tail_n")
print(hdr)
print("-" * len(hdr))

idx = 0
for sr_w in SR_WEIGHTS:
    hsc_asym = round(1.0 - sr_w - MPP_MPP_WEIGHT, 10)
    print("--- HSC SR=%.3f  asym=%.3f  comm=%.3f ---" % (sr_w, hsc_asym, MPP_MPP_WEIGHT))
    for seed in SEEDS:
        rid    = RUN_START + idx
        idx   += 1
        stdout = run_one(sr_w, seed)
        m      = parse_output(stdout) if stdout else {}
        status, m4_at_ss = classify(m)

        n     = m.get("final_n",           "?")
        hpct  = m.get("HSC_pct",           float("nan"))
        mpct  = m.get("MPP_pct",           float("nan"))
        mat   = m.get("mature_pct",         float("nan"))
        tail  = m.get("tail_mean_pop_size", float("nan"))
        tgt_d = (n - TARGET) if isinstance(n, int) else float("nan")
        dev_p = abs(tgt_d) / TARGET * 100 if isinstance(n, int) else float("nan")

        results.append(dict(
            run_id=rid, sr_weight=sr_w, seed=seed,
            status=status, m4_at_ss=m4_at_ss, **m,
        ))

        print("%4d  %6.3f  %4d | %6s  %+7s  %6.1f  %5.1f  %5.1f  %5.1f  %6.0f | %s%s" % (
            rid, sr_w, seed,
            str(n),
            str(tgt_d) if isinstance(n, int) else "?",
            dev_p if not math.isnan(dev_p) else -1,
            hpct if not math.isnan(hpct) else -1,
            mpct if not math.isnan(mpct) else -1,
            mat  if not math.isnan(mat)  else -1,
            tail if not math.isnan(tail) else -1,
            status,
            " [M4!]" if m4_at_ss else "",
        ))
    print()


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

valid     = [r for r in results if isinstance(r.get("final_n"), int)]
on_target = [r for r in valid if r["status"] == "on_target"]
m4_active = [r for r in results if r.get("m4_at_ss")]

print()
print("=" * 80)
print("SWEEP21 ANALYSIS  HSC SR-weight composition scan  (v0.12 recal baseline)")
print("=" * 80)

print("\n(1) Summary:")
print("    on_target  (dev<=10%%): %d/%d" % (len(on_target), len(results)))
print("    M4 active at SS       : %d/%d" % (len(m4_active), len(results)))

# --- (A) All runs ---
print("\n(A) All runs (sorted by HSC%):")
print("    %4s  %6s  %4s  %6s  %6s  %5s  %5s  %5s  %5s  %s" % (
    "rid","sr_w","seed","n","dev%","hsc%","mpp%","cmp%","mat%","M4_SS"))
for r in sorted(valid, key=lambda x: -x.get("HSC_pct", 0)):
    dev_p = abs(r["final_n"] - TARGET) / TARGET * 100
    print("    %4d  %6.3f  %4d  %6d  %6.1f  %5.1f  %5.1f  %5.1f  %5.1f  %s" % (
        r["run_id"], r["sr_weight"], r["seed"],
        r["final_n"], dev_p,
        r.get("HSC_pct",0), r.get("MPP_pct",0),
        r.get("CMP_pct",0), r.get("mature_pct",0),
        "active" if r.get("m4_at_ss") else "OFF"))

# --- (B) Sweet spot ---
print("\n(B) Runs satisfying all criteria (dev<=10%%, HSC 10-20%%, mature 30-45%%, M4 off):")
sweet = [r for r in valid
         if abs(r["final_n"]-TARGET)/TARGET <= 0.10
         and 10.0 <= r.get("HSC_pct", 0) <= 20.0
         and 30.0 <= r.get("mature_pct", 0) <= 45.0
         and not r.get("m4_at_ss")]
if sweet:
    print("    %4s  %6s  %4s  %6s  %6s  %5s  %5s  %5s" % (
        "rid","sr_w","seed","n","dev%","hsc%","mpp%","mat%"))
    for r in sweet:
        print("    %4d  %6.3f  %4d  %6d  %6.1f  %5.1f  %5.1f  %5.1f" % (
            r["run_id"], r["sr_weight"], r["seed"],
            r["final_n"], abs(r["final_n"]-TARGET)/TARGET*100,
            r.get("HSC_pct",0), r.get("MPP_pct",0), r.get("mature_pct",0)))
else:
    print("    NONE — check individual criteria below.")
    best4 = sorted(valid, key=lambda x: (
        abs(x["final_n"]-TARGET)/TARGET
        + abs(max(0, 10.0 - x.get("HSC_pct",0)) + max(0, x.get("HSC_pct",0) - 20.0))
    ))[:4]
    for r in best4:
        dev_p = abs(r["final_n"]-TARGET)/TARGET*100
        fails = []
        if dev_p > 10.0:                                        fails.append("dev=%.1f%%" % dev_p)
        if not (10.0 <= r.get("HSC_pct",0) <= 20.0):           fails.append("HSC%%=%.1f" % r.get("HSC_pct",0))
        if not (30.0 <= r.get("mature_pct",0) <= 45.0):        fails.append("mat%%=%.1f" % r.get("mature_pct",0))
        if r.get("m4_at_ss"):                                   fails.append("M4_active")
        print("    sr=%.3f seed=%d: n=%d  FAIL: %s" % (
            r["sr_weight"], r["seed"], r["final_n"], ", ".join(fails)))

# --- (C) SR weight effect on composition ---
print("\n(C) SR weight effect on composition (seed=42):")
print("    %6s  %6s  %5s  %5s  %5s  %5s  %5s" % (
    "sr_w","n","dev%","hsc%","mpp%","cmp%","mat%"))
for sr_w in SR_WEIGHTS:
    r = next((r for r in results if r["sr_weight"]==sr_w and r["seed"]==42), None)
    if r and isinstance(r.get("final_n"), int):
        dev_p = abs(r["final_n"]-TARGET)/TARGET*100
        print("    %6.3f  %6d  %5.1f  %5.1f  %5.1f  %5.1f  %5.1f" % (
            sr_w, r["final_n"], dev_p,
            r.get("HSC_pct",0), r.get("MPP_pct",0),
            r.get("CMP_pct",0), r.get("mature_pct",0)))

# --- (D) Seed variance ---
print("\n(D) Seed variance |n42 - n1|:")
print("    %6s  %8s" % ("sr_w","|n42-n1|"))
for sr_w in SR_WEIGHTS:
    r42 = next((r for r in results if r["sr_weight"]==sr_w and r["seed"]==42), None)
    r1  = next((r for r in results if r["sr_weight"]==sr_w and r["seed"]==1),  None)
    if (r42 and r1
            and isinstance(r42.get("final_n"), int)
            and isinstance(r1.get("final_n"), int)):
        print("    %6.3f  %8d" % (sr_w, abs(r42["final_n"]-r1["final_n"])))

# --- (E) Hierarchy check ---
print("\n(E) Hierarchy completeness (all compartments > 0?):")
for r in sorted(valid, key=lambda x: x["sr_weight"]):
    missing = [ct for ct in ["HSC","MPP","CMP","CLP","Myeloid","Erythroid","B_cell","T_cell"]
               if r.get(ct, 0) == 0]
    ok = "OK" if not missing else "MISSING: " + ",".join(missing)
    print("    sr=%.3f seed=%d: %s" % (r["sr_weight"], r["seed"], ok))

# --- (F) Verdict ---
print()
print("=" * 80)
print("VERDICT")
print("=" * 80)

if sweet:
    by_key: dict = {}
    for r in sweet:
        by_key.setdefault(r["sr_weight"], []).append(r)
    both = {k: v for k, v in by_key.items() if len(v) == 2}
    if both:
        best_sr = min(both, key=lambda k: (
            sum(abs(r.get("HSC_pct",0) - 15.0) for r in both[k])  # closest to 15% HSC
        ))
        rr = both[best_sr]
        mean_dev  = sum(abs(r["final_n"]-TARGET)/TARGET*100 for r in rr) / 2
        mean_hsc  = sum(r.get("HSC_pct",0) for r in rr) / 2
        mean_mat  = sum(r.get("mature_pct",0) for r in rr) / 2
        print()
        print("SUCCESS: Both seeds pass all criteria.")
        print("  Best SR weight: %.3f  mean_dev=%.1f%%  mean_HSC=%.1f%%  mean_mat=%.1f%%  M4=OFF" % (
            best_sr, mean_dev, mean_hsc, mean_mat))
        print()
        print("  Recommended update to baseline division_fates.HSC:")
        hsc_asym = round(1.0 - best_sr - MPP_MPP_WEIGHT, 10)
        print("    [HSC, HSC] : %.3f" % best_sr)
        print("    [HSC, MPP] : %.3f" % hsc_asym)
        print("    [MPP, MPP] : %.3f" % MPP_MPP_WEIGHT)
    else:
        best = min(sweet, key=lambda r: abs(r["final_n"]-TARGET))
        print()
        print("PARTIAL: criteria met but not by both seeds simultaneously.")
        print("  Best: sr=%.3f seed=%d n=%d dev=%.1f%% HSC%%=%.1f%%" % (
            best["sr_weight"], best["seed"], best["final_n"],
            abs(best["final_n"]-TARGET)/TARGET*100, best.get("HSC_pct",0)))
else:
    best = min(valid, key=lambda r: abs(r.get("HSC_pct",0) - 15.0)) if valid else None
    if best:
        print()
        print("NOT YET: no run meets all criteria.")
        print("  Closest: sr=%.3f seed=%d n=%d dev=%.1f%% HSC%%=%.1f%% mat%%=%.1f%%" % (
            best["sr_weight"], best["seed"], best["final_n"],
            abs(best["final_n"]-TARGET)/TARGET*100,
            best.get("HSC_pct",0), best.get("mature_pct",0)))
        # Hint for next step
        mean_hsc = sum(r.get("HSC_pct",0) for r in valid) / len(valid)
        if mean_hsc < 10.0:
            print()
            print("  All HSC%% below 10%% — SR weight too low even at 0.85.")
            print("  Options: raise SR to {0.875, 0.90, 0.925} OR reduce MPP SR weight.")
        elif mean_hsc > 20.0:
            print()
            print("  HSC%% above target — SR weight too high.")
            print("  Try narrower grid: {0.78, 0.80, 0.82}.")
        else:
            print()
            print("  HSC%% in range but mature%% off — check MPP/CMP/CLP weights.")

print()
print("JSON_START")
print(json.dumps(results, default=str))
print("JSON_END")
