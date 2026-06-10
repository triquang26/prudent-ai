# 5. Findings: The Decidability Map (Claim C1)

This section establishes the empirical anchor of **Claim C1**: *on the distribution of
right-sizing queries one would actually pose to deployment evidence, many decisions are not
evidence-decidable, and the cause is **structured** — not random — missingness.* We
instantiate the dependent variable **DV1** (decidability) as a map over
`{archetype τ × evidence-regime R × confidence κ}`, report it first over a structured query
grid and then over a query distribution derived from **1716 real LLM deployments**, and
characterize the structural blind spots that make the result irreducible rather than a
data-collection artifact.

All numbers below are reproduced from the P3 findings (`docs/P3_decidability_map.md`,
`docs/P3_empirical_query_prior.md`). Unless stated otherwise the aggregation is **φ=point**,
confidence policy **κ=H+M**, with 95% percentile bootstrap CIs (n=1000, deterministic seed).

## 5.1 Setup and the decidability question

The substrate is a frozen snapshot of `data/apt_substrate.db`: **182 configurations** over
three evidence-source archetypes — function-calling (109 BFCL configs), inference-serving
(42 MLPerf + ML.ENERGY configs), and general-qa (31 HELM configs) — carrying **3392
observations** (478 high-confidence / 2666 medium / 248 low). Crucially, **only 5 of 8
right-sizing axes carry any evidence at all** (`quality, latency_p95, throughput, cost,
energy`); the remaining three — `memory_hw, governance, reviewer_burden` — are ⊥ (bottom,
unobserved) everywhere in the corpus.

DV1 asks, for a query `q = (τ, c)` that binds a set of axes:

> Of the right-sizing queries one would actually pose, what fraction are evidence-**decidable**,
> **underdetermined**, or **infeasible-under-E** — as a function of archetype, evidence regime,
> and confidence policy?

A query is **decidable** iff the evidence identifies the minimum-sufficient configuration:
some candidate is *provably feasible and fully costed*, and its `argmin cost` is invariant
across every completion `Comp(E)` of the missing or straddling cells (P0 §5). It is
**underdetermined** iff a ⊥ or straddling field could flip the argmin (non-identifiability),
and **infeasible-under-E** iff no candidate is provably feasible across all completions. This
is a different measurement from benchmark precision: sharpening the point estimate (more rows,
tighter intervals) does not answer *when E suffices to identify the decision*. The
classifier respects the **C7 firewall** — every verdict reads the substrate only through
`classify_query → classify_candidate → aggregate` over `candidates(τ) / cell(x,a)`; the only
direct-DB read is the **descriptive** blind-spot miss-rate of §5.3, which never feeds a verdict.

The evidence regimes form the **regime ladder** (the §16 independent variable), an
inclusion chain of axis sets a rule is allowed to see:
`accuracy_only → acc_cost → acc_cost_latency → acc_cost_lat_throughput → plus_energy → full`.
A rule restricted to regime `R` is *blind* to any axis `a ∉ R`: off-regime cells are treated
as ⊥ regardless of what the substrate actually holds. The conservative choice of φ=point (no
straddle band) means the map can only **over**-state decidability, so every underdetermination
fraction we report is a **lower bound**.

## 5.2 DV1 over the structured grid

We first measure DV1 over a structured query battery: for each τ, one single-axis bind per
axis (8 queries) plus 6 curated realistic 2-axis bundles (e.g. quality+cost, quality+latency,
quality+energy, throughput+energy, quality+governance), totalling **14 queries/τ, 42 queries**.
Thresholds are **percentile-grounded** — the median observed κ-filtered value for that
(τ, axis) cell — so the bar is realistic rather than a magic number; axes with no evidence
are still *probed* (the point being that such a binding is undecidable *for lack of evidence*,
whatever the number).

Pooled over the grid:

| Regime | decidable | underdetermined | infeasible |
|---|---|---|---|
| `accuracy_only` | **0.000** | **1.000** | 0.000 |
| `full` (all 8 axes) | **0.143** (6/42) | **0.857** (36/42) | 0.000 |

