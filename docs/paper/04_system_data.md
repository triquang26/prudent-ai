# 4 System and Data

The formulation of §3 demands a particular kind of evidence base: one that stores **observations
with provenance and context as the atomic unit**, derives $\bot$ from absence under a confidence
filter, and exposes nothing to the solver but raw observation sets. This section describes the
substrate that realizes those requirements, the immutable interface that enforces the
substrate$\,\leftrightarrow\,$solver separation, the public corpora ingested into it, and the
real-deployment query prior over which the decidability map is evaluated. Every count below is read
from the frozen snapshot `data/apt_substrate.db`.

## 4.1 The evidential substrate

The substrate is a relational store (SQLite via SQLAlchemy) whose schema is *forced* by the
observation model rather than chosen by preference. Four requirements of §3.3 dictate it directly,
and each maps onto a structural feature that a flat $(x, a) \mapsto \text{value}$ table cannot
express:

1. **The observation is the atomic unit.** A cell $(x, a)$ holds *many* observations, each carrying
   $\langle \text{value}, \text{confidence} \in \{H, M, L\}, \text{evidence\_id}, \text{source\_type},
   \text{context}\rangle$, so the storage unit is an observation row, not a point. The `observation`
   table is the substrate's center of gravity.
2. **Composition is first-class.** A configuration decomposes into reusable components with lineage
   (`component`, `config`, and a many-to-many `config_component` table), so component reuse and the
   provenance of a value are both expressible.
3. **Referential integrity is the provenance guarantee.** Every observation carries a foreign key
   `evidence_id` into a `source` table (`source_type`, `citation`, `snapshot_version`). The FK *is*
   the auditability constraint made executable: an observation cannot exist without a source it
   points to, so "$\exists$ source" is enforced at the storage layer rather than asserted in prose.
4. **$\bot$ via absence, queried under $\kappa$.** Missingness is not a stored boolean. A cell is
   $\bot$ under policy $\kappa$ iff $\mathrm{COUNT}(\text{observations with confidence} \in \kappa) = 0$,
   so the same cell can be present or missing depending on the filter — exactly the semantics §3.3
   requires.

Comparison context (metric, unit, dataset, split, hardware tier, decoding configuration, date) rides
on every observation so that commensurability is checkable rather than assumed. SQLite is chosen for
the reproducibility properties the research needs — zero-config, offline, snapshot-versioned — and
for nothing the solver depends on: all aggregation, certification, value-of-information, and
calibration live in a separate layer.

## 4.2 The immutable interface — the C7 firewall

The substrate exposes exactly three functions, and the contract that they are *all* it exposes is
fixed for the lifetime of the project (constraint C7); this immutability is what lets the solver be
swapped — lexicographic, chance-constrained, selective — without touching storage, and what makes
the decidability measurement a property of the evidence rather than of one solver's idiosyncrasies.

```text
candidates(τ)        → the set of configurations x ∈ X(τ), with components/lineage; no filtering by c
cell(x, a)           → O_E(x, a): the full observation set for the cell, every confidence level, untouched
required_fields(c)   → the axes the bundle c mentions; a pure syntactic function of c
```

The contract is **$\kappa$-free and $\varphi$-free**: the confidence filter, the aggregation mode,
the risk level $\alpha$, the three-state certifier, value-of-information, the coverage guarantee, and
the Pareto frontier are *all* solver-side. Two design notes are load-bearing. First,
`required_fields(c)` is **syntactic, not semantic** — it returns the axes that *appear* in the
bundle, $\{k.\text{axis} : k \in c\}$, never the axes that *bind* at the optimum; returning binding
axes would require the substrate to run the optimization and would collapse the firewall. The
blocking set $F$ that the selective procedure reports is then
$\text{required\_fields}(c) \cap \{a : \text{is\_missing}(x, a \mid \kappa)\}$, computed solver-side.
Second, the firewall is checked, not merely declared: an interface-invariance test asserts that two
different solvers issue a *byte-identical multiset of substrate calls* on the same query, so any leak
— a solver asking for $\kappa$-prefiltered cells, for *which* axes bind, or for an aggregated value
instead of the observation set — fails the test. Every result downstream reads the substrate only
through `candidates / cell / required_fields`; the sole direct-DB read is the descriptive
reportability map (a retrieve-and-filter query that surfaces the per-cell $\bot$ picture), which is
labelled descriptive and never feeds a verdict.

## 4.3 Ingested evidence regimes

