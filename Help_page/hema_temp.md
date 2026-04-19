\# Introduction

This document is the user manual for the hematopoiesis simulator --- an interactive, browser-based tool that models how blood cells are produced in the bone marrow.

The simulator lets you observe how a small pool of stem cells (HSC) divides, differentiates, and maintains a stable population of millions of specialised blood cells. You can adjust dozens of parameters, toggle regulatory mechanisms on and off, and watch how the system responds in real time.

\*\*What this document covers:\*\*

\- Part 1: the biology behind the model --- cell types, differentiation, and the key concepts used throughout.

\- Part 2: every parameter in the simulator, organised by panel (Basic Settings, then Advanced Settings groups).

\- Part 3: the model\'s known limitations and when not to trust its results.

\*\*Who this is for:\*\* anyone using the simulator --- no specialist background in biology or mathematics is required. Technical terms are explained when first introduced, and a glossary is provided at the end of the document.

\*\*How to read it:\*\* first-time users should read Part 1 and Part 2.1, then run the simulator once with all defaults. After that, read the remaining sections in any order depending on what you want to investigate.

\-\--

Contents

Part 1: Hematopoiesis and Cell Hierarchy in the Model

1.1 What Is Hematopoiesis

1.2 Differentiation Tree

1.2.1 Diagram

1.2.2 Cell Type Properties

1.3 Division Fate

1.4 Key Concepts

Part 2.1: Core Simulation Parameters

2.1.1 Introduction

2.1.2 Parameter Overview Table

2.1.3 Parameter Details (Parameters 1--6)

2.1.4 Recommended Parameter Combinations (4 scenarios)

Part 2.2: Control Mechanisms (Advanced Parameters)

2.2.1 Introduction

2.2.2 Mechanisms Overview

2.2.3 Mechanism 1 --- Population Regulation (M6.4)

2.2.4 Mechanism 2 --- Niche Modulation (M6.2)

2.2.5 Mechanism 3 --- Crowding Apoptosis (M4)

2.2.6 How All Three Work Together

2.2.7 Recommended Combinations (5 scenarios)

Part 2.3: Division & Apoptosis Rates

2.3.1 Introduction

2.3.2 Full Rate Table

2.3.3 Interpreting the Rates

2.3.4 Location in UI & How to Modify

2.3.5 Change Examples & Expected Effects (3 examples)

2.3.6 Recommended Scenarios (6 scenarios)

Part 2.4: Additional Advanced Parameters

2.4.1 Introduction

2.4.2 State Modulation

2.4.3 Inheritance Details

2.4.4 Epigenetic Details

2.4.5 Lifetime Dynamics

2.4.6 Quick Reference Summary

2.5 Division Fate Weights

2.5.1 Introduction

2.5.2 The Three Fate Outcomes

2.5.3 Default Fate Weights by Cell Type

2.5.4 How Changing Fate Weights Affects the System

2.5.5 Recommended Scenarios (4 scenarios)

Part 3.1: Model Limitations

3.1.1 Introduction

3.1.2 Limitations Overview (10 limitations)

3.1.3 Summary: What the Model Does Well vs. Poorly

3.1.4 When to Trust the Results

3.1.5 Possible Future Improvements

Part 3.2: Reading the Simulator Output

3.2.1 Overview

3.2.2 Chart Descriptions

3.2.3 Common Patterns and What They Mean

Appendix: Glossary

\-\--

\# Part 1: Hematopoiesis and Cell Hierarchy in the Model

\-\--

\## 1.1 What Is Hematopoiesis

Hematopoiesis is the continuous process by which the body produces blood cells. It takes place primarily in the \*\*bone marrow\*\*, where a small pool of stem cells generates billions of new cells every day. This renewal is essential because blood cells are short-lived --- in biological reality, red blood cells survive \~120 days, platelets \~10 days, and most white blood cells only hours to days. The simulator uses compressed timescales to keep runs tractable: model hours do not map 1-to-1 onto real time, and cell lifespans in the simulator are proportionally shorter. The process is hierarchical: a few highly potent \*\*stem cells (HSC)\*\* sit at the top and progressively give rise to more specialized, less flexible descendants.

\> 💡 \*\*Analogy:\*\* Hematopoiesis is a factory. A handful of stem cells at the center keep dividing and differentiating, sending specialized workers (red cells, immune cells, platelets) into the bloodstream around the clock.

\-\--

\## 1.2 Differentiation Tree

\### Diagram

