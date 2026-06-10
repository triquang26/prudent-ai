# P3 — The Decidability Map (§5 Findings)

**Status:** P3 finding, paper-grade feed for §5 Findings. Instantiates the master-plan
dependent variable **DV1** (decidability) and the P3 deliverable: a decidability map +
blind-spot characterization + CI/sensitivity. The empirical anchor of **Claim C1**.

**Substrate snapshot.** `data/apt_substrate.db` — 182 configs over 3 archetypes
(function-calling = 109 BFCL configs; inference-serving = 42 MLPerf+ML.ENERGY; general-qa
= 31 HELM), 3392 observations (478 H / 2666 M / 248 L). Five of eight right-sizing axes
carry any evidence (`quality, latency_p95, throughput, cost, energy`); `memory_hw,
governance, reviewer_burden` are ⊥ everywhere.

**How the numbers were produced (reproducible).**
```bash
PYTHONNOUSERSITE=1 uv run python -c "
from prudent_ai.substrate import Substrate
from prudent_ai.analysis.decidability_map import build_map, blind_spot_report, sensitivity_kappa
from prudent_ai.solver import Phi
sub=Substrate('data/apt_substrate.db')
m   = build_map(sub, phi=Phi.POINT)          # κ=H+M, n_boot=1000
b   = blind_spot_report(sub)                  # descriptive miss-rate
s   = sensitivity_kappa(sub, Phi.POINT)        # κ ∈ {H+M, H, H+M+L}
sub.close()"
```
All reported fractions use **φ=point, κ=H+M**, bootstrap n=1000 (locally seeded
`Random(12345)`, deterministic). CIs are 95% percentile bootstrap.

---

## 1. Question (DV1)

> **Of the right-sizing queries one would actually pose to this substrate, what fraction
> are evidence-*decidable*, *underdetermined*, or *infeasible* — as a function of
> {archetype τ × evidence-regime R × confidence κ}?**

A query `q=(τ, c)` is decidable iff the evidence identifies the minimum-sufficient
configuration: there is a provably-feasible, fully-costed `x` whose `argmin cost` is
invariant across all completions `Comp(E)` of the missing/straddling cells (P0 §5). It is
**underdetermined** iff a ⊥ or straddling field could flip the argmin (non-identifiability),
and **infeasible-under-E** iff no candidate is provably feasible across all completions.
DV1 is the empirical distribution of these three labels — the measurement that sharpening
`B_E` (more HELM/HAL rows) does **not** produce, because it asks *when E suffices to
identify the decision*, not how precise the point estimate is.

---

## 2. Method

**Solver-side classifier (§4 three-state → §5 completion-flip).** Each candidate is sorted
into `{provably-feasible, provably-infeasible, possibly-feasible(F)}` by certifying every
constraint against the derived belief `B_E(x,a)=Agg_φ(O_E|κ)` (P0 §4). The query verdict
then applies the completion-flip rule (P0 §5): DECIDABLE iff some candidate is sure-feasible
**and** sure-costed and no completion of a pending/⊥-cost candidate can undercut it;
otherwise UNDERDETERMINED with the responsible `blocking_axes`; INFEASIBLE iff nothing can
be feasible even optimistically.

**C7 firewall.** Every decidability verdict reads the substrate *only* through
`candidates(τ) / cell(x,a)` via `classify_query → classify_candidate → aggregate`. No raw
SQL, no `_session`/`_engine`. The single direct-DB read is the **descriptive** blind-spot
miss-rate (§3, H2), labelled as such; it never feeds a verdict.

**Regime masking (§8.1).** A rule restricted to regime `R ⊆ A` is *blind* to any axis
`a ∉ R`: the classifier treats off-regime cells as ⊥ regardless of what the substrate holds.
The ladder is the §16 IV: `accuracy_only → acc_cost → acc_cost_latency →
acc_cost_lat_throughput → plus_energy → full`.

**Settings.** φ=point, κ=H+M (DEFAULT_KAPPA), α implicit at the point estimate (no
straddle band — the conservative reading is that point-mode *over*-states decidability, so
the underdetermination we report is a **lower bound**).

**Query battery (structured grid — open gate Q2).** For each τ: one single-axis bind per
axis (8 queries) + 6 curated realistic 2-axis bundles (quality+cost, quality+latency,
quality+energy, latency+cost, throughput+energy, quality+governance) = **14 queries/τ, 42
total**. Thresholds are **percentile-grounded** — the median observed κ-filtered value for
that (τ,axis) — so the bar is realistic, not a magic number. Axes with no κ-evidence are
still *probed* with a nominal threshold; the point of H2 is that such a binding is
undecidable *for lack of evidence*, whatever the number.

