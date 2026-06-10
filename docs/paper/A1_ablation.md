# A1 — Evidence-Regime Ablation (DV1 by regime)

**Status:** Paper-grade appendix feeding §5 Findings and §7 Evaluation. Instantiates the
master-plan **independent variable (§16 IV)** — *evidence regime* — as a controlled ablation
on the master-plan dependent variable **DV1 (decidability)**, plus two robustness ablations
(confidence model κ; tag→axis prior). Every cut stress-tests **Claim C1** ("on a real
deployment-query distribution many right-sizing decisions are not evidence-decidable, because
of *structured* missingness").

**What this ablation isolates.** P3's headline reports a single decidability profile. This
appendix turns the §16 IV into the experimental knob: we sweep the evidence regime along the
ladder `accuracy_only → acc_cost → acc_cost_latency → acc_cost_lat_throughput → plus_energy →
full`, holding everything else fixed, and read DV1 at each rung **on the real-traffic query
prior** (not the 42-query grid). The shape of that curve — *rise then plateau* — is the
empirical shadow of the limit theorem (§8.5 `E[regret] ≥ c·Δ(R)`, §8.7 `VoI(a*) = Δ(R)`,
§8.6 `decidable ⇔ bind(q) ⊆ cl(R)`): decidability climbs exactly when a rung admits a
*binding* axis, and stops climbing once the corpus has no more usable axes to admit.

**Provenance & settings (reproducible).** Numbers are read from
`outputs/p3/empirical_prior_map.json` (the real-traffic prior, **n = 1716** weighted queries
over the τ-mixture `general-qa 1219 / function-calling 427 / inference-serving 70`) and
`outputs/p3/decidability_map.json` (the structured grid + `sensitivity_kappa`). All decidability
fractions use **φ = point, κ = H+M**, bootstrap n = 1000 (locally seeded `Random(12345)`,
deterministic), 95% percentile CIs. φ = point is the *conservative* (decidability-**over**-stating)
reading, so every "underdetermined" fraction below is a **lower bound**. Every verdict reads the
substrate **only** through `candidates(τ)/cell(x,a)` via the solver classifier (C7 firewall);
no raw SQL feeds a verdict. To recompute:

```bash
PYTHONNOUSERSITE=1 uv run python -c "
from prudent_ai.solver import CachedSubstrate
from prudent_ai.substrate import Substrate
from prudent_ai.analysis.empirical_prior_map import build_map
from prudent_ai.analysis.decidability_map import sensitivity_kappa
from prudent_ai.solver import Phi
sub = CachedSubstrate(Substrate('data/apt_substrate.db'))
m = build_map(sub, phi=Phi.POINT)            # real-traffic prior, n=1716
s = sensitivity_kappa(sub.base, Phi.POINT)    # κ ∈ {H, H+M, H+M+L}
sub.close()"
```

---

## A1.1 Primary ablation — DV1 vs evidence regime (real-traffic prior, n = 1716)

The §16 IV is the regime ladder. Each rung *admits* one more axis to the classifier; an axis
not in the regime is treated as ⊥ regardless of what the substrate holds (regime masking,
§8.1). The table is DV1 on the **real query prior**, with the dominant blocking axes among the
still-underdetermined queries at each rung.

| Evidence regime (axes admitted) | % decidable | % underdetermined | dominant blocking axes (underdetermined) |
|---|---:|---:|---|
| `accuracy_only` ({quality}) | **0.00%** | **100.00%** | cost (1716), governance (954), latency_p95 (804), reviewer_burden (751) |
| `acc_cost` (+cost) | **5.19%** (89) | **94.81%** (1627) | cost (1289), governance (954), latency_p95 (804), reviewer_burden (751) |
| `acc_cost_latency` (+latency) | **8.92%** (153) | **91.08%** (1563) | cost (1289), governance (954), reviewer_burden (751), latency_p95 (557) |
| `acc_cost_lat_throughput` (+throughput) | **8.92%** (153) | **91.08%** (1563) | cost (1289), governance (954), reviewer_burden (751), latency_p95 (557) |
| `plus_energy` (+energy) | **8.92%** (153) | **91.08%** (1563) | cost (1289), governance (954), reviewer_burden (751), latency_p95 (557) |
| `full` (all 8 axes) | **8.92%** (153) | **91.08%** (1563) | cost (1289), governance (954), reviewer_burden (751), latency_p95 (557) |

*Counts are weighted-prior queries; `%decidable` 95% CIs (bootstrap): `acc_cost` [4.19, 6.18],
`acc_cost_latency` and beyond [7.63, 10.26]. `accuracy_only` is exactly [0.00, 0.00].*

**Headline (decidable% per regime):** **0.00 → 5.19 → 8.92 → 8.92 → 8.92 → 8.92.**

### The reading — rise, then plateau (the limit theorem's empirical shadow)

Three facts, all load-bearing for C1, are visible in that single column.

1. **Accuracy-only is fully blind.** Under a leaderboard-style `accuracy_only` regime, **100.00%**
   of the real-traffic prior is underdetermined — *zero* decidable. The dominant blocker is
   **cost**: it is ⊥-off-regime for every one of the 1716 queries (the min-cost objective is
   itself unknown when cost is masked), so no query can be decided whatever its threshold. This
   is the C1 claim at its sharpest: an accuracy-only decision rule answers a question it has no
   evidence to answer for *every* deployment query in the prior.

2. **Decidability rises exactly where a binding axis enters.** Adding cost (`+cost`) unblocks
   the objective and flips **5.19%** of the prior to decidable (cost-attributable blocking drops
   1716 → 1289). Adding latency (`+latency`) unblocks the latency-bound queries and lifts
   decidability to **8.92%** (latency blocking drops 804 → 557). These are precisely the rungs
   that admit an axis many queries *bind on*. This is `decidable ⇔ bind(q) ⊆ cl(R)` (§8.6) read
   off real traffic: a query flips only when the rung supplies its binding axis.

3. **The ladder PLATEAUS at +latency.** Adding throughput, energy, and the governance/burden
   axes (`acc_cost_lat_throughput → plus_energy → full`) buys **exactly zero** additional
   decidability — DV1 is flat at 8.92% / 91.08% across the last four rungs. The reason is
   structural, not a sampling artifact: the queries that remain underdetermined bind on axes the
   *corpus does not carry on any candidate*. `governance` (954 queries), `reviewer_burden` (751),
   and `memory_hw` (20) are ⊥ **everywhere** in the substrate (miss-rate 1.000), so admitting
   them to the regime cannot certify them — `Δ(R) > 0` for every regime reachable inside this
   substrate. The plateau is the empirical face of the limit theorem: **a regime omitting the
   binding axis cannot decide**, and once the regime has admitted every axis the corpus can
   actually certify, growing it further is inert (§8.5 / §8.7). Sharpening evidence *precision*
   does not move this curve — only acquiring a *new axis on a candidate* does.

> **Why this is confirmation, not a corollary (§8.8 discipline).** The theorem says a rule blind
> to the binding axis must incur regret; this ablation *measures* that the corresponding queries
> are undecidable and that admitting the axis is exactly what flips them. The monotone-then-flat
> curve is the predicted signature observed on real data — never re-derived from the theorem.

**Grid vs prior (robustness of the shape).** The same curve on the structured 42-query grid runs
0.00 → 21.4% → 42.9% → plateau for function-calling and stays 0.00 for the two cost-/quality-blind
archetypes; pooled grid decidability at `full` is 14.3% vs the prior's 8.92%
(`delta_underdetermined = 0.054`). The prior is *more* underdetermined than the grid because it
up-weights `general-qa` (1219/1716), which is cost-⊥ and therefore decidable=0 at every rung. The
**shape** (rise-then-plateau, plateau onset at +latency) is identical under both query
distributions — the headline is not an artifact of the hand-built grid.

---

## A1.2 Ablation on the confidence model — κ sensitivity (H / H+M / H+M+L)

The default belief admits H- and M-tier observations. This cut re-grounds the entire map under
three confidence policies (re-grounding thresholds per κ), isolating whether decidability is a
confidence-threshold artifact. Reported on the 18 (τ × regime) cells of `sensitivity_kappa`.

| κ policy | evidence admitted | % decidable | % underdetermined |
|---|---|---:|---:|
| **H only** | measured only (478 / 3392 obs) | **0.00%** | **100.00%** |
| **H + M** (default) | + leaderboard / paper-reported | **10.71%** | **89.29%** |
| **H + M + L** | + vendor-doc / paper-estimated | **10.71%** | **89.29%** |

**The reading.** The finding **survives** the sweep — underdetermination is never below
**89.29%**. Two asymmetric ends:

- **Tightening to H-only → 100.00% underdetermined.** Every decidable case rests on M-tier
  (leaderboard / paper-reported) cost and latency values; filtering to measured-only evidence
  removes them and the map collapses to fully undecidable. This *strengthens* C1: the small
  decidable mass exists only because we trust leaderboard-tier numbers.
- **Loosening to admit L → no change (+0.00).** L-tier observations land on axes already
  populated or already blocked, so they unblock not a single query. The blind spots are not a
  confidence-threshold artifact — they are absence of the axis, which no confidence policy
  manufactures.

This ablation stress-tests the C1 sub-claim that the result is **robust to the uncertainty/
confidence model** (§16 IV: *confidence threshold · uncertainty model*). It is: the decidable
fraction lives in a narrow [0%, 10.71%] band and the underdetermined fraction never drops below
0.893.

---

## A1.3 Ablation on the prior — tag→axis mapping robustness (drop-one)

The real-traffic prior is built by mapping ZenML/MedHELM query tags to bound axes. If a single
tag drove the whole result, the prior would be fragile. We re-derive the `full`-regime
underdetermined fraction with each mapping tag dropped in turn (`mapping_sensitivity`, baseline
0.9108).

| dropped tag | underdetermined @ full | Δ vs baseline |
|---|---:|---:|
| `latency_optimization` | 0.9108 | 0.000 |
| `cost_optimization` | 0.9108 | 0.000 |
| `governance` | 0.9056 | −0.005 |
| `high_stakes_application` | 0.9009 | −0.010 |
| `regulatory_compliance` | 0.9003 | −0.010 |
| `human_in_the_loop` | **0.8322** | **−0.079** |

**The reading.** No single tag moves the underdetermined fraction by more than **7.9 percentage
points** (worst case `human_in_the_loop`, which carries the bulk of the reviewer_burden /
governance bindings). Dropping the two purely-measurable tags (latency/cost optimization) changes
nothing — those axes are already certifiable, so removing their queries leaves the
underdetermined mass intact. Even the most influential tag leaves the headline at **83.2%**
underdetermined, well inside the C1 claim. This stress-tests the C1 sub-claim that the result is
**robust to the query-distribution / prior construction** (§16 threats: *query-distribution
bias*). It is: the prior is not a one-tag artifact; the structural blind spots (governance,
reviewer_burden, memory_hw ⊥ everywhere) survive any single-tag deletion.

---

## A1.4 What each ablation stress-tests (C1 robustness summary)

| Ablation (§16 IV knob) | Varies | Holds C1? | Margin |
|---|---|---|---|
| **Evidence regime** (primary) | accuracy_only → full | **Yes** | underdetermined 100.00% → 91.08%; decidable plateaus at 8.92% once corpus axes exhausted |
| **Confidence model κ** | H / H+M / H+M+L | **Yes** | underdetermined ≥ 89.29%; H-only → 100.00% |
| **Prior tag→axis map** | drop-one over 6 tags | **Yes** | max swing 7.9 pp; underdetermined ≥ 83.2% |

**Bottom line.** The decidability deficit is robust along all three §16 IV axes that could
plausibly explain it away. It is not a regime artifact (it *rises and then plateaus* exactly as
the limit theorem predicts, and the plateau is structural — three axes are ⊥ everywhere), not a
confidence-threshold artifact (κ-band is narrow; loosening adds nothing, tightening makes it
worse), and not a prior artifact (no single mapping tag swings it more than 7.9 pp). Each cut
sharpens rather than weakens C1: *on the real deployment-query prior, the evidence cannot decide
the right-sizing question for ~91% of queries, and no admissible regime within this corpus
recovers more than ~9%.*