Averaged over all 18 (τ × regime) cells: **decidable 0.107, underdetermined 0.893,
infeasible 0.000**. Even when the rule is handed *every* axis the substrate holds, **~86% of
the battery remains underdetermined**; under a leaderboard-style accuracy-only regime it is
**100%**.

The per-archetype breakdown at the full regime shows the missingness is structural, not
noise:

| τ | decidable | underdetermined | 95% CI (underdetermined) |
|---|---|---|---|
| function-calling (BFCL, 109 cfg) | 0.429 (6/14) | 0.571 | [0.286, 0.786] |
| general-qa (HELM, 31 cfg) | 0.000 | **1.000** | [1.000, 1.000] |
| inference-serving (MLPerf+ML.ENERGY, 42 cfg) | 0.000 | **1.000** | [1.000, 1.000] |

Only function-calling — the single archetype with quality *and* cost *and* latency populated
— ever becomes decidable, and only on 6 of its 14 queries. The two archetypes missing a
measurable objective or constraint axis (general-qa has no cost; inference-serving has neither
cost nor quality) are **uniformly underdetermined with a degenerate CI**: `[1.000, 1.000]` is
not bootstrap noise, it is the signature of a structural gap.

We are explicit (open gate **Q2** of the P3 map) that this is the decidability profile of a
*hand-built grid*: the thresholds are grounded but the mixture over queries is one we chose,
so the exact 86% is "decidability of this grid," not of real deployment traffic. §5.6 closes
that gap.

## 5.3 Structural blind spots and fragmentation of the measurable axes

The decidability result is driven by *which* axes are missing, and missingness is far from
uniform. The descriptive miss-rate (fraction of configs with zero κ=H+M observation on an
axis; a direct-DB read, descriptive provenance, feeding no verdict) is:

| axis | overall | general-qa | function-calling | inference-serving |
|---|---|---|---|---|
| quality | 0.231 | 0.00 | 0.00 | **1.00** |
| latency_p95 | 0.170 | 1.00 | 0.00 | 0.00 |
| throughput | 0.769 | 1.00 | 1.00 | 0.00 |
| cost | 0.401 | **1.00** | 0.00 | **1.00** |
| energy | 0.813 | 1.00 | 1.00 | 0.19 |
| **memory_hw** | **1.000** | 1.00 | 1.00 | 1.00 |
| **governance** | **1.000** | 1.00 | 1.00 | 1.00 |
| **reviewer_burden** | **1.000** | 1.00 | 1.00 | 1.00 |

Two facts carry the C1 structuredness argument.

**(1) Three axes are 100% bottom across every source** — `memory_hw, governance,
reviewer_burden`. These are exactly the hard-to-observe axes `A_h`. Any query that binds on
them is underdetermined *by construction of the evidence base*, not by sampling luck. This is
C1 in its sharpest form: governance and reviewer-burden are absent to the point of being
un-checkable, so a decision that binds on them **cannot be validated at all** — and the
correct response is to **abstain**, not impute (`⊥` stays `⊥`, C7).

**(2) The measurable axes are fragmented across sources — no single config spans them.**
function-calling carries {quality, latency, cost, partial-throughput} but no energy;
inference-serving carries {latency, throughput, energy} but **neither cost nor quality};
general-qa carries {quality, latency} but no cost/energy/throughput. There is **no
configuration that simultaneously carries quality ∧ cost ∧ energy**. Consequently even a
cross-axis query over *nominally measurable* axes (quality+energy, or anything cost-bound in
inference-serving) is underdetermined: the evidence exists somewhere in the corpus but is
never *co-located on a candidate*. The classifier's `blocking_axes` confirm the mechanism —
**cost** is the dominant blocker (it blocks all 14 queries in both general-qa and
inference-serving, because a ⊥ cost makes the min-cost *objective itself* unknown), with
`quality` blocking 5 queries in inference-serving and a persistent tail of
`governance, reviewer_burden, memory_hw, energy` across every archetype.

