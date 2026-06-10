# 1. Introduction

Every system that helps a practitioner choose how to deploy an LLM — which model, which
context length, which retrieval backend, which decoding budget — answers the same question:
*given a task and its constraints, what is the smallest sufficient configuration?* The
evaluation community has spent its effort making the **estimate** of each axis better. Holistic
benchmarks broaden the metrics measured per model; cost-aware agent harnesses add real dollars
and tokens to accuracy; reliability work makes LLM judges more trustworthy; routing and cascade
methods drive cost down under an objective the practitioner already observes. The tacit prior
behind all of it is that the frontier is *estimate quality*: a sharper belief about each axis
yields a better deployment decision. **We flip the prior question.** Before asking how precise
the belief about an axis is, we ask whether the deployment decision is **identified at all** from
the evidence that exists — whether *any* configuration is certifiably minimum-sufficient, or
whether a missing axis could flip the answer. The hook is one sentence: **the evidence we have
does not just leave right-sizing imprecise; it leaves right-sizing *underdetermined* — the
decision is not identifiable from the evidence, no matter how the present axes are sharpened.**

We make that intuition a measurement. A right-sizing query is **evidence-decidable** under a
corpus `E` iff some configuration is provably feasible and provably minimum-sufficient — its
`argmin cost` is invariant across every completion of the missing or straddling cells — and
**evidence-underdetermined** iff a missing axis could flip the optimum (§3). On a query prior
derived from **1716 real LLM-deployment case studies** (ZenML's LLMOps database), and reading a
frozen evidence substrate of 182 configurations over BFCL, MLPerf, ML.ENERGY and HELM (3392
provenance-tracked observations, 5 of 8 axes carrying any evidence at all), we find that **91.1%
of right-sizing queries stay underdetermined even when a rule is handed every axis the substrate
measures, and 100% are underdetermined under an accuracy-only (leaderboard) regime** (Claim C1).
Decidability tops out at 8.9% and reaches that ceiling already at accuracy+cost+latency: adding
throughput, energy, or governance to the regime buys *nothing*. This is not sampling noise — the
two archetypes lacking a measurable objective or constraint axis are 100% underdetermined with a
95% CI of [1.00, 1.00].

The cause is **structured missingness**, and it falls on exactly the axes that gate real
deployments. Three right-sizing axes — `governance`, `reviewer_burden`, `memory_hw` — are ⊥
(unobserved) across *every* source in the corpus, miss-rate 1.000. These are not exotic: more
than half of real deployments **bind** `governance` (55.6%) and 43.8% bind `reviewer_burden`,
and both axes are 100% silent in the entire evidence base. The structural form is sharper still:
72.4% of all real queries are underdetermined *because a binding axis is unmeasurable
corpus-wide*, and the measurable axes are themselves **fragmented** — no single configuration
carries quality *and* cost *and* energy together, so even a cross-axis query over nominally
measurable axes is underdetermined for lack of co-location. The right answer to such a query is
to **abstain and name the missing axis**, not to impute it; `⊥` stays `⊥`.

Diagnosis is not a method. We give a **selective right-sizing procedure** that acts on the
diagnosis: it **commits** the identified minimum-sufficient configuration when the query is
decidable, and otherwise **abstains informatively** — returning the blocking axis set and a
cost-aware Value-of-Information ranking that names the single field worth measuring next. The
acquisition is principled, not a heuristic: we prove that the implemented VoI of an omitted
binding axis equals the irreducible regret of the evidence regime that omits it,
**`VoI(a*) = Δ(R) = δλ/(δ+λ)`** exactly on the two-world gadget (Claim C3, pinned to
`rel_tol=1e-9` over four `(δ,λ)` points), tying the acquisition signal to a limit theorem: *no
regime-restricted rule can drive expected regret below `Δ(R)` when the binding axis lies outside
the regime.* Run blind over the 1716-query prior, the procedure commits on the 8.9% decidable
minority and abstains on 91.1%, and its acquisition budget lands **entirely** on the
corpus-wide-⊥ axes it was never told about (`cost` 82.5%, `reviewer_burden` 12.9%, `governance`
4.7%). It also carries a distribution-free coverage guarantee `P(feasible ∧ min-sufficient |
commit) ≥ 1−α`, whose Trust-or-Escalate–shaped coverage–risk curve makes the cost of reliability
literal: at α∈{0.05, 0.10} the committed slice has 0% risk but only ≈10% coverage — the guarantee
is purchasable only by escalating most traffic.

Underdetermination would be a curiosity if answering anyway were harmless; our **validation**
shows it is not. On ground-truth slices (BFCL function-calling and the per-benchmark RouterBench
slices where cost is model-comparable) we bind axes, mask one binding axis, let each rule commit
from the visible evidence, and score against the hidden truth. Across **28 H-confidence biting
slices and 476 queries with real measured ground truth** — RouterBench per-benchmark restrictions
auto-discovered from the substrate — current honest practice (**B2** observed-Pareto) and both its
standard defences — **B3** imputation ("just fill it in") and **B6** cost-accuracy (FrugalGPT-style)
— commit configurations that **silently violate the hidden constraint at a pooled hidden-violation
rate of 0.57** (per-slice 0.06–1.00), while the selective procedure abstains on exactly those
queries: hidden-violation **0.00**. The gap is significant **on the H-confidence ground-truth data
alone** — difference **0.57, 95% CI [0.53, 0.62]**, one-sided exact McNemar **p ≈ 0** (272 discordant
pairs, 0 against) — and the flagship does **not** depend on any medium-confidence data; folding the
M-confidence BFCL slice back in (29 biting slices, 493 queries) leaves it unchanged (gap **0.58
[0.54, 0.62]**, McNemar 287/0). Imputation does not rescue the case: B3's hidden-violation equals
B2's, refuting the "imputation solves it" objection with a number (Claim C2). The abstention pays
back: when the procedure names its VoI pick as the field to measure, un-masking it yields a correct
commit **100% of the time versus 20% for a random axis**. We report the no-bite controls
(mask-latency, where cheap⇒fast; the RouterBench cross-benchmark confound) alongside, so the claim
stays falsifiable: current practice mis-sizes *where multiple axes truly bind and cheap trades off
the hidden one*, not universally.

**Contributions.**
1. **A reframe and its measurement (C1).** We recast deployment right-sizing as an
   *identifiability* question — is the decision determined by the evidence, not is the estimate
   precise — and operationalize it as a three-state decidability map. On a query prior from 1716
   real LLM deployments we measure that **91.1% of right-sizing decisions are
   evidence-underdetermined** at the full evidence regime (100% under accuracy-only), a result
   that grounding the prior in real traffic *sharpens* rather than weakens (85.7% on a uniform
   grid → 91.1% on real traffic).
2. **The structural blind spots (C1, cont.).** We show the underdetermination is *structured*,
   not random: three deployment-gating axes (`governance`, `reviewer_burden`, `memory_hw`) are ⊥
   across the entire corpus while binding **55.6% / 43.8%** of real traffic respectively, the
   measurable axes are fragmented across sources, and 72.4% of queries are undecidable because a
   binding axis is unmeasurable corpus-wide — robust to the tag→axis taxonomy (≥83.2% under any
   single-mapping ablation) and to the confidence policy (≥89.3% across κ).
3. **A selective right-sizing method with an informative abstention and a guarantee (C3).** A
   three-state procedure (commit / abstain / infeasible) that, when it abstains, names the
   blocking axes and a cost-aware VoI-ranked acquisition plan, under a distribution-free coverage
   guarantee `P(feasible ∧ min-sufficient | commit) ≥ 1−α`. We prove the acquisition is anchored
   to a limit theorem: **`VoI(a*) = Δ(R) = δλ/(δ+λ)`** exactly, making the abstention's "measure
   this next" the theorem's irreducible-regret bound made operational. The procedure's *positive*
   action is validated too: across all 31 biting slices it commits **527** configs that are
   **100% feasible and 100% minimum-sufficient** (zero regret) against ground truth, and the
   min-sufficiency half of the guarantee is calibrated on real held-out GT via a two-sided band
   (test min-sufficiency-risk ≤ α).
4. **A falsification of current practice and the abstention's payoff (C2).** Across **28
   H-confidence biting slices (476 queries) with real measured ground truth**, observed-Pareto,
   imputation, and cost-accuracy hidden-violate at a pooled **0.57** while the selective procedure
   hidden-violates **0.0**; the gap **0.57 [0.53, 0.62]** is significant against both must-beat
   baselines (McNemar 272/0, p ≈ 0) **without relying on any medium-confidence data**, and at scale
   the VoI pick converts an abstention into a correct commit **527/527 (1.0)** vs **0.129** for a
   random axis (McNemar 459/0, p ≪ 0.05) — demonstrated with honest no-bite controls that keep the
   claim falsifiable. The biting axes are **certified binding per-instance** from Pareto structure
   (not declared from tags): the mis-sizing bite tracks active-constraint binding exactly
   (`bite ⟺ binding` agreement 1.0). The coverage guarantee holds against genuine full-sample
   measured ground truth (test feasibility-risk ≤ α at α∈{0.05, 0.10} on a held-out split).

All numbers in this paper are reproduced verbatim from frozen, seeded artifacts; the substrate is
read only through an immutable `candidates / cell / required_fields` interface (C7), and no
missing axis is ever imputed.
