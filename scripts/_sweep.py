"""Local sensitivity sweep — 27 runs. Called once, results written to JSON."""
import sys, copy, json, yaml
sys.path.insert(0, '.')
from cell_diff_sim.cell import Cell
from cell_diff_sim.engine.ctmc import CTMCEngine
from cell_diff_sim.models.hematopoiesis import HCellType, HematopoiesisModel
from cell_diff_sim.observers.recorder import Recorder
from cell_diff_sim.population import Population

baseline_cfg = yaml.safe_load(open('configs/hematopoiesis_baseline.yaml').read())

csf_vals   = [0.005, 0.010, 0.015]
wdivs_vals = [0.20,  0.25,  0.30]
seeds      = [42, 1, 99]

results = []
run_num = 91

for csf in csf_vals:
    for wds in wdivs_vals:
        for seed in seeds:
            cfg = copy.deepcopy(baseline_cfg)
            cfg['inheritance']['centriole_stress_factor'] = csf
            cfg['state_modulation']['w_div_stress'] = wds

            model = HematopoiesisModel(cfg)
            pop   = Population([Cell(cell_type=HCellType.HSC) for _ in range(10)])
            rec   = Recorder()
            rec.on_step(0.0, pop)
            CTMCEngine(model, pop, observers=[rec], rng_seed=seed).run(t_max=100.0)

            counts = pop.snapshot()
            total  = sum(counts.values())

            def pct(k):
                return round(100.0 * counts.get(k, 0) / total, 1) if total else 0.0

            hsc = counts.get('HSC', 0)
            mpp = counts.get('MPP', 0)
            clp = counts.get('CLP', 0)
            cmp_= counts.get('CMP', 0)
            bc  = counts.get('B_cell', 0)
            tc  = counts.get('T_cell', 0)
            my  = counts.get('Myeloid', 0)
            er  = counts.get('Erythroid', 0)
            mature     = bc + tc + my + er
            progenitor = hsc + mpp + cmp_ + clp
            hsc_mpp_r  = round(hsc / mpp, 3) if mpp else None
            n_events   = len(rec.snapshots) - 1

            hsc_pct = pct('HSC')
            mat_pct = round(100.0 * mature / total, 1) if total else 0
            if total == 0:
                status = 'extinct'
            elif hsc == 0:
                status = 'hsc_loss'
            elif hsc_pct > 30:
                status = 'too_stem_heavy'
            elif mat_pct < 15:
                status = 'growth_suppressed'
            else:
                status = 'ok'

            results.append(dict(
                run_id=run_num,
                csf=csf, wds=wds, seed=seed,
                final_n=total,
                HSC=hsc,       HSC_pct=pct('HSC'),
                MPP=mpp,       MPP_pct=pct('MPP'),
                CLP_pct=pct('CLP'),      CMP_pct=pct('CMP'),
                B_cell_pct=pct('B_cell'), T_cell_pct=pct('T_cell'),
                Myeloid_pct=pct('Myeloid'), Erythroid_pct=pct('Erythroid'),
                mature_pct=mat_pct,
                progenitor_pct=round(100.0 * progenitor / total, 1) if total else 0,
                hsc_mpp_ratio=hsc_mpp_r,
                hsc_present=hsc > 0,
                n_events=n_events,
                status=status,
            ))
            run_num += 1

# Print compact table
header = "{:>4} {:>6} {:>5} {:>4} | {:>5} {:>6} {:>6} {:>6} {:>7} | {}".format(
    'rid', 'csf', 'wds', 'seed', 'n', 'hsc%', 'mpp%', 'mat%', 'ratio', 'status')
print(header)
print('-' * 76)
for r in results:
    tag = ' <BASELINE' if (r['csf'] == 0.01 and r['wds'] == 0.25 and r['seed'] == 42) else ''
    ratio_str = str(r['hsc_mpp_ratio']) if r['hsc_mpp_ratio'] is not None else 'N/A'
    print("{:>4} {:>6.3f} {:>5.2f} {:>4} | {:>5} {:>6.1f} {:>6.1f} {:>6.1f} {:>7} | {}{}".format(
        r['run_id'], r['csf'], r['wds'], r['seed'],
        r['final_n'], r['HSC_pct'], r['MPP_pct'], r['mature_pct'],
        ratio_str, r['status'], tag))

print('\nJSON_START')
print(json.dumps(results))
print('JSON_END')
