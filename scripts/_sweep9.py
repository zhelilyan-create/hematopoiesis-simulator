"""
v0.7 epigenetic activation test:
  Fixed: inheritance_noise=0.02, asymmetry_strength=0.02 (total_shift=0.04)
  w_diff_epigenetic     in {0.0, 0.03, 0.06}
  w_lineage_epigenetic  in {0.0, 0.05, 0.10}
  seeds                 in {42, 1, 99}
  → 27 runs, run_ids 207-233
"""
import subprocess, json, sys, re

BASELINE_CONFIG = "configs/hematopoiesis_baseline.yaml"
WDE_VALUES  = [0.0, 0.03, 0.06]           # w_diff_epigenetic
WLE_VALUES  = [0.0, 0.05, 0.10]           # w_lineage_epigenetic
SEEDS       = [42, 1, 99]
NOISE       = 0.02
ASYM        = 0.02

MATURE_TYPES     = {"B_cell", "T_cell", "Myeloid", "Erythroid"}
PROGENITOR_TYPES = {"HSC", "MPP", "CLP", "CMP"}


def run_one(wde, wle, seed):
    cmd = [
        sys.executable, "scripts/run_sim.py",
        "--config", BASELINE_CONFIG,
        "--seed", str(seed),
        "--epigenetic-inheritance-noise",    str(NOISE),
        "--epigenetic-asymmetry-strength",   str(ASYM),
        "--w-diff-epigenetic",               str(wde),
        "--w-lineage-epigenetic",            str(wle),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print(f"  FAIL wde={wde} wle={wle} seed={seed}: {result.stderr[-300:]}", file=sys.stderr)
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

    return m


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
run_id_start = 207   # next after series 17 (180-206)

header = (
    f"{'rid':>4}  {'wde':>5}  {'wle':>5}  {'seed':>4} | "
    f"{'n':>6}  {'hsc%':>5}  {'mpp%':>5}  {'clp%':>5}  {'cmp%':>5}  "
    f"{'mat%':>5} | "
    f"{'bstd':>5}  {'f>01':>5}  {'f>02':>5} | status"
)
print(header)
print("-" * len(header))

for i, wde in enumerate(WDE_VALUES):
    for j, wle in enumerate(WLE_VALUES):
        for k, seed in enumerate(SEEDS):
            rid = run_id_start + i * len(WLE_VALUES) * len(SEEDS) + j * len(SEEDS) + k
            stdout = run_one(wde, wle, seed)
            m = parse_output(stdout) if stdout else {}
            status = classify(m)
            results.append(dict(run_id=rid, wde=wde, wle=wle, seed=seed, status=status, **m))

            n    = m.get("final_n",    "?")
            hpct = m.get("HSC_pct",    float("nan"))
            mpct = m.get("MPP_pct",    float("nan"))
            clp  = m.get("CLP_pct",    float("nan"))
            cmp_ = m.get("CMP_pct",    float("nan"))
            mat  = m.get("mature_pct", float("nan"))
            bstd = m.get("bias_std",   float("nan"))
            f01  = m.get("bias_f01",   float("nan"))
            f02  = m.get("bias_f02",   float("nan"))
            print(
                f"{rid:>4}  {wde:>5.2f}  {wle:>5.2f}  {seed:>4} | "
                f"{n:>6}  {hpct:>5.1f}  {mpct:>5.1f}  {clp:>5.1f}  {cmp_:>5.1f}  "
                f"{mat:>5.1f} | "
                f"{bstd:>5.3f}  {f01:>5.1f}  {f02:>5.1f} | {status}"
            )

    print()  # blank line between wde groups

print("JSON_START")
print(json.dumps(results))
print("JSON_END")
