"""
v0.11 Exponential Strength sweep.

Goal: find gamma ∈ {4,6,8,10} where exp M6.4 achieves dev ≤ 10%
      while M4 stays inactive at steady state (safety-only role restored).

Changes vs sweep16:
  - gamma extended to {4.0, 6.0, 8.0, 10.0}  (sweep16 stopped at 4)
  - threshold raised to {1.1, 1.2, 1.3}       (sweep16 max was 1.5)
  - crowding_rate {0.10, 0.15, 0.20}           (sweep16 included 0.05)

Grid (72 runs, IDs 418-489):
  density_gamma        ∈ {4.0, 6.0, 8.0, 10.0}
  crowding_apoptosis_rate ∈ {0.10, 0.15, 0.20}
  crowding_threshold   ∈ {1.1, 1.2, 1.3}
  seed                 ∈ {42, 1}
  → 4 × 3 × 3 × 2 = 72 runs

Fixed: target=1000, niche_strength=4.0, asym=0.02, noise_std=0.02, t_max=100

Success criteria:
  on_target:    |dev| ≤ 10%   (n within 900–1100)
  soft_control: |dev| ≤ 15%   (n within 850–1150)
  M4_safety:    tail_mean_pop ≤ threshold * target  (M4 off at steady state)

Analytical note (exp vs power-law suppression factor at same gamma):
  exp(γ·δ) where δ=(target-n)/target vs (target/n)^γ

  n=1200 (δ=-0.20):  exp stronger by ~7% at γ=4, ~14% at γ=8
  n=1500 (δ=-0.50):  exp stronger by ~46% at γ=4, ~115% at γ=8
  n=2000 (δ=-1.00):  exp stronger by ~71% at γ=4, ~91% at γ=8

  Conclusion: exponential suppresses MORE aggressively than power-law at same gamma.
  sweep16 underperformed v0.9 because gamma was capped at 4; v0.9 used gamma=8.
  Exp(8) should comfortably beat PL(8) in accuracy.
"""

import subprocess, json, sys, re, math

BASELINE_CONFIG     = "configs/hematopoiesis_baseline.yaml"
TARGET              = 1000
NICHE_STRENGTH      = 4.0
DENSITY_GAMMAS      = [4.0, 6.0, 8.0, 10.0]
CROWDING_RATES      = [0.10, 0.15, 0.20]
CROWDING_THRESHOLDS = [1.1, 1.2, 1.3]
SEEDS               = [42, 1]
ASYM                = 0.02
NOISE_STD           = 0.02

MATURE_TYPES     = {"B_cell", "T_cell", "Myeloid", "Erythroid"}
PROGENITOR_TYPES = {"HSC", "MPP", "CLP", "CMP"}

# Success thresholds
ON_TARGET_DEV    = 0.10   # ≤10%
SOFT_CONTROL_DEV = 0.15   # ≤15%
M4_SAFETY_FRAC   = 1.0    # tail_mean ≤ threshold*target → M4 off at SS


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


def classify(m, threshold):
    """Returns (status, m4_at_ss) where m4_at_ss=True means M4 active at steady state."""
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
    elif dev_pct <= 40:
        status = "near_target"
    else:
        status = "overshoot"

    # M4 at steady state: tail mean pop > threshold * target
    tail = m.get("tail_mean_pop_size")
    if tail is not None:
        m4_at_ss = tail > threshold * TARGET
    else:
        m4_at_ss = n > threshold * TARGET  # fallback to final n
    return status, m4_at_ss


results = []
run_id_start = 418