This is the limit-theorem two-world gadget (§8.2) realized on real data: an inference-serving
cost-bound query has `R = {throughput, latency, energy}` while the binding axis `cost ∉ cl(R)`,
so two configs identical on the observed axes but with different true costs are
**observationally identical under E**. Every E-restricted rule must act the same while the
true optima differ — off-evidence binding yields **irreducible underdetermination**, not a
data-collection bug.

## 5.4 Robustness to the confidence policy κ

The finding survives tightening or loosening the confidence filter. Re-grounding thresholds
per κ and averaging over all (τ × regime) cells:

| κ policy | decidable | underdetermined |
|---|---|---|
| **H only** | 0.000 | **1.000** |
| **H + M** (default) | 0.107 | 0.893 |
| **H + M + L** | 0.107 | 0.893 |

Underdetermination is **never below 0.893** across the sweep. Tightening to H-only (measured
evidence alone, 478 of 3392 observations) pushes the map to **fully underdetermined**: the
decidable function-calling cases rest on M-tier (leaderboard/paper-reported) cost and latency
values, which H-only filters out. Loosening to admit L (vendor-doc / paper-estimated) adds
**no** decidability — the extra observations land on axes that are already populated or already
blocked, unblocking no query. The blind spots are not a confidence-threshold artifact.

## 5.5 The regime ladder — empirical shadow of the limit theorem

For the one archetype that moves, decidability rises **monotonically** as the regime grows,
then plateaus (function-calling):

| regime | decidable | 95% CI |
|---|---|---|
| accuracy_only ({quality}) | 0.000 | [0.000, 0.000] |
| acc_cost (+cost) | 0.214 | [0.000, 0.429] |
| acc_cost_latency (+latency) | 0.429 | [0.214, 0.714] |
| acc_cost_lat_throughput | 0.429 | [0.214, 0.714] |
| plus_energy | 0.429 | [0.214, 0.714] |
| full | 0.429 | [0.214, 0.714] |

The jumps land **exactly** where a previously-blind binding axis enters the regime: **+cost
unblocks the objective** (0 → 0.214), **+latency unblocks the latency-bound queries**
(0.214 → 0.429), and the ladder then **plateaus** — adding throughput, energy, or governance
buys nothing, because no further query's binding axis becomes certifiable (and
governance/reviewer-burden are ⊥ at every rung). This reads `decidable ⇔ bind(q) ⊆ cl(R)`
(P0 §8.6) directly off the data, and is the empirical **shadow** of the limit bound
`E[regret] ≥ c·Δ(R)` (§8.5) and the identity `VoI(a*) = Δ(R)` (§8.7). general-qa and
inference-serving never leave 1.000 underdetermined at any rung — their binding axis (cost;
cost+quality) is absent from the *evidence*, so `Δ(R) > 0` for every reachable regime. We
treat this as empirical *confirmation*, **never a corollary** of the theorem (§8.8 discipline).

## 5.6 DV1 on real traffic: the empirical query prior (closing Q2)

The structured-grid headline carries the explicit caveat that the *mixture over queries* was
hand-chosen. Constraint C8 of the master plan demands a *justified* distribution. We close
this gap (the distribution-level form of open gate Q2) by deriving the query prior from
`zenml/llmops-database` — **1716 real LLM-deployment case studies**, taken as a frozen
snapshot (C3). Each case study becomes exactly one query via a documented, auditable
tag→axis taxonomy (e.g. `cost_optimization → cost`, `regulatory_compliance → governance`,
`human_in_the_loop → reviewer_burden`, `internet_of_things → memory_hw`), plus a
regulated-industry rule binding `governance` for Healthcare/Finance/Legal/Insurance/Government,
and a universal `quality` floor. Critically, `throughput` and `energy` are **never** bound
from a tag — no tag signals them cleanly, so we leave them ⊥-able rather than fabricate a
binding (`⊥` stays `⊥`, C1/C7). Everything else — substrate, solver, three-state classifier,
completion-flip rule, regime ladder, C7 firewall — is **identical** to the structured-grid
run, so any delta is attributable purely to grounding the prior.

