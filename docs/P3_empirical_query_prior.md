# P3 — Empirical Query Prior: closing open gate Q2 (§5 Findings)

**Status:** P3 finding, paper-grade feed for §5 Findings. **Closes P3 open gate Q2**
(query-distribution grounding, constraint C8) for the decidability map of
`P3_decidability_map.md`. Re-runs the **DV1** decidability measurement over a query
distribution **derived from real LLM deployments** instead of the hand-built grid, so the
headline "% underdetermined" becomes a claim about *real deployment traffic*, not about a
mixture we chose. The empirical-confirmation slot for the limit theorem (§8/§11), now on
real traffic.

**Substrate snapshot.** Unchanged from `P3_decidability_map.md`: `data/apt_substrate.db`,
182 configs over 3 evidence-source archetypes (function-calling = BFCL; inference-serving =
MLPerf + ML.ENERGY; general-qa = HELM), 5 of 8 right-sizing axes carry any evidence
(`quality, latency_p95, throughput, cost, energy`); `memory_hw, governance,
reviewer_burden` are ⊥ everywhere. This node changes **only the query distribution**, not
the substrate, the solver, or the C7 interface.

**Query snapshot (the new artifact).** `zenml/llmops-database` — **1716 real
LLM-deployment case studies**, frozen snapshot (C3). Each case study is mapped to one
query `q = (τ, binding-axes)` by a documented tag→axis taxonomy. The multiset of 1716
derived queries **is** the empirical prior.

**How the numbers were produced (reproducible).**
```bash
PYTHONNOUSERSITE=1 uv run python -m prudent_ai.queries.run_empirical_prior \
    --db data/apt_substrate.db --out outputs/p3/empirical_prior_map.json
```
All reported fractions use **φ=point, κ=H+M**, bootstrap n=1000 (locally seeded,
deterministic). CIs are 95% percentile bootstrap. Numbers below are reproduced verbatim
from `outputs/p3/empirical_prior_map.json` / `.md`.

---

## 1. Q2 — what it was and why it mattered

`P3_decidability_map.md`'s headline — *≈86% of right-sizing queries are underdetermined at
the full regime; 100% under an accuracy-only (leaderboard) regime* — carried an explicit
caveat: the query **distribution** was a hand-built grid (14 queries/τ, 42 total). The
thresholds in that grid were percentile-grounded, but the **mixture over queries** was not.
Constraint **C8** of the master plan requires a *justified* query distribution, not a
cherry-picked one; until that holds, the exact percentages are "decidability of this grid,"
not "of real deployment traffic." That gap is **P3 open gate Q2**, recorded as Limitation 1
of `P3_decidability_map.md` and as **Open Q2** in `APT_P0_formalism_spine.md §11`.

There are in fact two layers to Q2, and this node closes the first:

- **Q2-distribution (closed here).** *Where does the query mixture come from?* — answered by
  grounding the prior in 1716 real deployments rather than hand-picking it.
- **Q2-binding (the deeper, still-open form, §11).** *Does a tag truly identify the axis
  that BINDS at the optimum, or merely the axis that is SALIENT?* `APT_P0_formalism_spine
  §1` defines `bind(q)` as the axes whose constraint is *active at the optimum* (relaxing
  them changes `x*`). A deployment tag is evidence that an axis is *declared a hard
  requirement*, which is a conservative over-approximation of binding, not binding itself.
  See §5.

This node delivers Q2-distribution and is explicit that it does not deliver Q2-binding.
The structural facts (which axes are ⊥, the corpus-wide blind spots) are
distribution-independent and survive both readings.

---

## 2. Method

### 2.1 The corpus

`zenml/llmops-database` (HuggingFace) is a curated database of **real LLM-deployment case
studies** — write-ups of production / near-production LLM systems with structured tags for
the application, the techniques used, and the industry. We take **1716** case studies as a
**frozen snapshot** (C3: a fixed, reproducible query set; we do not re-pull live). Each case
study becomes exactly one query, weight 1.

### 2.2 Tag → binding-axis taxonomy (C8-critical artifact, shown in full)

A tag binds an axis iff the deployment, *by carrying that tag*, declares a hard requirement
on that axis. The mapping is **conservative**: only tags with unambiguous axis semantics
appear, and tags are matched from either `application_tags` or `techniques_tags`. This table
is the artifact C8 demands be justified and auditable, reproduced verbatim from
`src/prudent_ai/queries/query_prior.py` (`TAG_TO_AXIS`):