> **Completion bounding, stated plainly.** "Across all completions" is bounded
> best-/worst-case: a pending candidate is optimistically feasible-and-cheapest, a ⊥-cost
> candidate optimistically costs 0 (costs are non-negative). DECIDABLE therefore requires a
> *sure* winner that *no* optimistic completion of any rival can beat. This is the §8.6
> characterization made operational: **decidable ⇔ every binding axis is certifiable from
> the regime** (`bind(q) ⊆ cl(R)`).

**Honest scope.** The query *distribution* is a hand-built grid, **not yet** the
ZenML/MedHELM-justified prior the master plan requires (constraint C8; open gate Q2). The
fractions below are "decidability of this structured battery," not "of real deployment
traffic." Thresholds are grounded; the mixture over queries is not.

---

## 3. Results

### H1 — Most right-sizing queries are underdetermined (headline)

Pooled over the 42-query grid (φ=point, κ=H+M):

| Regime | decidable | underdetermined | infeasible |
|---|---|---|---|
| `accuracy_only` | **0.000** | **1.000** | 0.000 |
| `full` (all 8 axes) | **0.143** (6/42) | **0.857** (36/42) | 0.000 |

Averaged over all 18 (τ × regime) cells: **decidable 0.107, underdetermined 0.893,
infeasible 0.000.** Even handing the rule *every* axis the substrate has, **~86% of the
battery stays underdetermined**, and under a leaderboard-style accuracy-only regime it is
**100%**. Per archetype at the full regime:

| τ | decidable | underdetermined | 95% CI (underdetermined) |
|---|---|---|---|
| function-calling (BFCL, 109 cfg) | 0.429 (6/14) | 0.571 (8/14) | [0.286, 0.786] |
| general-qa (HELM, 31 cfg) | 0.000 | **1.000** | [1.000, 1.000] |
| inference-serving (MLPerf+ML.ENERGY, 42 cfg) | 0.000 | **1.000** | [1.000, 1.000] |

Only function-calling — the one archetype with quality **and** cost **and** latency
populated — ever becomes decidable, and only on 6 of its 14 queries. The two archetypes
missing a *measurable objective or constraint axis* (general-qa has no cost; inference-serving
has no cost and no quality) are **uniformly underdetermined with a tight CI**: the missingness
is not bootstrap noise, it is structural.

> **HONEST (Q2).** This is the decidability profile of a *structured grid*, not of the
> ZenML/MedHELM query prior. The headline "~86% underdetermined" is conditional on that grid.

### H2 — Structural blind spots, and *fragmentation* of the measurable axes

**Descriptive miss-rate** (fraction of configs with zero κ=H+M observation on an axis;
direct-DB read, descriptive provenance — does **not** feed any verdict):

| axis | overall miss-rate | general-qa | function-calling | inference-serving |
|---|---|---|---|---|
| quality | 0.231 | 0.00 | 0.00 | **1.00** |
| latency_p95 | 0.170 | 1.00 | 0.00 | 0.00 |
| throughput | 0.769 | 1.00 | 1.00 | 0.00 |
| cost | 0.401 | **1.00** | 0.00 | **1.00** |
| energy | 0.813 | 1.00 | 1.00 | 0.19 |
| **memory_hw** | **1.000** | 1.00 | 1.00 | 1.00 |
| **governance** | **1.000** | 1.00 | 1.00 | 1.00 |
| **reviewer_burden** | **1.000** | 1.00 | 1.00 | 1.00 |

Two findings, both load-bearing for the §5 "structured missingness" claim:

1. **Three axes are 100% bottom across every source** — `memory_hw, governance,
   reviewer_burden`. These are exactly the §1 hard-to-observe axes `A_h`. Any query binding
   on them is underdetermined *by construction of the evidence base*, not by sampling luck.
   This is the C1 finding in its sharpest form: *governance/reviewer-burden are absent to
   the point of being un-checkable, so a decision that binds on them cannot be validated at
   all* — and the right answer is to **abstain**, not impute (`⊥` stays `⊥`, C7).

