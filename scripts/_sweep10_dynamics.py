"""
v0.8 dynamics sweep:
  Density-dependent apoptosis (M4) × stochastic epigenetic inheritance (M5)
  Fixed: seed=42, noise=0.02, asym=0.02 (baseline epigenetic layer)
  target_population_size   in {500, 1000}
  crowding_apoptosis_rate  in {0.01, 0.05}
  asymmetry_strength       in {0.02, 0.05}
  inheritance_noise_std    in {0.0, 0.02}
  → 16 runs, run_ids 234-249
"""
import subprocess, json, sys, re

BASELINE_CONFIG = "configs/hematopoiesis_baseline.yaml"
TARGET_SIZES    = [500, 1000]           # target_population_size
CROWDING_RATES  = [0.01, 0.05]          # crowding_apoptosis_rate
ASYM_VALUES     = [0.02, 0.05]          # asymmetry_strength
NOISE_STD_VALUES = [0.0, 0.02]          # inheritance_noise_std (σ of Gaussian)
SEED            = 42

MATURE_TYPES     = {"B_cell", "T_cell", "Myeloid", "Erythroid"}
PROGENITOR_TYPES = {"HSC", "MPP", "CLP", "CMP"}


def run_one(target_size, crowding_rate, asym, noise_std):
    cmd = [
        sys.executable, "scripts/run_sim.py",
        "--config",                       BASELINE_CONFIG,
        "--seed",                         str(SEED),
        "--epigenetic-asymmetry-strength", str(asym),
        "--epigenetic-inheritance-noise",  str(noise_std),
        "--target-population-size",        str(target_size),
        "--crowding-apoptosis-rate",       str(crowding_rate),
        "--track-states",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print(
            f"  FAIL tgt={target_size} cr={crowding_rate} "
            f"asym={asym} nstd={noise_std}: {result.stderr[-300:]}",
            file=sys.stderr,
        )
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
            m["mature_pct"]     = round(100 * sum(cell_counts.get(t, 0) for t in MATURE_TYPES) / total, 1)
            m["progenitor_pct"] = round(100 * sum(cell_counts.get(t, 0) for t in PROGENITOR_TYPES) / total, 1)
        mpp = m.get("MPP", 1)
        m["hsc_mpp_ratio"] = round(m["HSC"] / mpp, 3) if mpp else None

    # Epigenetic bias stats
    hit = re.search(
        r"Epigenetic bias stats \(n=\d+\):\s*\n"
        r"\s+mean=([+\-]?\d+\.\d+)\s+std=(\d+\.\d+)\s+min=[+\-]?\d+\.\d+\s+max=[+\-]?\d+\.\d+\s*\n"
        r"\s+p10=([+\-]?\d+\.\d+)\s+p50=([+\-]?\d+\.\d+)\s+p90=([+\-]?\d+\.\d+)\s*\n"
        r"\s+\|bias\|>0\.1:\s*([0-9.]+)%\s+\|bias\|>0\.2:\s*([0-9.]+)%",
        stdout,
    )
    if hit:
        m["bias_mean"] = float(hit.group(1))
        m["bias_std"]  = float(hit.group(2))
        m["bias_p10"]  = float(hit.group(3))
        m["bias_p50"]  = float(hit.group(4))
        m["bias_p90"]  = float(hit.group(5))
        m["bias_f01"]  = float(hit.group(6))
        m["bias_f02"]  = float(hit.group(7))

    # State distribution summary (--track-states)
    hit = re.search(
        r"State distributions.*?:\s*\n"
        r"\s+mean_stemness\s*:\s*([+\-]?\d+\.\d+)\s+/\s+([+\-]?\d+\.\d+)\s*\n"
        r"\s+mean_stress\s*:\s*([+\-]?\d+\.\d+)\s+/\s+([+\-]?\d+\.\d+)\s*\n"
        r"\s+mean_bias\s*:\s*([+\-]?\d+\.\d+)\s+/\s+([+\-]?\d+\.\d+)\s*\n"
        r"\s+mean_pop_size\s*:\s*(\d+)\s+/\s+([0-9.]+)",
        stdout,
    )
    if hit:
        m["final_mean_stemness"]  = float(hit.group(1))
        m["tail_mean_stemness"]   = float(hit.group(2))
        m["final_mean_stress"]    = float(hit.group(3))
        m["tail_mean_stress"]     = float(hit.group(4))
        m["final_mean_bias"]      = float(hit.group(5))
        m["tail_mean_bias"]       = float(hit.group(6))
        m["tail_mean_pop_size"]   = float(hit.group(8))

    return m


def classify(m):
    if not m or "final_n" not in m:
        return "error"
    if m.get("HSC", 1) == 0:
        return "hsc_loss"
    if m.get("final_n", 0) < 100:
        return "collapsed"
    if m.get("final_n", 0) < 500:
        return "growth_suppressed"
    if m.get("HSC_pct", 0) > 30 or (m.get("hsc_mpp_ratio") or 0) > 1.0:
        return "too_stem_heavy"
    return "ok"


results = []
run_id_start = 234   # next after series 18 (207-233)

header = (
    f"{'rid':>4}  {'tgt':>5}  {'cr':>5}  {'asym':>5}  {'nstd':>5} | "
    f"{'n':>6}  {'hsc%':>5}  {'mpp%':>5}  {'mat%':>5} | "
    f"{'stem':>6}  {'bias':>7} | status"
)
print(header)
print("-" * len(header))

idx = 0
for target_size in TARGET_SIZES:
    for crowding_rate in CROWDING_RATES:
        for asym in ASYM_VALUES:
            for noise_std in NOISE_STD_VALUES:
                rid    = run_id_start + idx
                idx   += 1
                stdout = run_one(target_size, crowding_rate, asym, noise_std)
                m      = parse_output(stdout) if stdout else {}
                status = classify(m)
                results.append(dict(
                    run_id=rid,
                    target_population_size=target_size,
                    crowding_apoptosis_rate=crowding_rate,
                    asymmetry_strength=asym,
                    inheritance_noise_std=noise_std,
                    seed=SEED,
                    status=status,
                    **m,
                ))

                n    = m.get("final_n",   "?")
                hpct = m.get("HSC_pct",   float("nan"))
                mpct = m.get("MPP_pct",   float("nan"))
                mat  = m.get("mature_pct", float("nan"))
                stem = m.get("tail_mean_stemness", float("nan"))
                bias = m.get("tail_mean_bias",     float("nan"))
                print(
                    f"{rid:>4}  {target_size:>5}  {crowding_rate:>5.2f}  "
                    f"{asym:>5.2f}  {noise_std:>5.2f} | "
                    f"{n:>6}  {hpct:>5.1f}  {mpct:>5.1f}  {mat:>5.1f} | "
                    f"{stem:>+6.3f}  {bias:>+7.4f} | {status}"
                )

        print()  # blank line between crowding_rate groups

print("JSON_START")
print(json.dumps(results))
print("JSON_END")