| ZenML tag | binds axis | rationale |
|---|---|---|
| `latency_optimization` | `latency_p95` | explicit latency engineering / real-time SLO |
| `realtime_application` | `latency_p95` | real-time SLO |
| `cost_optimization` | `cost` | explicit cost / token-budget engineering |
| `token_optimization` | `cost` | token-budget engineering |
| `regulatory_compliance` | `governance` | regulated / safety-gating workload |
| `high_stakes_application` | `governance` | high-stakes gating |
| `content_moderation` | `governance` | safety gating |
| `fraud_detection` | `governance` | safety gating |
| `human_in_the_loop` | `reviewer_burden` | a human is in the decision loop ⇒ review cost is a constraint |
| `internet_of_things` | `memory_hw` | on-device / edge ⇒ hardware-memory bound |

**Regulated-industry rule (second governance source).** A separate artifact binds
`governance` from the `industry` field regardless of technique tags, because deployments in
these sectors carry statutory obligations (HIPAA, SOX, GDPR, GLBA, …). Verbatim
`REGULATED_INDUSTRIES`:

```
{ Healthcare, Finance, Legal, Insurance, Government }
```

**Universal axis.** Every deployment carries an implicit **quality floor**, so `quality`
binds on every query (`UNIVERSAL_AXES = {quality}`). This is why `quality` binds 100% of the
corpus (§3).

### 2.3 Application archetype → substrate τ (and why the mismatch is itself a finding)

The substrate is sliced by **evidence-source** archetype (function-calling = BFCL,
general-qa = HELM, inference-serving = MLPerf/ML.ENERGY); ZenML is sliced by
**deployment-application** archetype. We map application → evidence-source **coarsely**, by
the first matching `application_tag` (else default `general-qa`). Verbatim `ARCHETYPE_MAP`:

| ZenML application tag | substrate τ |
|---|---|
| `code_generation`, `code_interpretation`, `structured_output`, `data_integration` | function-calling |
| `realtime_application`, `speech_recognition` | inference-serving |
| `chatbot`, `question_answering`, `customer_support`, `summarization`, `translation`, `classification`, `content_moderation`, `document_processing`, `data_analysis` | general-qa |

`DEFAULT_TAU = general-qa`.

**The mismatch is a finding, not a bug.** Real deployment archetypes do **not** align with
how the evidence corpus is sliced — there is no clean bijection between "what people deploy"
and "what the evaluation sources measure." We make this explicit and argue the decidability
result is robust to it: the off-evidence binding axes (`governance, reviewer_burden,
energy`) are ⊥ in **every** τ, so whichever τ a deployment maps to, a query binding one of
those axes is underdetermined regardless. The coarse map cannot manufacture or hide the
headline.

### 2.4 Axes deliberately left UNBOUND (C1, no fabrication)

`throughput` and `energy` are **never** bound from a ZenML tag. No tag signals these
cleanly, so we leave them ⊥-able rather than invent a binding. This is the same discipline
as the substrate side: `⊥` stays `⊥`, we never impute a missing axis (C1, C7). The
consequence is conservative — it can only **lower** the number of binding axes per query,
hence can only **under**-state underdetermination from those two axes.

### 2.5 Grounded thresholds and the runnable query

Each `DerivedQuery(τ, binding-axes)` becomes a runnable `Query` whose thresholds are
**per-(τ, axis) grounded** — the median observed κ-filtered value for that cell — so the bar
is realistic (the snapshot stores the grounded thresholds it used, e.g.
`general-qa|quality = 0.5527`, `function-calling|cost = 18.25`,
`inference-serving|latency_p95 = 81.56`). Axes with no κ-evidence are still *probed* at a
nominal threshold; the point (as in `P3_decidability_map.md` H2) is that such a binding is
undecidable **for lack of evidence**, whatever the number. Direction per axis (`>=` floor /
`<=` ceiling) follows `_AXIS_OP` in `query_prior.py`.

### 2.6 What stays fixed (C7)

The solver, the three-state classifier, the completion-flip rule, the regime ladder, and the
C7 firewall (`candidates / cell / required_fields` only) are **identical** to
`P3_decidability_map.md`. This node swaps the query distribution and nothing else — so any
delta between the two docs is attributable *purely* to grounding the prior.

---

## 3. Results

### 3.1 The empirical prior

**τ distribution (real traffic, n=1716):**

| archetype τ | n queries | fraction |
|---|---|---|
| general-qa | 1219 | 71.0% |
| function-calling | 427 | 24.9% |
| inference-serving | 70 | 4.1% |