2. **The measurable axes are FRAGMENTED across sources — no single config spans them.**
   function-calling has {quality, latency, cost, throughput-partial} but no energy;
   inference-serving has {latency, throughput, energy} but **no cost and no quality**;
   general-qa has {quality, latency} but no cost/energy/throughput. There is **no config
   that simultaneously carries quality AND cost AND energy**. So even a *cross-axis binding*
   query over nominally-measurable axes (e.g. quality+energy, or anything cost-bound in
   inference-serving) is underdetermined — the evidence exists in the corpus but never
   *co-located on a candidate*.

The classifier's `blocking_axes` confirm the mechanism. The dominant blocker is **cost**: it
blocks **all 14 queries** in general-qa and inference-serving (cost ⊥ for those sources → the
min-cost objective is itself unknown), and `quality` blocks 5 queries in inference-serving.
The persistent tail across *every* archetype is `governance, reviewer_burden, memory_hw,
energy` — the structural blind spots.

> **Tie to the §8.2 gadget.** This is the limit theorem's two-world gadget realized on real
> data. inference-serving with a cost-bound query is `R = {throughput, latency, energy}`,
> binding axis `cost ∉ R` (and ∉ `cl(R)` — cost is not a known function of throughput here):
> two configs identical on the observed axes but with different true costs are
> **observationally identical under E**, so *every* E-restricted rule must act the same while
> the optima differ. Off-regime (here off-*evidence*) binding ⇒ **irreducible
> underdetermination**, not a data-collection bug.

### H3 — Sensitivity to confidence policy κ

Underdetermined fraction averaged over all (τ × regime) cells, re-grounding thresholds per κ:

| κ policy | decidable | underdetermined |
|---|---|---|
| **H only** | 0.000 | **1.000** |
| **H + M** (default) | 0.107 | 0.893 |
| **H + M + L** | 0.107 | 0.893 |

The finding **survives** the sensitivity sweep — it is never weaker than 0.893
underdetermined. Tightening to H-only (measured evidence alone; 478 of 3392 obs) pushes the
map to **fully underdetermined**: the decidable cases in function-calling rest on M-tier
(leaderboard/paper-reported) cost and latency values, which the H-only policy filters out.
Loosening to admit L (vendor-doc / paper-estimated) adds **no** decidability — the L
observations land on axes that are already populated or already blocked, so they don't
unblock a single query. The blind spots are not a confidence-threshold artifact.

### Regime-ladder effect — the empirical shadow of the limit theorem (§8.5 / §8.7)

For the one archetype that moves, **decidability rises monotonically as the regime grows**:

| regime (function-calling) | decidable | 95% CI |
|---|---|---|
| accuracy_only ({quality}) | 0.000 | [0.000, 0.000] |
| acc_cost (+cost) | 0.214 | [0.000, 0.429] |
| acc_cost_latency (+latency) | 0.429 | [0.214, 0.714] |
| acc_cost_lat_throughput | 0.429 | [0.214, 0.714] |
| plus_energy | 0.429 | [0.214, 0.714] |
| full | 0.429 | [0.214, 0.714] |

The jumps are exactly where a previously-blind binding axis enters the regime: **+cost
unblocks the objective** (0→0.214), **+latency unblocks the latency-bound queries**
(0.214→0.429), and the ladder then **plateaus** — adding throughput/energy/governance buys
nothing because no further query's binding axis becomes certifiable (and governance/burden
are ⊥ regardless of regime). This is `decidable ⇔ bind(q) ⊆ cl(R)` (§8.6) read off real
data: each rung admits an axis, and decidability climbs *only* for queries whose binding
axis that rung supplies. general-qa and inference-serving never move off 1.000
underdetermined at any rung — their binding axis (cost; cost+quality) is absent from the
*evidence*, so no regime within the substrate can recover it (`Δ(R) > 0` for all R here).

---

## 4. Relation to claims

- **Empirical anchor of C1.** C1 = "on a real deployment-query distribution, many
  right-sizing decisions are not evidence-decidable, because of *structured* (non-random)
  missingness." DV1 here delivers the decidability map (≥86% underdetermined at the full
  regime; 100% under accuracy-only) **and** the structuredness: 3 axes globally ⊥, the
  measurable axes fragmented so no config spans them, miss-rate concentrated on the *same*
  axes across sources (governance/burden/memory 1.000 everywhere). Missingness being
  structured — not random — is the load-bearing half (P0 §5), and the per-axis miss-rate
  table is its direct evidence.

