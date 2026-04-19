"""
v0.7 epigenetic structure test:
  w_diff_epigenetic in {0.03, 0.05, 0.07}, seeds {42, 1, 99} → 9 runs
All other params from baseline YAML.
"""
import subprocess, json, sys, re

BASELINE_CONFIG = "configs/hematopoiesis_baseline.yaml"
WDE_VALUES = [0.03, 0.05, 0.07]
SEEDS = [42, 1, 99]

MATURE_TYPES     = {"B_cell", "T_cell", "Myeloid", "Erythroid"}
PROGENITOR_TYPES = {"HSC", "MPP", "CLP", "CMP"}


def run_one(wde, seed):
    cmd = [
        sys.executable, "scripts/run_sim.py",
        "--config", BASELINE_CONFIG,
        "--seed", str(seed),
        "--w-diff-epigenetic", str(wde),
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
            metrics[ctype]            = cell_counts.get(ctype, 0)
            metrics[f"{ctype}_pct"]   = cell_pcts.get(ctype, 0.0)

        total = metrics.get("final_n", sum(cell_counts.values()))
        if total:
            mature_n     = sum(cell_counts.get(t, 0) for t in MATURE_TYPES)
            progenitor_n = sum(cell_counts.get(t, 0) for t in PROGENITOR_TYPES)
            metrics["mature_pct"]     = round(100 * mature_n / total, 1)
            metrics["progenitor_pct"] = round(100 * progenitor_n / total, 1)

        mpp = metrics.get("MPP", 1)
        metrics["hsc_mpp_ratio"] = round(metrics["HSC"] / mpp, 3) if mpp else None

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
run_id_start = 145  # next after series 13 (136-144)

print(f"{'rid':>4}  {'wde':>5}  {'seed':>4} | {'n':>6}  {'hsc%':>5}  {'mpp%':>5}  {'clp%':>5}  {'cmp%':>5}  {'mat%':>5}  {'ratio':>6} | status")
print("-" * 90)

for i, wde in enumerate(WDE_VALUES):
    for j, seed in enumerate(SEEDS):
        rid = run_id_start + i * len(SEEDS) + j
        stdout = run_one(wde, seed)
        m = parse_output(stdout) if stdout else {}
        status = classify(m)
        results.append(dict(run_id=rid, wde=wde, seed=seed, status=status, **m))

        n     = m.get("final_n", "?")
        hpct  = m.get("HSC_pct", float("nan"))
        mpct  = m.get("MPP_pct", float("nan"))
        clp   = m.get("CLP_pct", float("nan"))
        cmp_  = m.get("CMP_pct", float("nan"))
        mat   = m.get("mature_pct", float("nan"))
        ratio = m.get("hsc_mpp_ratio") or float("nan")
        print(f"{rid:>4}  {wde:>5.2f}  {seed:>4} | {n:>6}  {hpct:>5.1f}  {mpct:>5.1f}  {clp:>5.1f}  {cmp_:>5.1f}  {mat:>5.1f}  {ratio:>6.3f} | {status}")

print("\nJSON_START")
print(json.dumps(results))
print("JSON_END")
