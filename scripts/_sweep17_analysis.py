"""
Sweep17 analysis only — no simulations re-run.
Data parsed from sweep17 output (runs 418-489, 72 total).
"""
import math

TARGET = 1000

# (run_id, gamma, cr, thr, seed, final_n, tail_n, hsc_pct, mat_pct)
RAW = [
    (418, 4.0, 0.10, 1.1, 42, 1247, 1224, 12.3, 21.7),
    (419, 4.0, 0.10, 1.1,  1, 1256, 1251, 17.0, 16.8),
    (420, 4.0, 0.10, 1.2, 42, 1274, 1291, 14.8, 18.1),
    (421, 4.0, 0.10, 1.2,  1, 1309, 1301, 24.3, 11.5),
    (422, 4.0, 0.10, 1.3, 42, 1345, 1345, 16.1, 16.5),
    (423, 4.0, 0.10, 1.3,  1, 1358, 1365, 26.4, 11.7),
    (424, 4.0, 0.15, 1.1, 42, 1234, 1210, 10.5, 22.1),
    (425, 4.0, 0.15, 1.1,  1, 1212, 1207, 16.0, 19.1),
    (426, 4.0, 0.15, 1.2, 42, 1265, 1266, 15.1, 19.1),
    (427, 4.0, 0.15, 1.2,  1, 1275, 1280, 21.5, 14.9),
    (428, 4.0, 0.15, 1.3, 42, 1343, 1343, 16.2, 15.3),
    (429, 4.0, 0.15, 1.3,  1, 1348, 1352, 26.9, 11.2),
    (430, 4.0, 0.20, 1.1, 42, 1163, 1177, 13.8, 24.6),
    (431, 4.0, 0.20, 1.1,  1, 1188, 1198, 16.2, 19.6),
    (432, 4.0, 0.20, 1.2, 42, 1259, 1252, 12.7, 21.2),
    (433, 4.0, 0.20, 1.2,  1, 1268, 1260, 20.0, 15.2),
    (434, 4.0, 0.20, 1.3, 42, 1347, 1330, 17.8, 17.3),
    (435, 4.0, 0.20, 1.3,  1, 1331, 1343, 24.9, 13.4),
    (436, 6.0, 0.10, 1.1, 42, 1185, 1186, 13.2, 17.1),
    (437, 6.0, 0.10, 1.1,  1, 1195, 1206, 28.0, 11.5),
    (438, 6.0, 0.10, 1.2, 42, 1238, 1248, 15.6, 14.7),
    (439, 6.0, 0.10, 1.2,  1, 1263, 1264, 30.8,  7.9),
    (440, 6.0, 0.10, 1.3, 42, 1311, 1314, 19.1, 10.1),
    (441, 6.0, 0.10, 1.3,  1, 1326, 1328, 41.3,  4.8),
    (442, 6.0, 0.15, 1.1, 42, 1172, 1170, 11.4, 18.8),
    (443, 6.0, 0.15, 1.1,  1, 1171, 1180, 23.1, 12.5),
    (444, 6.0, 0.15, 1.2, 42, 1245, 1239, 15.7, 14.7),
    (445, 6.0, 0.15, 1.2,  1, 1258, 1256, 31.2,  8.2),
    (446, 6.0, 0.15, 1.3, 42, 1314, 1316, 19.9, 10.4),
    (447, 6.0, 0.15, 1.3,  1, 1316, 1319, 38.5,  5.1),
    (448, 6.0, 0.20, 1.1, 42, 1155, 1164,  9.9, 19.0),
    (449, 6.0, 0.20, 1.1,  1, 1165, 1177, 23.6, 12.1),
    (450, 6.0, 0.20, 1.2, 42, 1236, 1227, 15.1, 11.8),
    (451, 6.0, 0.20, 1.2,  1, 1233, 1235, 30.2,  9.7),
    (452, 6.0, 0.20, 1.3, 42, 1301, 1308, 17.4, 10.8),
    (453, 6.0, 0.20, 1.3,  1, 1317, 1322, 38.6,  6.2),
    (454, 8.0, 0.10, 1.1, 42, 1156, 1163, 15.6, 13.6),
    (455, 8.0, 0.10, 1.1,  1, 1198, 1188, 35.0,  8.4),
    (456, 8.0, 0.10, 1.2, 42, 1223, 1224, 22.2,  8.3),
    (457, 8.0, 0.10, 1.2,  1, 1246, 1235, 43.3,  4.5),
    (458, 8.0, 0.10, 1.3, 42, 1278, 1278, 26.6,  6.1),
    (459, 8.0, 0.10, 1.3,  1, 1271, 1292, 50.5,  3.5),
    (460, 8.0, 0.15, 1.1, 42, 1157, 1155, 17.4, 14.3),
    (461, 8.0, 0.15, 1.1,  1, 1151, 1166, 31.1,  9.2),
    (462, 8.0, 0.15, 1.2, 42, 1225, 1223, 23.5,  9.4),
    (463, 8.0, 0.15, 1.2,  1, 1221, 1226, 42.8,  5.4),
    (464, 8.0, 0.15, 1.3, 42, 1278, 1278, 26.6,  6.1),
    (465, 8.0, 0.15, 1.3,  1, 1286, 1292, 50.6,  3.1),
    (466, 8.0, 0.20, 1.1, 42, 1142, 1146, 14.4, 15.2),
    (467, 8.0, 0.20, 1.1,  1, 1161, 1158, 26.3, 10.4),
    (468, 8.0, 0.20, 1.2, 42, 1214, 1217, 21.3,  8.8),
    (469, 8.0, 0.20, 1.2,  1, 1212, 1220, 42.2,  5.9),
    (470, 8.0, 0.20, 1.3, 42, 1263, 1287, 26.0,  6.3),
    (471, 8.0, 0.20, 1.3,  1, 1291, 1297, 50.0,  3.3),
    (472,10.0, 0.10, 1.1, 42, 1156, 1151, 22.0, 10.9),
    (473,10.0, 0.10, 1.1,  1, 1159, 1165, 39.2,  5.3),
    (474,10.0, 0.10, 1.2, 42, 1220, 1212, 26.1,  7.3),
    (475,10.0, 0.10, 1.2,  1, 1222, 1219, 48.4,  4.1),
    (476,10.0, 0.10, 1.3, 42, 1230, 1226, 28.5,  4.8),
    (477,10.0, 0.10, 1.3,  1, 1262, 1257, 51.7,  2.9),
    (478,10.0, 0.15, 1.1, 42, 1139, 1140, 24.1, 11.2),
    (479,10.0, 0.15, 1.1,  1, 1150, 1148, 33.8,  9.4),
    (480,10.0, 0.15, 1.2, 42, 1207, 1206, 27.2,  7.5),
    (481,10.0, 0.15, 1.2,  1, 1227, 1218, 46.8,  3.5),
    (482,10.0, 0.15, 1.3, 42, 1230, 1226, 28.5,  4.8),
    (483,10.0, 0.15, 1.3,  1, 1262, 1257, 51.7,  2.9),
    (484,10.0, 0.20, 1.1, 42, 1149, 1137, 19.8, 10.9),
    (485,10.0, 0.20, 1.1,  1, 1152, 1143, 35.1,  6.3),
    (486,10.0, 0.20, 1.2, 42, 1196, 1204, 26.7,  6.6),
    (487,10.0, 0.20, 1.2,  1, 1207, 1212, 47.4,  3.9),
    (488,10.0, 0.20, 1.3, 42, 1230, 1226, 28.5,  4.8),
    (489,10.0, 0.20, 1.3,  1, 1262, 1257, 51.7,  2.9),
]