**The empirical prior.** Real traffic is dominated by QA-shaped workloads (general-qa
**71.0%**, function-calling **24.9%**, inference-serving **4.1%**), and the axis-binding
frequencies expose the core tension:

| axis | n deployments binding it | fraction | measurable in substrate? |
|---|---|---|---|
| quality | 1716 | 100.0% | yes |
| governance | 954 | **55.6%** | **⊥ everywhere** |
| latency_p95 | 804 | 46.9% | yes (not in general-qa) |
| reviewer_burden | 751 | **43.8%** | **⊥ everywhere** |
| cost | 709 | 41.3% | yes (not general-qa / inference-serving) |
| memory_hw | 20 | 1.2% | ⊥ everywhere |

The load-bearing fact: **more than half of real deployments (55.6%) bind `governance` and
~44% bind `reviewer_burden` — both axes the evidence corpus is 100% silent on.** A majority of
real traffic constrains on exactly the axes the entire evidence base cannot check. Because
`throughput`/`energy` are never bound by construction, the true off-evidence binding load is
at least this large.

**Real-traffic decidability (DV1, n=1716):**

| regime | %decidable (95% CI) | %underdetermined (95% CI) | dominant blocking axes |
|---|---|---|---|
| `accuracy_only` | 0.0% [0.0, 0.0] | **100.0%** [100.0, 100.0] | cost(1716), governance(954), latency(804), reviewer_burden(751) |
| `acc_cost` | 5.2% [4.2, 6.2] | 94.8% [93.8, 95.8] | cost(1289), governance(954), latency(804), reviewer_burden(751) |
| `acc_cost_latency` | 8.9% [7.6, 10.3] | **91.1%** [89.7, 92.4] | cost(1289), governance(954), reviewer_burden(751), latency(557) |
| `full` (all 8 axes) | 8.9% [7.6, 10.3] | **91.1%** [89.7, 92.4] | cost(1289), governance(954), reviewer_burden(751), latency(557) |

**Headline.** On real deployment traffic, **91.1% of right-sizing queries (1563/1716) stay
underdetermined even when the rule is handed every axis the substrate measures**, and
**100% are underdetermined under an accuracy-only (leaderboard) regime**. Decidability tops
out at **8.9%** (153/1716) and reaches that ceiling already at `acc_cost_latency`; adding
throughput, energy, or governance buys nothing — the same monotonic-then-plateau ladder as
§5.5, now `0.0% → 5.2% (+cost) → 8.9% (+latency) → plateau`, the limit-theorem shadow read
off real traffic.

## 5.7 Attribution: the sharp form of C1

Decomposing *why* the 1563 underdetermined queries are undecidable at the full regime:

- **72.4%** (1243/1716) of **all** queries are underdetermined **because at least one binding
  axis is unmeasurable corpus-wide** — the unmeasurable set being
  `{energy, governance, memory_hw, reviewer_burden, throughput}`. For these, the decision
  cannot be made not for lack of *in-regime* evidence but because the constraint lives on an
  axis the **entire** evidence corpus is silent on.
- **16.0%** (274/1716) are underdetermined where **every** blocking axis is unmeasurable — the
  strictest reading: nothing in any reachable regime could ever decide them.
- Blocking-axis frequency among underdetermined queries: `cost 1289, governance 954,
  reviewer_burden 751, latency_p95 557, quality 70, memory_hw 20`.

This is C1 in its sharpest, real-traffic form: the majority of real deployment decisions bind
on an axis that is **un-checkable**, so committing to a recommendation cannot be validated at
all. The right answer is to **abstain and name the missing axis**, not impute.

## 5.8 Robustness of the taxonomy, and grid vs. real traffic

**Tag→axis robustness.** A drop-one-mapping sensitivity (baseline 91.1% underdetermined)
leaves the finding intact under every single deletion:

