import re, sys

DOC_PATH = r'C:\Users\75BD~1\AppData\Local\Temp\part1_unpacked\word\document.xml'
with open(DOC_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

original_len = len(content)
changes_applied = []
changes_failed = []

def para(text):
    t = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
    return (
        '<w:p w:rsidR="00AB1234" w:rsidRDefault="00AB1234">\n'
        '      <w:pPr>\n'
        '        <w:rPr>\n'
        '          <w:rFonts w:ascii="Cambria" w:hAnsi="Cambria"/>\n'
        '          <w:lang w:val="en-US"/>\n'
        '        </w:rPr>\n'
        '      </w:pPr>\n'
        '      <w:r>\n'
        '        <w:rPr>\n'
        '          <w:rFonts w:ascii="Cambria" w:hAnsi="Cambria"/>\n'
        '          <w:lang w:val="en-US"/>\n'
        '        </w:rPr>\n'
        f'        <w:t xml:space="preserve">{t}</w:t>\n'
        '      </w:r>\n'
        '    </w:p>'
    )

def empty_para():
    return (
        '<w:p w:rsidR="00AB1234" w:rsidRDefault="00AB1234">\n'
        '      <w:pPr>\n'
        '        <w:rPr>\n'
        '          <w:rFonts w:ascii="Cambria" w:hAnsi="Cambria"/>\n'
        '          <w:lang w:val="en-US"/>\n'
        '        </w:rPr>\n'
        '      </w:pPr>\n'
        '    </w:p>'
    )

# =============================================================================
# PART A-1: Delete section 1.5
# =============================================================================
start_marker = "<w:t>## 1.5 What's New in v0.12</w:t>"
end_marker = '<w:t>*End of Part 1'

pos_start_t = content.find(start_marker)
pos_end_t = content.find(end_marker)

if pos_start_t == -1:
    changes_failed.append('A1: Could not find section 1.5 heading')
elif pos_end_t == -1:
    changes_failed.append('A1: Could not find End of Part 1 marker')
else:
    para_open = content.rfind('<w:p ', 0, pos_start_t)
    para_end_open = content.rfind('<w:p ', 0, pos_end_t)
    prev_end_p = content.rfind('</w:p>', 0, para_end_open)
    removed_len = prev_end_p + len('</w:p>') - para_open
    content = content[:para_open] + content[prev_end_p + len('</w:p>'):]
    changes_applied.append(f'A1: Deleted section 1.5 ({removed_len} chars removed)')

# =============================================================================
# PART A-2
# =============================================================================
old = 'values calibrated for v0.12'
new = 'values are pre-calibrated and represent the recommended defaults'
if old in content:
    content = content.replace(old, new, 1)
    changes_applied.append('A2: Replaced calibrated for v0.12 in 2.3.1')
else:
    changes_failed.append('A2: Not found: ' + old)

# =============================================================================
# PART A-3
# =============================================================================
old = 'v0.12 represents the current optimal balance between **biological realism** and **usability**.'
new = 'The current model represents the optimal balance between **biological realism** and **usability**.'
if old in content:
    content = content.replace(old, new, 1)
    changes_applied.append('A3: Replaced v0.12 in 3.1.5')
else:
    changes_failed.append('A3: Not found 3.1.5 sentence')

# =============================================================================
# PART A-4
# =============================================================================
replacements_a4 = [
    ('leave at default in v0.12.', 'leave at default.'),
    ('Leave at defaults \u2014 values are calibrated for v0.12', 'Leave at defaults \u2014 values are pre-calibrated and represent the recommended defaults'),
    ('Leave at defaults \u2013 values are calibrated for v0.12', 'Leave at defaults \u2013 values are pre-calibrated and represent the recommended defaults'),
    ('Leave at defaults - values are calibrated for v0.12', 'Leave at defaults - values are pre-calibrated and represent the recommended defaults'),
    ('the calibrated v0.12 values are applied automatically', 'the pre-calibrated values are applied automatically'),
    ('# Part 3.1: Model Limitations (v0.12)', '# Part 3.1: Model Limitations'),
    ('Model v0.12 is well-suited', 'The model is well-suited'),
]
for old, new in replacements_a4:
    if old in content:
        content = content.replace(old, new)
        changes_applied.append(f'A4: replaced: {old[:50]}')
    else:
        changes_failed.append(f'A4 not found: {old[:60]}')

remaining = re.findall(r'<w:t[^>]*>[^<]*v0\.1[12][^<]*</w:t>', content)
if remaining:
    changes_failed.append(f'A4: Still has v0.12/v0.11: {remaining[:3]}')
else:
    changes_applied.append('A4: No remaining v0.12/v0.11 in text nodes')

# =============================================================================
# PART A-5a: Stochastic sentence in 1.3
# =============================================================================
commitment_bullet_marker = '- **Commitment** \u2014 drives active differentiation; the HSC &quot;sacrifices&quot; itself for production</w:t>'
pos_commit = content.find(commitment_bullet_marker)
if pos_commit == -1:
    # try with regular dash
    commitment_bullet_marker = '- **Commitment** — drives active differentiation; the HSC &quot;sacrifices&quot; itself for production</w:t>'
    pos_commit = content.find(commitment_bullet_marker)

if pos_commit == -1:
    changes_failed.append('A5a: Could not find Commitment bullet in 1.3')
else:
    pos_close = content.find('</w:p>', pos_commit)
    pos_close2 = content.find('</w:p>', pos_close + 1)
    new_p = '\n    ' + para('The fate is chosen stochastically at each division, making the system\u2019s behavior inherently variable across runs.') + '\n'
    content = content[:pos_close2 + len('</w:p>')] + new_p + content[pos_close2 + len('</w:p>'):]
    changes_applied.append('A5a: Added stochastic sentence to section 1.3')

# =============================================================================
# PART A-5b: Epigenetic memory sentence to 2.4.4
# =============================================================================
toggle_epigenetic = '**Toggle:** &quot;Customize epigenetics&quot; *(default: OFF)*</w:t>'
pos_toggle = content.find(toggle_epigenetic)
if pos_toggle == -1:
    changes_failed.append('A5b: Could not find 2.4.4 toggle paragraph')
else:
    pos_close_toggle = content.find('</w:p>', pos_toggle)
    epi_sentence = "Epigenetic memory is a core stability mechanism: without it, every fate decision is independent of the parent\u2019s history, producing a noisier and less predictable system."
    insert_text = '\n    ' + para(epi_sentence) + '\n'
    content = content[:pos_close_toggle + len('</w:p>')] + insert_text + content[pos_close_toggle + len('</w:p>'):]
    changes_applied.append('A5b: Added epigenetic memory sentence to 2.4.4')

# =============================================================================
# PART A-5c: Centriole mode sentence
# =============================================================================
centriole_how = 'Asymmetry emerges naturally from this mechanism without requiring explicit rules.</w:t>'
pos_centriole_how = content.find(centriole_how)
if pos_centriole_how == -1:
    changes_failed.append('A5c: Could not find Centriole how-it-works paragraph')
else:
    pos_close_c = content.find('</w:p>', pos_centriole_how)
    centriole_sentence = 'This mechanism is the primary reason the Centriole mode produces more realistic asymmetry than the Asymmetric mode without requiring manual parameter tuning.'
    insert_c = '\n    ' + para(centriole_sentence) + '\n'
    content = content[:pos_close_c + len('</w:p>')] + insert_c + content[pos_close_c + len('</w:p>'):]
    changes_applied.append('A5c: Added Centriole mode sentence to 2.4.3')

# =============================================================================
# PART B1: Fix density_factor
# =============================================================================
found_b1 = False
for variant in ['density_factor \u2248 55\u00d7', 'density_factor &asymp; 55&times;', 'density_factor ≈ 55×']:
    if variant in content:
        content = content.replace(variant, 'density_factor \u2248 37\u00d7', 1)
        changes_applied.append('B1a: Fixed density_factor 55x to 37x')
        found_b1 = True
        break
if not found_b1:
    changes_failed.append('B1: Not found density_factor 55x (tried multiple encodings)')

for variant in ['division massively accelerated', 'division massively accelerated']:
    if variant in content:
        content = content.replace(variant, 'division accelerates ~37\u00d7 \u2014 rapid recovery begins', 1)
        changes_applied.append('B1b: Fixed division massively accelerated description')
        break
else:
    if 'B1a: Fixed density_factor' in str(changes_applied):
        changes_failed.append('B1b: Not found: division massively accelerated')

# =============================================================================
# PART B2: Expand lifespan sentence in 1.1
# =============================================================================
# Try various dash encodings
old_b2_variants = [
    'This renewal is essential because blood cells are short-lived \u2014 red blood cells survive ~120 days, platelets ~10 days, and most white blood cells only hours to days.',
    'This renewal is essential because blood cells are short-lived \u2013 red blood cells survive ~120 days, platelets ~10 days, and most white blood cells only hours to days.',
    'This renewal is essential because blood cells are short-lived — red blood cells survive ~120 days, platelets ~10 days, and most white blood cells only hours to days.',
]
new_b2 = ('This renewal is essential because blood cells are short-lived \u2014 in biological reality, red blood cells survive ~120 days, '
           'platelets ~10 days, and most white blood cells only hours to days. '
           'The simulator uses compressed timescales to keep runs tractable: model hours do not map 1-to-1 onto real time, '
           'and cell lifespans in the simulator are proportionally shorter.')
found_b2 = False
for old_b2 in old_b2_variants:
    if old_b2 in content:
        content = content.replace(old_b2, new_b2, 1)
        changes_applied.append('B2: Expanded blood cell lifespan sentence in 1.1')
        found_b2 = True
        break
if not found_b2:
    changes_failed.append('B2: Not found lifespan sentence in any dash variant')

# =============================================================================
# PART B3: Two paragraphs after stochastic sentence in 1.3
# =============================================================================
stochastic_marker = "The fate is chosen stochastically at each division, making the system\u2019s behavior inherently variable across runs."
pos_stoch = content.find(stochastic_marker)
if pos_stoch == -1:
    changes_failed.append('B3: Could not find stochastic sentence')
else:
    pos_close_stoch = content.find('</w:p>', pos_stoch)
    b3_para1 = 'Progenitor cells (MPP, CMP, CLP) follow the same fate logic but with different default probabilities weighted toward commitment \u2014 they are designed to differentiate, not self-renew. Their fate weights can be customised in the Advanced Settings under Division Fates.'
    b3_para2 = 'The probabilities shown above are the default starting values. They can be adjusted in the Advanced Settings panel. Changing them shifts the balance between maintaining the stem cell pool and producing downstream lineages \u2014 see Section 2.5 (Division Fates) for details.'
    insert_b3 = (
        '\n    ' + empty_para() + '\n'
        '    ' + para(b3_para1) + '\n'
        '    ' + empty_para() + '\n'
        '    ' + para(b3_para2) + '\n'
    )
    content = content[:pos_close_stoch + len('</w:p>')] + insert_b3 + content[pos_close_stoch + len('</w:p>'):]
    changes_applied.append('B3: Added two paragraphs to section 1.3')

# =============================================================================
# PART B4: six sliders -> seven sliders
# =============================================================================
old_b4 = 'six sliders appear that control how stemness and accumulated stress modify division and apoptosis rates.'
new_b4 = 'seven sliders appear that control how stemness and accumulated stress modify division and apoptosis rates.'
if old_b4 in content:
    content = content.replace(old_b4, new_b4, 1)
    changes_applied.append('B4: Changed six sliders to seven sliders')
else:
    changes_failed.append('B4: Not found: six sliders appear')

# =============================================================================
# PART B5: Stress concept block updates
# =============================================================================
div_stress_context = '<w:t xml:space="preserve"> division rate    </w:t>'
pos_div_stress = content.find(div_stress_context)
if pos_div_stress == -1:
    changes_failed.append('B5: Could not find division rate stress text')
else:
    pos_para_end_div = content.find('</w:p>', pos_div_stress)
    pos_60_div = content.find('<w:t>60%)</w:t>', pos_div_stress)
    if pos_60_div != -1 and pos_60_div < pos_para_end_div:
        content = (content[:pos_60_div] +
                   '<w:t xml:space="preserve">60%, governed by w_div_stress in Advanced Settings \u2192 State Modulation)</w:t>' +
                   content[pos_60_div + len('<w:t>60%)</w:t>'):])
        changes_applied.append('B5a: Updated division stress w_div_stress text')
    else:
        changes_failed.append(f'B5a: 60%) not found near division rate')

apo_stress_context = '<w:t xml:space="preserve"> apoptosis rate   </w:t>'
pos_apo_stress = content.find(apo_stress_context)
if pos_apo_stress == -1:
    changes_failed.append('B5: Could not find apoptosis rate stress text')
else:
    pos_para_end_apo = content.find('</w:p>', pos_apo_stress)
    old_apo = '<w:t xml:space="preserve">  (up to +60%)</w:t>'
    pos_apo_60 = content.find(old_apo, pos_apo_stress)
    if pos_apo_60 != -1 and pos_apo_60 < pos_para_end_apo:
        new_apo = '<w:t xml:space="preserve">  (up to +60%, governed by w_apo_stress in Advanced Settings \u2192 State Modulation)</w:t>'
        content = content[:pos_apo_60] + new_apo + content[pos_apo_60 + len(old_apo):]
        changes_applied.append('B5b: Updated apoptosis stress w_apo_stress text')
    else:
        changes_failed.append(f'B5b: (up to +60%) not found near apoptosis rate')

# =============================================================================
# PART C1: Insert Introduction section
# =============================================================================
intro_lines = [
    '# Introduction',
    '',
    'This document is the user manual for the hematopoiesis simulator \u2014 an interactive, browser-based tool that models how blood cells are produced in the bone marrow.',
    '',
    'The simulator lets you observe how a small pool of stem cells (HSC) divides, differentiates, and maintains a stable population of millions of specialised blood cells. You can adjust dozens of parameters, toggle regulatory mechanisms on and off, and watch how the system responds in real time.',
    '',
    '**What this document covers:**',
    '',
    '- Part 1: the biology behind the model \u2014 cell types, differentiation, and the key concepts used throughout.',
    '- Part 2: every parameter in the simulator, organised by panel (Basic Settings, then Advanced Settings groups).',
    "- Part 3: the model's known limitations and when not to trust its results.",
    '',
    '**Who this is for:** anyone using the simulator \u2014 no specialist background in biology or mathematics is required. Technical terms are explained when first introduced, and a glossary is provided at the end of the document.',
    '',
    '**How to read it:** first-time users should read Part 1 and Part 2.1, then run the simulator once with all defaults. After that, read the remaining sections in any order depending on what you want to investigate.',
    '',
    '---',
    '',
    'Contents',
    '',
    '[This is a placeholder for the Table of Contents \u2014 list all major sections and subsections with their headings]',
    '',
    '---',
    '',
]

intro_xml = ''
for line in intro_lines:
    if line == '':
        intro_xml += '    ' + empty_para() + '\n'
    else:
        intro_xml += '    ' + para(line) + '\n'

part1_heading = '<w:t># Part 1: Hematopoiesis and Cell Hierarchy in the Model</w:t>'
pos_part1 = content.find(part1_heading)
if pos_part1 == -1:
    changes_failed.append('C1: Could not find Part 1 heading')
else:
    pos_part1_para = content.rfind('<w:p ', 0, pos_part1)
    content = content[:pos_part1_para] + intro_xml + '    ' + content[pos_part1_para:]
    changes_applied.append('C1: Inserted Introduction section')

# =============================================================================
# PART C2: Insert Part 2.5 after End of Part 2.4
# =============================================================================
part25_lines = [
    '---',
    '',
    '## Part 2.5: Division Fate Weights',
    '',
    '### 2.5.1 Introduction',
    '',
    'Division fate weights are the probabilities that determine what happens when a cell divides. They are the most direct lever for controlling the long-term balance of the system: too much self-renewal and progenitors accumulate; too much commitment and the stem cell pool depletes.',
    '',
    'Location in UI: Advanced Settings \u2192 "\u2696 Division Fates"',
    'Toggle: "Use custom fate weights" (default: OFF)',
    'When ON: sliders appear for each dividing cell type.',
    '',
    '### 2.5.2 The Three Fate Outcomes',
    '',
    '| Fate | Symbol | What happens at division |',
    '|---|---|---|',
    '| Self-renewal | SR | Both daughter cells are the same type as the parent. The pool grows by one cell. |',
    '| Asymmetric | AS | One daughter stays the same type; the other becomes the next type down the differentiation tree. Pool size is maintained. |',
    '| Commitment | CO | Both daughters become the next type down the tree. The parent type loses one cell. |',
    '',
    'The three probabilities must always sum to 100%. The simulator enforces this automatically \u2014 adjusting one slider rescales the others proportionally.',
    '',
    '### 2.5.3 Default Fate Weights by Cell Type',
    '',
    '| Cell type | Self-renewal % | Asymmetric % | Commitment % | Bias |',
    '|---|---|---|---|---|',
    '| HSC | 82.5 | 12.5 | 5.0 | Strong self-renewal |',
    '| MPP | 50.0 | 30.0 | 20.0 | Balanced |',
    '| CMP | 30.0 | 40.0 | 30.0 | Commitment-leaning |',
    '| CLP | 30.0 | 40.0 | 30.0 | Commitment-leaning |',
    '',
    'Terminal cells (Myeloid, Erythroid, B_cell, T_cell) do not divide and have no fate weights.',
    '',
    "Note: the percentages for MPP, CMP, and CLP above are representative defaults. Verify the exact values displayed in your simulator's interface, as they may differ from those shown here.",
    '',
    '### 2.5.4 How Changing Fate Weights Affects the System',
    '',
    '| Change | Immediate effect | Long-term effect |',
    '|---|---|---|',
    '| Increase HSC self-renewal | More HSC\u2013HSC divisions | HSC pool grows; downstream lineages may shrink temporarily |',
    '| Increase HSC commitment | Fewer HSC retained | HSC pool depletes; downstream lineages expand briefly, then collapse |',
    '| Increase MPP asymmetric | More MPP\u2192CMP/CLP output | Faster production of terminal cells |',
    '| Increase CMP commitment | Faster Myeloid/Erythroid production | CMP pool shrinks; burst of terminal output followed by deficit |',
    '',
    '**Rule of thumb:** HSC self-renewal probability is the single most influential fate parameter. Reducing it below ~70% makes the system structurally unstable at default population targets.',
    '',
    '### 2.5.5 Recommended Scenarios',
    '',
    '**Scenario 1 \u2014 "Default balance" (recommended)**',
    'All fate weights at defaults. Toggle OFF.',
    'Result: stable long-term equilibrium.',
    '',
    '**Scenario 2 \u2014 "HSC pool study"**',
    '',
    '| Parameter | Value |',
    '|---|---|',
    '| HSC self-renewal | 75% |',
    '| HSC asymmetric | 15% |',
    '| HSC commitment | 10% |',
    '',
    'Result: slightly lower HSC pool, faster downstream output. Good for studying how the system compensates for reduced stem cell self-maintenance.',
    '',
    '**Scenario 3 \u2014 "Forced differentiation"**',
    '',
    '| Parameter | Value |',
    '|---|---|',
    '| HSC commitment | 20% |',
    '| HSC self-renewal | 70% |',
    '',
    'Result: HSC pool gradually depletes; the system cannot sustain production without the Population Regulation mechanism (M6.4) compensating aggressively.',
    '',
    '**Scenario 4 \u2014 "Pure self-renewal experiment"**',
    '',
    '| Parameter | Value |',
    '|---|---|',
    '| HSC self-renewal | 95% |',
    '| HSC asymmetric | 4% |',
    '| HSC commitment | 1% |',
    '',
    'Result: HSC accumulate; downstream lineages starve. Terminal cell counts collapse. Useful as a pathological control case.',
    '',
]

part25_xml = ''
for line in part25_lines:
    if line == '':
        part25_xml += '    ' + empty_para() + '\n'
    else:
        part25_xml += '    ' + para(line) + '\n'

# Find the End of Part 2.4 marker (try multiple dash variants)
pos_end24 = -1
for variant in [
    '*End of Part 2.4 \u2014 Additional Advanced Parameters*</w:t>',
    '*End of Part 2.4 \u2013 Additional Advanced Parameters*</w:t>',
    '*End of Part 2.4 — Additional Advanced Parameters*</w:t>',
]:
    pos_end24 = content.find(variant)
    if pos_end24 != -1:
        break

if pos_end24 == -1:
    changes_failed.append('C2: Could not find End of Part 2.4 marker')
else:
    pos_end24_close = content.find('</w:p>', pos_end24)
    pos_page_break = content.find('<w:br w:type="page"/>', pos_end24_close)
    if pos_page_break != -1 and pos_page_break < pos_end24_close + 500:
        pos_after_pb = content.find('</w:p>', pos_page_break)
        insert_after = pos_after_pb + len('</w:p>')
    else:
        insert_after = pos_end24_close + len('</w:p>')
    content = content[:insert_after] + '\n' + part25_xml + content[insert_after:]
    changes_applied.append('C2: Inserted Part 2.5 Division Fate Weights')

# =============================================================================
# PART C3: Insert Part 3.2 after End of Part 3.1
# =============================================================================
part32_lines = [
    '---',
    '',
    '## Part 3.2: Reading the Simulator Output',
    '',
    '### 3.2.1 Overview',
    '',
    'After a simulation run completes, the right panel displays a set of charts. Each chart shows a different aspect of the population over simulated time (x-axis, in hours). This section explains what each chart shows and how to interpret common patterns.',
    '',
    '### 3.2.2 Chart Descriptions',
    '',
    '| Chart name | Y-axis | What to look for |',
    '|---|---|---|',
    '| Total Population | Cell count | Does the line plateau (homeostasis) or grow/collapse? The plateau level should approximate the Target Population setting. |',
    '| HSC Pool | HSC count | A stable or slowly-declining line is normal. Rapid decline indicates over-commitment; a rising line indicates excess self-renewal. |',
    "| Cell-type Composition | Cell count per type (stacked or overlaid) | Relative widths of each type's band show lineage balance. Disappearing bands indicate lineage collapse. |",
    '| Division Events | Events per time unit | Peaks indicate the system is recovering from a deficit; flat lines indicate equilibrium. |',
    '| Apoptosis Events | Events per time unit | Sustained elevation signals stress accumulation or crowding apoptosis (M4) activation. |',
    '| Mean Stemness | Average stemness across all HSC | A declining trend over time indicates centriole aging accumulating across the pool. |',
    '| Mean Stress | Average stress across all cells | Should grow slowly and plateau. Rapid growth means stress_accumulation_rate is set too high. |',
    '',
    'Note: not all charts may be visible by default \u2014 some may require toggling the display options in the chart panel.',
    '',
    '### 3.2.3 Common Patterns and What They Mean',
    '',
    '| Pattern | Likely cause | What to check |',
    '|---|---|---|',
    '| Population plateaus near target | Normal homeostasis | Nothing \u2014 system is working correctly |',
    '| Population oscillates and never settles | Density gamma (\u03b3) too high, or fate weights unbalanced | Reduce \u03b3; check HSC commitment probability |',
    '| HSC pool collapses within first 50 h | Commitment probability too high, or niche modulation OFF | Enable M6.2 or reduce commitment weight |',
    '| Terminal cells disappear gradually | Progenitor bottleneck (MPP or CMP depleted) | Check division rates; ensure M6.4 is ON |',
    '| Population grows without ceiling | Target Population toggle OFF, or M4 off with \u03b3 = 0 | Enable Target Population or increase \u03b3 |',
    '| Mean stress rises rapidly then plateaus early | Stress accumulation rate too high | Reduce stress_accumulation_rate in Basic Settings |',
    '| All charts flat from t = 0 | Simulation may not have run | Check for error messages; try reducing Duration |',
    '',
]

part32_xml = ''
for line in part32_lines:
    if line == '':
        part32_xml += '    ' + empty_para() + '\n'
    else:
        part32_xml += '    ' + para(line) + '\n'

pos_end31 = -1
for variant in [
    '*End of Part 3.1 \u2014 Model Limitations*</w:t>',
    '*End of Part 3.1 \u2013 Model Limitations*</w:t>',
    '*End of Part 3.1 — Model Limitations*</w:t>',
]:
    pos_end31 = content.find(variant)
    if pos_end31 != -1:
        break

if pos_end31 == -1:
    changes_failed.append('C3: Could not find End of Part 3.1 marker')
else:
    pos_end31_close = content.find('</w:p>', pos_end31)
    content = content[:pos_end31_close + len('</w:p>')] + '\n' + part32_xml + content[pos_end31_close + len('</w:p>'):]
    changes_applied.append('C3: Inserted Part 3.2')

# =============================================================================
# PART C4: Insert Glossary before </w:body>
# =============================================================================
glossary_lines = [
    '---',
    '',
    '# Appendix: Glossary',
    '',
    '| Term | Definition |',
    '|---|---|',
    '| Apoptosis | Programmed cell death \u2014 a cell actively destroys itself rather than being killed externally. In the model, expressed as a rate in events per hour. |',
    "| Asymmetric division | A division where one daughter cell retains the parent's identity and the other becomes a different cell type. |",
    '| Commitment | A division fate where both daughter cells differentiate into the next type down the hierarchy. The parent type "sacrifices" itself to produce two progenitors. |',
    '| CLP (Common Lymphoid Progenitor) | An intermediate cell type that gives rise to B-cells and T-cells. Cannot become myeloid cells. |',
    '| CMP (Common Myeloid Progenitor) | An intermediate cell type that gives rise to myeloid and erythroid cells. Cannot become lymphoid cells. |',
    '| Differentiation | The process by which a less-specialised cell becomes a more-specialised cell type. Always one-way in this model. |',
    '| Division rate | The average number of divisions a cell performs per hour. Expressed in units of 1/h. |',
    "| Epigenetic memory | In the model: a cell's tendency to repeat its parent's fate choice. Controlled by the inheritance_noise and drift_rate parameters. |",
    '| Hematopoiesis | The biological process of blood cell production, occurring primarily in the bone marrow. |',
    '| HSC (Hematopoietic Stem Cell) | The most primitive cell in the hierarchy. HSCs self-renew indefinitely and give rise to all other blood cell types. |',
    "| Homeostasis | The system's ability to maintain a stable population size over time despite ongoing cell death and renewal. |",
    '| MPP (Multipotent Progenitor) | A progenitor cell derived from HSC that can still produce both myeloid and lymphoid lineages, but has less self-renewal capacity. |',
    '| Niche | The bone marrow microenvironment surrounding HSCs. In the model, the niche suppresses commitment when the stem cell pool is depleted. |',
    '| Progenitor | Any cell that has partially differentiated from an HSC but has not yet reached a terminal fate (HSC, MPP, CMP, CLP are all progenitors). |',
    "| Self-renewal | A division fate where both daughters are identical to the parent. The cell type's pool grows by one. |",
    '| Seed | A number that initialises the random number generator. The same seed always produces the same simulation result. |',
    '| Stemness | A value between 0 and 1 representing a cell\'s capacity for sustained self-renewal. Higher stemness = more division potential. |',
    '| Stress | A cell-internal counter that accumulates over time, representing replicative damage. High stress slows division and accelerates apoptosis. |',
    '| Terminal cell | A fully differentiated cell that performs a specific function (Myeloid, Erythroid, B_cell, T_cell). Terminal cells do not divide. |',
    '',
]

glossary_xml = ''
for line in glossary_lines:
    if line == '':
        glossary_xml += '    ' + empty_para() + '\n'
    else:
        glossary_xml += '    ' + para(line) + '\n'

body_close = '</w:body>'
pos_body_close = content.rfind(body_close)
if pos_body_close == -1:
    changes_failed.append('C4: Could not find </w:body>')
else:
    content = content[:pos_body_close] + glossary_xml + '\n' + content[pos_body_close:]
    changes_applied.append('C4: Inserted Glossary')

# =============================================================================
# PART D4: Cross-reference at end of 1.3
# =============================================================================
b3_para2_marker = 'see Section 2.5 (Division Fates) for details.'
pos_b3p2 = content.find(b3_para2_marker)
if pos_b3p2 == -1:
    changes_failed.append('D4: Could not find B3 para2 anchor for D4')
else:
    pos_b3p2_close = content.find('</w:p>', pos_b3p2)
    d4_text = '\u2192 See Section 2.5 (Division Fate Weights) for the full parameter reference and how to adjust these values in the simulator.'
    insert_d4 = '\n    ' + para(d4_text) + '\n'
    content = content[:pos_b3p2_close + len('</w:p>')] + insert_d4 + content[pos_b3p2_close + len('</w:p>'):]
    changes_applied.append('D4: Added Section 2.5 cross-reference at end of 1.3')

# =============================================================================
# PART D5: Cross-reference at end of STRESS block in 1.4
# =============================================================================
stress_accumulation = 'Grows by:  stress_accumulation_rate per hour (default 0.001)</w:t>'
pos_stress_acc = content.find(stress_accumulation)
if pos_stress_acc == -1:
    changes_failed.append('D5: Could not find stress accumulation rate line')
else:
    pos_stress_acc_close = content.find('</w:p>', pos_stress_acc)
    d5_text = '\u2192 See Section 2.4.2 (State Modulation) for the parameters that control how strongly stress affects division and apoptosis rates.'
    insert_d5 = '\n    ' + para(d5_text) + '\n'
    content = content[:pos_stress_acc_close + len('</w:p>')] + insert_d5 + content[pos_stress_acc_close + len('</w:p>'):]
    changes_applied.append('D5: Added Section 2.4.2 cross-reference at end of STRESS block')

# =============================================================================
# PART D6: Update Division Fates row in 2.4.6
# =============================================================================
old_d6 = 'Change to study self-renewal vs. commitment balance |</w:t>'
new_d6 = 'Change to study self-renewal vs. commitment balance \u2014 see Section 2.5 |</w:t>'
if old_d6 in content:
    content = content.replace(old_d6, new_d6, 1)
    changes_applied.append('D6: Updated Division Fates row in 2.4.6')
else:
    changes_failed.append('D6: Not found: Division Fates row in 2.4.6')

# =============================================================================
# Write output
# =============================================================================
with open(DOC_PATH, 'w', encoding='utf-8') as f:
    f.write(content)

print("=== CHANGES APPLIED ===")
for c in changes_applied:
    print(f"  OK {c}")
print(f"\n=== CHANGES FAILED ===")
for c in changes_failed:
    print(f"  FAIL {c}")

print(f"\nOriginal size: {original_len}")
print(f"New size: {len(content)}")
print(f"Size increase: {len(content) - original_len} chars")
