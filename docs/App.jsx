/* ============================================================
   Hematopoiesis Simulator v0.12 — React Frontend
   Redesigned left panel: Basic (6) + Advanced (8 groups, toggles)
   ============================================================ */

const { useState, useRef, useCallback, useMemo } = React;
const API = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
  ? `http://${window.location.hostname}:8000`
  : 'https://hematopoiesis-simulator-api.onrender.com';

/* ─── Cell metadata ──────────────────────────────────────────── */
const CELL_COLOURS = {
  HSC:'#1f77b4', MPP:'#aec7e8', CMP:'#ff7f0e', CLP:'#ffbb78',
  Myeloid:'#2ca02c', Erythroid:'#98df8a', B_cell:'#d62728', T_cell:'#ff9896',
};
const ALL_TYPES = ['HSC','MPP','CMP','CLP','Myeloid','Erythroid','B_cell','T_cell'];

/* ─── Default params ─────────────────────────────────────────── */
const BASIC_DEF = {
  seed: 0,
  t_max: 100,
  enable_target_population: true,
  target_population_size: 1000,
  inheritance_mode: 'centriole',
  stress_accumulation_rate: 0.001,
  epigenetic_enabled: true,
};

const ADV_DEF = {
  // G1: Control Mechanisms
  enable_population_control: true,
  density_gamma: 4.0, density_beta: 0.0,
  enable_niche_modulation: true,
  niche_strength: 4.0,
  enable_crowding_apoptosis: true,
  crowding_threshold: 1.3, crowding_apoptosis_rate: 0.1,
  // G2: Division Rates
  use_custom_division_rates: false,
  div_HSC: 0.05, div_MPP: 0.10, div_CMP: 0.10, div_CLP: 0.10,
  // G3: Apoptosis Rates
  use_custom_apoptosis_rates: false,
  apo_HSC: 0.025, apo_MPP: 0.040, apo_CMP: 0.040, apo_CLP: 0.040,
  apo_Myeloid: 0.050, apo_Erythroid: 0.050, apo_B_cell: 0.020, apo_T_cell: 0.020,
  // G4: Division Fates
  use_custom_division_fates: false,
  fate_HSC_self: 0.825, fate_HSC_asym: 0.125, fate_HSC_commit: 0.05,
  fate_MPP_self: 0.55,  fate_MPP_myl:  0.15,  fate_MPP_lym:    0.15,
  fate_MPP_cmp:  0.075, fate_MPP_clp:  0.075,
  // G5: State Modulation
  use_custom_state_mod: false,
  w_div_stemness: 1.0, w_div_stress: 0.25, w_div_repl: 0.005,
  w_apo_stress:   1.0, w_apo_repl:   0.005,
  min_factor: 0.1, max_factor: 5.0,
  // G6: Inheritance Details
  use_custom_inheritance: false,
  stemness_factor: 0.015, stress_factor: 0.01, age_cap: 10,
  stemness_asymmetry: 0.2, stress_asymmetry: 0.1,
  // G7: Epigenetic Details
  use_custom_epigenetic: false,
  inheritance_noise: 0.02, asymmetry_strength: 0.02, drift_rate: 0.0005,
  // G8: Lifetime Dynamics
  use_custom_lifetime: false,
  stemness_drift_rate: 0.0,
};

/* ─── buildConfig ────────────────────────────────────────────── */
function buildConfig(b, a) {
  const c = {
    seed:                     b.seed,   // 0 = random (handled by backend), >0 = fixed
    t_max:                    b.t_max,
    target_population_size:   b.target_population_size,
    inheritance_mode:         b.inheritance_mode,
    stress_accumulation_rate: b.stress_accumulation_rate,
    epigenetic_enabled:       b.epigenetic_enabled,
    enable_target_population: b.enable_target_population,
    density_gamma:            (a.enable_population_control && b.enable_target_population) ? a.density_gamma  : 0.0,
    density_beta:             (a.enable_population_control && b.enable_target_population) ? a.density_beta   : 0.0,
    niche_strength:           (a.enable_niche_modulation   && b.enable_target_population) ? a.niche_strength : 0.0,
    crowding_threshold:       a.enable_crowding_apoptosis  ? a.crowding_threshold       : 0.0,
    crowding_apoptosis_rate:  a.enable_crowding_apoptosis  ? a.crowding_apoptosis_rate  : 0.0,
    self_renewal_weight:      a.use_custom_division_fates  ? a.fate_HSC_self            : 0.825,
  };
  if (a.use_custom_division_rates)
    c.division_rates = { HSC: a.div_HSC, MPP: a.div_MPP, CMP: a.div_CMP, CLP: a.div_CLP };
  if (a.use_custom_apoptosis_rates)
    c.apoptosis_rates = {
      HSC: a.apo_HSC, MPP: a.apo_MPP, CMP: a.apo_CMP, CLP: a.apo_CLP,
      Myeloid: a.apo_Myeloid, Erythroid: a.apo_Erythroid, B_cell: a.apo_B_cell, T_cell: a.apo_T_cell,
    };
  if (a.use_custom_division_fates) {
    c.division_fates_hsc = [a.fate_HSC_self, a.fate_HSC_asym, a.fate_HSC_commit];
    c.division_fates_mpp = [a.fate_MPP_self, a.fate_MPP_myl, a.fate_MPP_lym, a.fate_MPP_cmp, a.fate_MPP_clp];
  }
  if (a.use_custom_state_mod)
    Object.assign(c, {
      w_div_stemness: a.w_div_stemness, w_div_stress: a.w_div_stress, w_div_repl: a.w_div_repl,
      w_apo_stress:   a.w_apo_stress,  w_apo_repl:   a.w_apo_repl,
      min_factor: a.min_factor, max_factor: a.max_factor,
    });
  if (a.use_custom_inheritance) {
    if (b.inheritance_mode === 'centriole')
      Object.assign(c, { stemness_factor: a.stemness_factor, stress_factor: a.stress_factor, age_cap: a.age_cap });
    else if (b.inheritance_mode === 'asymmetric')
      Object.assign(c, { stemness_asymmetry: a.stemness_asymmetry, stress_asymmetry: a.stress_asymmetry });
  }
  if (b.epigenetic_enabled && a.use_custom_epigenetic)
    Object.assign(c, {
      inheritance_noise: a.inheritance_noise, asymmetry_strength: a.asymmetry_strength, drift_rate: a.drift_rate,
    });
  if (a.use_custom_lifetime)
    c.stemness_drift_rate = a.stemness_drift_rate;
  return c;
}

/* ─── Utilities ──────────────────────────────────────────────── */
function loadHistory()    { try { return JSON.parse(localStorage.getItem('hema_runs') || '[]'); } catch { return []; } }
function saveHistory(arr) { localStorage.setItem('hema_runs', JSON.stringify(arr.slice(-20))); }

function niceTicks(min, max, n = 5) {
  const range = max - min;
  if (range === 0) return [min];
  const mag  = Math.pow(10, Math.floor(Math.log10(range / n)));
  const nice = [1, 2, 5, 10].find(s => range / (s * mag) <= n) * mag;
  const ticks = [];
  for (let v = Math.ceil(min / nice) * nice; v <= max + nice * 0.01; v += nice)
    ticks.push(+v.toFixed(10));
  return ticks;
}