| dropped mapping | %underdetermined | Δ vs baseline |
|---|---|---|
| `latency_optimization` | 91.1% | 0.0% |
| `cost_optimization` | 91.1% | 0.0% |
| `regulatory_compliance` → governance | 90.0% | −1.0% |
| `high_stakes_application` → governance | 90.1% | −1.0% |
| `human_in_the_loop` → reviewer_burden | **83.2%** | **−7.9%** |
| regulated-industry → governance rule | 90.6% | −0.5% |

Every drop leaves underdetermination **above 83%**. The single most influential mapping is
`human_in_the_loop → reviewer_burden` (−7.9%), as expected since `reviewer_burden` binds
43.8% of traffic and is ⊥ everywhere — yet even removing it entirely, the headline survives at
**83.2%**. No single mapping choice is load-bearing; the result is a property of the corpus,
not of one rule (C8 robustness).

**Prior-robustness: the headline is not an artifact of the ZenML corpus (W3).** The drop-one
ablation perturbs the *taxonomy* but keeps the ZenML query distribution. Mock-review W3 raised the
deeper objection that the 91.1% headline is an artifact of that single corpus. We answer it by
**rebuilding the headline under independent, non-ZenML priors** that strip every plausible ZenML
bias, classified through the *identical* C7 path (`classify_query`, FULL regime, κ=H+M, φ=point) over
`CachedSubstrate(Substrate('data/apt_substrate.db'))`, battery 1716/prior, seed=12345 — verbatim
from `outputs/p3/prior_robustness.{json,md}`. The recomputed ZenML reference reproduces **91.1%**
exactly, so the comparison is apples-to-apples.

| prior | %underdetermined | Δ vs ZenML 91.1% | % attributable to a ⊥-axis | survives? |
|---|---|---|---|---|
| **ZenML (reference)** | 91.1% | — | 72.4% | — |
| Uniform (every axis p=0.5) | **98.5%** | +7.4% | 94.2% | **YES** |
| Adversarial governance-light (gov/rev p=0.05) | **95.7%** | +4.6% | 84.5% | **YES** |
| Benchmark-derived (∝ substrate coverage) | 12.4% | −78.7% | 0.0% | *control* |

The headline **survives every non-control prior**: a large majority of queries stay underdetermined,
and the *majority of that underdetermination is attributable to a blind-spot (corpus-wide ⊥) axis* —
**even the adversarial prior that assumes governance/reviewer_burden almost never bind** (95.7%
underdetermined, 84.5% ⊥-attributable). So 91.1% is **not** an artifact of the ZenML prior; it is a
property of the substrate's coverage — the evidence corpus is silent on the axes real (or synthetic)
deployments bind on. The **benchmark-derived prior is a deliberate negative control**: when the prior
demands *only what the corpus actually measures*, underdetermination collapses to **12.4%** and **0%**
is ⊥-attributable. That is the causal mechanism stated in reverse — remove the demand for
un-measured axes and the decisions become decidable — so the control **confirms** the causal story
rather than refuting the headline.

**Grid vs. empirical.** Grounding the prior does not merely preserve the finding — it
**sharpens** it:

| query source | n | %underdetermined (full regime) |
|---|---|---|
| P3 hand grid | 42 | 85.7% |
| **empirical prior** | **1716** | **91.1%** |

**Δ = +5.4%.** The hand grid, by spreading queries uniformly (one bind per axis per τ),
*under*-weighted the off-evidence axes that real traffic actually loads (governance 55.6%,
reviewer_burden 43.8%). Real deployments bind the un-checkable axes more often than a uniform
grid does, so real-traffic underdetermination is **higher**, not lower. The qualitative claim
— most right-sizing decisions are evidence-underdetermined — is, if anything, *conservative*
relative to real traffic.

## 5.9 Honesty: scope and the per-instance-binding open question

Three honest qualifications bound the strength of this section.