The substrate is seeded from four public evaluation corpora, deliberately spanning regimes that
measure *different* axes, plus a high-confidence ground-truth slice. The frozen snapshot holds
**512 configurations** and **4 052 observations** (1 138 $H$ / 2 666 $M$ / 248 $L$), of which **only
five of the eight right-sizing axes carry any evidence** — `quality, latency_p95, throughput, cost,
energy` — while `memory_hw, governance, reviewer_burden` are $\bot$ across every source.

| Regime | $\tau$ | configs | axes populated | typical confidence |
|---|---|---|---|---|
| **HELM Lite** | general-qa | 31 | quality, latency_p95 | M (leaderboard) |
| **BFCL** | function-calling | 109 | quality, latency_p95, cost, throughput (partial) | M |
| **MLPerf** + **ML.ENERGY** | inference-serving | 42 | latency_p95, throughput, energy | M / measured |
| **RouterBench (GT slice)** | routerbench | 330 | quality, cost | H (measured) |

HELM Lite contributes general-QA leaderboard scores with latency; BFCL contributes the
function-calling regime that is the only one carrying quality *and* cost *and* latency together;
MLPerf and ML.ENERGY supply the serving regime with throughput and energy but **no cost and no
quality**; and the RouterBench slice — 405 467 raw records across 11 models and 8 datasets, reduced
to 330 configurations — supplies the H-confidence quality$\,\times\,$cost ground truth used by the
validation study. The fragmentation is the finding: per-axis miss-rates are 1.000 for all three
$A_h$ axes across every source, 0.813 for energy, 0.769 for throughput, and 0.401 for cost, and
**no single configuration simultaneously carries quality, cost, and energy** — so even a cross-axis
binding over nominally measurable axes is underdetermined because the evidence, though present in the
corpus, is never co-located on a candidate. The substrate snapshot used for the decidability map
proper is the 182-configuration core (109 BFCL + 31 HELM + 42 MLPerf/ML.ENERGY); the RouterBench
slice extends it to 512 configurations / 4 052 observations to furnish the masked ground truth that
the §5 validation requires.

## 4.4 The real-deployment query prior

A decidability fraction is only as meaningful as the query distribution it is averaged over. To avoid
reporting "the decidability of a grid we chose" (constraint C8), the query prior is grounded in real
traffic: **1 716 production LLM-deployment case studies** from `zenml/llmops-database`, taken as a
frozen snapshot. Each case study becomes exactly one query $q = (\tau, \mathrm{bind})$ of weight one,
and the multiset of 1 716 derived queries *is* the empirical prior.

The mapping from a case study to its binding axes is a documented, conservative **tag$\,\to\,$axis
taxonomy**: only tags with unambiguous axis semantics participate. `latency_optimization` and
`realtime_application` bind `latency_p95`; `cost_optimization` and `token_optimization` bind `cost`;
`regulatory_compliance`, `high_stakes_application`, `content_moderation`, and `fraud_detection` bind
`governance`; `human_in_the_loop` binds `reviewer_burden`; `internet_of_things` binds `memory_hw`. A
second, independent rule binds `governance` from the `industry` field for the regulated sectors
$\{\text{Healthcare, Finance, Legal, Insurance, Government}\}$, since those deployments carry
statutory obligations regardless of technique tags. Every deployment carries an implicit quality
floor, so `quality` binds universally. Two axes — `throughput` and `energy` — are *never* bound from
a tag, because no tag signals them cleanly; leaving them $\bot$-able rather than inventing a binding
mirrors the substrate-side discipline ($\bot$ stays $\bot$) and can only *understate*
underdetermination. Deployment-application archetypes are mapped to the substrate's evidence-source
archetypes by a coarse first-match rule with a `general-qa` default; the mismatch between *what
people deploy* and *what the corpora measure* is itself a reported finding, and the headline is
robust to it because the decisive off-evidence axes are $\bot$ in *every* $\tau$.

The resulting traffic is QA-dominated — general-qa 71.0%, function-calling 24.9%, inference-serving
4.1% — and its axis-binding profile is the empirical anchor of the paper's central claim:
**`governance` binds 55.6% and `reviewer_burden` binds 43.8% of real deployments, and both are
100% $\bot$ in the evidence corpus** (`quality` 100%, `latency_p95` 46.9%, `cost` 41.3%, `memory_hw`
1.2%). A majority of real traffic constrains on exactly the axes the entire evidence base is silent
on. The taxonomy is not load-bearing on any single rule: under a drop-one-tag sensitivity sweep
underdetermination never falls below 83.2% (largest single effect: removing
`human_in_the_loop`$\,\to\,$`reviewer_burden`, $-7.9\%$), so the result is a property of the corpus,
not of one mapping choice.
