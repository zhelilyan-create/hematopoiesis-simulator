"""
v0.7 epigenetic bias calibration sweep:
  inheritance_noise    in {0.01, 0.03, 0.05}
  asymmetry_strength   in {0.01, 0.03, 0.05}
  seeds                in {42, 1, 99}
  → 27 runs

w_diff_epigenetic = 0.0, w_lineage_epigenetic = 0.0 (isolate bias formation only).
All other params from baseline YAML.
"""
import subprocess, json, sys, re

BASELINE_CONFIG   = "configs/hematopoiesis_baseline.yaml"
NOISE_VALUES      = [0.01, 0.03, 0.05]
ASYM_VALUES       = [0.01, 0.03, 0.05]
SEEDS             = [42, 1, 99]

MATURE_TYPES     = {"B_cell", "T_cell", "Myeloid", "Erythroid"}
PROGENITOR_TYPES = {"HSC", "MPP", "CLP", "CMP"}


def run_one(noise, asym, seed):
    cmd = [
        sys.executable, "scripts/run_sim.py",
        "--config", BASELINE_CONFIG,
        "--seed", str(seed),
        "--w-diff-epigenetic", "0.0",
        "--w-lineage-epigenetic", "0.0",
        "--epigenetic-inheritance-noise",    str(noise),
        "--epigenetic-asymmetry-strength",   str(asym),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print(f"  STDERR: {result.stderr[-400:]}", file=sys.stderr)
        return None
    return result.stdout


def parse_output(stdout):
    metrics = {}

    m = re.search(r"Final population\s+\(n=(\d+)", stdout)
    if m:
        metrics["final_n"] = int(m.group(1))

    m = re.search(r"Events recorded\s*:\s*(\d+)", stdout)
    if m:
        metrics["n_events"] = int(m.group(1))

    cell_counts, cell_pcts = {}, {}
    for line in stdout.splitlines():
        m = re.match(r"\s+(\w+)\s+(\d+)\s+\(\s*([0-9.]+)%\)", line)
        if m:
            cell_counts[m.group(1)] = int(m.group(2))
            cell_pcts[m.group(1)]   = float(m.group(3))

    if cell_counts:
        for ctype in ["HSC", "MPP", "CLP", "CMP", "B_cell", "T_cell", "Myeloid", "Erythroid"]:
            metrics[ctype]          = cell_counts.get(ctype, 0)
            metrics[f"{ctype}_pct"] = cell_pcts.get(ctype, 0.0)

        total = metrics.get("final_n", sum(cell_counts.values()))
        if total:
            mature_n     = sum(cell_counts.get(t, 0) for t in MATURE_TYPES)
            progenitor_n = sum(cell_counts.get(t, 0) for t in PROGENITOR_TYPES)
            metrics["mature_pct"]     = round(100 * mature_n / total, 1)
            metrics["progenitor_pct"] = round(100 * progenitor_n / total, 1)

        mpp = metrics.get("MPP", 1)
        metrics["hsc_mpp_ratio"] = round(metrics["HSC"] / mpp, 3) if mpp else None

    # --- Epigenetic bias stats -----------------------------------------------
    m = re.search(
        r"Epigenetic bias stats \(n=\d+\):\s*\n"
        r"\s+mean=([+\-]?\d+\.\d+)\s+std=(\d+\.\d+)\s+min=([+\-]?\d+\.\d+)\s+max=([+\-]?\d+\.\d+)\s*\n"
        r"\s+p10=([+\-]?\d+\.\d+)\s+p50=([+\-]?\d+\.\d+)\s+p90=([+\-]?\d+\.\d+)\s*\n"
        r"\s+\|bias\|>0\.1:\s*([0-9.]+)%\s+\|bias\|>0\.2:\s*([0-9.]+)%",
        stdout,
    )
    if m:
        metrics["bias_mean"]  = float(m.group(1))
        metrics["bias_std"]   = float(m.group(2))
        metrics["bias_min"]   = float(m.group(3))
        metrics["bias_max"]   = float(m.group(4))
        metrics["bias_p10"]   = float(m.group(5))
        metrics["bias_p50"]   = float(m.group(6))
        metrics["bias_p90"]   = float(m.group(7))
        metrics["bias_f01"]   = float(m.group(8))   # % |bias|>0.1
        metrics["bias_f02"]   = float(m.group(9))   # % |bias|>0.2

    return metrics


def classify(m):
    if not m or "final_n" not in m:
        return "error"
    if m.get("HSC", 1) == 0:
        return "hsc_loss"
    if m.get("final_n", 0) < 500:
        return "growth_suppressed"
    if m.get("HSC_pct", 0) > 30 or (m.get("hsc_mpp_ratio") or 0) > 1.0:
        return "too_stem_heavy"
    return "ok"


results = []
run_id_start = 180  # next after series 16 (168-179)

header = (
    f"{'rid':>4}  {'noise':>5}  {'asym':>5}  {'seed':>4} | "
    f"{'n':>6}  {'hsc%':>5} | "
    f"{'std':>6}  {'p10':>7}  {'p50':>7}  {'p90':>7}  "
    f"{'f>0.1':>6}  {'f>0.2':>6} | status"
)
print(header)
print("-" * len(header))

for i, noise in enumerate(NOISE_VALUES):
    for j, asym in enumerate(ASYM_VALUES):
        for k, seed in enumerate(SEEDS):
            rid = run_id_start + i * len(ASYM_VALUES) * len(SEEDS) + j * len(SEEDS) + k
            stdout = run_one(noise, asym, seed)
            m = parse_output(stdout) if stdout else {}
            status = classify(m)
            results.append(dict(
                run_id=rid, noise=noise, asym=asym, seed=seed, status=status, **m
            ))

            n    = m.get("final_n", "?")
            hpct = m.get("HSC_pct", float("nan"))
            std  = m.get("bias_std",  float("nan"))
            p10  = m.get("bias_p10",  float("nan"))
            p50  = m.get("bias_p50",  float("nan"))
            p90  = m.get("bias_p90",  float("nan"))
            f01  = m.get("bias_f01",  float("nan"))
            f02  = m.get("bias_f02",  float("nan"))
            print(
                f"{rid:>4}  {noise:>5.2f}  {asym:>5.2f}  {seed:>4} | "
                f"{n:>6}  {hpct:>5.1f} | "
                f"{std:>6.3f}  {p10:>+7.3f}  {p50:>+7.3f}  {p90:>+7.3f}  "
                f"{f01:>6.1f}  {f02:>6.1f} | {status}"
            )

        print()  # blank line between noise×asym groups

print("JSON_START")
print(json.dumps(results))
print("JSON_END")