\`\`\`

HSC

(Stem Cells)

│

│ differentiation

│

MPP

(Multipotent Progenitors)

/ \\

/ \\

CMP CLP

(Myeloid (Lymphoid

Progenitor) Progenitor)

/ \\ / \\

/ \\ / \\

Myeloid Erythroid B_cell T_cell

(Neutrophils)(Red cells)(B-cells)(T-cells)

\`\`\`

\*\*Key rule:\*\* Differentiation is \*\*one-way\*\* --- a cell can only move down the tree, never back up.

\-\--

\### Cell Type Properties

\| Type \| Stemness \| Division (1/h) \| Apoptosis (1/h) \| Lifespan \| Role \|

\|\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--\|

\| HSC \| 0.8 -- 1.0 \| 0.05 \| 0.025 \| Months \| Stem cell reservoir \|

\| MPP \| 0.4 -- 0.6 \| 0.10 \| 0.040 \| Days \| Multipotent transit \|

\| CMP \| 0.2 -- 0.3 \| 0.10 \| 0.040 \| Days \| Myeloid lineage \|

\| CLP \| 0.2 -- 0.3 \| 0.10 \| 0.040 \| Days \| Lymphoid lineage \|

\| Myeloid \| 0.0 -- 0.1 \| 0.00 \| 0.050 \| 1--2 days \| Immune defense \|

\| Erythroid \| 0.0 -- 0.1 \| 0.00 \| 0.050 \| 1--2 days \| Oxygen transport \|

\| B_cell \| 0.0 -- 0.05 \| 0.00 \| 0.020 \| Weeks \| Antibody production \|

\| T_cell \| 0.0 -- 0.05 \| 0.00 \| 0.020 \| Weeks \| Adaptive immunity \|

\*\*Legend:\*\*

\- \*\*Stemness (0--1):\*\* capacity for sustained self-renewal (1.0 = maximum, 0 = none)

\- \*\*Division rate:\*\* average divisions per hour

\- \*\*Apoptosis rate:\*\* average programmed death events per hour

\- \*\*Terminal cells\*\* (Myeloid, Erythroid, B/T cell) do \*\*not\*\* divide (Division = 0)

\-\--

\## 1.3 Division Fate

When an HSC divides, it probabilistically \"chooses\" one of three outcomes:

\| Division Type \| Probability \| Outcome \|

\|\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--\|

\| Self-renewal \| 82.5 % \| 1 HSC → 2 identical HSCs \*(pool grows by 1)\* \|

\| Asymmetric \| 12.5 % \| 1 HSC → 1 HSC + 1 MPP \*(one stays, one departs)\* \|

\| Commitment \| 5.0 % \| 1 HSC → 2 MPPs \*(both daughters differentiate)\* \|

\*\*Sum: 82.5% + 12.5% + 5.0% = 100% ✓\*\*

\- \*\*Self-renewal\*\* --- maintains the stem cell pool over time

\- \*\*Asymmetric\*\* --- balanced output: replenishes the pool while feeding downstream lineages

\- \*\*Commitment\*\* --- drives active differentiation; the HSC \"sacrifices\" itself for production

The fate is chosen stochastically at each division, making the system's behavior inherently variable across runs.

Progenitor cells (MPP, CMP, CLP) follow the same fate logic but with different default probabilities weighted toward commitment --- they are designed to differentiate, not self-renew. Their fate weights can be customised in the Advanced Settings under Division Fates.

\### Fate Outcomes for Progenitor Cells

\*\*MPP Division Fates:\*\*

\- \*\*Self-renewal:\*\* 1 MPP → 2 identical MPPs (pool grows by 1)

\- \*\*Asymmetric:\*\* 1 MPP → 1 MPP + 1 (CMP or CLP) --- probabilistically chosen 50/50

\- \*\*Commitment:\*\* 1 MPP → 2 CMPs or 2 CLPs --- probabilistically chosen to differentiate

\*\*CMP Division Fates:\*\*

\- \*\*Self-renewal:\*\* 1 CMP → 2 identical CMPs (pool grows by 1)

\- \*\*Asymmetric:\*\* 1 CMP → 1 CMP + 1 Myeloid (or Erythroid)

\- \*\*Commitment:\*\* 1 CMP → 2 Myeloid (or Erythroid) cells

\*\*CLP Division Fates:\*\*

\- \*\*Self-renewal:\*\* 1 CLP → 2 identical CLPs (pool grows by 1)

\- \*\*Asymmetric:\*\* 1 CLP → 1 CLP + 1 (B_cell or T_cell) --- probabilistically chosen 50/50

\- \*\*Commitment:\*\* 1 CLP → 2 B_cells or 2 T_cells --- probabilistically chosen

\*\*Key difference from HSC:\*\* Progenitors are weighted toward commitment (higher probability of differentiation) rather than self-renewal. This ensures rapid amplification of terminal cell types while limiting progenitor pool expansion.

The probabilities shown above are the default starting values. They can be adjusted in the Advanced Settings panel. Changing them shifts the balance between maintaining the stem cell pool and producing downstream lineages --- see Section 2.5 (Division Fates) for details.

→ See Section 2.5 (Division Fate Weights) for the full parameter reference and how to adjust these values in the simulator.

\-\--

\## 1.4 Key Concepts

\### STEMNESS

\`\`\`

Scale: 0.0 (fully mature) ◄────────────► 1.0 (fully stem)

├─ HSC (0.8--1.0) Long-lived, slow aging, high division capacity

├─ MPP (0.4--0.6) Several divisions, then disappear

└─ Terminal (0.0--0.1) No further division, rapid death

Affects → division rate, differentiation probability

Changes → inherited from parent cell or decreases with cell age

\`\`\`

\### STRESS

\`\`\`

Scale: 0.0 (fresh) ──────────────────► ∞ (heavily aged)

├─ Represents: accumulated damage from repeated divisions

├─ High stress → division rate ↓ (up to −60%, governed by w_div_stress in Advanced Settings → State Modulation)

├─ High stress → apoptosis rate ↑ (up to +60%, governed by w_apo_stress in Advanced Settings → State Modulation)

└─ Grows by: stress_accumulation_rate per hour (default 0.001)

→ See Section 2.4.2 (State Modulation) for the parameters that control how strongly stress affects division and apoptosis rates.

Meaning: models cellular aging and replicative exhaustion

\`\`\`

\### DIVISION FATE

\`\`\`

At each division, the cell stochastically \"decides\" its fate:

├─ Symmetric renewal → both daughters = parent type

├─ Asymmetric → one daughter = parent, one = new type

├─ Commitment → both daughters become progenitors

This choice regulates the long-term balance of the system.

\`\`\`

\-\--

\*End of Part 1 --- Hematopoiesis and Cell Hierarchy in the Model\*

\# Part 2.1: Core Simulation Parameters

\-\--

\## 2.1.1 Introduction

The six core parameters are located in the \*\*left panel\*\* of the simulator under \*\*Basic Settings\*\* --- they are the first controls you see at the top of the page. These parameters govern the fundamental behavior of the simulation. All remaining options are tucked away in the collapsible \*\*Advanced\*\* section and are optional.

\-\--

\## 2.1.2 Parameter Overview Table

\| \# \| Parameter \| Default \| Range \| UI Element \| What It Does \|

\|\-\--\|\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\--\|\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\-\--\|

\| 1 \| \*\*Seed\*\* \| \`0\` \| 0 -- 999 999 \| Text input \*(row 1)\* \| \`0\` = random seed (different results each run); any other number = fixed seed (reproducible results) \|

\| 2 \| \*\*Duration\*\* \*(hours)\* \| \`100 h\` \| 10 -- 1000 h, step 0.1 \| Text input + slider \*(row 2)\* \| Total simulation time in hours. Longer runs produce more data points and smoother curves. \|

\| 3 \| \*\*Target Population\*\* \| \`1000\` \| 100 -- 10 000 \| Text input + \*\*Enable toggle\*\* \*(row 3)\* \| Desired population size. \*\*Toggle ON\*\* → system self-regulates toward this number. \*\*Toggle OFF\*\* → population grows freely. \|

\| 4 \| \*\*Inheritance Mode\*\* \| \`Centriole\` \| 3 options \| Dropdown \*(row 4)\* \| How properties are passed from parent to daughter cells. Options: \*Centriole\*, \*Symmetric\*, \*Asymmetric\*. \|

\| 5 \| \*\*Stress Accumulation Rate\*\* \*(1/h)\* \| \`0.001\` \| 0.0 -- 0.01 \| Slider \*(row 5)\* \| Rate at which cells accumulate aging damage per hour. Higher values = faster cellular aging. \|

\| 6 \| \*\*Epigenetic Memory\*\* \| \`ON\` \| ON / OFF \| Toggle \*(row 6)\* \| Whether daughter cells inherit a \"memory\" of their parent\'s fate. ON = more stable lineages; OFF = fully random decisions. \|

\-\--

\## 2.1.3 Parameter Details

\#### Parameter 1 --- Seed

Controls the random number generator used throughout the simulation.

\- \*\*Seed = 0\*\* --- a new random seed is generated on every run, producing different outcomes each time. Use this to explore the typical range of system behavior.

\- \*\*Seed = 42\*\* (or any fixed number) --- the same sequence of random events is replayed on every run. Use this to reproduce and share a specific result.

\> 💡 \*Found an interesting run? Note the seed shown after simulation, set it here, and re-run to get the exact same outcome.\*

\-\--

\#### Parameter 2 --- Duration (hours)

Sets how many simulated hours the model runs.

\| Duration \| What You\'ll See \|

\|\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--\|

\| 10 h (min) \| Only the initial growth phase \|

\| 100 h (default) \| Full dynamics + equilibrium plateau \|

\| 1000 h (max) \| Long-term stability and aging effects \|

Longer durations also produce more chart data points, resulting in smoother plotted lines.

\-\--

\#### Parameter 3 --- Target Population

Defines the homeostatic population size the system tries to maintain.

\- The \*\*\"Enable Target Population\" toggle\*\* sits directly above the input field and must be \*\*ON\*\* for the value to take effect.

\- \*\*Toggle ON\*\* --- the density-based regulation module (M6.4) actively steers the population:

\- Below target → division rate increases

\- Above target → division rate decreases

\- \*\*Toggle OFF\*\* --- the target is ignored and the population grows exponentially without constraint.

Common values: \`100\` (small), \`1000\` (normal), \`5000\` (large).

\-\--

\#### Parameter 4 --- Inheritance Mode

Determines how a daughter cell inherits properties (stemness, fate bias) from its parent at division.

\| Mode \| Behavior \| Use When \|

\|\-\-\-\-\--\|\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\--\|

\| \*\*Centriole\*\* \*(default)\* \| Young centriole → high stemness; old centriole → low stemness. Biologically grounded. \| General use --- most realistic \|

\| \*\*Symmetric\*\* \| Both daughters are identical copies of the parent \| Simplified baseline runs \|

\| \*\*Asymmetric\*\* \| Explicit asymmetry: one daughter is \"old\", one is \"young\" \| Experimental / research \|

\-\--

\#### Parameter 5 --- Stress Accumulation Rate (1/h)

Controls how quickly cells accumulate replicative stress (aging damage) over time.

\| Rate \| Effect over 100 h \| Interpretation \|

\|\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--\|

\| \`0.000\` \| Stress stays at 0 \| Cells never age --- unrealistic \|

\| \`0.001\` \*(default)\* \| Stress ≈ 0.1 \| Slow, normal aging \|

\| \`0.005\` \| Stress ≈ 0.5 \| Accelerated aging --- degradation visible \|

\| \`0.010\` (max) \| Stress ≈ 1.0 \| Fast burnout --- system deteriorates \|

High stress → slower division rate (up to −60%) + faster apoptosis (up to +60%).

⚠️ \*\*Important note:\*\* The \`stress_accumulation_rate\` parameter also appears in Advanced Settings → Lifetime Dynamics (Section 2.4.5). \*\*Use only ONE location.\*\* The Basic Settings value here is recommended for most users --- it is simpler and more intuitive. Only change it in Lifetime Dynamics if you need to override this value for a specific experiment, but do not set both simultaneously.

\-\--

\#### Parameter 6 --- Epigenetic Memory

Enables or disables epigenetic inheritance of fate decisions.

\- \*\*ON (default)\*\* --- daughters carry a memory bias toward their parent\'s division fate, adding stability and lineage consistency. Fine-tunable via \`inheritance_noise\` and \`asymmetry_strength\` in the Advanced section.

\- \*\*OFF\*\* --- every fate decision is drawn purely at random, independently of the parent. Results in a simpler but noisier model.

\-\--

\## 2.1.4 Recommended Parameter Combinations

\#### Scenario 1 --- \"Normal Hematopoiesis\" (starting point)

\| Parameter \| Value \|

\|\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\--\|

\| Seed \| \`0\` \*(random)\* \|

\| Duration \| \`100 h\` \|

\| Target Population \| \`1000\`, Enable = \*\*ON\*\* \|

\| Inheritance Mode \| \`Centriole\` \|

\| Stress Rate \| \`0.001\` \|

\| Epigenetic Memory \| \*\*ON\*\* \|

\*\*Expected result:\*\* system reaches a stable equilibrium around 1 000 cells.

\-\--

\#### Scenario 2 --- \"Reproducible Run\"

\| Parameter \| Value \|

\|\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\--\|

\| Seed \| \`42\` \*(or any fixed number)\* \|

\| All others \| Same as Scenario 1 \|

\*\*Expected result:\*\* identical output on every run --- useful for sharing or debugging.

\-\--

\#### Scenario 3 --- \"Studying Cellular Aging\"

\| Parameter \| Value \|

\|\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\--\|

\| Seed \| \`0\` \|

\| Duration \| \`200 h\` \*(longer to see the effect)\* \|

\| Stress Rate \| \`0.005\` \*(above default)\* \|

\| All others \| Default \|

\*\*Expected result:\*\* visible population degradation over time as stress accumulates.

\-\--

\#### Scenario 4 --- \"Unconstrained Growth\"

\| Parameter \| Value \|

\|\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\--\|

\| Target Population \| Enable = \*\*OFF\*\* \|

\| All others \| Default \|

\*\*Expected result:\*\* exponential growth with no homeostatic ceiling.

\-\--

\*End of Part 2.1 --- Core Simulation Parameters\*

\# Part 2.2: Control Mechanisms (Advanced Parameters)

\-\--

\## 2.2.1 Introduction

The \*\*Advanced Settings\*\* panel contains three key regulatory mechanisms that govern system homeostasis. Each mechanism can be independently enabled or disabled with its own toggle, and its behavior can be fine-tuned via dedicated sliders. Together they form a layered control system that keeps the cell population stable and biologically realistic.

\-\--

\## 2.2.2 Mechanisms Overview

\| Mechanism \| Default \| UI Type \| Location in UI \| What It Does \|

\|\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\-\--\|

\| \*\*Population Regulation\*\* (M6.4) \| γ = 4.0, β = 0.0 \| Toggle + 2 sliders \| Advanced → \"📊 Population Regulation\" \| Primary homeostatic regulator --- speeds up or slows down division based on current vs. target population \|

\| \*\*Niche Modulation\*\* (M6.2) \| k = 4.0 \| Toggle + 1 slider \| Advanced → \"🎯 Niche Modulation\" \| Suppresses commitment (differentiation) when HSCs are scarce, protecting the stem cell pool \|

\| \*\*Crowding Apoptosis\*\* (M4) \| threshold = 1.3, rate = 0.1 \| Toggle + 2 sliders \| Advanced → \"🚨 Crowding Apoptosis\" \| Safety valve --- triggers enhanced apoptosis if population exceeds the crowding threshold \|

\-\--

\## 2.2.3 Mechanism 1 --- Population Regulation (M6.4)

\*\*What it is:\*\* The primary homeostatic regulator. It continuously compares current cell count to the Target Population and adjusts division rates accordingly.

\*\*How it works:\*\*

\- Current \< target → division accelerates (system grows toward target)

\- Current = target → no change (system is balanced)

\- Current \> target → division decelerates (system contracts toward target)

\*\*Formula:\*\*

\`\`\`

density_factor = exp(γ × (target − current) / target)

effective_division_rate = base_rate × density_factor

\`\`\`

\*\*Worked examples\*\* (target = 1000, γ = 4.0):

\| Scenario \| Current \| Ratio \| density_factor \| Effect \|

\|\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\--\|\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\--\|

\| Deficit \| 500 \| +0.5 \| exp(2.0) ≈ \*\*7.4×\*\* \| Division accelerates 7.4× \|

\| Balanced \| 1000 \| 0 \| exp(0) = \*\*1.0×\*\* \| No change \|

\| Overcrowded \| 1500 \| −0.5 \| exp(−2.0) ≈ \*\*0.14×\*\* \| Division slows to \~14% of normal \|

\*\*Parameters:\*\*

\*\`density_gamma\` (γ)\*

\| Value \| Effect \|

\|\-\-\-\-\-\--\|\-\-\-\-\-\-\--\|

\| \`0\` \| No regulation --- factor is always 1.0 \|

\| \`4.0\` \*(default)\* \| Moderate sensitivity --- recommended \|

\| \`10\` \| High sensitivity --- very fast recovery \|

\*\`density_beta\` (β)\* --- Default \`0.0\`. Secondary dampening term; leave at default.

\*\*Why it matters:\*\* Without M6.4, the system grows unconstrained. With it, the population naturally converges to the target from any starting point, mimicking the feedback loops present in real bone marrow.

\-\--

\## 2.2.4 Mechanism 2 --- Niche Modulation (M6.2)

\*\*What it is:\*\* A signal from the bone marrow microenvironment (the \"niche\") that suppresses HSC commitment when the stem cell pool is depleted.

\*\*How it works:\*\*

\- When cell count is low → niche signal is strong → commitment probability is suppressed → HSCs are preserved

\- When cell count is normal → niche signal is neutral → commitment proceeds as usual

\- When cell count is high → niche signal may promote commitment → differentiation is encouraged

\*\*Formula:\*\*

\`\`\`

niche_signal = (target − current) / target

modifier_commitment = exp(−k × niche_signal × stemness)

p_commitment ×= modifier_commitment

\`\`\`

\*\*Worked examples\*\* (target = 1000, k = 4.0, stemness = 0.8):

\| Scenario \| Current \| niche_signal \| modifier \| Effect on commitment \|

\|\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--\|

\| Low HSC \| 500 \| +0.5 \| exp(−1.6) ≈ \*\*0.20\*\* \| Commitment probability reduced to 20% of baseline (80% suppression) --- HSCs preserved \|

\| Normal \| 1000 \| 0 \| exp(0) = \*\*1.0\*\* \| No change \|

\| Overcrowded \| 1500 \| −0.5 \| exp(+1.6) ≈ \*\*4.95\*\* \| Commitment promoted (capped internally) \|

\*\*Parameter:\*\*

\*\`niche_strength\` (k)\*

\| Value \| Effect \|

\|\-\-\-\-\-\--\|\-\-\-\-\-\-\--\|

\| \`0\` \| Niche has no influence --- commitment always proceeds freely \|

\| \`4.0\` \*(default)\* \| Good HSC protection --- recommended \|

\| \`10\` \| Very strong niche --- very hard to lose HSCs \|

\*\*Why it matters:\*\* The niche is a well-documented biological reality (osteoblasts, megakaryocytes, and endothelial cells all participate). Toggling M6.2 off lets you study what happens to the HSC pool in a \"niche-free\" environment.

\-\--

\## 2.2.5 Mechanism 3 --- Crowding Apoptosis (M4)

\*\*What it is:\*\* A safety valve that activates only when the population significantly exceeds the target --- a last-resort mechanism in case M6.4 and M6.2 are insufficient.

\*\*How it works:\*\*

\- While population ≤ threshold × target → M4 is silent

\- Once population \> threshold × target → extra apoptosis rate is added to all cells

\*\*Formula:\*\*

\`\`\`

if (current / target) \> crowding_threshold:

apoptosis_rate += crowding_apoptosis_rate

else:

no extra apoptosis

\`\`\`

\*\*Worked examples\*\* (target = 1000, threshold = 1.3, rate = 0.1):

\| Scenario \| Current \| Ratio \| M4 active? \| Effect \|

\|\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\--\|\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\--\|

\| Normal \| 1000 \| 1.0 \| ❌ No \| Standard apoptosis only \|

\| At threshold \| 1300 \| 1.3 \| ✅ Yes \| +0.1/h apoptosis added \|

\| Out of control \| 2000 \| 2.0 \| ✅ Yes \| +0.1/h --- rapid population decline \|

\*\*Parameters:\*\*

\*\`crowding_threshold\`\*

\| Value \| Triggers at \| Sensitivity \|

\|\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\--\|

\| \`1.0\` \| 100% of target \| Immediate --- very tight \|

\| \`1.3\` \*(default)\* \| 130% of target \| Normal tolerance \|

\| \`2.0\` \| 200% of target \| Only extreme overcrowding \|

\| \`3.0\` \| 300% of target \| Rarely triggers \|

\*\`crowding_apoptosis_rate\`\*

\| Value \| Effect \|

\|\-\-\-\-\-\--\|\-\-\-\-\-\-\--\|

\| \`0.0\` \| M4 has no effect even when triggered \|

\| \`0.1\` \*(default)\* \| Moderate extra apoptosis \|

\| \`0.5\` \| Aggressive --- population drops fast \|

\| \`1.0\` \| Extreme --- near-collapse response \|

\*\*Why it matters:\*\* Acts as a biological analog to contact inhibition. Guarantees the simulation cannot produce runaway exponential growth regardless of other parameter settings.

\-\--

\## 2.2.6 How All Three Work Together

The three mechanisms form a \*\*three-layer defense system:\*\*

\`\`\`

LAYER 1 --- Population Regulation (M6.4) \[Primary regulator\]

└─ Watches total population size

└─ Accelerates / decelerates division continuously

└─ Keeps system near target at all times

LAYER 2 --- Niche Modulation (M6.2) \[HSC guardian\]

└─ Watches HSC availability

└─ Suppresses commitment when HSCs are scarce

└─ Accelerates recovery by preserving the stem cell reservoir

LAYER 3 --- Crowding Apoptosis (M4) \[Emergency brake\]

└─ Dormant under normal conditions

└─ Activates only above crowding threshold

└─ Hard ceiling --- guarantees no population explosion

\`\`\`

\*\*Example: Recovery after 90% depletion\*\* (target = 1000)

\| Time \| Population \| M6.4 response \| M6.2 response \| M4 \|

\|\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\-\-\--\|\-\-\-\--\|

\| t = 0 h \| 100 \| density_factor ≈ 37× --- division accelerates \~37× --- rapid recovery begins \| niche_signal = 0.9 → commitment suppressed \~5× \| Dormant \|

\| t = 50 h \| 800 \| density_factor ≈ 1.2 --- gently accelerating \| niche_signal = 0.2 → commitment nearly normal \| Dormant \|

\| t = 100 h \| 1000 \| density_factor = 1.0 --- balanced \| niche_signal = 0 → normal \| Dormant \|

\*\*Result:\*\* Full recovery in \~100 hours. ✓

\-\--

\## 2.2.7 Recommended Combinations

\#### Scenario 1 --- \"Normal System\" \*(default --- recommended starting point)\*

\| Mechanism \| Setting \|

\|\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\--\|

\| Population Regulation \| ON, γ = 4.0 \|

\| Niche Modulation \| ON, k = 4.0 \|

\| Crowding Apoptosis \| ON, threshold = 1.3, rate = 0.1 \|

\*\*Expected result:\*\* Stable, realistic hematopoiesis with natural equilibrium.

\-\--

\#### Scenario 2 --- \"No Regulation\" \*(uncontrolled baseline)\*

\| Mechanism \| Setting \|

\|\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\--\|

\| Population Regulation \| OFF (γ = 0) \|

\| Niche Modulation \| OFF (k = 0) \|

\| Crowding Apoptosis \| OFF (rate = 0) \|

\*\*Expected result:\*\* Exponential, unconstrained growth --- useful as a control condition.

\-\--

\#### Scenario 3 --- \"Regulation Without Niche\" \*(HSC-depleting run)\*

\| Mechanism \| Setting \|

\|\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\--\|

\| Population Regulation \| ON, γ = 4.0 \|

\| Niche Modulation \| OFF (k = 0) \|

\| Crowding Apoptosis \| ON, rate = 0.1 \|

\*\*Expected result:\*\* Population size is controlled, but HSCs differentiate more aggressively and the stem cell pool shrinks over time.

\-\--

\#### Scenario 4 --- \"Hard Mode\" \*(maximum stability)\*

\| Mechanism \| Setting \|

\|\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\--\|

\| Population Regulation \| ON, γ = 10.0 \|

\| Niche Modulation \| ON, k = 10.0 \|

\| Crowding Apoptosis \| ON, threshold = 1.0, rate = 0.5 \|

\*\*Expected result:\*\* Extremely stable system --- very difficult to perturb. Good for stress-testing the model.

\-\--

\#### Scenario 5 --- \"Fast Recovery\" \*(post-depletion resilience)\*

\| Mechanism \| Setting \|

\|\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\--\|

\| Population Regulation \| ON, γ = 8.0 \|

\| Niche Modulation \| ON, k = 6.0 \|

\| Crowding Apoptosis \| ON, threshold = 1.2, rate = 0.2 \|

\*\*Expected result:\*\* Rapid rebound after a population drop --- useful for studying bone marrow recovery dynamics.

\-\--

\*End of Part 2.2 --- Control Mechanisms\*

\# Part 2.3: Division & Apoptosis Rates

\-\--

\## 2.3.1 Introduction

Every cell type has its own division rate (how often it divides) and apoptosis rate (how quickly it dies). By default the simulator uses values are pre-calibrated and represent the recommended defaults. These can be overridden in \*\*Advanced Settings\*\* by enabling the \*\*\"Use custom division rates\"\*\* and \*\*\"Use custom apoptosis rates\"\*\* toggles --- useful for research and sensitivity analysis, but leave them off unless you have a specific reason to change them.

\-\--

\## 2.3.2 Full Rate Table

\| Cell Type \| Division Rate (1/h) \| Avg. interval \| Apoptosis Rate (1/h) \| Avg. interval \| Approximate lifespan \| Notes \|

\|\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\--\|

\| \*\*HSC\*\* \| 0.05 \| 1 div / 20 h \| 0.025 \| 1 death / 40 h \| Months \| Long-lived stem cells \|

\| \*\*MPP\*\* \| 0.10 \| 1 div / 10 h \| 0.040 \| 1 death / 25 h \| Days \| A few divisions, then gone \|

\| \*\*CMP\*\* \| 0.10 \| 1 div / 10 h \| 0.040 \| 1 death / 25 h \| Days \| Myeloid-committed progenitor \|

\| \*\*CLP\*\* \| 0.10 \| 1 div / 10 h \| 0.040 \| 1 death / 25 h \| Days \| Lymphoid-committed progenitor \|

\| \*\*Myeloid\*\* \| \*\*0.00\*\* \| ⛔ Never \| 0.050 \| 1 death / 20 h \| 1--2 days \| Terminal --- does not divide \|

\| \*\*Erythroid\*\* \| \*\*0.00\*\* \| ⛔ Never \| 0.050 \| 1 death / 20 h \| 1--2 days \| Terminal --- does not divide \|

\| \*\*B_cell\*\* \| \*\*0.00\*\* \| ⛔ Never \| 0.020 \| 1 death / 50 h \| Weeks \| Terminal --- longest-lived terminal \|

\| \*\*T_cell\*\* \| \*\*0.00\*\* \| ⛔ Never \| 0.020 \| 1 death / 50 h \| Weeks \| Terminal --- longest-lived terminal \|

\> ⚠️ \*\*Terminal cells (Myeloid, Erythroid, B_cell, T_cell) never divide.\*\* Their division rate is locked at 0.00 and cannot be modified in the UI.

\-\--

\## 2.3.3 Interpreting the Rates

\*\*Unit:\*\* \`\[1/h\]\` = events per hour. The mean time between events = \`1 ÷ rate\`.

\| Rate \| Mean interval \| Interpretation \|

\|\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--\|

\| 0.05 \| 20 h \| One event every \~20 hours \|

\| 0.10 \| 10 h \| One event every \~10 hours \|

\| 0.020 \| 50 h \| One event every \~50 hours \|

\| 0.050 \| 20 h \| One event every \~20 hours \|

\*\*Per cell type:\*\*

\*\*HSC\*\* (div = 0.05, apo = 0.025) --- Divides slowly (every 20 h), dies even more slowly (every 40 h). Net effect: HSCs accumulate over time and persist for months. Their purpose is long-term reservoir maintenance.

\*\*MPP / CMP / CLP\*\* (div = 0.10, apo = 0.040) --- Divide twice as fast as HSCs. They undergo a few rounds of division before differentiating or dying. Purpose: rapid amplification of the downstream lineages.

\*\*Myeloid / Erythroid\*\* (div = 0.00, apo = 0.050) --- Terminally differentiated; they never divide. They die every \~20 hours, so the system must continuously replenish them via progenitors. High turnover, short service life.

\*\*B_cell / T_cell\*\* (div = 0.00, apo = 0.020) --- Also terminally differentiated, but die more slowly (every \~50 h). They persist for weeks, providing sustained immune coverage with lower replacement demand.

\-\--

\## 2.3.4 Location in UI & How to Modify

\*\*Division rates:\*\*

\`\`\`

Advanced Settings → \"⚡ Division Rates\"

├─ Toggle: \"Use custom division rates\" \[default: OFF\]

│ OFF → model uses calibrated defaults (recommended)

│ ON → sliders appear for each dividing cell type

└─ Sliders (visible when ON):

HSC : 0.01 -- 0.20 \[1/h\]

MPP : 0.05 -- 0.30 \[1/h\]

CMP : 0.05 -- 0.30 \[1/h\]

CLP : 0.05 -- 0.30 \[1/h\]

Terminal cells: NOT shown (locked at 0.00)

\`\`\`

\*\*Apoptosis rates:\*\*

\`\`\`

Advanced Settings → \"💀 Apoptosis Rates\"

├─ Toggle: \"Use custom apoptosis rates\" \[default: OFF\]

│ OFF → model uses calibrated defaults (recommended)

│ ON → sliders appear for all 8 cell types

└─ Sliders (visible when ON):

HSC : 0.01 -- 0.10 \[1/h\]

MPP : 0.01 -- 0.15 \[1/h\]

CMP : 0.01 -- 0.15 \[1/h\]

CLP : 0.01 -- 0.15 \[1/h\]

Myeloid : 0.01 -- 0.15 \[1/h\]

Erythroid: 0.01 -- 0.15 \[1/h\]

B_cell : 0.01 -- 0.10 \[1/h\]

T_cell : 0.01 -- 0.10 \[1/h\]

\`\`\`

\*\*When to change rates:\*\*

\| Situation \| Recommendation \|

\|\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\-\-\--\|

\| Normal simulation \| Leave at defaults --- values are pre-calibrated and represent the recommended defaults \|

\| Sensitivity analysis \| Change one parameter at a time and note results \|

\| Modeling a disease state \| Adjust specific rates to reflect the condition \|

\| Comparing lineages \| Use asymmetric rates between CMP and CLP \|

\> 🔴 \*\*Caution:\*\* Changing rates affects the entire system. Always document what you changed so results can be reproduced (use a fixed Seed).

\-\--

\## 2.3.5 Change Examples & Expected Effects

\#### Example 1 --- Increase HSC division rate (faster stem cell cycling)

\| \| Before \| After \|

\|\--\|\-\-\-\-\-\-\--\|\-\-\-\-\-\--\|

\| HSC division \| 0.05 (1 div / 20 h) \| \*\*0.10\*\* (1 div / 10 h) \|

\*\*Effect:\*\* HSCs divide twice as fast → the HSC pool grows larger → downstream progenitors receive more input → overall population grows faster and at a higher plateau. On the population chart: steeper initial slope.

\-\--

\#### Example 2 --- Increase apoptosis rate of terminal cells (higher turnover)

\| \| Before \| After \|

\|\--\|\-\-\-\-\-\-\--\|\-\-\-\-\-\--\|

\| Myeloid apoptosis \| 0.050 (live \~20 h) \| \*\*0.10\*\* (live \~10 h) \|

\| Erythroid apoptosis \| 0.050 (live \~20 h) \| \*\*0.10\*\* (live \~10 h) \|

\*\*Effect:\*\* Myeloid and erythroid cells die twice as fast → constant deficit of terminal cells → M6.4 detects deficit and accelerates CMP division to compensate → on the cell-type composition chart: Myeloid and Erythroid bands narrow, CMP band widens.

\-\--

\#### Example 3 --- Decrease MPP division rate (progenitor bottleneck)

\| \| Before \| After \|

\|\--\|\-\-\-\-\-\-\--\|\-\-\-\-\-\--\|

\| MPP division \| 0.10 (1 div / 10 h) \| \*\*0.05\*\* (1 div / 20 h) \|

\*\*Effect:\*\* MPPs amplify more slowly → CMP and CLP receive fewer cells → all terminal lineages become deficient → total population drops toward a lower equilibrium. On the population chart: lower steady-state plateau; terminal cell counts decline progressively.

\-\--

\## 2.3.6 Recommended Scenarios

\#### Scenario 1 --- \"Calibrated Default\" \*(recommended)\*

All rates at table defaults. System reaches a stable, realistic equilibrium.

\-\--

\#### Scenario 2 --- \"Fast Growth\"

\| Parameter \| Change \|

\|\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\--\|

\| HSC division \| 0.05 → \*\*0.10\*\* \|

\| MPP division \| 0.10 → \*\*0.15\*\* \|

\| CMP division \| 0.10 → \*\*0.15\*\* \|

\| CLP division \| 0.10 → \*\*0.15\*\* \|

\*\*Result:\*\* System grows rapidly and stabilizes at a larger population.

\-\--

\#### Scenario 3 --- \"HSC Exhaustion\"

\| Parameter \| Change \|

\|\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\--\|

\| HSC division \| 0.05 → \*\*0.02\*\* \|

\*\*Result:\*\* HSC pool depletes gradually; the system becomes unstable as progenitor input decreases over time.

\-\--

\#### Scenario 4 --- \"High Demand\" \*(elevated terminal turnover)\*

\| Parameter \| Change \|

\|\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\--\|

\| Myeloid apoptosis \| 0.050 → \*\*0.10\*\* \|

\| Erythroid apoptosis \| 0.050 → \*\*0.10\*\* \|

\*\*Result:\*\* Short-lived terminal cells require twice the production rate; progenitor activity increases to compensate.

\-\--

\#### Scenario 5 --- \"Long-lived Immune Cells\"

\| Parameter \| Change \|

\|\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\--\|

\| B_cell apoptosis \| 0.020 → \*\*0.010\*\* \|

\| T_cell apoptosis \| 0.020 → \*\*0.010\*\* \|

\*\*Result:\*\* B and T cells persist twice as long and accumulate steadily; their share of the composition chart expands over time.

\-\--

\#### Scenario 6 --- \"Asymmetric Lineages\" \*(research)\*

\| Parameter \| Change \|

\|\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\--\|

\| CMP division \| 0.10 → \*\*0.05\*\* \|

\| CLP division \| 0.10 → \*\*0.15\*\* \|

\*\*Result:\*\* Myeloid lineage is slower, lymphoid lineage is faster --- the cell-type balance shifts toward B/T cells, useful for studying lineage competition.

\-\--

\*End of Part 2.3 --- Division & Apoptosis Rates\*

\# Part 2.4: Additional Advanced Parameters

\-\--

\## 2.4.1 Introduction

Beyond division rates, apoptosis rates, and control mechanisms, there are four more Advanced parameter groups that govern how a cell\'s internal state (stemness, stress) influences its behavior. These are intended for experienced users. All four are \*\*OFF by default\*\*, and the pre-calibrated values are applied automatically --- leave them off unless you have a specific research question in mind.

\-\--

\## 2.4.2 State Modulation

\*\*Location:\*\* Advanced Settings → \"📈 State Modulation\"

\*\*Toggle:\*\* \"Customize state modulation\" \*(default: OFF)\*

When \*\*ON\*\*, seven sliders appear that control how stemness and accumulated stress modify division and apoptosis rates.

\| Parameter \| Default \| Range \| What It Controls \|

\|\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\--\|\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--\|

\| \`w_div_stemness\` \| 1.0 \| 0 -- 5 \| How strongly stemness \*\*accelerates\*\* division. \`0\` = no effect; \`1\` = moderate; \`5\` = very strong \|

\| \`w_div_stress\` \| 0.25 \| 0 -- 1 \| How strongly stress \*\*slows\*\* division. \`0\` = stress has no effect; \`1\` = very strong slowdown \|

\| \`w_apo_stress\` \| 1.0 \| 0 -- 5 \| How strongly stress \*\*accelerates\*\* apoptosis. \`0\` = no effect; \`1\` = moderate; \`5\` = very strong \|

\| \`min_factor\` \| 0.1 \| 0.01 -- 0.5 \| Floor multiplier --- rate can never fall below \`base × 0.1\`. Prevents population collapse \|

\| \`max_factor\` \| 5.0 \| 2 -- 20 \| Ceiling multiplier --- rate can never rise above \`base × 5.0\`. Prevents runaway growth \|

\| \`w_div_repl\` \| 0.005 \| 0 -- 0.05 \| How cumulative division count \*\*slows\*\* further division \*(optional; rarely changed)\* \|

\| \`w_apo_repl\` \| 0.005 \| 0 -- 0.05 \| How cumulative division count \*\*accelerates\*\* apoptosis \*(optional; rarely changed)\* \|

\*\*How it works:\*\*

\`\`\`

Division modifier = exp( w_div_stemness × stemness ) × exp( −w_div_stress × stress )

Apoptosis modifier = exp( w_apo_stress × stress )

Both modifiers are clamped to \[min_factor, max_factor\]

\`\`\`

\*Example --- HSC with stemness = 0.9, stress = 0.5 (defaults):\*

\- Division modifier = exp(1.0 × 0.9) × exp(−0.25 × 0.5) ≈ 2.46 × 0.88 ≈ \*\*2.16×\*\*

\- Apoptosis modifier = exp(1.0 × 0.5) ≈ \*\*1.65×\*\*

\- \*\*Clamping:\*\* 2.16× is within \[min=0.1×, max=5.0×\], so no adjustment applied.

\- \*\*Final rates:\*\* Division ×2.16, Apoptosis ×1.65

\*Example with high stress --- HSC with stemness = 0.9, stress = 2.0:\*

\- Division modifier = exp(1.0 × 0.9) × exp(−0.25 × 2.0) ≈ 2.46 × 0.61 ≈ \*\*1.50×\*\*

\- Apoptosis modifier = exp(1.0 × 2.0) ≈ 7.39× (but clamped to max=5.0×)

\- \*\*Clamping:\*\* Apoptosis 7.39× exceeds \[max=5.0×\], so clamped downward.

\- \*\*Final rates:\*\* Division ×1.50, Apoptosis ×5.0 (capped)

This demonstrates why the clamps (min_factor, max_factor) are essential --- they prevent extreme cellular behavior from overwhelming the system.

\*\*When to change:\*\* Leave OFF for normal use. Enable to investigate questions like \*\"What if stress had no effect on division?\"\* (set \`w_div_stress = 0\`) or \*\"What if stemness is less important?\"\* (lower \`w_div_stemness\`).

\-\--

\## 2.4.3 Inheritance Details

\*\*Location:\*\* Advanced Settings → \"🧬 Inheritance Details\"

\*\*Toggle:\*\* \"Customize inheritance\" \*(default: OFF)\*

The parameters shown depend on the \*\*Inheritance Mode\*\* selected in Basic Settings.

\-\--

\*\*Mode: Centriole\*\* \*(default --- recommended)\*

\| Parameter \| Default \| Range \| Meaning \|

\|\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\--\|\-\-\-\-\-\--\|\-\-\-\-\-\-\-\--\|

\| \`centriole_stemness_factor\` \| 0.015 \| 0 -- 0.05 \| Rate at which stemness decreases with centriole age. Higher = stronger age effect \|

\| \`centriole_age_cap\` \| 10 \| 1 -- 50 \| Maximum centriole age. Above this cap, stemness stabilizes \|

\| \`centriole_stress_factor\` \| 0.01 \| 0 -- 0.05 \| Rate at which stress increases with centriole age \|

\*How it works:\* At each division, one daughter receives the old centriole (lower stemness) and the other receives a new one (higher stemness). Asymmetry emerges naturally from this mechanism without requiring explicit rules.

This mechanism is the primary reason the Centriole mode produces more realistic asymmetry than the Asymmetric mode without requiring manual parameter tuning.

\-\--

\*\*Mode: Symmetric\*\*

No additional parameters. Both daughters inherit identical copies of all parent properties.

\-\--

\*\*Mode: Asymmetric\*\*

\| Parameter \| Default \| Range \| Meaning \|

\|\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\--\|\-\-\-\-\-\--\|\-\-\-\-\-\-\-\--\|

\| \`stemness_asymmetry\` \| 0.2 \| 0 -- 1 \| Stemness difference between the two daughters (\~one gets +0.2, the other −0.2) \|

\| \`stress_asymmetry\` \| 0.1 \| 0 -- 1 \| Stress difference between the two daughters \|

\*How it works:\* Asymmetry is applied explicitly at every division. One daughter is \"young\" (high stemness, low stress), the other is \"old\" (low stemness, high stress). Biologically motivated but can produce instability at high values.

\-\--

\## 2.4.4 Epigenetic Details

\*\*Location:\*\* Advanced Settings → \"📊 Epigenetic Details\"

\*\*Visibility:\*\* \*Only available when Epigenetic Memory = ON in Basic Settings\*

\*\*Toggle:\*\* \"Customize epigenetics\" \*(default: OFF)\*

Epigenetic memory is a core stability mechanism: without it, every fate decision is independent of the parent's history, producing a noisier and less predictable system.

\| Parameter \| Default \| Range \| What It Controls \|

\|\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\--\|\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--\|

\| \`inheritance_noise\` \| 0.02 \| 0 -- 0.2 \| Random variation added when passing fate bias to daughters. \`0\` = perfect copy; \`0.02\` = slight noise; \`0.2\` = nearly random \|

\| \`asymmetry_strength\` \| 0.02 \| 0 -- 0.1 \| Size of the epigenetic bias shift between daughters. \`0\` = identical; \`0.1\` = strong divergence \|

\| \`drift_rate\` \| 0.0005 \| 0 -- 0.001 \| Speed at which epigenetic memory fades toward a neutral state over time. \`0\` = permanent memory; \`0.001\` = fades over \~1 000 h \|

\*\*How it works:\*\* When a cell divides, daughters inherit a probabilistic bias toward the parent\'s last fate choice (self-renewal or commitment). This bias:

\- Is passed with some noise (\`inheritance_noise\`)

\- Can differ slightly between the two daughters (\`asymmetry_strength\`)

\- Gradually erodes toward neutrality over time (\`drift_rate\`)

\*\*When to change:\*\*

\| Goal \| Adjustment \|

\|\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\--\|

\| Study a world without epigenetic memory \| Set \`drift_rate = 0.01\` (memory fades quickly) \|

\| Study permanent epigenetic locking \| Set \`drift_rate = 0\` \|

\| More heritable fate decisions \| Lower \`inheritance_noise\` toward 0 \|

\| More random, noisy inheritance \| Raise \`inheritance_noise\` toward 0.2 \|

\-\--

\## 2.4.5 Lifetime Dynamics

\*\*Location:\*\* Advanced Settings → \"⏳ Lifetime Dynamics\"

\*\*Toggle:\*\* \"Customize lifetime evolution\" \*(default: OFF)\*

\| Parameter \| Default \| Range \| What It Controls \|

\|\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\--\|\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--\|

\| \`stress_accumulation_rate\` \| 0.001 \| 0 -- 0.01 \| Per-hour stress accumulation (overrides the Basic Settings value if set here) \|

\| \`stemness_drift_rate\` \| 0.0 \| 0 -- 0.001 \| Rate at which stemness passively declines over time, independent of division. Default \`0\` = disabled \|

\*\*Notes:\*\*

⚠️ \*\*Warning:\*\* The \`stress_accumulation_rate\` parameter here \*\*overrides\*\* the Basic Settings value if both are set. This is intended for advanced users who want to explore the same scenario with different stress profiles. \*\*Most users should set stress_accumulation_rate in Basic Settings (Section 2.1.3) only.\*\*

\- \`stemness_drift_rate\` is disabled by default. If you want stemness to erode over time without relying on epigenetic inheritance, you can activate it here --- but in most cases the centriole-based or epigenetic mechanisms already handle this more realistically.

\-\--

\## 2.4.6 Quick Reference Summary

\### Parameter importance at a glance

\| Group \| Importance \| Typical Use \|

\|\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\--\|

\| Control Mechanisms (M6.4, M6.2, M4) \| 🔴 High \| Keep ON --- core homeostasis \|

\| Division Fates (2.5) \| 🔴 High \| Change to study self-renewal vs. commitment balance --- direct control over HSC pool stability \|

\| Division Rates \| 🟡 Medium \| Change for sensitivity analysis only \|

\| Apoptosis Rates \| 🟡 Medium \| Change for sensitivity analysis only \|

\| Inheritance Details \| 🟡 Medium \| Depends on chosen Inheritance Mode \|

\| State Modulation \| 🟢 Low \| Specialized; defaults are well calibrated \|

\| Epigenetic Details \| 🟢 Low \| Fine-tuning only; defaults are stable \|

\| Lifetime Dynamics \| 🟢 Low \| Rarely needed; stress handled in Basic Settings \|

\-\--

\### Recipe for beginners

\`\`\`

Basic Settings → all defaults

Control Mechanisms → all ON (M6.4, M6.2, M4)

Division Rates → OFF (use defaults)

Apoptosis Rates → OFF (use defaults)

Division Fates → OFF (or ON if you want to adjust fate balance)

State Modulation → OFF

Inheritance Details → OFF (Centriole mode handles this automatically)

Epigenetic Details → OFF (even if Epigenetic Memory = ON)

Lifetime Dynamics → OFF

\`\`\`

\*\*Result:\*\* A stable, realistic, well-calibrated simulation. ✓

\-\--

\### Recipe for advanced users

\- Enable \*\*State Modulation\*\* to probe how strongly stemness and stress drive behavior

\- Enable \*\*Inheritance Details\*\* to study centriole aging or explicit asymmetry

\- Enable \*\*Epigenetic Details\*\* to test scenarios where memory is permanent, absent, or noisy

\- Always record what you changed and use a fixed \*\*Seed\*\* so results are reproducible

\- Change \*\*one parameter group at a time\*\* --- changing several simultaneously makes it hard to attribute observed effects

\-\--

\*End of Part 2.4 --- Additional Advanced Parameters\*

\-\--

\## 2.5 Division Fate Weights

\### 2.5.1 Introduction

Division fate weights are the probabilities that determine what happens when a cell divides. They are the most direct lever for controlling the long-term balance of the system: too much self-renewal and progenitors accumulate; too much commitment and the stem cell pool depletes.

Location in UI: Advanced Settings → \"⚖ Division Fates\"

Toggle: \"Use custom fate weights\" (default: OFF)

When ON: sliders appear for each dividing cell type.

\### 2.5.2 The Three Fate Outcomes

\| Fate \| Symbol \| What happens at division \|

\|\-\--\|\-\--\|\-\--\|

\| Self-renewal \| SR \| Both daughter cells are the same type as the parent. The pool grows by one cell. \|

\| Asymmetric \| AS \| One daughter stays the same type; the other becomes the next type down the differentiation tree. Pool size is maintained. \|

\| Commitment \| CO \| Both daughters become the next type down the tree. The parent type loses one cell. \|

The three probabilities must always sum to 100%. The simulator enforces this automatically --- adjusting one slider rescales the others proportionally.

\### 2.5.3 Default Fate Weights by Cell Type

\| Cell type \| Self-renewal % \| Asymmetric % \| Commitment % \| Bias \|

\|\-\--\|\-\--\|\-\--\|\-\--\|\-\--\|

\| HSC \| 82.5 \| 12.5 \| 5.0 \| Strong self-renewal \|

\| MPP \| 50.0 \| 30.0 \| 20.0 \| Balanced \|

\| CMP \| 30.0 \| 40.0 \| 30.0 \| Commitment-leaning \|

\| CLP \| 30.0 \| 40.0 \| 30.0 \| Commitment-leaning \|

Terminal cells (Myeloid, Erythroid, B_cell, T_cell) do not divide and have no fate weights.

Note: the percentages for MPP, CMP, and CLP above are representative defaults. Verify the exact values displayed in your simulator\'s interface, as they may differ from those shown here.

\### 2.5.4 How Changing Fate Weights Affects the System

\| Change \| Immediate effect \| Long-term effect \|

\|\-\--\|\-\--\|\-\--\|

\| Increase HSC self-renewal \| More HSC--HSC divisions \| HSC pool grows; downstream lineages may shrink temporarily \|

\| Increase HSC commitment \| Fewer HSC retained \| HSC pool depletes; downstream lineages expand briefly, then collapse \|

\| Increase MPP asymmetric \| More MPP→CMP/CLP output \| Faster production of terminal cells \|

\| Increase CMP commitment \| Faster Myeloid/Erythroid production \| CMP pool shrinks; burst of terminal output followed by deficit \|

\*\*Rule of thumb:\*\* HSC self-renewal probability is the single most influential fate parameter. Reducing it below \~70% makes the system structurally unstable at default population targets.

\### 2.5.5 Recommended Scenarios

\*\*Scenario 1 --- \"Default balance\" (recommended)\*\*

All fate weights at defaults. Toggle OFF.

Result: stable long-term equilibrium.

\*\*Scenario 2 --- \"HSC pool study\"\*\*

\| Parameter \| Value \|

\|\-\--\|\-\--\|

\| HSC self-renewal \| 75% \|

\| HSC asymmetric \| 15% \|

\| HSC commitment \| 10% \|

Result: slightly lower HSC pool, faster downstream output. Good for studying how the system compensates for reduced stem cell self-maintenance.

\*\*Scenario 3 --- \"Forced differentiation\"\*\*

\| Parameter \| Value \|

\|\-\--\|\-\--\|

\| HSC commitment \| 20% \|

\| HSC self-renewal \| 70% \|

Result: HSC pool gradually depletes; the system cannot sustain production without the Population Regulation mechanism (M6.4) compensating aggressively.

\*\*Scenario 4 --- \"Pure self-renewal experiment\"\*\*

\| Parameter \| Value \|

\|\-\--\|\-\--\|

\| HSC self-renewal \| 95% \|

\| HSC asymmetric \| 4% \|

\| HSC commitment \| 1% \|

Result: HSC accumulate; downstream lineages starve. Terminal cell counts collapse. Useful as a pathological control case.

\# Part 3.1: Model Limitations

\-\--

\## 3.1.1 Introduction

The model is well-suited for studying normal hematopoiesis, but it has real limitations. Knowing where the model performs reliably --- and where its results cannot be trusted --- is as important as knowing how to run it. Use the model within its intended scope, and treat its outputs accordingly.

\-\--

\## 3.1.2 Limitations Overview

\| \# \| Limitation \| Consequences \| What you cannot do \|

\|\-\--\|\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--\|

\| 1 \| \*\*No spatial structure\*\* \*(well-mixed)\* \| Ignores local niche geometry; no cytokine gradients; no HSC migration between niches \| Model post-irradiation recovery; study HSC niche localization \|

\| 2 \| \*\*Simplified cell type hierarchy\*\* \| Only 8 cell types; no megakaryocytes; no intermediate progenitor stages \| Model megakaryopoiesis; model thrombopoiesis accurately \|

\| 3 \| \*\*No peripheral cell death\*\* \| All cells \"die\" inside the bone marrow compartment; real terminal cells die in circulation and tissues \| Get accurate cell lifespan estimates; model tissue-specific turnover \|

\| 4 \| \*\*No mutations or clonality\*\* \| No selective advantage for mutant clones; no clonal competition \| Model leukemia, clonal hematopoiesis, myelodysplastic syndromes \|

\| 5 \| \*\*Chronic stress only\*\* \| Only slow, cumulative stress (\`stress_accumulation_rate\`); no acute perturbations \| Model acute chemotherapy, radiation doses, or infectious shock \|

\| 6 \| \*\*No cytokine signaling\*\* \| No G-CSF, GM-CSF, EPO, TPO, or other growth factors; system regulates only through its own internal mechanisms \| Simulate cytokine therapy; calculate treatment efficacy \|

\| 7 \| \*\*Simplified differentiation pathways\*\* \| CMP → Myeloid and CLP → B/T are linearized; no branching at intermediate stages \| Accurately model granulopoiesis sub-steps or early lymphopoiesis \|

\| 8 \| \*\*Calibrated to mouse, not human\*\* \| Physiological timescales differ (mouse: days; human: weeks--months); absolute numbers are not transferable \| Apply results directly to human patients or clinical data \|

\| 9 \| \*\*Simplified epigenetics\*\* \| Memory is a single continuous variable, not DNA methylation, histone modification, or chromatin state \| Predict specific epigenetic marks or long-term epigenetic reprogramming \|

\| 10 \| \*\*No immune feedback\*\* \| HSCs do not respond to signals from circulating lymphocytes, macrophages, or inflammatory cytokines \| Model autoimmune hematopoietic failure, infection-driven expansion, or immune-mediated aplasia \|

\-\--

\## 3.1.3 Summary: What the Model Does Well vs. Poorly

\### ✅ The model works well for:

\| Domain \| Suitable questions \|

\|\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--\|

\| \*\*Normal hematopoiesis\*\* \| How does the system reach steady state? What is the HSC/MPP ratio at equilibrium? \|

\| \*\*Homeostasis & regulation\*\* \| What role does population regulation (M6.4) play? How does niche signaling protect HSCs? \|

\| \*\*Long-term stability\*\* \| Does the HSC pool persist over hundreds of simulated hours? \|

\| \*\*Mechanism ablation studies\*\* \| What happens if M6.2 is turned off? How sensitive is the system to changes in fate weights? \|

\| \*\*Parametric sensitivity\*\* \| Which parameters matter most? What drives the system toward or away from equilibrium? \|

\| \*\*Education\*\* \| Understanding stochastic cell systems, homeostasis, and hierarchical differentiation \|

\> 💡 \*\*Good questions to ask:\*\* \*\"How does the system recover from a 50% depletion?\" / \"What balance between self-renewal and commitment keeps the HSC pool stable?\" / \"How does increased stress rate affect long-term cell composition?\"\*

\-\--

\### ❌ The model does not work well for:

\| Domain \| Why it fails \|

\|\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\--\|

\| \*\*Leukemia / cancer\*\* \| No mutation mechanism, no selective pressure, no clonal competition \|

\| \*\*Acute clinical events\*\* \| No acute stress pathway --- only chronic accumulation \|

\| \*\*Cytokine therapy\*\* \| No signaling molecules in the model \|

\| \*\*Clinical predictions for patients\*\* \| Calibrated to mouse; human physiology differs substantially \|

\| \*\*Post-irradiation recovery\*\* \| No spatial structure; local niche dynamics are absent \|

\| \*\*Aplastic anemia\*\* \| System recovers too well; no mechanism for persistent HSC exhaustion \|

\| \*\*Polycythemia / thrombocytosis\*\* \| No lineage-specific feedback; regulation is global \|

\| \*\*Immune disorders\*\* \| No B/T cell → HSC feedback loop \|

\> ⚠️ \*\*Poor questions to ask:\*\* \*\"Will this drug cure leukemia?\" / \"What are the correct parameters for a human patient?\" / \"How many days will a patient's neutrophils recover after chemotherapy?\"\*

\-\--

\### Practical Examples: When Limitations Bite

\*\*Example 1: No mutations → Cannot model leukemia\*\*

\- \*What you might try:\* "Let me increase HSC self-renewal to 95% to mimic uncontrolled growth"

\- \*What happens:\* HSC pool explodes, but there's no selective advantage --- all cells are equivalent

\- \*Why it fails:\* Real leukemia requires mutant cells to outcompete normal HSCs. The model has no mechanism for clonal selection.

\- \*Better approach:\* Use this model to understand normal HSC regulation under high self-renewal, then consult a specialized leukemia simulator.

\*\*Example 2: Only chronic stress → Cannot model chemotherapy\*\*

\- \*What you might try:\* "Let me increase stress_accumulation_rate to 0.1 to simulate acute chemo damage"

\- \*What happens:\* Slow, gradual cell degradation over 100--200 hours --- not an acute insult

\- \*Why it fails:\* Chemotherapy delivers a sudden burst of damage, not slow aging. The model only knows cumulative stress over time.

\- \*Better approach:\* Use Duration=200+ hours to study long-term recovery dynamics, understanding that the initial phase will not accurately reflect acute chemo effects.

\*\*Example 3: Mouse-calibrated → Cannot apply to humans directly\*\*

\- \*What you might try:\* "Let me run Duration=1000 hours to model months of human time"

\- \*What happens:\* You get long-term dynamics, but in mouse timescales, not human physiology

\- \*Why it fails:\* All parameters are calibrated to mouse bone marrow. Human HSCs divide much more slowly, and cell lifespans are weeks--months, not hours--days.

\- \*Better approach:\* Use the model for qualitative understanding of mechanisms, not as a clinical predictor. Any translation to humans would require complete recalibration.

\*\*Example 4: No spatial structure → Cannot study local niche effects\*\*

\- \*What you might try:\* "Let me set Niche Modulation (k=10) to maximum to study how the niche affects recovery"

\- \*What happens:\* The niche signal is global --- all HSCs feel it equally. There is no local geometry, no gradients, no proximity effects.

\- \*Why it fails:\* Real bone marrow has discrete HSC niches (perivascular, endosteal). Some HSCs are "sheltered" while others are not. The model treats all HSCs as if they experience an identical niche signal.

\- \*Better approach:\* Study how the strength of niche signaling (k parameter) affects HSC pool behavior, knowing that you're studying a simplified, well-mixed version of the true spatial problem.

\-\--

\## 3.1.4 When to Trust the Results

\### ✅ Trust the results when:

\- The question concerns \*\*normal hematopoiesis\*\* under stable or mildly perturbed conditions

\- You are studying \*\*qualitative effects\*\* (\"more / less\", \"faster / slower\") rather than exact quantities

\- You are comparing \*\*two scenarios\*\* under the same parameter set (\"what if X is on vs. off?\")

\- You are performing a \*\*mechanism ablation\*\* (toggle one control mechanism and observe the difference)

\- Parameters are within \*\*reasonable ranges\*\* (not pushed to extremes)

\- You are aware of the limitations and are accounting for them in your interpretation

\### ❌ Do not trust the results when:

\- The question involves \*\*disease, mutation, or clonal dynamics\*\*

\- You need \*\*precise quantitative values\*\* (absolute cell counts, exact lifespans)

\- You are trying to apply results \*\*directly to human biology or clinical outcomes\*\*

\- Parameters have been pushed to \*\*extreme or unrealistic values\*\*

\- You are using the model as a \*\*predictive clinical tool\*\*

\-\--

\### The golden rule

\> \*\"A model is a simplification of reality --- not reality itself.\"\*

Use it as a tool for \*\*understanding mechanisms\*\* and exploring \*\*qualitative behavior\*\*, not as an oracle for predicting specific outcomes.

\| The model is good for \| The model is not suitable for \|

\|\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--\|

\| Understanding mechanisms \| Clinical predictions \|

\| Qualitative system behavior \| Exact quantitative calculations \|

\| Parametric sensitivity \| Disease modeling \|

\| Ablation / comparative studies \| Drug target selection \|

\| Educational purposes \| Direct application to patients \|

\-\--

\## 3.1.5 Possible Future Improvements

The limitations above reflect deliberate design trade-offs, not bugs. Each would require substantial development effort to address:

\| \# \| Improvement \| What it would enable \|

\|\-\--\|\-\-\-\-\-\-\-\-\-\-\-\--\|\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--\|

\| 1 \| \*\*Spatial structure\*\* --- add (x, y, z) coordinates and local niches \| Post-irradiation recovery; cytokine gradient effects; HSC migration \|

\| 2 \| \*\*Mutations & clonality\*\* --- random mutation events + selective advantage \| Leukemia modeling; clonal hematopoiesis; myelodysplasia \|

\| 3 \| \*\*Cytokine signaling\*\* --- G-CSF, EPO, TPO, GM-CSF etc. \| Cytokine therapy simulation; treatment efficacy calculations \|

\| 4 \| \*\*Multiple organs\*\* --- spleen, peripheral vasculature, inter-organ migration \| Extramedullary hematopoiesis; stress erythropoiesis \|

\| 5 \| \*\*Immune feedback\*\* --- B/T cell → HSC signaling; inflammation and infection \| Immune-mediated aplasia; infection-driven expansion \|

\| 6 \| \*\*Detailed epigenetics\*\* --- DNA methylation, histone states, chromatin \| Long-term epigenetic reprogramming; precise fate inheritance \|

\| 7 \| \*\*Human-calibrated parameters\*\* --- recalibrated to human physiological timescales \| Translational relevance; age-dependent variation (young vs. elderly) \|

\| 8 \| \*\*Acute perturbations\*\* --- radiation dose model, acute infection, chemotherapy shock \| Bone marrow recovery modeling; treatment scheduling \|

All of these improvements would require additional experimental data, extended validation, and significant increases in computational cost. The current model represents the optimal balance between \*\*biological realism\*\* and \*\*usability\*\*.

\-\--

\*End of Part 3.1 --- Model Limitations\*

\-\--

\## Part 3.2: Reading the Simulator Output

\### 3.2.1 Overview

After a simulation run completes, the right panel displays a set of charts. Each chart shows a different aspect of the population over simulated time (x-axis, in hours). This section explains what each chart shows and how to interpret common patterns.

\### 3.2.2 Chart Descriptions

\| Chart name \| Y-axis \| What to look for \|

\|\-\--\|\-\--\|\-\--\|

\| Total Population \| Cell count \| Does the line plateau (homeostasis) or grow/collapse? The plateau level should approximate the Target Population setting. \|

\| HSC Pool \| HSC count \| A stable or slowly-declining line is normal. Rapid decline indicates over-commitment; a rising line indicates excess self-renewal. \|

\| Cell-type Composition \| Cell count per type (stacked or overlaid) \| Relative widths of each type\'s band show lineage balance. Disappearing bands indicate lineage collapse. \|

\| Division Events \| Events per time unit \| Peaks indicate the system is recovering from a deficit; flat lines indicate equilibrium. \|

\| Apoptosis Events \| Events per time unit \| Sustained elevation signals stress accumulation or crowding apoptosis (M4) activation. \|

\| Mean Stemness \| Average stemness across all HSC \| A declining trend over time indicates centriole aging accumulating across the pool. \|

\| Mean Stress \| Average stress across all cells \| Should grow slowly and plateau. Rapid growth means stress_accumulation_rate is set too high. \|

Note: not all charts may be visible by default --- some may require toggling the display options in the chart panel.

\### 3.2.3 Common Patterns and What They Mean

\| Pattern \| Likely cause \| What to check \|

\|\-\--\|\-\--\|\-\--\|

\| Population plateaus near target \| Normal homeostasis \| Nothing --- system is working correctly \|

\| Population oscillates and never settles \| Density gamma (γ) too high, or fate weights unbalanced \| Reduce γ; check HSC commitment probability \|

\| HSC pool collapses within first 50 h \| Commitment probability too high, or niche modulation OFF \| Enable M6.2 or reduce commitment weight \|

\| Terminal cells disappear gradually \| Progenitor bottleneck (MPP or CMP depleted) \| Check division rates; ensure M6.4 is ON \|

\| Population grows without ceiling \| Target Population toggle OFF, or M4 off with γ = 0 \| Enable Target Population or increase γ \|

\| Mean stress rises rapidly then plateaus early \| Stress accumulation rate too high \| Reduce stress_accumulation_rate in Basic Settings \|

\| All charts flat from t = 0 \| Simulation may not have run \| Check for error messages; try reducing Duration \|

\-\--

\# Appendix: Glossary

\| Term \| Definition \|

\|\-\--\|\-\--\|

\| Apoptosis \| Programmed cell death --- a cell actively destroys itself rather than being killed externally. In the model, expressed as a rate in events per hour. \|

\| Asymmetric division \| A division where one daughter cell retains the parent\'s identity and the other becomes a different cell type. \|

\| Commitment \| A division fate where both daughter cells differentiate into the next type down the hierarchy. The parent type \"sacrifices\" itself to produce two progenitors. \|

\| CLP (Common Lymphoid Progenitor) \| An intermediate cell type that gives rise to B-cells and T-cells. Cannot become myeloid cells. \|

\| CMP (Common Myeloid Progenitor) \| An intermediate cell type that gives rise to myeloid and erythroid cells. Cannot become lymphoid cells. \|

\| Differentiation \| The process by which a less-specialised cell becomes a more-specialised cell type. Always one-way in this model. \|

\| Division rate \| The average number of divisions a cell performs per hour. Expressed in units of 1/h. \|

\| Epigenetic memory \| In the model: a cell\'s tendency to repeat its parent\'s fate choice. Controlled by the inheritance_noise and drift_rate parameters. \|

\| Hematopoiesis \| The biological process of blood cell production, occurring primarily in the bone marrow. \|

\| HSC (Hematopoietic Stem Cell) \| The most primitive cell in the hierarchy. HSCs self-renew indefinitely and give rise to all other blood cell types. \|

\| Homeostasis \| The system\'s ability to maintain a stable population size over time despite ongoing cell death and renewal. \|

\| MPP (Multipotent Progenitor) \| A progenitor cell derived from HSC that can still produce both myeloid and lymphoid lineages, but has less self-renewal capacity. \|

\| Niche \| The bone marrow microenvironment surrounding HSCs. In the model, the niche suppresses commitment when the stem cell pool is depleted. \|

\| Progenitor \| Any cell that has partially differentiated from an HSC but has not yet reached a terminal fate (HSC, MPP, CMP, CLP are all progenitors). \|

\| Self-renewal \| A division fate where both daughters are identical to the parent. The cell type\'s pool grows by one. \|

\| Seed \| A number that initialises the random number generator. The same seed always produces the same simulation result. \|

\| Stemness \| A value between 0 and 1 representing a cell\'s capacity for sustained self-renewal. Higher stemness = more division potential. \|

\| Stress \| A cell-internal counter that accumulates over time, representing replicative damage. High stress slows division and accelerates apoptosis. \|

\| Terminal cell \| A fully differentiated cell that performs a specific function (Myeloid, Erythroid, B_cell, T_cell). Terminal cells do not divide. \|