header = "%4s  %5s  %5s  %5s  %4s | %6s  %7s  %6s  %5s  %5s  %6s | status" % (
    "rid", "g", "cr", "thr", "seed", "n", "dev", "dev%", "hsc%", "mat%", "tail_n"
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
                status, m4_at_ss = classify(m, threshold)

                n      = m.get("final_n",           "?")
                hpct   = m.get("HSC_pct",           float("nan"))
                mat    = m.get("mature_pct",         float("nan"))
                tail   = m.get("tail_mean_pop_size", float("nan"))
                tgt_d  = (n - TARGET) if isinstance(n, int) else float("nan")
                dev_p  = abs(tgt_d) / TARGET * 100 if isinstance(tgt_d, (int, float)) and str(tgt_d) != "nan" else float("nan")

                results.append(dict(
                    run_id=rid, target=TARGET,
                    density_gamma=gamma,
                    crowding_apoptosis_rate=crowding_rate,
                    crowding_threshold=threshold,
                    seed=seed, status=status,
                    m4_at_ss=m4_at_ss,
                    **m,
                ))

                print("%4d  %5.1f  %5.2f  %5.1f  %4d | %6s  %+7s  %6.1f  %5.1f  %5.1f  %6.0f | %s%s" % (
                    rid, gamma, crowding_rate, threshold, seed,
                    str(n), str(tgt_d) if isinstance(tgt_d, int) else "?",
                    dev_p, hpct, mat,
                    tail if not math.isnan(tail) else -1,
                    status,
                    " [M4!]" if m4_at_ss else "",
                ))
        print()
    print()


# ===========================================================================
print()
print("=" * 80)
print("SWEEP17 ANALYSIS — exp M6.4 strength (gamma up to 10)")
print("=" * 80)

on_target    = [r for r in results if r["status"] == "on_target"]
soft_control = [r for r in results if r["status"] == "soft_control"]
near_target  = [r for r in results if r["status"] == "near_target"]
overshoot    = [r for r in results if r["status"] == "overshoot"]
errors       = [r for r in results if r["status"] in ("error", "hsc_loss", "collapsed")]
m4_ss_on     = [r for r in results if r.get("m4_at_ss")]

print("\n(1) Equilibrium accuracy:")
print("    on_target    (dev<=10%%): %d/%d" % (len(on_target),    len(results)))
print("    soft_control (dev<=15%%): %d/%d" % (len(soft_control), len(results)))
print("    near_target  (dev<=40%%): %d/%d" % (len(near_target),  len(results)))
print("    overshoot    (dev>40%%) : %d/%d" % (len(overshoot),     len(results)))
print("    errors                : %d/%d" % (len(errors),         len(results)))
print("    M4 active at SS       : %d/%d" % (len(m4_ss_on),       len(results)))

# --- (A) Best parameter sets by deviation ---
print("\n(A) Top-10 runs by lowest |dev%%|:")
print("    %4s  %5s  %5s  %5s  %4s  %6s  %6s  %6s  %s" % (
    "rid", "g", "cr", "thr", "seed", "n", "dev%", "tail_n", "M4_SS"))
rr_valid = [r for r in results if isinstance(r.get("final_n"), int)]
rr_sorted = sorted(rr_valid, key=lambda r: abs(r["final_n"] - TARGET))
for r in rr_sorted[:10]:
    dev_p = abs(r["final_n"] - TARGET) / TARGET * 100
    tail  = r.get("tail_mean_pop_size", float("nan"))
    print("    %4d  %5.1f  %5.2f  %5.1f  %4d  %6d  %6.1f  %6.0f  %s" % (
        r["run_id"], r["density_gamma"], r["crowding_apoptosis_rate"],
        r["crowding_threshold"], r["seed"], r["final_n"], dev_p,
        tail if not math.isnan(tail) else -1,
        "active" if r.get("m4_at_ss") else "OFF",
    ))

# --- (B) Mean dev by gamma + M4 activation ---
print("\n(B) Effect of gamma - mean dev%% and M4 SS rate:")
print("    %5s  %8s  %8s  %8s  %7s  %8s" % (
    "gamma", "mean_dev%", "min_dev%", "max_dev%", "on_tgt", "M4_SS%"))
for g in DENSITY_GAMMAS:
    rr = [r for r in results if r["density_gamma"] == g and isinstance(r.get("final_n"), int)]
    if rr:
        devs   = [abs(r["final_n"] - TARGET) / TARGET * 100 for r in rr]
        n_on   = sum(1 for r in rr if r["status"] == "on_target")
        n_m4ss = sum(1 for r in rr if r.get("m4_at_ss"))
        print("    %5.1f  %8.1f  %8.1f  %8.1f  %d/%d     %5.1f%%" % (
            g, sum(devs)/len(devs), min(devs), max(devs),
            n_on, len(rr), 100 * n_m4ss / len(rr)))

# --- (C) Region: dev<=10% AND M4 off at SS ---
print("\n(C) Runs where BOTH hold: dev<=10%% AND M4 off at steady state:")
sweet_spot = [r for r in rr_valid
              if abs(r["final_n"] - TARGET) / TARGET <= ON_TARGET_DEV
              and not r.get("m4_at_ss")]
if sweet_spot:
    print("    %4s  %5s  %5s  %5s  %4s  %6s  %6s" % (
        "rid", "g", "cr", "thr", "seed", "n", "dev%"))
    for r in sweet_spot:
        dev_p = abs(r["final_n"] - TARGET) / TARGET * 100
        print("    %4d  %5.1f  %5.2f  %5.1f  %4d  %6d  %6.1f" % (
            r["run_id"], r["density_gamma"], r["crowding_apoptosis_rate"],
            r["crowding_threshold"], r["seed"], r["final_n"], dev_p))
else:
    print("    NONE found.")

# --- (D) Seed variance ---
print("\n(D) Seed variance |n42 - n1| (gamma, cr, thr):")
print("    %5s  %5s  %5s  %8s  %s" % ("gamma", "cr", "thr", "|n42-n1|", "both_on_tgt"))
for g in DENSITY_GAMMAS:
    for cr in CROWDING_RATES:
        for thr in CROWDING_THRESHOLDS:
            r42 = next((r for r in results if r["density_gamma"] == g and
                        r["crowding_apoptosis_rate"] == cr and
                        r["crowding_threshold"] == thr and r["seed"] == 42), None)
            r1  = next((r for r in results if r["density_gamma"] == g and
                        r["crowding_apoptosis_rate"] == cr and
                        r["crowding_threshold"] == thr and r["seed"] == 1),  None)
            if (r42 and r1 and isinstance(r42.get("final_n"), int)
                    and isinstance(r1.get("final_n"), int)):
                delta = abs(r42["final_n"] - r1["final_n"])
                both_on = (r42["status"] == "on_target" and r1["status"] == "on_target")
                print("    %5.1f  %5.2f  %5.1f  %8d  %s" % (
                    g, cr, thr, delta, "YES" if both_on else ""))

# --- (E) HSC persistence ---
print("\n(E) HSC persistence:")
hsc_lost = [r for r in results if r.get("HSC", 1) == 0 or r.get("status") == "hsc_loss"]
print("    Lost HSC: %d/%d  %s" % (len(hsc_lost), len(results),
                                    "OK" if not hsc_lost else "FAIL"))

# --- (F) Analytical: exp vs power-law factor comparison ---
print("\n(F) Analytical: suppression factor exp(gamma*delta) vs (target/n)^gamma")
print("    (lower factor = stronger division suppression)")
print()
test_ns = [1100, 1200, 1300, 1500, 2000]
print("    %-6s  %-6s  %10s  %10s  %8s" % ("n", "gamma", "exp factor", "PL factor", "ratio e/PL"))
for g in DENSITY_GAMMAS:
    for n_test in test_ns:
        delta  = (TARGET - n_test) / TARGET
        f_exp  = math.exp(g * delta)
        f_pl   = (TARGET / n_test) ** g
        ratio  = f_exp / f_pl
        print("    %-6d  %-6.1f  %10.4f  %10.4f  %8.3f" % (
            n_test, g, f_exp, f_pl, ratio))
    print()

# --- (G) Comparison with v0.9 power-law ---
print("\n(G) v0.9 power-law vs v0.10 exp (seed=42):")
print("    v0.9 PL  gamma=8:  n=1069  dev=+6.9%%  (sweep14 run 338)")
print("    v0.9 PL  gamma=16: n=1061  dev=+6.1%%  (sweep15b run 358)")
for g in DENSITY_GAMMAS:
    r = next((r for r in results if r["density_gamma"] == g and r["seed"] == 42
              and r["crowding_apoptosis_rate"] == 0.10
              and r["crowding_threshold"] == 1.2), None)
    if r and isinstance(r.get("final_n"), int):
        dev = (r["final_n"] - TARGET) / TARGET * 100
        print("    v0.10 exp gamma=%4.1f (cr=0.10,thr=1.2): n=%d  dev=%+.1f%%  M4_SS=%s" % (
            g, r["final_n"], dev, "active" if r.get("m4_at_ss") else "OFF"))

# --- Final verdict ---
print("\n" + "=" * 80)
print("VERDICT")
print("=" * 80)
if sweet_spot:
    best = min(sweet_spot, key=lambda r: abs(r["final_n"] - TARGET))
    print("\nOption A: Sweet spot found (dev≤10%% + M4 inactive at SS).")
    print("  Best: run %d  gamma=%.1f  cr=%.2f  thr=%.1f  seed=%d  n=%d  dev=%.1f%%" % (
        best["run_id"], best["density_gamma"], best["crowding_apoptosis_rate"],
        best["crowding_threshold"], best["seed"], best["final_n"],
        abs(best["final_n"] - TARGET) / TARGET * 100))
    print("  → Adopt as new baseline.")
else:
    # Check if on_target exists (even with M4 active)
    if on_target:
        best = min(on_target, key=lambda r: abs(r["final_n"] - TARGET))
        print("\nOption A (partial): on_target exists but M4 always active at SS.")
        print("  Best on_target: run %d  g=%.1f  cr=%.2f  thr=%.1f  n=%d  dev=%.1f%%  M4_SS=%s" % (
            best["run_id"], best["density_gamma"], best["crowding_apoptosis_rate"],
            best["crowding_threshold"], best["final_n"],
            abs(best["final_n"] - TARGET) / TARGET * 100,
            "active" if best.get("m4_at_ss") else "OFF"))
        print()
        print("  Exponential controller achieves dev≤10%% only when M4 co-regulates.")
        print("  Conclusion: exp formula is structurally sufficient for accuracy,")
        print("  but its equilibrium naturally drifts above threshold*target.")
        print("  Recommendation: accept M4 as co-regulator (not pure safety valve)")
        print("  OR test hybrid controller: exp(gamma*delta) * (target/n)^beta")
        print("  Suggested beta sweep: beta ∈ {0.5, 1.0, 2.0}, gamma fixed at 4–6.")
    else:
        print("\nOption B: No on_target region found.")
        print("  Exponential formula exp(gamma*delta) is insufficient for dev≤10%%.")
        print("  Recommend hybrid controller: density_factor = exp(gamma*delta) * (target/n)^beta")
        print("  Suggested next sweep:")
        print("    gamma ∈ {4.0, 6.0}")
        print("    beta  ∈ {0.5, 1.0, 2.0}")
        print("    crowding_threshold = 1.3  (keep M4 as true safety valve)")
        print("    crowding_rate = 0.1")

print()
print("JSON_START")
print(json.dumps(results))
print("JSON_END")
