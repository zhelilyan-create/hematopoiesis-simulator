"""
Local refinement sweep: csf=0.015, w_div_stress in {0.28, 0.30, 0.32}, seeds {42, 1, 99}
9 runs total. All other params from baseline YAML via CLI overrides.
"""
import subprocess, json, sys, re

BASELINE_CONFIG = "configs/hematopoiesis_baseline.yaml"
CSF = 0.015
WDS_VALUES = [0.28, 0.30, 0.32]
SEEDS = [42, 1, 99]

MATURE_TYPES = {"B_cell", "T_cell", "Myeloid", "Erythroid"}
PROGENITOR_TYPES = {"HSC", "MPP", "CLP", "CMP"}


def run_one(wds, seed):
    cmd = [
        sys.executable, "scripts/run_sim.py",
        "--config", BASELINE_CONFIG,
        "--seed", str(seed),
        "--centriole-stress-factor", str(CSF),
        "--w-div-stress", str(wds),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print(f"  STDERR: {result.stderr[-400:]}", file=sys.stderr)
        return None
    return result.stdout


def parse_output(stdout):
    metrics = {}

    # final_n from "Final population  (n=XXXX, ...)"
    m = re.search(r"Final population\s+\(n=(\d+)", stdout)
    if m:
        metrics["final_n"] = int(m.group(1))

    # events
    m = re.search(r"Events recorded\s*:\s*(\d+)", stdout)
    if m:
        metrics["n_events"] = int(m.group(1))

    # per-cell-type: "    HSC               204  ( 10.0%)"
    cell_counts = {}
    cell_pcts = {}
    for line in stdout.splitlines():
        m = re.match(r"\s+(\w+)\s+(\d+)\s+\(\s*([0-9.]+)%\)", line)
        if m:
            ctype = m.group(1)
            count = int(m.group(2))
            pct   = float(m.group(3))
            cell_counts[ctype] = count
            cell_pcts[ctype]   = pct

    if cell_counts:
        metrics["HSC"]     = cell_counts.get("HSC", 0)
        metrics["HSC_pct"] = cell_pcts.get("HSC", 0.0)
        metrics["MPP"]     = cell_counts.get("MPP", 0)
        metrics["MPP_pct"] = cell_pcts.get("MPP", 0.0)
        metrics["CLP_pct"] = cell_pcts.get("CLP", 0.0)
        metrics["CMP_pct"] = cell_pcts.get("CMP", 0.0)
        metrics["B_cell_pct"]    = cell_pcts.get("B_cell", 0.0)
        metrics["T_cell_pct"]    = cell_pcts.get("T_cell", 0.0)
        metrics["Myeloid_pct"]   = cell_pcts.get("Myeloid", 0.0)
        metrics["Erythroid_pct"] = cell_pcts.get("Erythroid", 0.0)

        total = metrics.get("final_n", sum(cell_counts.values()))
        mature_count     = sum(cell_counts.get(t, 0) for t in MATURE_TYPES)
        progenitor_count = sum(cell_counts.get(t, 0) for t in PROGENITOR_TYPES)
        if total:
            metrics["mature_pct"]     = round(100 * mature_count / total, 1)
            metrics["progenitor_pct"] = round(100 * progenitor_count / total, 1)

        hsc = metrics.get("HSC", 0)
        mpp = metrics.get("MPP", 1)
        metrics["hsc_mpp_ratio"] = round(hsc / mpp, 3) if mpp else None

    return metrics


def classify(m):
    if not m or "final_n" not in m:
        return "error"
    hsc_pct = m.get("HSC_pct", 0)
    ratio   = m.get("hsc_mpp_ratio") or 0
    final_n = m.get("final_n", 0)
    if m.get("HSC", 1) == 0:
        return "hsc_loss"
    if final_n < 500:
        return "growth_suppressed"
    if hsc_pct > 30 or ratio > 1.0:
        return "too_stem_heavy"
    return "ok"


results = []
run_id_start = 118  # next after series 10 (91–117)

print(f"{'rid':>4}  {'csf':>6}  {'wds':>5}  {'seed':>4} | {'n':>6}  {'hsc%':>5}  {'mpp%':>5}  {'mat%':>5}  {'ratio':>6} | status")
print("-" * 78)

for i, wds in enumerate(WDS_VALUES):
    for j, seed in enumerate(SEEDS):
        rid = run_id_start + i * len(SEEDS) + j
        stdout = run_one(wds, seed)
        m = parse_output(stdout) if stdout else {}
        status = classify(m)
        results.append(dict(run_id=rid, csf=CSF, wds=wds, seed=seed, status=status, **m))

        n     = m.get("final_n", "?")
        hpct  = m.get("HSC_pct", float("nan"))
        mpct  = m.get("MPP_pct", float("nan"))
        mat   = m.get("mature_pct", float("nan"))
        ratio = m.get("hsc_mpp_ratio") or float("nan")
        print(f"{rid:>4}  {CSF:>6.3f}  {wds:>5.2f}  {seed:>4} | {n:>6}  {hpct:>5.1f}  {mpct:>5.1f}  {mat:>5.1f}  {ratio:>6.3f} | {status}")

print("\nJSON_START")
print(json.dumps(results))
print("JSON_END")