function fmtVal(v, step) {
  if (step >= 1)     return String(v);
  if (step >= 0.1)   return v.toFixed(1);
  if (step >= 0.01)  return v.toFixed(2);
  if (step >= 0.001) return v.toFixed(3);
  return v.toFixed(4);
}

/* ─── UI Primitives ──────────────────────────────────────────── */

function Toggle({ checked, onChange, label, hint, disabled }) {
  return (
    <label className={`flex items-start gap-2 select-none ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}>
      <div className="flex-shrink-0 relative mt-0.5"
           onClick={() => !disabled && onChange(!checked)}>
        <div className={`w-8 h-4 rounded-full transition-colors duration-150 ${checked ? 'bg-blue-600' : 'bg-gray-600'}`}/>
        <div className={`absolute top-0.5 left-0.5 w-3 h-3 rounded-full bg-white shadow transition-transform duration-150 ${checked ? 'translate-x-4' : ''}`}/>
      </div>
      <div className="min-w-0">
        <div className="text-xs text-gray-300 leading-tight">{label}</div>
        {hint && <div className="text-xs text-gray-600 leading-tight mt-0.5">{hint}</div>}
      </div>
    </label>
  );
}

function MechTag({ on, onClick, disabled }) {
  return (
    <button onClick={onClick} disabled={disabled}
            className={`flex-shrink-0 text-xs px-2 py-0.5 rounded font-bold transition-colors disabled:opacity-40
              ${on ? 'bg-blue-600 text-white hover:bg-blue-500' : 'bg-gray-700 text-gray-500 hover:bg-gray-600'}`}>
      {on ? 'ON' : 'OFF'}
    </button>
  );
}

function Sld({ label, hint, value, min, max, step, onChange, disabled }) {
  return (
    <div className={`mb-2.5 transition-opacity ${disabled ? 'opacity-35' : ''}`}>
      <div className="flex justify-between items-center mb-0.5">
        <span className="text-xs text-gray-400 leading-tight">{label}</span>
        <span className="text-xs font-mono text-blue-300 ml-2 flex-shrink-0">{fmtVal(value, step)}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value} disabled={disabled}
             className="w-full h-1.5 rounded accent-blue-500 disabled:cursor-not-allowed"
             onChange={e => onChange(step < 1 ? parseFloat(e.target.value) : parseInt(e.target.value))}/>
      {hint && <div className="text-xs text-gray-600 italic mt-0.5 leading-tight">{hint}</div>}
    </div>
  );
}

function Num({ label, hint, value, min, max, onChange, disabled }) {
  return (
    <div className={`mb-2.5 transition-opacity ${disabled ? 'opacity-35' : ''}`}>
      <div className="flex justify-between items-center">
        <span className="text-xs text-gray-400">{label}</span>
        <input type="number" min={min} max={max} value={value} disabled={disabled}
               className="w-28 bg-gray-900 border border-gray-600 rounded px-2 py-0.5 text-xs font-mono text-blue-300 text-right focus:border-blue-500 focus:outline-none disabled:opacity-40"
               onChange={e => onChange(Number(e.target.value))}/>
      </div>
      {hint && <div className="text-xs text-gray-600 italic mt-0.5">{hint}</div>}
    </div>
  );
}

function GroupBox({ title, children }) {
  return (
    <div className="border border-gray-700/60 rounded-lg p-2.5 mb-2 bg-gray-900/30">
      {title && <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">{title}</div>}
      {children}
    </div>
  );
}

function Accordion({ icon, title, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="mb-1">
      <button onClick={() => setOpen(o => !o)}
              className="w-full flex items-center justify-between px-2.5 py-1.5 bg-gray-800 hover:bg-gray-700 rounded text-xs font-semibold text-gray-300 transition-colors">
        <span>{icon} {title}</span>
        <span className="text-gray-600">{open ? '▲' : '▼'}</span>
      </button>
      {open && <div className="mt-1 pl-1 pr-0.5">{children}</div>}
    </div>
  );
}

/* ─── Advanced Group 1: Control Mechanisms ───────────────────── */
function GrpControlMechanisms({ a, set, disabled }) {
  return (
    <Accordion icon="⚙️" title="Control Mechanisms" defaultOpen={true}>
      <GroupBox title="Population Regulation (M6.4)">
        <div className="flex items-center gap-2 mb-2">
          <MechTag on={a.enable_population_control} disabled={disabled}
                   onClick={() => set('enable_population_control')(!a.enable_population_control)}/>
          <span className="text-xs text-gray-400">Enable density feedback</span>
        </div>
        <Sld label="Density Strength (γ)" hint="Exp term — recovery speed toward target"
             value={a.density_gamma} min={0} max={10} step={0.1}
             onChange={set('density_gamma')} disabled={disabled || !a.enable_population_control}/>
        <Sld label="Density Beta (β)" hint="Power-law anchor (usually 0)"
             value={a.density_beta} min={0} max={2} step={0.1}
             onChange={set('density_beta')} disabled={disabled || !a.enable_population_control}/>
      </GroupBox>

      <GroupBox title="Niche Modulation (M6.2)">
        <div className="flex items-center gap-2 mb-2">
          <MechTag on={a.enable_niche_modulation} disabled={disabled}
                   onClick={() => set('enable_niche_modulation')(!a.enable_niche_modulation)}/>
          <span className="text-xs text-gray-400">Enable niche signaling</span>
        </div>
        <Sld label="Niche Strength (k)" hint="Suppresses differentiation when underpopulated"
             value={a.niche_strength} min={0} max={10} step={0.1}
             onChange={set('niche_strength')} disabled={disabled || !a.enable_niche_modulation}/>
      </GroupBox>

      <GroupBox title="Crowding Apoptosis (M4)">
        <div className="flex items-center gap-2 mb-2">
          <MechTag on={a.enable_crowding_apoptosis} disabled={disabled}
                   onClick={() => set('enable_crowding_apoptosis')(!a.enable_crowding_apoptosis)}/>
          <span className="text-xs text-gray-400">Enable emergency apoptosis</span>
        </div>
        <Sld label="Crowding Threshold" hint="M4 fires above this × target"
             value={a.crowding_threshold} min={1.0} max={3.0} step={0.1}
             onChange={set('crowding_threshold')} disabled={disabled || !a.enable_crowding_apoptosis}/>
        <Sld label="Apoptosis Rate" hint="Emergency apoptosis strength"
             value={a.crowding_apoptosis_rate} min={0} max={1.0} step={0.01}
             onChange={set('crowding_apoptosis_rate')} disabled={disabled || !a.enable_crowding_apoptosis}/>
      </GroupBox>
    </Accordion>
  );
}

/* ─── Advanced Group 2: Division Rates ───────────────────────── */
function GrpDivisionRates({ a, set, disabled }) {
  const on = a.use_custom_division_rates;
  return (
    <Accordion icon="⚡" title="Division Rates">
      <div className="mb-3">
        <Toggle label="Use custom division rates" hint="OFF = baseline YAML values"
                checked={on} onChange={set('use_custom_division_rates')} disabled={disabled}/>
      </div>
      {['HSC','MPP','CMP','CLP'].map(ct => (
        <Sld key={ct} label={`${ct} (per hour)`}
             value={a[`div_${ct}`]} min={0.01} max={0.3} step={0.01}
             onChange={set(`div_${ct}`)} disabled={disabled || !on}/>
      ))}
      <div className="text-xs text-gray-600 italic mt-1">Terminal cells (Myeloid, etc.) = 0</div>
    </Accordion>
  );
}

/* ─── Advanced Group 3: Apoptosis Rates ──────────────────────── */
function GrpApoptosisRates({ a, set, disabled }) {
  const on = a.use_custom_apoptosis_rates;
  return (
    <Accordion icon="💀" title="Apoptosis Rates">
      <div className="mb-3">
        <Toggle label="Use custom apoptosis rates" hint="OFF = v0.12 calibrated values"
                checked={on} onChange={set('use_custom_apoptosis_rates')} disabled={disabled}/>
      </div>
      {ALL_TYPES.map(ct => (
        <Sld key={ct} label={`${ct} (per hour)`}
             value={a[`apo_${ct}`]} min={0.001} max={0.3} step={0.001}
             onChange={set(`apo_${ct}`)} disabled={disabled || !on}/>
      ))}
    </Accordion>
  );
}

/* ─── Advanced Group 4: Division Fates ───────────────────────── */
function GrpDivisionFates({ a, set, disabled }) {
  const on = a.use_custom_division_fates;
  return (
    <Accordion icon="🎲" title="Division Fates">
      <div className="mb-3">
        <Toggle label="Use custom division fates" hint="Weights auto-normalize on backend"
                checked={on} onChange={set('use_custom_division_fates')} disabled={disabled}/>
      </div>
      <div className="text-xs text-gray-500 font-semibold uppercase tracking-wider mb-1.5">HSC fates</div>
      <Sld label="Self-renewal [HSC,HSC]" hint="Higher = more stem cells retained"
           value={a.fate_HSC_self} min={0.5} max={0.95} step={0.005}
           onChange={set('fate_HSC_self')} disabled={disabled || !on}/>
      <Sld label="Asymmetric [HSC,MPP]"
           value={a.fate_HSC_asym} min={0.05} max={0.3} step={0.005}
           onChange={set('fate_HSC_asym')} disabled={disabled || !on}/>
      <Sld label="Commitment [MPP,MPP]"
           value={a.fate_HSC_commit} min={0.01} max={0.2} step={0.005}
           onChange={set('fate_HSC_commit')} disabled={disabled || !on}/>
      <div className="text-xs text-gray-500 font-semibold uppercase tracking-wider mb-1.5 mt-2">MPP fates</div>
      <Sld label="Self-renewal [MPP,MPP]"
           value={a.fate_MPP_self} min={0.2} max={0.8} step={0.01}
           onChange={set('fate_MPP_self')} disabled={disabled || !on}/>
      <Sld label="Myeloid [MPP,CMP]"
           value={a.fate_MPP_myl} min={0.05} max={0.3} step={0.01}
           onChange={set('fate_MPP_myl')} disabled={disabled || !on}/>
      <Sld label="Lymphoid [MPP,CLP]"
           value={a.fate_MPP_lym} min={0.05} max={0.3} step={0.01}
           onChange={set('fate_MPP_lym')} disabled={disabled || !on}/>
      <Sld label="Myeloid commit [CMP,CMP]"
           value={a.fate_MPP_cmp} min={0.01} max={0.2} step={0.005}
           onChange={set('fate_MPP_cmp')} disabled={disabled || !on}/>
      <Sld label="Lymphoid commit [CLP,CLP]"
           value={a.fate_MPP_clp} min={0.01} max={0.2} step={0.005}
           onChange={set('fate_MPP_clp')} disabled={disabled || !on}/>
    </Accordion>
  );
}

/* ─── Advanced Group 5: State Modulation ────────────────────── */
function GrpStateModulation({ a, set, disabled }) {
  const on = a.use_custom_state_mod;
  return (
    <Accordion icon="📈" title="State Modulation">
      <div className="mb-3">
        <Toggle label="Customize state modulation weights" hint="OFF = baseline weights"
                checked={on} onChange={set('use_custom_state_mod')} disabled={disabled}/>
      </div>
      <div className="text-xs text-gray-500 font-semibold uppercase tracking-wider mb-1.5">Division</div>
      <Sld label="w_div_stemness" hint="Higher stemness → faster division"
           value={a.w_div_stemness} min={0} max={5} step={0.1}
           onChange={set('w_div_stemness')} disabled={disabled || !on}/>
      <Sld label="w_div_stress" hint="Higher stress → slower division"
           value={a.w_div_stress} min={0} max={1} step={0.05}
           onChange={set('w_div_stress')} disabled={disabled || !on}/>
      <Sld label="w_div_repl" hint="More divisions → slightly slower"
           value={a.w_div_repl} min={0} max={0.1} step={0.001}
           onChange={set('w_div_repl')} disabled={disabled || !on}/>
      <div className="text-xs text-gray-500 font-semibold uppercase tracking-wider mb-1.5 mt-2">Apoptosis</div>
      <Sld label="w_apo_stress" hint="Higher stress → more apoptosis"
           value={a.w_apo_stress} min={0} max={5} step={0.1}
           onChange={set('w_apo_stress')} disabled={disabled || !on}/>
      <Sld label="w_apo_repl" hint="More divisions → more apoptosis"
           value={a.w_apo_repl} min={0} max={0.1} step={0.001}
           onChange={set('w_apo_repl')} disabled={disabled || !on}/>
      <div className="text-xs text-gray-500 font-semibold uppercase tracking-wider mb-1.5 mt-2">Clamp</div>
      <Sld label="min_factor" hint="Minimum rate = base × this"
           value={a.min_factor} min={0.01} max={1} step={0.01}
           onChange={set('min_factor')} disabled={disabled || !on}/>
      <Sld label="max_factor" hint="Maximum rate = base × this"
           value={a.max_factor} min={1} max={10} step={0.1}
           onChange={set('max_factor')} disabled={disabled || !on}/>
    </Accordion>
  );
}

/* ─── Advanced Group 6: Inheritance Details ─────────────────── */
function GrpInheritanceDetails({ a, set, b, disabled }) {
  const on   = a.use_custom_inheritance;
  const mode = b.inheritance_mode;
  return (
    <Accordion icon="🧬" title="Inheritance Details">
      <div className="mb-3">
        <Toggle label="Customize inheritance parameters" hint="OFF = baseline values"
                checked={on} onChange={set('use_custom_inheritance')} disabled={disabled}/>
      </div>
      {mode === 'centriole' && <>
        <Sld label="Stemness Factor" hint="Age-dependent stemness change per division"
             value={a.stemness_factor} min={0} max={0.1} step={0.001}
             onChange={set('stemness_factor')} disabled={disabled || !on}/>
        <Sld label="Stress Factor" hint="Age-dependent stress change per division"
             value={a.stress_factor} min={0} max={0.1} step={0.001}
             onChange={set('stress_factor')} disabled={disabled || !on}/>
        <Sld label="Age Cap" hint="Maximum centriole age (divisions)"
             value={a.age_cap} min={1} max={50} step={1}
             onChange={set('age_cap')} disabled={disabled || !on}/>
      </>}
      {mode === 'asymmetric' && <>
        <Sld label="Stemness Asymmetry" hint="Stemness difference between daughters"
             value={a.stemness_asymmetry} min={0} max={1} step={0.01}
             onChange={set('stemness_asymmetry')} disabled={disabled || !on}/>
        <Sld label="Stress Asymmetry" hint="Stress difference between daughters"
             value={a.stress_asymmetry} min={0} max={1} step={0.01}
             onChange={set('stress_asymmetry')} disabled={disabled || !on}/>
      </>}
      {mode === 'symmetric' && (
        <div className="text-xs text-gray-600 italic">Symmetric mode has no inheritance parameters.</div>
      )}
    </Accordion>
  );
}

/* ─── Advanced Group 7: Epigenetic Details ───────────────────── */
function GrpEpigeneticDetails({ a, set, b, disabled }) {
  const on  = a.use_custom_epigenetic;
  const epi = b.epigenetic_enabled;
  return (
    <Accordion icon="📊" title="Epigenetic Details">
      {!epi && <div className="text-xs text-yellow-700 italic mb-2">⚠ Enable Epigenetic Memory (Basic) first</div>}
      <div className="mb-3">
        <Toggle label="Customize epigenetic parameters"
                checked={on} onChange={set('use_custom_epigenetic')} disabled={disabled || !epi}/>
      </div>
      <Sld label="Inheritance Noise" hint="Noise in bias inheritance"
           value={a.inheritance_noise} min={0} max={0.1} step={0.001}
           onChange={set('inheritance_noise')} disabled={disabled || !on || !epi}/>
      <Sld label="Asymmetry Strength" hint="Asymmetric bias shift at division"
           value={a.asymmetry_strength} min={0} max={0.1} step={0.001}
           onChange={set('asymmetry_strength')} disabled={disabled || !on || !epi}/>
      <Sld label="Drift Rate" hint="Return to neutral bias per step"
           value={a.drift_rate} min={0} max={0.01} step={0.0001}
           onChange={set('drift_rate')} disabled={disabled || !on || !epi}/>
    </Accordion>
  );
}

/* ─── Advanced Group 8: Lifetime Dynamics ───────────────────── */
function GrpLifetimeDynamics({ a, set, disabled }) {
  const on = a.use_custom_lifetime;
  return (
    <Accordion icon="⏳" title="Lifetime Dynamics">
      <div className="mb-3">
        <Toggle label="Customize lifetime evolution" hint="OFF = baseline values"
                checked={on} onChange={set('use_custom_lifetime')} disabled={disabled}/>
      </div>
      <Sld label="Stemness Drift Rate" hint="Reserved — currently unused"
           value={a.stemness_drift_rate} min={0} max={0.01} step={0.0001}
           onChange={set('stemness_drift_rate')} disabled={disabled || !on}/>
    </Accordion>
  );
}

/* ─── DurationInput ──────────────────────────────────────────── */
function DurationInput({ value, onChange, disabled }) {
  const [raw, setRaw] = React.useState(String(value));

  // Keep raw in sync if value changes externally (e.g. RunHistory restore)
  React.useEffect(() => { setRaw(String(value)); }, [value]);

  const commit = str => {
    const num = parseFloat(str);
    if (isNaN(num)) { setRaw(String(value)); return; }
    const clamped = Math.min(1000, Math.max(10, +num.toFixed(1)));
    setRaw(String(clamped));
    onChange(clamped);
  };

  const pts = Math.round(value / 0.1) + 1;

  return (
    <div className={`mb-2.5 transition-opacity ${disabled ? 'opacity-35' : ''}`}>
      <div className="flex justify-between items-center mb-0.5">
        <span className="text-xs text-gray-400 leading-tight">Duration (hours)</span>
        <input
          type="number" min={10} max={1000} step={0.1}
          value={raw} disabled={disabled}
          onChange={e => setRaw(e.target.value)}
          onBlur={e => commit(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && commit(e.target.value)}
          className="w-20 text-xs font-mono text-blue-300 bg-gray-800 border border-gray-600 rounded px-1.5 py-0.5 text-right
                     focus:outline-none focus:border-blue-500 disabled:cursor-not-allowed"
        />
      </div>
      <input type="range" min={10} max={1000} step={0.1} value={value} disabled={disabled}
             className="w-full h-1.5 rounded accent-blue-500 disabled:cursor-not-allowed"
             onChange={e => { setRaw(e.target.value); onChange(parseFloat(e.target.value)); }}/>
      <div className="text-xs text-gray-600 italic mt-0.5 leading-tight">
        Total simulation run time · ~{pts.toLocaleString()} graph points
      </div>
    </div>
  );
}

/* ─── BasicParameters ────────────────────────────────────────── */
function BasicParameters({ b, setB, disabled }) {
  const set = k => v => setB(s => ({...s, [k]: v}));
  return (
    <div className="p-4">
      <div className="mb-3 text-xs font-semibold text-gray-400 uppercase tracking-widest">Simulation Settings</div>
      <Num label="Seed" hint="0 = random seed, other = fixed"
           value={b.seed} min={0} max={999999} onChange={set('seed')} disabled={disabled}/>
      <DurationInput value={b.t_max} onChange={set('t_max')} disabled={disabled}/>
      <div className="mb-2.5">
        <Toggle label="Enable Target Population"
                hint="OFF = free growth, no size limit"
                checked={b.enable_target_population}
                onChange={set('enable_target_population')}
                disabled={disabled}/>
        <div className={`mt-1.5 pl-5 border-l-2 ${b.enable_target_population ? 'border-blue-600' : 'border-gray-700'}`}>
          <Num label="Target Population Size" hint="System homeostatic equilibrium size"
               value={b.target_population_size} min={100} max={10000}
               onChange={set('target_population_size')}
               disabled={disabled || !b.enable_target_population}/>
        </div>
      </div>
      <div className="mb-2.5">
        <div className="text-xs text-gray-400 mb-1">Inheritance Mode</div>
        <select value={b.inheritance_mode} disabled={disabled}
                className="w-full bg-gray-900 border border-gray-600 rounded px-2 py-1.5 text-xs text-gray-200 focus:border-blue-500 focus:outline-none disabled:opacity-40"
                onChange={e => setB(s => ({...s, inheritance_mode: e.target.value}))}>
          <option value="centriole">Centriole (age-based)</option>
          <option value="symmetric">Symmetric</option>
          <option value="asymmetric">Asymmetric</option>
        </select>
        <div className="text-xs text-gray-600 italic mt-0.5">Daughter cell state inheritance</div>
      </div>
      <Sld label="Stress Accumulation Rate" hint="Cell aging — stress growth per hour"
           value={b.stress_accumulation_rate} min={0} max={0.01} step={0.0001}
           onChange={set('stress_accumulation_rate')} disabled={disabled}/>
      <div className="mt-3">
        <Toggle label="Epigenetic Memory" hint="Enable heritable epigenetic bias"
                checked={b.epigenetic_enabled} onChange={set('epigenetic_enabled')} disabled={disabled}/>
      </div>
    </div>
  );
}

/* ─── AdvancedSection ────────────────────────────────────────── */
function AdvancedSection({ a, setA, b, disabled, onResetAll, onResetAdv }) {
  const [open, setOpen] = useState(false);
  const set = k => v => setA(s => ({...s, [k]: v}));
  return (
    <div className="border-t border-gray-700">
      <button onClick={() => setOpen(o => !o)}
              className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-gray-750 text-xs font-semibold text-yellow-400 transition-colors">
        <span>⚠ Advanced Parameters</span>
        <span className="text-gray-500">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="px-3 pb-3">
          <p className="text-xs text-yellow-700 mb-3 px-1 leading-snug">
            These parameters can destabilize the simulation. Use toggles to disable mechanisms for ablation studies — disabled mechanisms send 0.0 to the backend.
          </p>
          <GrpControlMechanisms a={a} set={set} disabled={disabled}/>
          <GrpDivisionRates     a={a} set={set} disabled={disabled}/>
          <GrpApoptosisRates    a={a} set={set} disabled={disabled}/>
          <GrpDivisionFates     a={a} set={set} disabled={disabled}/>
          <GrpStateModulation   a={a} set={set} disabled={disabled}/>
          <GrpInheritanceDetails a={a} set={set} b={b} disabled={disabled}/>
          <GrpEpigeneticDetails  a={a} set={set} b={b} disabled={disabled}/>
          <GrpLifetimeDynamics   a={a} set={set} disabled={disabled}/>
          <div className="pt-3 space-y-1.5">
            <button onClick={onResetAll} disabled={disabled}
                    className="w-full py-1.5 px-3 bg-gray-700 hover:bg-gray-600 disabled:opacity-40 rounded text-xs transition-colors text-gray-200">
              🔄 Reset All Parameters
            </button>
            <button onClick={onResetAdv} disabled={disabled}
                    className="w-full py-1.5 px-3 bg-gray-700 hover:bg-gray-600 disabled:opacity-40 rounded text-xs transition-colors text-gray-200">
              🔄 Reset Advanced Only
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── SVG Line Chart ─────────────────────────────────────────── */
function LineChart({ data, lines, refLines = [], xLabel = 'Time (h)', yLabel = 'Count' }) {
  const W    = 560;
  const IH   = 182;                               // plot area height
  const PAD  = { top:12, right:16, bottom:36, left:56 };
  const IW   = W - PAD.left - PAD.right;          // 488
  const COLS = 5;
  const LEGEND_ROWS = Math.ceil(lines.length / COLS);
  const H    = PAD.top + IH + PAD.bottom + LEGEND_ROWS * 17 + 10;  // total SVG height
  const legendY = PAD.top + IH + PAD.bottom + 8;  // legend top (absolute)
  const COL_W   = IW / COLS;                      // ~97.6px per legend column

  const [tip, setTip] = useState(null);
  const svgRef = useRef(null);

  const pts = useMemo(() => {
    if (!data || data.length < 2) return null;
    return data;
  }, [data]);

  if (!pts || pts.length < 2) return (
    <div className="flex items-center justify-center h-48 text-gray-600 text-sm">
      Run a simulation to see the graph
    </div>
  );

  const xMin = pts[0].time, xMax = pts[pts.length-1].time;
  // Use reduce instead of spread to avoid stack overflow with large arrays
  const yMax = (lines.reduce((m, l) => {
    for (const d of pts) { const v = d[l.key] || 0; if (v > m) m = v; }
    return m;
  }, refLines.reduce((m, r) => r.y > m ? r.y : m, 0))) * 1.08 || 10;
  const yMin = 0;
  const sx = v => ((v - xMin) / (xMax - xMin || 1)) * IW;
  const sy = v => IH - ((v - yMin) / (yMax - yMin || 1)) * IH;
  // toFixed(2) → 0.01px resolution (was 0.1 → caused collapsed x coords)
  const mkPath = key => pts.map((d,i) => `${i?'L':'M'}${sx(d.time).toFixed(2)},${sy(d[key]||0).toFixed(2)}`).join(' ');

  const onMove = e => {
    if (!svgRef.current) return;
    const rect  = svgRef.current.getBoundingClientRect();
    const tReal = xMin + ((e.clientX - rect.left) / rect.width * W - PAD.left) / IW * (xMax - xMin);
    const near  = pts.reduce((a,b) => Math.abs(b.time - tReal) < Math.abs(a.time - tReal) ? b : a);
    setTip(near);
  };

  const tipX   = tip ? Math.min(sx(tip.time) + 8, IW - 115) : 0;
  const tipH   = 14 + lines.length * 13;

  return (
    <svg ref={svgRef} width="100%" viewBox={`0 0 ${W} ${H}`}
         onMouseMove={onMove} onMouseLeave={() => setTip(null)} style={{cursor:'crosshair'}}>

      {/* ── Plot area ── */}
      <g transform={`translate(${PAD.left},${PAD.top})`}>

        {/* Grid */}
        {niceTicks(yMin, yMax, 5).map(v => (
          <line key={v} x1={0} y1={sy(v)} x2={IW} y2={sy(v)} stroke="#374151" strokeDasharray="3,3"/>
        ))}

        {/* Reference lines (horizontal) */}
        {refLines.map(r => <>
          <line key={r.label} x1={0} y1={sy(r.y)} x2={IW} y2={sy(r.y)}
                stroke={r.color||'#6b7280'} strokeDasharray="6,3" strokeWidth={1}/>
          <text key={r.label+'t'} x={IW-2} y={sy(r.y)-4}
                fill={r.color||'#6b7280'} fontSize={9} textAnchor="end">{r.label}</text>
        </>)}

        {/* Data lines */}
        {lines.map(l => (
          <path key={l.key} d={mkPath(l.key)} fill="none"
                stroke={l.color} strokeWidth={l.width||1.5} strokeDasharray={l.dash||'none'}/>
        ))}

        {/* X axis */}
        <line x1={0} y1={IH} x2={IW} y2={IH} stroke="#4b5563"/>
        {niceTicks(xMin, xMax, 6).map(v => (
          <g key={v} transform={`translate(${sx(v)},${IH})`}>
            <line y2={4} stroke="#4b5563"/>
            <text y={14} textAnchor="middle" fill="#9ca3af" fontSize={9}>{v.toFixed(0)}</text>
          </g>
        ))}
        <text x={IW/2} y={IH+28} textAnchor="middle" fill="#9ca3af" fontSize={10}>{xLabel}</text>

        {/* Y axis */}
        <line x1={0} y1={0} x2={0} y2={IH} stroke="#4b5563"/>
        {niceTicks(yMin, yMax, 5).map(v => (
          <g key={v} transform={`translate(0,${sy(v)})`}>
            <line x2={-4} stroke="#4b5563"/>
            <text x={-7} textAnchor="end" dominantBaseline="middle" fill="#9ca3af" fontSize={9}>
              {v >= 1000 ? (v/1000).toFixed(1)+'k' : v}
            </text>
          </g>
        ))}
        <text transform={`translate(-44,${IH/2}) rotate(-90)`}
              textAnchor="middle" fill="#9ca3af" fontSize={10}>{yLabel}</text>

        {/* Tooltip */}
        {tip && <>
          <line x1={sx(tip.time)} y1={0} x2={sx(tip.time)} y2={IH} stroke="#ffffff18" strokeWidth={1}/>
          {lines.map(l => <circle key={l.key} cx={sx(tip.time)} cy={sy(tip[l.key]||0)} r={2.5} fill={l.color}/>)}
          <g transform={`translate(${tipX},4)`}>
            <rect width={112} height={tipH} rx={4} fill="#111827" stroke="#374151" strokeWidth={0.5}/>
            <text x={6} y={11} fill="#d1d5db" fontSize={9} fontWeight="600">t = {tip.time.toFixed(1)} h</text>
            {lines.map((l,i) => (
              <text key={l.key} x={6} y={23+i*13} fill={l.color} fontSize={9}>
                {l.label}: {(tip[l.key]||0).toLocaleString()}
              </text>
            ))}
          </g>
        </>}
      </g>

      {/* ── Legend — horizontal, below x-axis label ── */}
      <g transform={`translate(${PAD.left},${legendY})`}>
        {lines.map((l, i) => {
          const col = i % COLS;
          const row = Math.floor(i / COLS);
          return (
            <g key={l.key} transform={`translate(${col * COL_W},${row * 17})`}>
              <line x1={0} y1={5} x2={15} y2={5}
                    stroke={l.color} strokeWidth={2} strokeDasharray={l.dash||'none'}/>
              <text x={19} y={9} fill="#9ca3af" fontSize={9}>{l.label}</text>
            </g>
          );
        })}
      </g>
    </svg>
  );
}

/* ─── SVG Stacked Area Chart ─────────────────────────────────── */
function StackedAreaChart({ data, layers }) {
  const W = 540, H = 210;
  const PAD = { top:10, right:125, bottom:32, left:38 };
  const IW = W - PAD.left - PAD.right;
  const IH = H - PAD.top  - PAD.bottom;
  const svgRef = useRef(null);
  const [tip, setTip] = useState(null);

  const pts = useMemo(() => {
    if (!data || data.length < 2) return null;
    return data;
  }, [data]);

  if (!pts || pts.length < 2) return null;

  const xMin = pts[0].time, xMax = pts[pts.length-1].time;
  const sx = v => ((v - xMin) / (xMax - xMin || 1)) * IW;
  const sy = f => IH * (1 - f);

  const n = pts.length;
  let bottoms = new Float32Array(n);
  const paths = [];
  for (const layer of layers) {
    const tops = pts.map((d,i) => bottoms[i] + (d[layer.key] || 0));
    const fwd  = tops.map((y,i) => `${i?'L':'M'}${sx(pts[i].time).toFixed(2)},${sy(y).toFixed(2)}`).join(' ');
    const bwd  = [...bottoms].reverse().map((y,ri) =>
      `L${sx(pts[n-1-ri].time).toFixed(2)},${sy(y).toFixed(2)}`
    ).join(' ');
    paths.push({ ...layer, d: `${fwd} ${bwd} Z` });
    bottoms = new Float32Array(tops);
  }

  const onMove = e => {
    if (!svgRef.current) return;
    const rect  = svgRef.current.getBoundingClientRect();
    const tReal = xMin + ((e.clientX - rect.left) / rect.width * W - PAD.left) / IW * (xMax - xMin);
    const near  = pts.reduce((a,b) => Math.abs(b.time - tReal) < Math.abs(a.time - tReal) ? b : a);
    setTip(near);
  };

  // Tooltip dimensions
  const TW = 148, TH = 14 + layers.length * 13 + 16;
  const tipX = tip ? Math.min(sx(tip.time) + 8, IW - TW + PAD.left - PAD.left) : 0;
  const tipXClamped = tip ? Math.max(0, Math.min(sx(tip.time) + 8, IW - TW)) : 0;

  return (
    <svg ref={svgRef} width="100%" viewBox={`0 0 ${W} ${H}`}
         onMouseMove={onMove} onMouseLeave={() => setTip(null)} style={{cursor:'crosshair'}}>
      <g transform={`translate(${PAD.left},${PAD.top})`}>
        {paths.map(p => <path key={p.key} d={p.d} fill={p.color} fillOpacity={0.85} stroke="none"/>)}
        <line x1={0} y1={0} x2={IW} y2={0} stroke="#374151"/>
        <line x1={0} y1={IH} x2={IW} y2={IH} stroke="#4b5563"/>
        {niceTicks(xMin, xMax, 5).map(v => (
          <g key={v} transform={`translate(${sx(v)},${IH})`}>
            <line y2={4} stroke="#4b5563"/>
            <text y={13} textAnchor="middle" fill="#9ca3af" fontSize={9}>{v.toFixed(0)}</text>
          </g>
        ))}
        <text x={IW/2} y={IH+27} textAnchor="middle" fill="#9ca3af" fontSize={10}>Time (h)</text>
        <line x1={0} y1={0} x2={0} y2={IH} stroke="#4b5563"/>
        {[0,25,50,75,100].map(pct => (
          <g key={pct} transform={`translate(0,${sy(pct/100)})`}>
            <line x2={-3} stroke="#4b5563"/>
            <text x={-5} textAnchor="end" dominantBaseline="middle" fill="#9ca3af" fontSize={9}>{pct}%</text>
          </g>
        ))}

        {/* Crosshair + tooltip */}
        {tip && <>
          <line x1={sx(tip.time)} y1={0} x2={sx(tip.time)} y2={IH} stroke="#ffffff18" strokeWidth={1}/>
          <g transform={`translate(${tipXClamped},2)`}>
            <rect width={TW} height={TH} rx={4} fill="#111827" stroke="#374151" strokeWidth={0.5}/>
            <text x={6} y={11} fill="#d1d5db" fontSize={9} fontWeight="600">t = {tip.time.toFixed(1)} h</text>
            {layers.map((l, i) => {
              const count = Math.round((tip[l.key] || 0) * (tip.total || 0));
              const pct   = tip.total > 0 ? ((tip[l.key] || 0) * 100).toFixed(1) : '0.0';
              return (
                <text key={l.key} x={6} y={23 + i * 13} fill={l.color} fontSize={9}>
                  {l.label}: {count.toLocaleString()} ({pct}%)
                </text>
              );
            })}
            <text x={6} y={23 + layers.length * 13} fill="#6b7280" fontSize={9}>
              Total: {(tip.total || 0).toLocaleString()}
            </text>
          </g>
        </>}
      </g>
      <g transform={`translate(${PAD.left+IW+10},${PAD.top+4})`}>
        {layers.map((l,i) => (
          <g key={l.key} transform={`translate(0,${i*16})`}>
            <rect width={11} height={11} rx={2} fill={l.color} fillOpacity={0.85}/>
            <text x={15} y={9} fill="#9ca3af" fontSize={9}>{l.label||l.key}</text>
          </g>
        ))}
      </g>
    </svg>
  );
}

/* ─── PopulationTable ────────────────────────────────────────── */
function PopulationTable({ population, total }) {
  if (!population) return <div className="text-gray-600 text-sm italic">No data yet.</div>;
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-gray-400 border-b border-gray-700">
          <th className="text-left py-1 font-medium">Cell Type</th>
          <th className="text-right py-1 font-medium">Count</th>
          <th className="text-right py-1 font-medium">%</th>
        </tr>
      </thead>
      <tbody>
        {ALL_TYPES.map((ct, i) => {
          const n = population[ct] || 0;
          return (
            <tr key={ct} className={i%2===0 ? 'bg-gray-800/30' : ''}>
              <td className="py-1 flex items-center gap-2">
                <span className="inline-block w-2.5 h-2.5 rounded-sm flex-shrink-0"
                      style={{backgroundColor: CELL_COLOURS[ct]}}/>
                {ct}
              </td>
              <td className="text-right py-1 font-mono">{n.toLocaleString()}</td>
              <td className="text-right py-1 font-mono text-gray-400">
                {total > 0 ? (n/total*100).toFixed(1) : '0.0'}%
              </td>
            </tr>
          );
        })}
        <tr className="border-t border-gray-700 font-semibold">
          <td className="py-1">Total</td>
          <td className="text-right py-1 font-mono">{(total||0).toLocaleString()}</td>
          <td className="text-right py-1 text-gray-400">100%</td>
        </tr>
      </tbody>
    </table>
  );
}

/* ─── MetricsCards ───────────────────────────────────────────── */
function MetricsCards({ states, time, total, target }) {
  const dev = (total && target) ? Math.abs(total - target) / target * 100 : null;
  const cards = [
    { label:'Time (h)',      value: time  != null ? time.toFixed(1) : '—' },
    { label:'Total Cells',   value: total ? total.toLocaleString() : '—',
      badge: dev != null ? `${dev<=10?'✓':'⚠'} ${dev.toFixed(1)}% from target (${target})` : null,
      good: dev != null && dev <= 10 },
    { label:'Mean Stemness', value: states ? states.mean_stemness.toFixed(3) : '—' },
    { label:'Mean Stress',   value: states ? states.mean_stress.toFixed(3)   : '—' },
  ];
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 mb-4">
      {cards.map(c => (
        <div key={c.label} className="bg-gray-800 rounded-lg p-3">
          <div className="text-xs text-gray-400 mb-1">{c.label}</div>
          <div className="text-xl font-mono font-semibold">{c.value}</div>
          {c.badge && <div className={`text-xs mt-1 ${c.good?'text-green-400':'text-yellow-400'}`}>{c.badge}</div>}
        </div>
      ))}
    </div>
  );
}

/* ─── RunHistory ─────────────────────────────────────────────── */
function RunHistory({ runs, onRestore }) {
  if (!runs.length) return <div className="text-gray-600 text-sm italic">No completed runs yet.</div>;
  return (
    <div className="space-y-2 max-h-52 overflow-y-auto pr-1">
      {[...runs].reverse().map(r => (
        <div key={r.session_id}
             className="bg-gray-800/60 border border-gray-700 rounded-lg p-3 flex justify-between items-start gap-2">
          <div className="min-w-0">
            <div className="text-xs text-gray-500">
              {new Date(r.saved_at).toLocaleTimeString()} · seed {r.seed} · t={r.t_max}h
            </div>
            <div className="text-sm font-mono mt-0.5 text-gray-200">
              n={r.total.toLocaleString()} · HSC={r.hsc_pct}% · mat={r.mat_pct}%
            </div>
          </div>
          <button onClick={() => onRestore(r)} className="text-xs text-blue-400 hover:text-blue-300 flex-shrink-0">
            ↺ Restore
          </button>
        </div>
      ))}
    </div>
  );
}

/* ─── App ────────────────────────────────────────────────────── */
function App() {
  const [basic,      setBasic]      = useState({...BASIC_DEF});
  const [adv,        setAdv]        = useState({...ADV_DEF});
  const [sessionId,  setSessionId]  = useState(null);
  const [running,    setRunning]    = useState(false);
  const [finished,   setFinished]   = useState(false);
  const [history,    setHistory]    = useState([]);
  const [current,    setCurrent]    = useState(null);
  const [progress,   setProgress]   = useState(0);
  const [error,      setError]      = useState(null);
  const [runHistory, setRunHistory] = useState(loadHistory);
  const [showHelp,   setShowHelp]   = useState(false);

  const stopRef = useRef(false);

  // Listen for "close-help" postMessage from the help iframe
  React.useEffect(() => {
    const handler = e => { if (e.data === 'close-help') setShowHelp(false); };
    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, []);

  const startSim = useCallback(async () => {
    setError(null); stopRef.current = false;
    setHistory([]); setCurrent(null); setProgress(0); setFinished(false); setSessionId(null);
    try {
      const config = buildConfig(basic, adv);
      const res = await fetch(`${API}/session/start`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ params: config, seed: config.seed, t_max: config.t_max }),
      });
      if (!res.ok) { const e = await res.json(); setError(e.detail?.error || JSON.stringify(e.detail)); return; }
      const { session_id } = await res.json();
      console.log('[SIM] Session started:', session_id);
      window.currentSessionId = session_id;          // debug: inspect in console
      setSessionId(session_id);
      setRunning(true);
      let batchCount = 0;
      while (!stopRef.current) {
        const sr = await fetch(`${API}/session/${session_id}/step`, {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({ n_events: 500 }),
        });
        if (!sr.ok) { console.error('[SIM] /step failed:', sr.status); break; }
        const d = await sr.json();
        batchCount++;
        setCurrent(d);
        setProgress(d.finished ? 100 : Math.min(99, d.time / config.t_max * 100));

        // ── Fetch full recorder history after every step ──
        try {
          const snapRes = await fetch(`${API}/session/${session_id}/snapshot`);
          if (snapRes.ok) {
            const snapData = await snapRes.json();
            if (snapData.history && snapData.history.length > 1) {
              setHistory(snapData.history.map(s => ({
                time: s.time, total: s.total, population: s.population, states: s.states, ...s.population,
              })));
            }
          }
        } catch (_) {}

        if (d.finished) {
          setFinished(true);
          const pop = d.population, tot = d.total || 1;
          const mat = ['Myeloid','Erythroid','B_cell','T_cell'].reduce((s,ct) => s + (pop[ct]||0), 0);
          const rec = {
            session_id, saved_at: new Date().toISOString(),
            seed: config.seed, t_max: config.t_max, params: config, total: d.total,
            hsc_pct: ((pop.HSC||0)/tot*100).toFixed(1),
            mat_pct: (mat/tot*100).toFixed(1),
            states: d.states,
          };
          const upd = [...runHistory, rec]; setRunHistory(upd); saveHistory(upd); break;
        }
      }
    } catch(e) { setError(String(e)); }
    finally   { setRunning(false); }
  }, [basic, adv, runHistory]);

  const stopSim = useCallback(async () => {
    stopRef.current = true; setRunning(false); setFinished(true);
    if (sessionId) await fetch(`${API}/session/${sessionId}/stop`, { method:'POST' }).catch(()=>{});
  }, [sessionId]);

  const exportPDF = useCallback(() => {
    if (!sessionId) return;
    const a = document.createElement('a');
    a.href = `${API}/session/${sessionId}/export/pdf`;
    a.download = `hema_${sessionId}.pdf`; a.click();
  }, [sessionId]);

  const stackData = useMemo(() => history.map(s => {
    const tot = s.total || 1, row = { time: s.time, total: s.total || 0 };
    ALL_TYPES.forEach(ct => { row[ct] = (s.population[ct]||0) / tot; });
    return row;
  }), [history]);

  const lineSpecs = [
    { key:'total',     color:'#e5e7eb',             width:2,   dash:'5,3', label:'Total'     },
    { key:'HSC',       color:CELL_COLOURS.HSC,       width:1.5,             label:'HSC'       },
    { key:'MPP',       color:CELL_COLOURS.MPP,       width:1.5,             label:'MPP'       },
    { key:'CMP',       color:CELL_COLOURS.CMP,       width:1.5,             label:'CMP'       },
    { key:'CLP',       color:CELL_COLOURS.CLP,       width:1.5,             label:'CLP'       },
    { key:'Myeloid',   color:CELL_COLOURS.Myeloid,   width:1.5,             label:'Myeloid'   },
    { key:'Erythroid', color:CELL_COLOURS.Erythroid, width:1.5,             label:'Erythroid' },
    { key:'B_cell',    color:CELL_COLOURS.B_cell,    width:1.5,             label:'B_cell'    },
    { key:'T_cell',    color:CELL_COLOURS.T_cell,    width:1.5,             label:'T_cell'    },
  ];
  const stackLayers = ALL_TYPES.map(ct => ({ key:ct, color:CELL_COLOURS[ct], label:ct }));

  return (
    <div className="flex flex-col h-screen bg-gray-900 text-gray-100">

      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 px-6 py-3 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <img src="./logo.png" alt="Logo" className="w-9 h-9 rounded-md object-contain"/>
          <h1 className="font-bold text-lg tracking-tight">Hematopoiesis Simulator</h1>
          <span className="text-xs text-gray-500 bg-gray-700 px-2 py-0.5 rounded">v0.12</span>
        </div>
        <div className="flex items-center gap-4 text-sm">
          {running && <span className="flex items-center gap-2 text-blue-400">
            <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse"/>
            Running… {progress.toFixed(0)}%
          </span>}
          {finished && !running && <span className="text-green-400">✓ Complete</span>}
          <button onClick={() => setShowHelp(true)}
             className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition-colors cursor-pointer">
            📖 Help
          </button>
          <a href={`${API}/docs`} target="_blank" className="text-gray-500 hover:text-gray-300 text-xs">API docs ↗</a>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">

        {/* Left panel */}
        <aside className="w-72 bg-gray-800 border-r border-gray-700 overflow-y-auto flex-shrink-0 flex flex-col">
          <div className="flex-1">
            <BasicParameters b={basic} setB={setBasic} disabled={running}/>
            <AdvancedSection
              a={adv} setA={setAdv} b={basic} disabled={running}
              onResetAll={() => { setBasic({...BASIC_DEF}); setAdv({...ADV_DEF}); }}
              onResetAdv={() => setAdv({...ADV_DEF})}
            />
          </div>

          <div className="p-4 border-t border-gray-700 space-y-2 flex-shrink-0">
            {error && (
              <div className="bg-red-900/40 border border-red-700 rounded p-2 text-xs text-red-300">{error}</div>
            )}
            {running && (
              <div className="h-1.5 bg-gray-700 rounded overflow-hidden">
                <div className="h-full bg-blue-500 rounded transition-all duration-200" style={{width:`${progress}%`}}/>
              </div>
            )}
            <button onClick={startSim} disabled={running}
                    className="w-full py-2 px-4 bg-green-600 hover:bg-green-500 disabled:bg-gray-700 disabled:text-gray-500 rounded-lg font-semibold text-sm transition-colors">
              {running ? '⏳ Running…' : '▶  Start'}
            </button>
            <button onClick={stopSim} disabled={!running}
                    className="w-full py-2 px-4 bg-red-700 hover:bg-red-600 disabled:bg-gray-700 disabled:text-gray-500 rounded-lg font-semibold text-sm transition-colors">
              ■  Stop
            </button>
            <button onClick={exportPDF} disabled={!sessionId || running}
                    className="w-full py-2 px-4 bg-blue-700 hover:bg-blue-600 disabled:bg-gray-700 disabled:text-gray-500 rounded-lg font-semibold text-sm transition-colors">
              ⬇  Export PDF
            </button>
          </div>
        </aside>

        {/* Right panel */}
        <main className="flex-1 overflow-y-auto p-5 space-y-4">
          <MetricsCards states={current?.states} time={current?.time} total={current?.total}
                        target={basic.enable_target_population ? basic.target_population_size : null}/>

          <div className="bg-gray-800 rounded-xl p-4">
            <h2 className="text-sm font-semibold text-gray-300 mb-3">Population over Time</h2>
            <LineChart data={history} lines={lineSpecs}
                       refLines={basic.enable_target_population
                         ? [{y: basic.target_population_size,
                             label: `Target (${basic.target_population_size})`,
                             color: '#6b7280'}]
                         : []}/>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="bg-gray-800 rounded-xl p-4">
              <h2 className="text-sm font-semibold text-gray-300 mb-3">Cell-Type Composition</h2>
              <StackedAreaChart data={stackData} layers={stackLayers}/>
            </div>
            <div className="bg-gray-800 rounded-xl p-4">
              <h2 className="text-sm font-semibold text-gray-300 mb-3">Current Counts</h2>
              <PopulationTable population={current?.population} total={current?.total||0}/>
            </div>
          </div>

          <div className="bg-gray-800 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-gray-300">Run History ({runHistory.length})</h2>
              {runHistory.length > 0 && (
                <button onClick={() => { setRunHistory([]); saveHistory([]); }}
                        className="text-xs text-red-500 hover:text-red-400">Clear all</button>
              )}
            </div>
            <RunHistory runs={runHistory} onRestore={r => setBasic(b => ({...b, seed: r.params.seed, t_max: r.params.t_max}))}/>
          </div>
        </main>
      </div>

      {/* ── Help overlay (full-screen iframe, no page reload) ── */}
      {showHelp && (
        <div style={{position:'fixed', inset:0, zIndex:9999, background:'#fff', display:'flex', flexDirection:'column'}}>
          <iframe
            src="./Help_page/help.html"
            style={{flex:1, border:'none', width:'100%'}}
            title="Help"
          />
        </div>
      )}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