results = []
for (rid, g, cr, thr, seed, n, tail, hsc_pct, mat_pct) in RAW:
    dev_abs = abs(n - TARGET) / TARGET
    m4_at_ss = tail > thr * TARGET
    if dev_abs <= 0.10:
        status = "on_target"
    elif dev_abs <= 0.15:
        status = "soft_control"
    elif dev_abs <= 0.40:
        status = "near_target"
    else:
        status = "overshoot"
    results.append(dict(
        run_id=rid, gamma=g, cr=cr, thr=thr, seed=seed,
        n=n, tail=tail, hsc_pct=hsc_pct, mat_pct=mat_pct,
        dev_pct=round(dev_abs * 100, 1),
        status=status, m4_at_ss=m4_at_ss,
    ))

on_target    = [r for r in results if r["status"] == "on_target"]
soft_control = [r for r in results if r["status"] == "soft_control"]
near_target  = [r for r in results if r["status"] == "near_target"]
overshoot    = [r for r in results if r["status"] == "overshoot"]
m4_active    = [r for r in results if r["m4_at_ss"]]

GAMMAS      = [4.0, 6.0, 8.0, 10.0]
CRS         = [0.10, 0.15, 0.20]
THRESHOLDS  = [1.1, 1.2, 1.3]

print("=" * 76)
print("SWEEP17 ANALYSIS  exp M6.4 strength (gamma up to 10)")
print("=" * 76)

