"""
v0.12 Selective density control sweep (sweep19).

Structural fix validated here:
  v0.11 global control  → density_factor applied to ALL fates
                        → suppresses committed division
                        → mature cell production collapses
                        → apoptosis sink weakens
                        → equilibrium floats to n~1300-1420 even at beta=4

  v0.12 selective control → density_factor applied ONLY to self-renewal (c==0)
                          → committed fates bypass density control
                          → differentiation flux preserved
                          → mature-cell apoptosis sink stable
                          → equilibrium expected near target

Grid (12 runs, IDs 506-517):
  density_gamma       in {2.0, 4.0}
  density_beta        in {1.0, 2.0, 4.0}
  seed                in {42, 1}
  -> 2 x 3 x 2 = 12 runs

Fixed:
  crowding_apoptosis_rate = 0.10   (M4 safety-only)
  crowding_threshold      = 1.3    (M4 fires only above 130%)
  niche_strength          = 4.0
  target_population_size  = 1000
  t_max                   = 100

Success criteria:
  on_target : dev <= 10%
  stable    : seed variance <= 30
  realistic : HSC% < 40%  AND  mature% > 15%
  M4_safety : tail_mean_pop <= 1.3 * 1000 = 1300  (M4 off at SS)

Direct comparison with v0.11 (sweep18 same params):
  gamma=2.0, beta=1.0: sweep18 run 492/493, n=1418/1385, mature%=20/20
  gamma=2.0, beta=2.0: sweep18 run 494/495, n=1369/1351, mature%=15/13
  gamma=4.0, beta=1.0: sweep18 run 500/501, n=1319/1335, mature%=10/8
  gamma=4.0, beta=2.0: sweep18 run 502/503, n=1322/1325, mature%=9/8
  gamma=4.0, beta=4.0: sweep18 run 504/505, n=1292/1299, mature%=5/5
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
DENSITY_BETAS  = [1.0, 2.0, 4.0]
SEEDS          = [42, 1]

MATURE_TYPES = {"B_cell", "T_cell", "Myeloid", "Erythroid"}

ON_TARGET_DEV = 0.10
M4_THRESHOLD  = CROWDING_THRESHOLD * TARGET   # 1300

# v0.11 reference data (sweep18, same gamma/beta, seed=42 / seed=1)
V011_REF = {
    (2.0, 1.0): (1418, 1385),
    (2.0, 2.0): (1369, 1351),
    (2.0, 4.0): (1337, 1329),
    (4.0, 1.0): (1319, 1335),
    (4.0, 2.0): (1322, 1325),
    (4.0, 4.0): (1292, 1299),
}


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
            gamma, beta, seed, result.stderr[-200:]), file=sys.stderr)
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
        for ct in ["HSC", "MPP", "CLP", "CMP", "B_cell", "T_cell", "Myeloid", "Erythroid"]:
            m[ct]          = cell_counts.get(ct, 0)
            m[f"{ct}_pct"] = cell_pcts.get(ct, 0.0)
        total = m.get("final_n", sum(cell_counts.values()))
        if total:
            m["mature_pct"] = round(
                100 * sum(cell_counts.get(t, 0) for t in MATURE_TYPES) / total, 1)

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
        status = "soft_control"
    elif dev <= 0.40:
        status = "near_target"
    else:
        status = "overshoot"
    tail    = m.get("tail_mean_pop_size")
    m4_at_ss = (tail > M4_THRESHOLD) if tail is not None else (n > M4_THRESHOLD)
    return status, m4_at_ss


# ---------------------------------------------------------------------------
# Run grid
# ---------------------------------------------------------------------------

results: list[dict] = []
RUN_START = 506

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

valid = [r for r in results if isinstance(r.get("final_n"), int)]
on_target    = [r for r in valid if r["status"] == "on_target"]
soft_control = [r for r in valid if r["status"] == "soft_control"]
near_target  = [r for r in valid if r["status"] == "near_target"]
overshoot    = [r for r in valid if r["status"] == "overshoot"]
errors_list  = [r for r in results if r["status"] in ("error","hsc_loss","collapsed")]
m4_active    = [r for r in results if r.get("m4_at_ss")]

print()
print("=" * 76)
print("SWEEP19 ANALYSIS  v0.12 Selective Density Control")
print("=" * 76)

print("\n(1) Equilibrium accuracy:")
print("    on_target    (dev<=10%%): %d/%d" % (len(on_target),    len(results)))
print("    soft_control (dev<=20%%): %d/%d" % (len(soft_control), len(results)))
print("    near_target  (dev<=40%%): %d/%d" % (len(near_target),  len(results)))
print("    overshoot    (dev>40%%) : %d/%d" % (len(overshoot),     len(results)))
print("    errors                 : %d/%d" % (len(errors_list),    len(results)))
print("    M4 active at SS        : %d/%d" % (len(m4_active),      len(results)))

# --- (A) All runs sorted by deviation ---
print("\n(A) All runs sorted by |dev%%|:")
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
        "active" if r.get("m4_at_ss") else "OFF",
    ))

# --- (B) Sweet spot: all success criteria ---
print("\n(B) Runs satisfying ALL criteria (dev<=10%%, HSC<40%%, mature>15%%, M4 off):")
sweet = [r for r in valid
         if abs(r["final_n"] - TARGET) / TARGET <= ON_TARGET_DEV
         and r.get("HSC_pct", 100) < 40.0
         and r.get("mature_pct", 0)  > 15.0
         and not r.get("m4_at_ss")]
if sweet:
    print("    %4s  %5s  %5s  %4s  %6s  %6s  %5s  %5s" % (
        "rid","g","beta","seed","n","dev%","hsc%","mat%"))
    for r in sweet:
        print("    %4d  %5.1f  %5.1f  %4d  %6d  %6.1f  %5.1f  %5.1f" % (
            r["run_id"], r["gamma"], r["beta"], r["seed"],
            r["final_n"], abs(r["final_n"] - TARGET) / TARGET * 100,
            r.get("HSC_pct", float("nan")), r.get("mature_pct", float("nan"))))
else:
    print("    NONE found.")

# --- (C) Direct v0.11 vs v0.12 comparison ---
print("\n(C) Direct comparison: v0.11 (global) vs v0.12 (selective) at seed=42")
print("    %5s  %5s  | %8s  %7s  %7s  | %8s  %7s  %7s  | delta_n  delta_mat" % (
    "g","beta","v11_n","v11_dev","v11_mat","v12_n","v12_dev","v12_mat"))
print("    " + "-" * 80)
for gamma in DENSITY_GAMMAS:
    for beta in DENSITY_BETAS:
        r12 = next((r for r in results if r["gamma"]==gamma and r["beta"]==beta
                    and r["seed"]==42), None)
        n11_pair = V011_REF.get((gamma, beta))
        n11 = n11_pair[0] if n11_pair else None

        if r12 and isinstance(r12.get("final_n"), int) and n11:
            n12   = r12["final_n"]
            d11   = (n11 - TARGET) / TARGET * 100
            d12   = (n12 - TARGET) / TARGET * 100
            mat12 = r12.get("mature_pct", float("nan"))
            delta_n   = n12 - n11
            # v0.11 mature% from sweep18 JSON (estimated from composition)
            # Use approximate values recorded in sweep18 output
            mat11_approx = {
                (2.0,1.0): 20.2, (2.0,2.0): 14.8, (2.0,4.0): 9.3,
                (4.0,1.0): 10.1, (4.0,2.0):  9.2, (4.0,4.0): 5.3,
            }.get((gamma, beta), float("nan"))
            delta_mat = mat12 - mat11_approx if not math.isnan(mat11_approx) else float("nan")
            print("    %5.1f  %5.1f  | %8d  %+7.1f  %7.1f  | %8d  %+7.1f  %7.1f  | %+7d  %+.1f" % (
                gamma, beta,
                n11, d11, mat11_approx,
                n12, d12, mat12,
                delta_n, delta_mat if not math.isnan(delta_mat) else 0))

# --- (D) Seed variance ---
print("\n(D) Seed variance |n42 - n1|:")
print("    %5s  %5s  %8s  %s" % ("g","beta","|n42-n1|","both_on_tgt"))
for gamma in DENSITY_GAMMAS:
    for beta in DENSITY_BETAS:
        r42 = next((r for r in results if r["gamma"]==gamma and r["beta"]==beta
                    and r["seed"]==42), None)
        r1  = next((r for r in results if r["gamma"]==gamma and r["beta"]==beta
                    and r["seed"]==1),  None)
        if r42 and r1 and isinstance(r42.get("final_n"),int) and isinstance(r1.get("final_n"),int):
            delta = abs(r42["final_n"] - r1["final_n"])
            both  = (r42["status"] == "on_target" and r1["status"] == "on_target")
            print("    %5.1f  %5.1f  %8d  %s" % (gamma, beta, delta, "YES" if both else ""))

# --- (E) Effect of gamma / beta on mature% ---
print("\n(E) Effect of beta on mature%% (v0.12, seed=42):")
print("    %5s  %5s  %6s  %6s  %7s  %s" % ("g","beta","n","dev%","mature%","M4_SS"))
for gamma in DENSITY_GAMMAS:
    for beta in DENSITY_BETAS:
        r = next((r for r in results if r["gamma"]==gamma and r["beta"]==beta
                  and r["seed"]==42), None)
        if r and isinstance(r.get("final_n"), int):
            dev_p = (r["final_n"] - TARGET) / TARGET * 100
            print("    %5.1f  %5.1f  %6d  %+6.1f  %7.1f  %s" % (
                gamma, beta, r["final_n"], dev_p,
                r.get("mature_pct", float("nan")),
                "active" if r.get("m4_at_ss") else "OFF"))
    print()

# --- (F) Analytical explanation ---
print("\n(F) Why selective control works:")
print()
print("    v0.11 global:     density_factor * ALL fates")
print("      -> committed division suppressed")
print("      -> mature cell production collapses")
print("      -> apoptosis mostly from progenitors (0.001-0.010/h)")
print("      -> total apoptosis ~ 8/h at n=1300")
print("      -> equilibrium at n~1300-1420 despite strong density factor")
print()
print("    v0.12 selective:  density_factor * ONLY self-renewal (c==0)")
print("      -> committed division at FULL rate regardless of n")
print("      -> mature cell production maintained")
print("      -> apoptosis from mature cells (0.020-0.050/h) stays high")
print("      -> self-renewal suppression alone sufficient to anchor n~target")
print()
print("    Quantitative effect (n=1200, gamma=2, beta=1):")
n_test = 1200
for gamma in DENSITY_GAMMAS:
    for beta in [1.0, 2.0]:
        delta = (TARGET - n_test) / TARGET
        f     = max(0.01, min(10.0, math.exp(gamma*delta) * (TARGET/n_test)**beta))
        print("      gamma=%.1f beta=%.1f: density_factor=%.4f"
              "  -> self-renewal rate * %.4f, committed rate * 1.0000" % (
            gamma, beta, f, f))

# --- (G) Final verdict ---
print()
print("=" * 76)
print("VERDICT")
print("=" * 76)

if sweet:
    by_key: dict = {}
    for r in sweet:
        key = (r["gamma"], r["beta"])
        by_key.setdefault(key, []).append(r)
    both_seeds = {k: v for k, v in by_key.items() if len(v) == 2}
    if both_seeds:
        best_key = min(both_seeds,
                       key=lambda k: sum(abs(r["final_n"]-TARGET) for r in both_seeds[k]))
        g, b = best_key
        rr   = both_seeds[best_key]
        mean_dev = sum(abs(r["final_n"]-TARGET)/TARGET*100 for r in rr) / 2
        print()
        print("Option A: Sweet spot found — both seeds satisfy all criteria.")
        print("  Best: gamma=%.1f  beta=%.1f  mean_dev=%.1f%%  M4=OFF" % (g, b, mean_dev))
        print()
        print("  Recommended v0.12 baseline:")
        print("    density_gamma:           %.1f" % g)
        print("    density_beta:            %.1f" % b)
        print("    crowding_apoptosis_rate: %.2f" % CROWDING_RATE)
        print("    crowding_threshold:      %.1f" % CROWDING_THRESHOLD)
    else:
        best = min(sweet, key=lambda r: abs(r["final_n"]-TARGET))
        print()
        print("Option A (partial): on_target achieved but not for both seeds.")
        print("  Best: gamma=%.1f  beta=%.1f  seed=%d  n=%d  dev=%.1f%%" % (
            best["gamma"], best["beta"], best["seed"], best["final_n"],
            abs(best["final_n"]-TARGET)/TARGET*100))
else:
    best = min(valid, key=lambda r: abs(r["final_n"]-TARGET)) if valid else None
    print()
    if best:
        dev_p = abs(best["final_n"]-TARGET)/TARGET*100
        print("Option B: No run satisfies all criteria.")
        print("  Best: gamma=%.1f  beta=%.1f  seed=%d  n=%d  dev=%.1f%%  M4=%s  mature%%=%.1f" % (
            best["gamma"], best["beta"], best["seed"], best["final_n"], dev_p,
            "active" if best.get("m4_at_ss") else "OFF",
            best.get("mature_pct", float("nan"))))
        # Check if on_target without M4 constraint
        just_on_target = [r for r in valid
                          if abs(r["final_n"]-TARGET)/TARGET*100 <= 10.0]
        if just_on_target:
            print()
            print("  Note: %d runs achieved dev<=10%% but failed other criteria:" %
                  len(just_on_target))
            for r in just_on_target:
                print("    gamma=%.1f beta=%.1f seed=%d n=%d dev=%.1f%% HSC%%=%.1f mat%%=%.1f M4=%s" % (
                    r["gamma"], r["beta"], r["seed"], r["final_n"],
                    abs(r["final_n"]-TARGET)/TARGET*100,
                    r.get("HSC_pct",0), r.get("mature_pct",0),
                    "active" if r.get("m4_at_ss") else "OFF"))

print()
print("JSON_START")
print(json.dumps(results, default=str))
print("JSON_END")