- **Empirical-confirmation slot for the limit theorem (§11).** The regime-ladder
  monotonicity and the cost-blocks-everything pattern are the *empirical shadow* of the §8.5
  bound `E[regret] ≥ c·Δ(R)` and the §8.7 identity `VoI(a*) = Δ(R)`: a regime missing the
  binding axis cannot identify the decision (decidable=0 for general-qa/inference-serving),
  and admitting the binding axis is exactly what flips queries to decidable (function-calling
  ladder). This is empirical *confirmation*, **never a corollary** of the theorem (§8.8
  discipline).

- **What this does NOT yet show.** It quantifies that decisions are *underdetermined*; it
  does **not** show that a leaderboard rule that commits anyway *mis-sizes* by a measurable
  margin. Decision regret + hidden-violation magnitude (DV2/DV3, C2) are **P5**. P3 is the
  "many decisions are undecidable" half; the "and answering them anyway hurts, measurably"
  half is validation. Per §18.2: P3 alone is not an Oral.

---

## 5. Limitations / open gates

1. **Query-distribution grounding (Q2, C8).** The 42-query battery is a structured grid with
   percentile-grounded *thresholds* but a *hand-built mixture*. The headline fractions are
   "decidability of this grid," not of real ZenML/MedHELM traffic. Until the prior is
   justified, H1's exact percentages are illustrative; H2's structural facts (which axes are
   ⊥, fragmentation) are distribution-independent and robust.
2. **Binding-axis operationalization (Q2).** We approximate `bind(q)` by the constrained
   axes plus the cost objective. The §8.6 closure `cl(R)` (e.g. energy as a known function of
   latency×power under fixed hardware) is **not** yet exploited — so we may *under*-count
   decidability where a closure map exists. Making `bind(q)` and `cl(R)` first-class is P3/P4
   work.
3. **φ=interval vs point.** All numbers are φ=point, the *conservative* (decidability-
   over-stating) reading. φ=interval would add a straddle band and can only **raise**
   underdetermination — the reported ~86% is a floor. The interval re-run is a cheap robustness
   check and belongs in the ablation.
4. **Two distinct underdetermination causes are currently pooled.** "cost ⊥ ⇒ objective
   unknown" (inference-serving/general-qa: cost blocks all 14) is *objective-bottom*
   underdetermination; "a bound axis is ⊥/straddles" (governance, energy) is
   *constraint-bottom*. They have different fixes (acquire cost evidence vs acquire the
   binding axis) and should be reported as separate columns — the map currently labels both
   UNDERDETERMINED. Splitting them sharpens the VoI story for P4.
5. **Noisy-interval / multi-submitter sources.** ML.ENERGY and BFCL pool observations from
   multiple submitters under heterogeneous context; φ=point takes the median, but commensability
   (C6 context match) is not enforced inside a cell. For multi-submitter axes this can make a
   belief artificially present or artificially wide; the κ filter mitigates but does not
   resolve it.

---

## 6. Key numbers the paper will cite

- **Underdetermined fraction ≈ 0.86** at the full (all-8-axis) regime over the structured
  grid (36/42); **0.89** averaged over all regimes; **1.00** under an accuracy-only
  (leaderboard) regime.
- **Decidable = 0** for general-qa and inference-serving at **every** regime (95% CI
  [1.00,1.00] underdetermined); only function-calling reaches **0.429** decidable, and only
  at +cost+latency.
- **Three axes 100% bottom across all sources:** `memory_hw, governance, reviewer_burden`
  (miss-rate 1.000). `energy` 0.813, `throughput` 0.769, `cost` 0.401 overall.
- **No config spans quality ∧ cost ∧ energy** — the measurable axes are fragmented; cost is
  the single most frequent blocker (all 14 queries in two of three archetypes).
- **κ-robust:** underdetermined never below **0.893** across κ ∈ {H, H+M, H+M+L}; H-only ⇒
  **1.000** (the decidable cases depend on M-tier cost/latency evidence).
- **Regime-ladder monotonicity (function-calling):** 0.000 → 0.214 (+cost) → 0.429
  (+latency) → plateau — the empirical shadow of `decidable ⇔ bind(q) ⊆ cl(R)` (§8.6) and
  `VoI(a*) = Δ(R)` (§8.7).
- Substrate: **182 configs, 3392 observations** (478 H / 2666 M / 248 L), **5/8 axes**
  carry any evidence.