print("\n(1) Equilibrium accuracy:")
print("    on_target    (dev<=10%%): %d/%d" % (len(on_target),    len(results)))
print("    soft_control (dev<=15%%): %d/%d" % (len(soft_control), len(results)))
print("    near_target  (dev<=40%%): %d/%d" % (len(near_target),  len(results)))
print("    overshoot    (dev>40%%) : %d/%d" % (len(overshoot),     len(results)))
print("    M4 active at SS        : %d/%d" % (len(m4_active),     len(results)))

print("\n(A) Top-10 runs by lowest dev%%:")
print("    %4s  %5s  %5s  %5s  %4s  %6s  %6s  %6s  %s" % (
    "rid", "g", "cr", "thr", "seed", "n", "dev%", "tail_n", "M4_SS"))
for r in sorted(results, key=lambda x: x["dev_pct"])[:10]:
    print("    %4d  %5.1f  %5.2f  %5.1f  %4d  %6d  %6.1f  %6d  %s" % (
        r["run_id"], r["gamma"], r["cr"], r["thr"], r["seed"],
        r["n"], r["dev_pct"], r["tail"],
        "active" if r["m4_at_ss"] else "OFF"))

print("\n(B) Effect of gamma - mean dev%% and M4 SS rate:")
print("    %5s  %9s  %8s  %8s  %7s  %8s" % (
    "gamma", "mean_dev%", "min_dev%", "max_dev%", "on_tgt", "M4_SS%"))
for g in GAMMAS:
    rr = [r for r in results if r["gamma"] == g]
    devs   = [r["dev_pct"] for r in rr]
    n_on   = sum(1 for r in rr if r["status"] == "on_target")
    n_m4ss = sum(1 for r in rr if r["m4_at_ss"])
    print("    %5.1f  %9.1f  %8.1f  %8.1f  %d/%d     %5.1f%%" % (
        g, sum(devs)/len(devs), min(devs), max(devs),
        n_on, len(rr), 100 * n_m4ss / len(rr)))

print("\n(C) Runs where BOTH hold: dev<=10%% AND M4 off at steady state:")
sweet = [r for r in results if r["dev_pct"] <= 10.0 and not r["m4_at_ss"]]
if sweet:
    print("    %4s  %5s  %5s  %5s  %4s  %6s  %6s" % (
        "rid", "g", "cr", "thr", "seed", "n", "dev%"))
    for r in sweet:
        print("    %4d  %5.1f  %5.2f  %5.1f  %4d  %6d  %6.1f" % (
            r["run_id"], r["gamma"], r["cr"], r["thr"],
            r["seed"], r["n"], r["dev_pct"]))
else:
    print("    NONE found.")

print("\n(D) Seed variance |n42 - n1| (best cr per gamma, thr=1.1):")
print("    %5s  %5s  %5s  %8s  %s" % ("gamma", "cr", "thr", "|n42-n1|", "both_soft"))
for g in GAMMAS:
    for cr in CRS:
        for thr in THRESHOLDS:
            r42 = next((r for r in results if r["gamma"]==g and r["cr"]==cr and r["thr"]==thr and r["seed"]==42), None)
            r1  = next((r for r in results if r["gamma"]==g and r["cr"]==cr and r["thr"]==thr and r["seed"]==1),  None)
            if r42 and r1:
                delta = abs(r42["n"] - r1["n"])
                both_soft = (r42["status"] in ("on_target","soft_control") and
                             r1["status"]  in ("on_target","soft_control"))
                print("    %5.1f  %5.2f  %5.1f  %8d  %s" % (
                    g, cr, thr, delta, "YES" if both_soft else ""))

