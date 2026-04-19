"""
v0.11 Hybrid density controller sweep (sweep18).

Goal: find (gamma, beta) where hybrid M6.4 achieves dev<=10%
      with M4 inactive at steady state and no HSC accumulation.

Architecture (v0.11):
  delta          = (target - n) / target
  density_factor = exp(gamma * delta) * (target / n) ** beta
  density_factor = clamp(density_factor, 0.01, 10.0)

  gamma: smooth exp term — symmetric around n=target
  beta:  power-law anchor — asymmetric, stronger when n > target,
         pins the equilibrium at n=target (removes stochastic drift)

  beta=0  -> pure exp (v0.10, sweep16/17: best dev~14%, M4 always active)
  gamma=0 -> pure PL  (v0.9, sweep14: best dev~7%, no M4 needed but no smooth recovery)
  hybrid  -> target: dev<=10%, M4 truly dormant at thr=1.3

Grid (16 runs, IDs 490-505):
  density_gamma       in {2.0, 4.0}
  density_beta        in {0.5, 1.0, 2.0, 4.0}
  seed                in {42, 1}
  -> 2 x 4 x 2 = 16 runs

Fixed:
  crowding_apoptosis_rate = 0.10   (keep M4 weak)
  crowding_threshold      = 1.3    (M4 only fires >130% of target)
  niche_strength          = 4.0
  target_population_size  = 1000
  t_max                   = 100

Success criteria:
  on_target: dev <= 10%
  stable:    seed variance <= 30
  realistic: HSC% < 40%  AND  mature% > 15%
  M4_safety: tail_mean_pop <= threshold * target  (M4 off at SS)
"""

import json
import math
import re
import subprocess
import sys

BASELINE_CONFIG      = "configs/hematopoiesis_baseline.yaml"
TARGET               = 1000
NICHE_STRENGTH       = 4.0
CROWDING_RATE        = 0.10
CROWDING_THRESHOLD   = 1.3
ASYM                 = 0.02
NOISE_STD            = 0.02
T_MAX                = 100

DENSITY_GAMMAS = [2.0, 4.0]
DENSITY_BETAS  = [0.5, 1.0, 2.0, 4.0]
SEEDS          = [42, 1]

MATURE_TYPES     = {"B_cell", "T_cell", "Myeloid", "Erythroid"}
PROGENITOR_TYPES = {"HSC", "MPP", "CLP", "CMP"}

ON_TARGET_DEV    = 0.10   # <= 10%
SOFT_CONTROL_DEV = 0.15   # <= 15%
M4_THRESHOLD     = CROWDING_THRESHOLD * TARGET   # 1300


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

    hit = re.search(r"Events recorded\s*:\s*(\d+)", stdout)
    if hit:
        m["n_events"] = int(hit.group(1))

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
            m["mature_pct"]     = round(100 * sum(cell_counts.get(t, 0) for t in MATURE_TYPES)     / total, 1)
            m["progenitor_pct"] = round(100 * sum(cell_counts.get(t, 0) for t in PROGENITOR_TYPES) / total, 1)

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


def classify(m: dict, threshold: float) -> tuple[str, bool]:
    """Returns (status_label, m4_at_steady_state)."""
    if not m or "final_n" not in m:
        return "error", False
    if m.get("HSC", 1) == 0:
        return "hsc_loss", False
    n = m["final_n"]
    if n < 50:
        return "collapsed", False

    dev_pct = abs(n - TARGET) / TARGET * 100
    if dev_pct <= ON_TARGET_DEV * 100:
        status = "on_target"
    elif dev_pct <= SOFT_CONTROL_DEV * 100:
        status = "soft_control"
    elif dev_pct <= 40.0:
        status = "near_target"
    else:
        status = "overshoot"

    tail = m.get("tail_mean_pop_size")
    m4_at_ss = (tail > threshold * TARGET) if tail is not None else (n > threshold * TARGET)
    return status, m4_at_ss


