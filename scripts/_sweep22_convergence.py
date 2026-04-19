"""
Sweep22: Steady-state convergence verification after HSC SR adjustment.

Background:
  Sweep21 raised HSC SR 0.70->0.825/0.850. Composition improved (HSC%=12-25%,
  mature%=38-49%, M4 OFF), but all 6 runs show tail_mean > final_n at t=100,
  meaning the system had not yet reached true steady state.

  This sweep re-runs the best sr candidates at t_max=200 and t_max=300 to
  confirm where the true equilibrium lies WITHOUT changing any parameters.

Grid (8 runs, IDs 532-539):
  sr_weight in {0.825, 0.85}
  seed      in {42, 1}
  t_max     in {200, 300}
  -> 2 x 2 x 2 = 8 runs

Fixed (sweep20/21 best config — NO changes):
  density_gamma           = 4.0
  density_beta            = 0.0
  crowding_threshold      = 1.3
  crowding_apoptosis_rate = 0.10
  niche_strength          = 4.0
  target                  = 1000
  apoptosis_rates: unchanged from v0.12 recal baseline

Success criteria:
  convergence : tail_mean ~= final_n  (|tail - final| < 30)
  on_target   : |dev| <= 10%  (n within 900-1100)
  composition : HSC% in [10%, 20%],  mature% in [30%, 45%]
  M4 safety   : M4 NOT active at SS (tail_mean < 1300)
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

MPP_MPP_WEIGHT = 0.05

SR_WEIGHTS = [0.825, 0.85]
SEEDS      = [42, 1]
T_MAXES    = [200, 300]

MATURE_TYPES = {"B_cell", "T_cell", "Myeloid", "Erythroid"}
M4_THRESHOLD = CROWDING_THRESHOLD * TARGET   # 1300


def make_config(sr_weight: float) -> dict:
    with open(BASELINE_CONFIG, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    hsc_asym = round(1.0 - sr_weight - MPP_MPP_WEIGHT, 10)
    cfg["division_fates"]["HSC"] = [
        {"daughters": ["HSC", "HSC"], "weight": sr_weight},
        {"daughters": ["HSC", "MPP"], "weight": hsc_asym},
        {"daughters": ["MPP", "MPP"], "weight": MPP_MPP_WEIGHT},
    ]
    return cfg


def run_one(sr_weight: float, seed: int, t_max: int) -> str | None:
    cfg = make_config(sr_weight)
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".yaml", prefix="sweep22_")
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
            "--t-max",                         str(t_max),
            "--track-states",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            print("  FAIL sr=%.3f seed=%d t=%d: %s" % (
                sr_weight, seed, t_max, result.stderr[-300:]), file=sys.stderr)
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
RUN_START = 532

hdr = "%4s  %6s  %4s  %4s | %6s  %7s  %6s  %5s  %5s  %6s  %6s | %s" % (
    "rid", "sr_w", "seed", "tmax", "n", "dev", "dev%", "hsc%", "mat%",
    "tail_n", "gap", "status")
print(hdr)
print("-" * len(hdr))

idx = 0
for sr_w in SR_WEIGHTS:
    print("=== HSC SR=%.3f ===" % sr_w)
    for t_max in T_MAXES:
        print("  -- t_max=%d --" % t_max)
        for seed in SEEDS:
            rid    = RUN_START + idx
            idx   += 1
            stdout = run_one(sr_w, seed, t_max)
            m      = parse_output(stdout) if stdout else {}
            status, m4_at_ss = classify(m)

            n     = m.get("final_n",           "?")
            hpct  = m.get("HSC_pct",           float("nan"))
            mat   = m.get("mature_pct",         float("nan"))
            tail  = m.get("tail_mean_pop_size", float("nan"))
            tgt_d = (n - TARGET) if isinstance(n, int) else float("nan")
            dev_p = abs(tgt_d) / TARGET * 100 if isinstance(n, int) else float("nan")
            gap   = (tail - n) if (isinstance(n, int) and not math.isnan(tail)) else float("nan")

            results.append(dict(
                run_id=rid, sr_weight=sr_w, seed=seed, t_max=t_max,
                status=status, m4_at_ss=m4_at_ss, **m,
            ))

            print("%4d  %6.3f  %4d  %4d | %6s  %+7s  %6.1f  %5.1f  %5.1f  %6.0f  %+6.0f | %s%s" % (
                rid, sr_w, seed, t_max,
                str(n),
                str(tgt_d) if isinstance(n, int) else "?",
                dev_p if not math.isnan(dev_p) else -1,
                hpct if not math.isnan(hpct) else -1,
                mat  if not math.isnan(mat)  else -1,
                tail if not math.isnan(tail) else -1,
                gap  if not math.isnan(gap)  else 0,
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
print("SWEEP22 ANALYSIS  Convergence verification (t_max=200/300)")
print("=" * 80)

print("\n(1) Summary:")
print("    on_target  (dev<=10%%): %d/%d" % (len(on_target), len(results)))
print("    M4 active at SS       : %d/%d" % (len(m4_active), len(results)))

# --- (A) Convergence: does final_n stabilize as t_max increases? ---
print("\n(A) Convergence check: final_n vs t_max  (gap = tail_mean - final_n):")
print("    %6s  %4s  | t200: n / tail / gap  |  t300: n / tail / gap" % ("sr_w","seed"))
for sr_w in SR_WEIGHTS:
    for seed in SEEDS:
        r200 = next((r for r in results if r["sr_weight"]==sr_w and r["seed"]==seed
                     and r["t_max"]==200), None)
        r300 = next((r for r in results if r["sr_weight"]==sr_w and r["seed"]==seed
                     and r["t_max"]==300), None)
        def _fmt(r):
            if not r or not isinstance(r.get("final_n"), int):
                return "  ?  /   ?  /  ?"
            n    = r["final_n"]
            tail = r.get("tail_mean_pop_size", float("nan"))
            gap  = tail - n if not math.isnan(tail) else float("nan")
            return "%4d / %4.0f / %+4.0f" % (n, tail if not math.isnan(tail) else -1,
                                               gap if not math.isnan(gap) else 0)
        print("    %6.3f  %4d  | %s  |  %s" % (sr_w, seed, _fmt(r200), _fmt(r300)))

# --- (B) Composition at steady state ---
print("\n(B) Composition at t_max=300 (closest to SS):")
print("    %6s  %4s  %6s  %6s  %5s  %5s  %5s  %5s  %6s  M4" % (
    "sr_w","seed","n","dev%","hsc%","mpp%","cmp%","mat%","tail_n"))
for sr_w in SR_WEIGHTS:
    for seed in SEEDS:
        r = next((r for r in results if r["sr_weight"]==sr_w and r["seed"]==seed
                  and r["t_max"]==300), None)
        if r and isinstance(r.get("final_n"), int):
            dev_p = abs(r["final_n"]-TARGET)/TARGET*100
            tail  = r.get("tail_mean_pop_size", float("nan"))
            print("    %6.3f  %4d  %6d  %6.1f  %5.1f  %5.1f  %5.1f  %5.1f  %6.0f  %s" % (
                sr_w, seed, r["final_n"], dev_p,
                r.get("HSC_pct",0), r.get("MPP_pct",0),
                r.get("CMP_pct",0), r.get("mature_pct",0),
                tail if not math.isnan(tail) else -1,
                "M4!" if r.get("m4_at_ss") else "OFF"))

# --- (C) Sweet spot at t=300 ---
print("\n(C) Runs at t=300 satisfying all criteria (dev<=10%%, HSC 10-20%%, mature 30-45%%, M4 off):")
sweet300 = [r for r in valid
            if r["t_max"] == 300
            and abs(r["final_n"]-TARGET)/TARGET <= 0.10
            and 10.0 <= r.get("HSC_pct", 0) <= 20.0
            and 30.0 <= r.get("mature_pct", 0) <= 45.0
            and not r.get("m4_at_ss")]
if sweet300:
    for r in sweet300:
        print("    sr=%.3f seed=%d n=%d dev=%.1f%% HSC%%=%.1f%% mat%%=%.1f%%" % (
            r["sr_weight"], r["seed"], r["final_n"],
            abs(r["final_n"]-TARGET)/TARGET*100,
            r.get("HSC_pct",0), r.get("mature_pct",0)))
else:
    print("    NONE at t=300 strict criteria.")
    # Softer check: convergence + composition (even if n slightly off)
    converging = [r for r in valid if r["t_max"]==300]
    for r in sorted(converging, key=lambda x: abs(x["final_n"]-TARGET)):
        dev_p = abs(r["final_n"]-TARGET)/TARGET*100
        tail  = r.get("tail_mean_pop_size", float("nan"))
        gap   = tail - r["final_n"] if not math.isnan(tail) else float("nan")
        fails = []
        if dev_p > 10:             fails.append("dev=%.1f%%" % dev_p)
        if not (10 <= r.get("HSC_pct",0) <= 20): fails.append("HSC%%=%.1f" % r.get("HSC_pct",0))
        if not (30 <= r.get("mature_pct",0) <= 45): fails.append("mat%%=%.1f" % r.get("mature_pct",0))
        if r.get("m4_at_ss"):      fails.append("M4_active")
        converged = "|gap|<30" if (not math.isnan(gap) and abs(gap) < 30) else ("gap=%+.0f" % gap if not math.isnan(gap) else "gap=?")
        print("    sr=%.3f seed=%d: n=%d  %s  FAIL: %s" % (
            r["sr_weight"], r["seed"], r["final_n"], converged, ", ".join(fails) if fails else "none"))

# --- (D) Verdict ---
print()
print("=" * 80)
print("VERDICT")
print("=" * 80)

# Check if system is still drifting at t=300 or has settled
all_t300 = [r for r in valid if r["t_max"]==300]
still_drifting = [r for r in all_t300
                  if abs(r.get("tail_mean_pop_size", r["final_n"]) - r["final_n"]) > 30]
settled        = [r for r in all_t300
                  if abs(r.get("tail_mean_pop_size", r["final_n"]) - r["final_n"]) <= 30]

if sweet300:
    print()
    print("SUCCESS: system at true SS with target composition.")
    for r in sweet300:
        print("  sr=%.3f seed=%d -> n=%d dev=%.1f%% HSC%%=%.1f%% mat%%=%.1f%%" % (
            r["sr_weight"], r["seed"], r["final_n"],
            abs(r["final_n"]-TARGET)/TARGET*100,
            r.get("HSC_pct",0), r.get("mature_pct",0)))
elif settled:
    mean_n_300 = sum(r["final_n"] for r in all_t300) / len(all_t300)
    mean_dev   = abs(mean_n_300 - TARGET) / TARGET * 100
    mean_hsc   = sum(r.get("HSC_pct",0) for r in all_t300) / len(all_t300)
    mean_mat   = sum(r.get("mature_pct",0) for r in all_t300) / len(all_t300)
    print()
    print("CONVERGED but off target:")
    print("  mean_n=%.0f  mean_dev=%.1f%%  mean_HSC=%.1f%%  mean_mat=%.1f%%" % (
        mean_n_300, mean_dev, mean_hsc, mean_mat))
    if mean_dev > 10:
        print()
        print("  Equilibrium has shifted up due to higher HSC SR.")
        print("  Option A: Raise density_gamma (e.g. 4->5) to compress back.")
        print("  Option B: Slightly lower HSC SR (e.g. 0.80) and run t=300.")
        print("  Option C: Accept n~%.0f as new equilibrium and adjust target." % mean_n_300)
    else:
        print("  Population size acceptable — baseline update recommended.")
elif still_drifting:
    print()
    print("NOT CONVERGED at t=300: system still drifting.")
    print("  Largest gap: %+.0f" % max(
        abs(r.get("tail_mean_pop_size", r["final_n"]) - r["final_n"]) for r in all_t300))
    print("  Options: run t=500, or diagnose oscillation vs slow decay.")
else:
    print()
    print("No t=300 results to analyze.")

print()
print("JSON_START")
print(json.dumps(results, default=str))
print("JSON_END")