Real deployment traffic is dominated by QA-shaped workloads; latency-dominated serving is a
thin 4.1% tail. This is itself notable: the archetype the substrate measures *best*
(function-calling, the only one that ever becomes decidable in `P3_decidability_map.md`) is a
quarter of real traffic, and the serving archetype is rare.

**Axis-binding frequency (how many of 1716 deployments bind each axis):**

| axis | n deployments binding it | fraction | measurable in substrate? |
|---|---|---|---|
| quality | 1716 | 100.0% | yes |
| governance | 954 | **55.6%** | **⊥ everywhere** |
| latency_p95 | 804 | 46.9% | yes (not in general-qa) |
| reviewer_burden | 751 | **43.8%** | **⊥ everywhere** |
| cost | 709 | 41.3% | yes (not in general-qa / inference-serving) |
| memory_hw | 20 | 1.2% | ⊥ everywhere |

The load-bearing fact: **more than half of real deployments (55.6%) bind `governance`, and
~44% bind `reviewer_burden` — and both axes are 100% ⊥ in the evidence corpus.** A majority
of real traffic constrains on exactly the axes the entire evidence base is silent on. (As a
floor: `throughput` and `energy` are never bound by construction — §2.4 — so the true
off-evidence binding load is at least this large.)

### 3.2 Real-traffic decidability by regime (DV1)

φ=point, κ=H+M, n=1716, 95% percentile-bootstrap CIs:

| regime | %decidable (95% CI) | %underdetermined (95% CI) | %infeasible | dominant blocking axes |
|---|---|---|---|---|
| `accuracy_only` | 0.0% [0.0, 0.0] | **100.0%** [100.0, 100.0] | 0.0% | cost(1716), governance(954), latency(804), reviewer_burden(751) |
| `acc_cost` | 5.2% [4.2, 6.2] | 94.8% [93.8, 95.8] | 0.0% | cost(1289), governance(954), latency(804), reviewer_burden(751) |
| `acc_cost_latency` | 8.9% [7.6, 10.3] | **91.1%** [89.7, 92.4] | 0.0% | cost(1289), governance(954), reviewer_burden(751), latency(557) |
| `acc_cost_lat_throughput` | 8.9% [7.6, 10.3] | 91.1% [89.7, 92.4] | 0.0% | cost(1289), governance(954), reviewer_burden(751), latency(557) |
| `plus_energy` | 8.9% [7.6, 10.3] | 91.1% [89.7, 92.4] | 0.0% | cost(1289), governance(954), reviewer_burden(751), latency(557) |
| `full` (all 8 axes) | 8.9% [7.6, 10.3] | **91.1%** [89.7, 92.4] | 0.0% | cost(1289), governance(954), reviewer_burden(751), latency(557) |

**Headline.** On real deployment traffic, **91.1% of right-sizing queries stay
underdetermined even when the rule is handed every axis the substrate measures**, and
**100% are underdetermined under an accuracy-only (leaderboard) regime**. Decidability tops
out at **8.9%** (153/1716) — and reaches it already at `acc_cost_latency`; adding
throughput, energy, or governance buys nothing.

### 3.3 Attribution — the sharp form of C1

At the full regime, of the 1716 queries, 1563 (91.1%) are underdetermined. Decomposing
*why*:

- **72.4%** (1243/1716) of **all** queries are underdetermined **because at least one of
  their binding axes is unmeasurable corpus-wide** — the unmeasurable set being
  `{energy, governance, memory_hw, reviewer_burden, throughput}`. For these, the decision
  cannot be made not for lack of *in-regime* evidence but because the constraint lives on an
  axis the **entire** evidence corpus is silent on.
- **16.0%** (274/1716) are underdetermined where **every** blocking axis is unmeasurable —
  the strictest reading: nothing in any reachable regime could ever decide them.
- Blocking-axis frequency among underdetermined queries (full regime):
  `cost 1289, governance 954, reviewer_burden 751, latency_p95 557, quality 70,
  memory_hw 20`.

This is **C1 in its sharpest, real-traffic form**: the majority of real deployment decisions
bind on an axis that is **un-checkable**, so committing to a recommendation on them cannot be
validated at all — the right answer is to **abstain and name the missing axis**, not impute
(`⊥` stays `⊥`, C7).

### 3.4 Regime-ladder effect — the limit-theorem shadow on real traffic

Decidability rises monotonically as the regime grows, then **plateaus**:

`accuracy_only 0.0% → acc_cost 5.2% → acc_cost_latency 8.9% → (throughput / energy / full) 8.9%`.

The two jumps are exactly where a previously-blind binding axis enters the regime: **+cost
unblocks the cost objective** (0.0→5.2%), **+latency unblocks latency-bound queries**
(5.2→8.9%). The ladder then **flatlines** — adding throughput, energy, or governance moves
*nothing*, because no further query's binding axis becomes certifiable (governance /
reviewer_burden are ⊥ regardless of regime; throughput / energy were never bound, §2.4).
This is `decidable ⇔ bind(q) ⊆ cl(R)` (`APT_P0_formalism_spine §8.6`) read off real traffic:
each rung admits an axis, and decidability climbs *only* for queries whose binding axis that
rung supplies. It is the empirical **shadow** of the §8.5 bound `E[regret] ≥ c·Δ(R)` and the
§8.7 identity `VoI(a*) = Δ(R)` — empirical *confirmation*, never a corollary of the theorem
(§8.8 discipline).

### 3.5 Mapping robustness — no single tag→axis rule carries the finding

Drop-one-tag sensitivity at the full regime (baseline 91.1% underdetermined). Each row
removes one mapping and recomputes:

| dropped mapping | %underdetermined | Δ vs baseline |
|---|---|---|
| `latency_optimization` | 91.1% | 0.0% |
| `cost_optimization` | 91.1% | 0.0% |
| `regulatory_compliance` → governance | 90.0% | −1.0% |
| `high_stakes_application` → governance | 90.1% | −1.0% |
| `human_in_the_loop` → reviewer_burden | **83.2%** | **−7.9%** |
| regulated-industry → governance rule | 90.6% | −0.5% |

The finding is **robust to the taxonomy**: every drop leaves underdetermination above 83%.
The single most influential mapping is `human_in_the_loop → reviewer_burden` (−7.9%, to
83.2%) — expected, since `reviewer_burden` binds 43.8% of traffic and is ⊥ everywhere — yet
*even removing it entirely* the headline survives at **83.2% underdetermined**. No single
mapping choice is load-bearing; the result is a property of the corpus, not of one rule
(C8 robustness).

### 3.6 Grid vs empirical — the headline holds under real-traffic reweighting

| query source | n | %underdetermined (full regime) |
|---|---|---|
| P3 hand grid (`P3_decidability_map.md`) | 42 | 85.7% |
| **empirical prior (this node)** | **1716** | **91.1%** |

**Δ = +5.4%.** Grounding the prior does not merely *preserve* the finding — it **sharpens**
it. The hand grid, by spreading queries uniformly across axes (one bind per axis per τ),
*under*-weighted the off-evidence axes that real traffic actually loads (governance 55.6%,
reviewer_burden 43.8%). Real deployments bind the un-checkable axes more often than a uniform
grid does, so the real-traffic underdetermination is **higher**, not lower. The qualitative
claim — *most right-sizing decisions are evidence-underdetermined* — is not an artifact of
the uniform hand grid; it is, if anything, conservative relative to real traffic.

---

## 4. Relation to claims & the limit theorem

- **Q2-distribution closed (C8).** The decidability headline of
  `P3_decidability_map.md` is now stated over a **justified, real-deployment** query
  distribution, not a hand grid. C8's "no cherry-picking" obligation is met for the
  distribution: 1716 real case studies, a fully-documented and drop-one-robust taxonomy, and
  axes left ⊥ rather than fabricated.

- **Empirical-confirmation slot for the limit theorem (§8/§11), now real-traffic.** The
  regime-ladder monotonicity-then-plateau (§3.4) is the empirical shadow of
  `E[regret] ≥ c·Δ(R)` (§8.5) and `VoI(a*) = Δ(R)` (§8.7), measured on the distribution of
  decisions practitioners actually face. **Off-evidence binding ⇒ irreducible
  underdetermination on the majority of real traffic**: governance (55.6%) and
  reviewer_burden (43.8%) bind off the evidence — `bind(q) ⊄ cl(R)` for any reachable
  regime — so by §8.6 those queries are *provably* undecidable, not data-collection bugs.
  This is empirical *confirmation*, never a corollary (§8.8).

- **Sharpens C1.** `P3_decidability_map.md` showed structured missingness on a grid; this
  node shows that on **real traffic**, 72.4% of all decisions are underdetermined *because a
  binding axis is corpus-wide ⊥* — the structured-missingness claim is not just present, it
  is load-bearing on the majority of deployments people actually run.