**Structured grid vs. ZenML prior.** §5.2 and §5.6 measure DV1 over two different
distributions. The grid's exact 85.7% is "decidability of this grid"; the real-traffic 91.1%
is the C8-justified claim. We report both and rely on the empirical prior for the headline.
The *structural* facts of §5.3 — which axes are ⊥, the fragmentation, the corpus-wide blind
spots — are **distribution-independent** and hold under either reading.

**Distribution-level Q2 closed, per-instance binding still open.** A deployment tag is
evidence that an axis is *declared a hard requirement* — a conservative over-approximation of
`bind(q)`, the set of axes *active at the optimum* (P0 §1). We close Q2 at the **distribution**
level (where the query mixture comes from), not at the **per-instance** level (does this tag
truly bind at *this* deployment's optimum, or is it merely salient?). Recovering `bind(q)`
first-class — from the constraint bundle *and* the observed Pareto structure — remains the
deeper Open-Q2 (§11) and is P3/P4 work. The distribution-level claim does not depend on
resolving it, because the decisive off-evidence axes are ⊥ in *every* τ regardless of how the
per-instance binding resolves.

**What this section does NOT show.** It quantifies that real decisions are *underdetermined*;
it does **not** show that a leaderboard rule that commits anyway *mis-sizes by a measurable
margin*. Decision regret and hidden-violation magnitude (DV2/DV3, Claim C2) are P5 validation.
Two further caveats are inherited: φ=point is the decidability-over-stating reading, so 91.1%
is a **floor**; and the *measured* prior is ZenML-only — MedHELM returned HTTP 401 at snapshot
time, and a medical/high-governance corpus would, if anything, *raise* the already-55.6%
governance load. The "single-corpus" worry is directly addressed in §5.8: rebuilding the headline
under **independent synthetic priors** (Uniform, adversarial governance-light) keeps it ≥ 95.7%, so
the result is not a ZenML artifact — it is a property of the substrate's coverage. P3 owns the "many
real decisions are undecidable" half of the thesis; "and answering them anyway hurts, measurably" is
owned by P5.

## 5.10 Summary of headline numbers

- **Substrate:** 182 configs, 3392 observations (478 H / 2666 M / 248 L); **5/8 axes** carry
  any evidence.
- **Empirical prior:** **1716** real LLM deployments (`zenml/llmops-database`, frozen
  snapshot). τ split: general-qa 71.0%, function-calling 24.9%, inference-serving 4.1%.
- **Structured grid:** **85.7%** underdetermined at the full regime (36/42); **89.3%**
  averaged over all regimes; **100%** under accuracy-only.
- **Real traffic:** **91.1%** underdetermined at the full regime (1563/1716); **100%** under
  accuracy-only; decidability tops out at **8.9%** (153/1716).
- **Structural blind spots:** `memory_hw, governance, reviewer_burden` 100% ⊥ across all
  sources; no config spans `quality ∧ cost ∧ energy`; cost is the most frequent blocker.
- **Off-evidence binding load:** governance binds **55.6%** and reviewer_burden **43.8%** of
  real traffic, both 100% ⊥ in the corpus.
- **Attribution:** **72.4%** of all queries underdetermined because a binding axis is
  unmeasurable corpus-wide; **16.0%** blocked *only* by unmeasurable axes.
- **Robustness:** underdetermination ≥ **0.893** across κ ∈ {H, H+M, H+M+L} (H-only ⇒ 1.000);
  ≥ **83.2%** under any single tag→axis drop; grid→empirical Δ = **+5.4%** (grounding sharpens).
- **Prior-robustness (W3):** the 91.1% headline **survives independent non-ZenML priors** — Uniform
  **98.5%** (+7.4%), Adversarial governance-light **95.7%** (+4.6%), each majority-⊥-attributable;
  the benchmark-derived negative control collapses to **12.4%** (0% ⊥-attributable), confirming the
  causal mechanism. Not an artifact of the ZenML corpus.
- **Regime ladder:** monotonic-then-plateau — the empirical shadow of `decidable ⇔ bind(q) ⊆
  cl(R)` (§8.6) and `VoI(a*) = Δ(R)` (§8.7).