# ---------------------------------------------------------------------------
# Run grid
# ---------------------------------------------------------------------------

results: list[dict] = []
run_id_start = 490

hdr = "%4s  %5s  %5s  %4s | %6s  %7s  %6s  %5s  %5s  %6s | status" % (
    "rid", "g", "beta", "seed", "n", "dev", "dev%", "hsc%", "mat%", "tail_n"
)
print(hdr)
print("-" * len(hdr))

idx = 0
for gamma in DENSITY_GAMMAS:
    print("--- gamma=%.1f ---" % gamma)
    for beta in DENSITY_BETAS:
        for seed in SEEDS:
            rid    = run_id_start + idx
            idx   += 1
            stdout = run_one(gamma, beta, seed)
            m      = parse_output(stdout) if stdout else {}
            status, m4_at_ss = classify(m, CROWDING_THRESHOLD)

            n      = m.get("final_n",           "?")
            hpct   = m.get("HSC_pct",           float("nan"))
            mat    = m.get("mature_pct",         float("nan"))
            tail   = m.get("tail_mean_pop_size", float("nan"))
            tgt_d  = (n - TARGET) if isinstance(n, int) else float("nan")
            dev_p  = abs(tgt_d) / TARGET * 100 if isinstance(n, int) else float("nan")

            results.append(dict(
                run_id=rid,
                density_gamma=gamma,
                density_beta=beta,
                seed=seed,
                status=status,
                m4_at_ss=m4_at_ss,
                **m,
            ))

            print("%4d  %5.1f  %5.1f  %4d | %6s  %+7s  %6.1f  %5.1f  %5.1f  %6.0f | %s%s" % (
                rid, gamma, beta, seed,
                str(n),
                str(tgt_d) if isinstance(tgt_d, (int, float)) and not math.isnan(tgt_d) else "?",
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

print()
print("=" * 76)
print("SWEEP18 ANALYSIS  v0.11 Hybrid Controller")
print("=" * 76)

on_target    = [r for r in results if r["status"] == "on_target"]
soft_control = [r for r in results if r["status"] == "soft_control"]
near_target  = [r for r in results if r["status"] == "near_target"]
overshoot    = [r for r in results if r["status"] == "overshoot"]
errors_list  = [r for r in results if r["status"] in ("error", "hsc_loss", "collapsed")]
m4_active    = [r for r in results if r.get("m4_at_ss")]

valid        = [r for r in results if isinstance(r.get("final_n"), int)]

print("\n(1) Equilibrium accuracy:")
print("    on_target    (dev<=10%%): %d/%d" % (len(on_target),    len(results)))
print("    soft_control (dev<=15%%): %d/%d" % (len(soft_control), len(results)))
print("    near_target  (dev<=40%%): %d/%d" % (len(near_target),  len(results)))
print("    overshoot    (dev>40%%) : %d/%d" % (len(overshoot),     len(results)))
print("    errors                 : %d/%d" % (len(errors_list),    len(results)))
print("    M4 active at SS        : %d/%d" % (len(m4_active),      len(results)))

# --- (A) All runs table (sorted by dev) ---
print("\n(A) All runs sorted by |dev%%|:")
print("    %4s  %5s  %5s  %4s  %6s  %6s  %5s  %5s  %6s  %s" % (
    "rid", "g", "beta", "seed", "n", "dev%", "hsc%", "mat%", "tail_n", "M4_SS"))
for r in sorted(valid, key=lambda x: abs(x["final_n"] - TARGET)):
    dev_p = abs(r["final_n"] - TARGET) / TARGET * 100
    tail  = r.get("tail_mean_pop_size", float("nan"))
    print("    %4d  %5.1f  %5.1f  %4d  %6d  %6.1f  %5.1f  %5.1f  %6.0f  %s" % (
        r["run_id"], r["density_gamma"], r["density_beta"], r["seed"],
        r["final_n"], dev_p,
        r.get("HSC_pct", float("nan")), r.get("mature_pct", float("nan")),
        tail if not math.isnan(tail) else -1,
        "active" if r.get("m4_at_ss") else "OFF",
    ))

# --- (B) Best configs by deviation ---
print("\n(B) Best configurations (dev<=15%%):")
print("    %4s  %5s  %5s  %4s  %6s  %6s  %5s  %5s  %s" % (
    "rid", "g", "beta", "seed", "n", "dev%", "hsc%", "mat%", "M4_SS"))
good = [r for r in valid if abs(r["final_n"] - TARGET) / TARGET * 100 <= 15.0]
for r in sorted(good, key=lambda x: abs(x["final_n"] - TARGET)):
    dev_p = abs(r["final_n"] - TARGET) / TARGET * 100
    print("    %4d  %5.1f  %5.1f  %4d  %6d  %6.1f  %5.1f  %5.1f  %s" % (
        r["run_id"], r["density_gamma"], r["density_beta"], r["seed"],
        r["final_n"], dev_p,
        r.get("HSC_pct", float("nan")), r.get("mature_pct", float("nan")),
        "active" if r.get("m4_at_ss") else "OFF",
    ))
if not good:
    print("    NONE found.")

# --- (C) Sweet spot: ALL criteria ---
print("\n(C) Runs satisfying ALL criteria (dev<=10%%, HSC<40%%, mature>15%%, M4 off):")
sweet = [r for r in valid
         if abs(r["final_n"] - TARGET) / TARGET * 100 <= 10.0
         and r.get("HSC_pct", 100) < 40.0
         and r.get("mature_pct", 0) > 15.0
         and not r.get("m4_at_ss")]
if sweet:
    print("    %4s  %5s  %5s  %4s  %6s  %6s  %5s  %5s" % (
        "rid", "g", "beta", "seed", "n", "dev%", "hsc%", "mat%"))
    for r in sweet:
        dev_p = abs(r["final_n"] - TARGET) / TARGET * 100
        print("    %4d  %5.1f  %5.1f  %4d  %6d  %6.1f  %5.1f  %5.1f" % (
            r["run_id"], r["density_gamma"], r["density_beta"], r["seed"],
            r["final_n"], dev_p,
            r.get("HSC_pct", float("nan")), r.get("mature_pct", float("nan"))))
else:
    print("    NONE found.")

# --- (D) Seed variance ---
print("\n(D) Seed variance |n42 - n1|:")
print("    %5s  %5s  %8s  %s" % ("g", "beta", "|n42-n1|", "both_on_tgt"))
for gamma in DENSITY_GAMMAS:
    for beta in DENSITY_BETAS:
        r42 = next((r for r in results if r["density_gamma"] == gamma and
                    r["density_beta"] == beta and r["seed"] == 42), None)
        r1  = next((r for r in results if r["density_gamma"] == gamma and
                    r["density_beta"] == beta and r["seed"] == 1),  None)
        if r42 and r1 and isinstance(r42.get("final_n"), int) and isinstance(r1.get("final_n"), int):
            delta = abs(r42["final_n"] - r1["final_n"])
            both  = (r42["status"] == "on_target" and r1["status"] == "on_target")
            print("    %5.1f  %5.1f  %8d  %s" % (gamma, beta, delta, "YES" if both else ""))

# --- (E) Effect of beta per gamma ---
print("\n(E) Effect of beta on equilibrium accuracy (seed=42):")
print("    %5s  %5s  %6s  %6s  %s" % ("g", "beta", "n", "dev%", "M4_SS"))
for gamma in DENSITY_GAMMAS:
    for beta in DENSITY_BETAS:
        r = next((r for r in results if r["density_gamma"] == gamma and
                  r["density_beta"] == beta and r["seed"] == 42), None)
        if r and isinstance(r.get("final_n"), int):
            dev_p = (r["final_n"] - TARGET) / TARGET * 100
            print("    %5.1f  %5.1f  %6d  %+6.1f  %s" % (
                gamma, beta, r["final_n"], dev_p,
                "active" if r.get("m4_at_ss") else "OFF"))
    print()

# --- (F) Analytical explanation ---
print("\n(F) Analytical: role of gamma and beta terms")
print("    density_factor = exp(gamma * delta) * (target / n) ** beta")
print("    delta = (target - n) / target")
print()
print("    exp(gamma*delta) [symmetric recovery]:")
print("    lower = stronger suppression of division")
print()
print("    %-6s  %-5s  %12s  %-6s  %12s" % ("n", "delta", "exp(2*d)", "exp(4*d)", "interpretation"))
print("    " + "-" * 60)
for n_test in [900, 950, 1000, 1050, 1100, 1200, 1300]:
    delta  = (TARGET - n_test) / TARGET
    e2     = math.exp(2.0 * delta)
    e4     = math.exp(4.0 * delta)
    if n_test < TARGET:
        interp = "div UP (underpop)"
    elif n_test == TARGET:
        interp = "no effect"
    else:
        interp = "div DOWN (overpop)"
    print("    %-6d  %+5.2f  %12.4f  %12.4f  %s" % (n_test, delta, e2, e4, interp))

print()
print("    (target/n)^beta [anchor term — asymmetric]:")
print("    At n=target: factor=1.0 regardless of beta (neutral point)")
print("    At n>target: factor<1  (additional suppression)")
print("    At n<target: factor>1  (additional boost)")
print()
print("    %-6s  %-7s  %10s  %10s  %10s  %10s" % (
    "n", "delta", "b=0.5", "b=1.0", "b=2.0", "b=4.0"))
print("    " + "-" * 60)
for n_test in [900, 1000, 1050, 1100, 1200, 1300]:
    row = "    %-6d  %+7.3f" % (n_test, (TARGET - n_test) / TARGET)
    for beta in [0.5, 1.0, 2.0, 4.0]:
        f = (TARGET / max(1, n_test)) ** beta
        row += "  %10.4f" % f
    print(row)

print()
print("    Combined factor = exp_term * PL_term (why hybrid is better):")
print("    At n=1100 (+10%% overshoot):")
for gamma in DENSITY_GAMMAS:
    for beta in DENSITY_BETAS:
        n_test = 1100
        delta  = (TARGET - n_test) / TARGET
        f_exp  = math.exp(gamma * delta)
        f_pl   = (TARGET / n_test) ** beta
        f_tot  = max(0.01, min(10.0, f_exp * f_pl))
        print("      g=%.1f b=%.1f: exp=%.4f * PL=%.4f = %.4f  (div rate * %.4f)" % (
            gamma, beta, f_exp, f_pl, f_tot, f_tot))

# --- (G) Why hybrid removes drift ---
print()
print("\n(G) Why hybrid removes equilibrium drift:")
print("    Pure exp (beta=0):")
print("      At steady state: net_birth = net_death")
print("      exp(gamma*delta)*base_div = base_apo")
print("      This is satisfied at delta = ln(base_apo/base_div)/gamma")
print("      Since base_apo < base_div for progenitors, delta < 0 -> n > target")
print("      Equilibrium FLOATS above target by amount = -ln(apo/div)/gamma * target")
print()
print("    Hybrid (beta > 0):")
print("      density_factor = exp(gamma*delta) * (target/n)^beta")
print("      Both terms equal 1.0 when n = target exactly")
print("      Power-law term provides ADDITIONAL suppression for any n > target")
print("      Together they anchor the equilibrium tighter to n = target")
print("      beta >= 1 gives sufficient restoring force for dev <= 10%%")

# --- (H) Comparison with prior versions ---
print()
print("\n(H) Version comparison (seed=42, target=1000):")
print("    v0.9  PL  only  g=0   b=8:  n=1069  dev=+6.9%%  M4=off  (sweep14)")
print("    v0.10 exp only  g=4   b=0:  n=1163  dev=+16.3%% M4=active (sweep16)")
print("    v0.10 exp only  g=10  b=0:  n=1156  dev=+15.6%% M4=active (sweep17)")
print("    v0.11 hybrid g=?  b=?:  (sweep18 below)")
for gamma in DENSITY_GAMMAS:
    for beta in [1.0, 2.0]:
        r = next((r for r in results if r["density_gamma"] == gamma and
                  r["density_beta"] == beta and r["seed"] == 42), None)
        if r and isinstance(r.get("final_n"), int):
            dev = (r["final_n"] - TARGET) / TARGET * 100
            print("    v0.11 hybrid g=%.1f b=%.1f: n=%d  dev=%+.1f%%  M4=%s" % (
                gamma, beta, r["final_n"], dev,
                "active" if r.get("m4_at_ss") else "OFF"))

# --- (I) Final verdict ---
print()
print("=" * 76)
print("VERDICT")
print("=" * 76)

if sweet:
    # Both seeds on_target AND all criteria met
    best_pairs = {}
    for r in sweet:
        key = (r["density_gamma"], r["density_beta"])
        best_pairs.setdefault(key, []).append(r)
    both_seeds = {k: v for k, v in best_pairs.items() if len(v) == 2}
    if both_seeds:
        best_key = min(both_seeds,
                       key=lambda k: sum(abs(r["final_n"] - TARGET) for r in both_seeds[k]))
        g_best, b_best = best_key
        rr = both_seeds[best_key]
        mean_dev = sum(abs(r["final_n"] - TARGET) / TARGET * 100 for r in rr) / 2
        print()
        print("Option A: Sweet spot found — both seeds satisfy all criteria.")
        print("  Best: gamma=%.1f  beta=%.1f  mean_dev=%.1f%%  M4=OFF" % (
            g_best, b_best, mean_dev))
        print()
        print("  Recommended baseline (v0.11):")
        print("    density_gamma:          %.1f" % g_best)
        print("    density_beta:           %.1f" % b_best)
        print("    crowding_apoptosis_rate: %.2f" % CROWDING_RATE)
        print("    crowding_threshold:      %.1f" % CROWDING_THRESHOLD)
    else:
        best_r = min(sweet, key=lambda r: abs(r["final_n"] - TARGET))
        print()
        print("Option A (partial): some seeds on_target but not both.")
        print("  Best: gamma=%.1f  beta=%.1f  seed=%d  n=%d  dev=%.1f%%  M4=OFF" % (
            best_r["density_gamma"], best_r["density_beta"], best_r["seed"],
            best_r["final_n"], abs(best_r["final_n"] - TARGET) / TARGET * 100))
else:
    best_r = min(valid, key=lambda r: abs(r["final_n"] - TARGET)) if valid else None
    print()
    if best_r:
        dev_p = abs(best_r["final_n"] - TARGET) / TARGET * 100
        print("Option B: No run satisfies all criteria simultaneously.")
        print("  Best achieved: gamma=%.1f  beta=%.1f  seed=%d  n=%d  dev=%.1f%%  M4=%s  HSC%%=%.1f  mat%%=%.1f" % (
            best_r["density_gamma"], best_r["density_beta"], best_r["seed"],
            best_r["final_n"], dev_p,
            "active" if best_r.get("m4_at_ss") else "OFF",
            best_r.get("HSC_pct", float("nan")), best_r.get("mature_pct", float("nan"))))
        print()
        print("  Recommend sweep19 with expanded beta range or recalibrated fate weights.")
    else:
        print("Option B: All runs errored — check model and config.")

print()
print("JSON_START")
print(json.dumps(results, default=str))
print("JSON_END")