- **What this does NOT show.** It quantifies that real decisions are *underdetermined*; it
  does **not** show that a leaderboard rule committing anyway *mis-sizes by a measurable
  margin*. Decision regret + hidden-violation magnitude (DV2/DV3, C2; §11 Q3) are **P5**.
  P3 owns the "many real decisions are undecidable" half; "and answering them anyway hurts,
  measurably" is P5 validation.

---

## 5. Honest limitations

1. **Q2 closed at the DISTRIBUTION level, not per-instance binding (the deeper Open-Q2).**
   A tag signals which axis is **salient / declared a hard requirement**, not which axis
   truly **binds at the optimum** (`bind(q)` = active-at-optimum, `APT_P0_formalism_spine
   §1`). We over-approximate binding by the declared-requirement set. This is conservative in
   one direction (we may call an axis binding when it is slack at the optimum) and the
   deliberate ⊥-leaving of throughput/energy is conservative in the other. Making `bind(q)`
   first-class — recovered from the constraint bundle *and* the observed Pareto structure —
   remains **Open Q2** (§11) and is P3/P4 work. The distribution-level claim does not depend
   on resolving it, because the off-evidence axes are ⊥ in every τ regardless.

2. **Archetype → τ map is coarse.** ZenML's deployment-application archetypes are mapped to
   the substrate's evidence-source archetypes by a first-match rule with a `general-qa`
   default (§2.3). The mismatch is real and is itself reported as a finding; the result is
   robust to it only because the decisive off-evidence axes are ⊥ in every τ. A finer
   archetype alignment is future work and could shift the *per-τ* split without moving the
   pooled headline.

3. **MedHELM stayed gated.** The master plan named ZenML **and** MedHELM as prior sources.
   MedHELM was **not** added: the source returned HTTP 401 (access-gated) at snapshot time.
   The prior is therefore ZenML-only; a medical/high-governance corpus would, if anything,
   *raise* the governance-binding fraction (already 55.6%) and strengthen the finding, but it
   is not yet measured.

4. **Mis-sizing MAGNITUDE is still P5.** This node measures *how often* real decisions are
   undecidable, not *how badly* a rule that commits anyway is wrong. The regret / hidden-
   violation magnitude (whether real mis-sizing meets or exceeds `Δ(R)`) is **P5**, open per
   §11 Q3 and §8.8.

5. **Inherited solver-side caveats.** φ=point (decidability-over-stating, so 91.1% is a
   floor), κ=H+M, and the `cl(R)` closure not yet exploited — all as in
   `P3_decidability_map.md` Limitations 2–3. Two distinct underdetermination causes
   (objective-bottom: cost ⊥; constraint-bottom: governance/reviewer_burden ⊥) are still
   pooled under one UNDERDETERMINED label, though the §3.3 attribution begins to separate
   them.

---

## 6. Key numbers the paper cites

- **Empirical prior:** **1716** real LLM-deployment case studies (`zenml/llmops-database`,
  frozen snapshot, C3). τ split: general-qa **71.0%**, function-calling **24.9%**,
  inference-serving **4.1%**.
- **Off-evidence binding load:** **governance binds 55.6%** and **reviewer_burden binds
  43.8%** of real traffic — both **100% ⊥** in the evidence corpus. (`quality` 100%,
  `latency_p95` 46.9%, `cost` 41.3%, `memory_hw` 1.2%; `throughput`/`energy` never bound, by
  design, C1.)
- **Real-traffic underdetermination:** **91.1%** (1563/1716) at the full regime; **100%**
  under accuracy-only; decidability tops out at **8.9%** (153/1716).
- **Attribution (sharp C1):** **72.4%** (1243/1716) of all queries underdetermined **because
  a binding axis is unmeasurable corpus-wide**; **16.0%** (274/1716) blocked *only* by
  unmeasurable axes.
- **Grid → empirical:** **85.7%** (grid, n=42) → **91.1%** (real traffic, n=1716),
  **Δ = +5.4%** — grounding *sharpens* the finding.
- **Regime-ladder (real traffic):** 0.0% → 5.2% (+cost) → 8.9% (+latency) → **plateau** —
  the empirical shadow of `decidable ⇔ bind(q) ⊆ cl(R)` (§8.6) and `VoI(a*) = Δ(R)` (§8.7).
- **Mapping robustness:** underdetermination ≥ **83.2%** under any single tag→axis drop
  (largest effect: `human_in_the_loop`, −7.9%) — no single mapping carries the finding (C8).