print("\n(E) HSC warning — high HSC%% at large gamma:")
print("    (increasing gamma suppresses committed fates,")
print("     driving HSC accumulation at steady state)")
print()
for g in GAMMAS:
    rr = [r for r in results if r["gamma"] == g]
    mean_hsc = sum(r["hsc_pct"] for r in rr) / len(rr)
    mean_mat = sum(r["mat_pct"] for r in rr) / len(rr)
    max_hsc  = max(r["hsc_pct"] for r in rr)
    print("    gamma=%-4.1f  mean_HSC%%=%5.1f  max_HSC%%=%5.1f  mean_mature%%=%5.1f" % (
        g, mean_hsc, max_hsc, mean_mat))

print("\n(F) Analytical: exp(gamma*delta) vs (target/n)^gamma")
print("    delta = (target - n) / target   (negative when n > target)")
print("    lower factor = stronger division suppression")
print()
print("    %-6s  %-6s  %12s  %12s  %10s" % (
    "n", "gamma", "exp factor", "PL factor", "ratio e/PL"))
print("    " + "-"*56)
for n_test in [1100, 1200, 1300, 1500, 2000]:
    for g in GAMMAS:
        delta = (TARGET - n_test) / TARGET
        f_exp = math.exp(g * delta)
        f_pl  = (TARGET / n_test) ** g
        ratio = f_exp / f_pl
        marker = " <-- exp stronger" if ratio < 1.0 else ""
        print("    %-6d  %-6.1f  %12.5f  %12.5f  %10.4f%s" % (
            n_test, g, f_exp, f_pl, ratio, marker))
    print()

print("\n(G) v0.9 PL vs v0.10 exp summary (seed=42):")
print("    v0.9 PL  gamma=8  n=1069  dev=+6.9%%  M4=off  (sweep14 run 338)")
print("    v0.9 PL  gamma=16 n=1061  dev=+6.1%%  M4=off  (sweep15b run 358)")
print()
for g in GAMMAS:
    r = next((r for r in results
              if r["gamma"]==g and r["cr"]==0.10 and r["thr"]==1.2 and r["seed"]==42), None)
    if r:
        print("    v0.10 exp gamma=%4.1f (cr=0.10,thr=1.2): n=%d  dev=%+.1f%%  M4=%s" % (
            g, r["n"], (r["n"]-TARGET)/TARGET*100, "active" if r["m4_at_ss"] else "OFF"))

print()
print("=" * 76)
print("VERDICT")
print("=" * 76)
print()
if sweet:
    best = min(sweet, key=lambda r: r["dev_pct"])
    print("Option A: Sweet spot found (dev<=10%% + M4 inactive).")
    print("  Best: run %d  gamma=%.1f  cr=%.2f  thr=%.1f  seed=%d  n=%d  dev=%.1f%%" % (
        best["run_id"], best["gamma"], best["cr"], best["thr"],
        best["seed"], best["n"], best["dev_pct"]))
else:
    best_on = min(results, key=lambda r: r["dev_pct"])
    print("Option B: No sweet spot found (no run achieves dev<=10%% with M4 off).")
    print()
    print("  Best achieved: run %d  gamma=%.1f  cr=%.2f  thr=%.1f  seed=%d  n=%d  dev=%.1f%%  M4=%s" % (
        best_on["run_id"], best_on["gamma"], best_on["cr"], best_on["thr"],
        best_on["seed"], best_on["n"], best_on["dev_pct"],
        "active" if best_on["m4_at_ss"] else "OFF"))
    print()
    print("  Root cause: exp(gamma*delta) equilibrium floor is ~1140-1160 when")
    print("  M4 co-regulates (thr=1.1).  Without M4 (thr=1.3), floor is ~1230-1290.")
    print("  Pure exponential cannot push equilibrium below threshold*target.")
    print()
    print("  Recommendation: Hybrid controller:")
    print("    density_factor = exp(gamma * delta) * (target/n)^beta")
    print()
    print("  The power-law tail (target/n)^beta keeps the equilibrium anchored")
    print("  closer to target, while exp(gamma*delta) handles smooth recovery.")
    print("  With beta providing the restoring force below threshold*target,")
    print("  M4 can be a true safety valve.")
    print()
    print("  Suggested sweep18 grid:")
    print("    gamma  in {2.0, 4.0}")
    print("    beta   in {0.5, 1.0, 2.0, 4.0}")
    print("    cr     = 0.10  (keep M4 weak)")
    print("    thr    = 1.3   (M4 truly safety-only)")
    print("    seed   in {42, 1}")
    print("    -> 2 x 4 x 2 = 16 runs")
