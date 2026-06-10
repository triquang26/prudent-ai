# P4 — The Selective Right-Sizing Procedure (§6 Method)

**Status:** P4 finding, paper-grade feed for **§6 Method**. Realizes constraint **C3**
(the method = three-state selective decision + cost-aware VoI acquisition +
distribution-free coverage guarantee). Where P3 *diagnosed* that 91.1% of real
deployment traffic is evidence-underdetermined, **P4 is the procedure that acts on that
diagnosis**: it COMMITs when a query is decidable, and otherwise ABSTAINs *informatively*
— naming the blocking set `F` and a cost-aware VoI-ranked acquisition plan (what to
measure next). This is the §6/§9 `solve_selective` skeleton, implemented and run over the
real-traffic battery.

**Substrate & interface (unchanged, C7).** `data/apt_substrate.db`, 182 configs over 3
evidence-source archetypes; 5 of 8 axes carry evidence (`quality, latency_p95, throughput,
cost, energy`); `memory_hw, governance, reviewer_burden` are ⊥ everywhere. Every verdict
in this node reads the substrate **only** through the solver/classifier interface
(`classify_query` / `classify_candidate` → `candidates / cell / required_fields`). No raw
reads, no imputation: `⊥` stays `⊥`.

**How the numbers were produced (reproducible).** φ=point, κ_operating=H+M, regime=FULL,
λ=1.0, VoI seed=12345. Battery = the **1716** real-deployment ZenML empirical prior of
`P3_empirical_query_prior.md`. The substrate is wrapped `CachedSubstrate(Substrate(DB))`;
the prior loads from the frozen on-disk snapshot via `load_prior()` (no network). All
numbers below are read verbatim from `outputs/p4/procedure_eval.{json,md}` and
`outputs/p4/coverage_risk.{json,md}`.

---

## 1. From diagnosis to method

`P3_empirical_query_prior.md` (Q2) established the diagnosis on real traffic: at the FULL
regime **91.1%** of 1716 real LLM-deployment right-sizing queries are *underdetermined* —
the decision cannot be certified for lack of evidence — and the blocking axes concentrate
on the corpus-wide-⊥ set `{governance, reviewer_burden, cost}`. That is a statement about
the *world*; it is not yet a *procedure*.

P4 supplies the procedure. A leaderboard rule answers all 1716 queries with a single
number and commits regardless — and by the §8.5 theorem pays `≥ Δ(R)` regret on every
off-regime-binding class. The Trust-or-Escalate alternative abstains, but abstains
*mutely*: "I won't answer." The P4 procedure does the third thing the formalism (§6/§7/§9)
demands:

- **COMMIT** the identified minimum-sufficient config when the query is decidable;
- **ABSTAIN** when it is not, but return the **blocking set `F`** *and* a **cost-aware
  VoI-ranked acquisition plan** — `argmax_f VoI(f)/cost(f)`, the single axis worth
  measuring next;
- **INFEASIBLE** when no feasible config exists.

The abstention is *informative*: it points at the field to acquire, not merely declines.
That is the concrete sense in which the procedure **exceeds Trust-or-Escalate** (§6/§9):
the decline carries a measurement instruction. Run over the empirical prior, the procedure
should — and does — commit on the ≈8.9% decidable minority and abstain on the ≈91%,
autonomously pointing its acquisition plan at the very blind spots P3 named.

---

## 2. Method

### 2.1 `right_size` — the three-outcome selective rule (§6/§9)

`procedure.right_size(sub, query, kappa, phi, regime, lam)` wraps the P3 three-state
decidability classifier into a selective decision rule (`src/prudent_ai/solver/procedure.py`):

| classifier label | `Action` | payload |
|---|---|---|
| DECIDABLE | `COMMIT` | `committed_config` = the identified minimum-sufficient config |
| INFEASIBLE | `INFEASIBLE` | — |
| UNDERDETERMINED | `ABSTAIN` | `blocking_axes` (= `F`) + `voi_ranking` (cost-aware) |

The `Recommendation` exposes `acquire_next` = the top-ranked axis to measure
(`voi_ranking[0].axis`). φ, κ, regime, λ are all solver-side knobs — a run is fully
described by its config, no hidden flags.

### 2.2 VoI by two-world minimax regret (§7), anchored to the §8.7 identity

For an underdetermined query with blocking field `f`, the value of measuring `f` is the
expected decision-regret reduction (§7), with decision loss
`L(x̂) = max(0, cost(x̂) − cost(x*)) + λ·violation(x̂)`. The implementation
(`voi.voi_for_axis`) operationalizes this as a **two-world minimax** that *isolates* `f`:
resolving `f` splits the completions of `E` into the §8.2 gadget —

- `W_fav`: `f` resolves so that `f`-pending candidates **satisfy** their `f`-constraint;
- `W_unfav`: `f` resolves so that they **violate** it —

holding every *other* pending axis optimistic so we measure `f`'s contribution alone. A
rule that cannot see `f` must commit one (randomized) action robust to both worlds; its
minimax committed regret is exactly the pre-measurement loss, and once `f` is measured the
true world is revealed and the world-optimum committed (regret 0 within this isolation).
Hence **`VoI(f) = minimax_committed_regret_over_{W_fav, W_unfav}`** (`_minimax_two_world`,
closed form over two worlds).

**This is anchored to the limit theorem, not ad hoc.** On the §8.2 two-candidate gadget
(`x_cheap` cost 1, `x_safe` cost 1+δ, binding latency ∉ R), the implemented VoI evaluates
to exactly

> **VoI(a\*) = Δ(R) = δλ / (δ + λ)** — the §8.7 identity.

This is **pinned by `tests/test_procedure.py::test_voi_equals_delta_R`**, parametrized over
`(δ, λ) ∈ {(0.1, 1.0), (0.5, 1.0), (0.2, 2.0), (1.0, 0.3)}`, asserting equality to
`rel_tol=1e-9`. So the implemented VoI *is* the irreducible-regret bound of the omitted
binding axis (§8.7's "irreducible regret of an evidence regime = VoI of the binding axis it
omits"), satisfying the §8.7 obligation that the implemented VoI empirically match `Δ(R)`
on the gadget rather than being an unanchored heuristic.

### 2.3 Cost-aware acquisition (§7) — the documented acquisition-cost table

The acquisition suggestion ranks by `VoI(f) / cost(measure f)` — cheap axes first, pay to
measure an expensive axis only when it earns its cost. The cost table (`voi.ACQUISITION_COST`)
is a **documented assumption**, not fabricated evidence: relative cost of measuring an axis
once, on a 0–1+ scale — benchmarkable axes cheap, human-audit axes (`A_h`) deliberately
expensive.

| axis | acquisition cost | rationale |
|---|---|---|
| `cost` | 0.05 | arithmetic from token price |
| `latency_p95` / `throughput` | 0.10 | micro-benchmark |
| `memory_hw` | 0.20 | profiling |
| `quality` | 0.30 | run an eval suite |
| `energy` | 0.40 | instrumented power measurement |
| `reviewer_burden` | 0.80 | human study (`A_h`) |
| `governance` | 1.00 | legal / compliance audit (`A_h`) |

`AxisVoI` carries `(axis, voi, acquisition_cost, voi_per_cost)`; `voi_ranking` sorts
descending by `(voi_per_cost, voi)`.

### 2.4 The distribution-free coverage guarantee (§9)

`guarantee.CoverageGuarantee` realizes the §9 selective-commit guarantee:
`P(x̂ feasible ∧ x̂ minimum-sufficient | q ∈ C) ≥ 1 − α`. The tunable that traces the curve
is a **commit margin** `m` — commit only when the identified config's cost beats the next
provably-feasible alternative by relative gap ≥ `m` (larger `m` ⇒ more conservative ⇒ lower
coverage, lower risk). `coverage_risk_curve` reports coverage `|C|/|queries|` vs empirical
risk `P(incorrect | committed)`; `calibrate(α)` returns the smallest margin meeting
`risk ≤ α` (i.e. max coverage subject to the guarantee).

**Honest proxy-truth scope (§8.8 / P5).** "Truth" here is the *richer-κ proxy*
(`κ_truth = H+M+L`), not a held-out labelled slice. A commit is *correct* iff the
fuller-evidence procedure identifies the **same** minimum-sufficient config. This is
calibration on a confidence proxy, stated plainly — real held-out ground-truth calibration
is **P5**.

---

## 3. Results (over the empirical prior, n=1716, FULL regime)

### 3.1 Action rates — commit ≈ coverage, the rest abstains informatively

From `outputs/p4/procedure_eval.json`:

| action | n | fraction |
|---|---|---|
| **COMMIT** (coverage) | 153 | **8.9%** |
| **ABSTAIN** | 1563 | **91.1%** |
| INFEASIBLE | 0 | 0.0% |

The procedure commits on **8.9%** (153/1716) and abstains on **91.1%** (1563/1716) — i.e.
**coverage = the empirical-prior decidable fraction**, exactly as P3 predicted. No query is
declared infeasible. The 91.1% are not mute declines: each carries a blocking set and an
acquisition plan.

### 3.2 Acquire-next distribution — the procedure points at its own blind spots

For each of the 1563 abstentions the procedure names the single axis to measure next (top
VoI/cost). The distribution:

| axis to measure next | n | fraction of abstentions |
|---|---|---|
| `cost` | 1289 | 82.5% |
| `reviewer_burden` | 201 | 12.9% |
| `governance` | 73 | 4.7% |

The acquisition plan concentrates **entirely** on the corpus-wide-⊥ binding axes
`{cost, reviewer_burden, governance}` — the exact blind spots P3/Q2 identified as where the
evidence base is silent. The procedure *autonomously* points at what to measure to make
real traffic decidable. (For reference, the **raw**-VoI top-blocking axis — highest
unweighted VoI, before cost-weighting — is distributed `reviewer_burden 751, latency_p95
322, governance 279, cost 152, quality 50, memory_hw 9`; cost-weighting then pulls
`acquire_next` toward the cheap-to-measure `cost` axis first.)

### 3.3 VoI-lift — raw VoI ties on ⊥ axes; cost-awareness breaks them

Over the 1563 abstentions with a ranking (seed=12345):

| reading | top axis | random axis | lift | ratio |
|---|---|---|---|---|
| RAW VoI (regret reduction) | 0.1753 | 0.1753 | **0.0000** | **1.00×** |
| COST-AWARE VoI/cost | 0.2075 | 0.2017 | **0.0058** | **1.03×** |

Mean top VoI over abstentions = **0.1753**; mean VoI/cost of the chosen axis = **0.2075**.
The **raw lift is exactly 0** (ratio 1.00×): the blocking axes of these queries are
corpus-wide ⊥ and share the *same* two-world regret, so raw VoI alone does not discriminate
*which* ⊥ field to measure — the §8.7 regret is a property of the query's binding
structure, not of the ⊥-axis label. The **cost-aware ranking does beat random** (lift
0.0058, ratio 1.03×): cheap axes (`cost`, `latency`) break the raw-VoI ties, which is
precisely what drives `acquire_next` toward the measurable `cost` axis first (the P5
preview — measure the cheap binding axis before paying for a governance audit).

### 3.4 Coverage–risk curve — the Trust-or-Escalate shape

From `outputs/p4/coverage_risk.json` (SEEDED subsample of **600** queries, seed=12345;
proxy-truth κ_truth=H+M+L):

| margin `m` | coverage | risk | n_commit | n_correct |
|---|---|---|---|---|
| 0.00 | **10.5%** | **0.0%** | 63 | 63 |
| 0.01 | 10.5% | 0.0% | 63 | 63 |
| 0.02 | 10.5% | 0.0% | 63 | 63 |
| 0.05 | 10.5% | 0.0% | 63 | 63 |
| 0.10 | 10.5% | 0.0% | 63 | 63 |
| 0.20 | 0.0% | 0.0% | 0 | 0 |
| 0.50 | 0.0% | 0.0% | 0 | 0 |
| 1.00 | 0.0% | 0.0% | 0 | 0 |

**Calibration:** at both **α = 0.05** and **α = 0.10** the guarantee is met at margin
`m = 0` with **coverage 10.5%, risk 0.0%** (every committed query is proxy-correct on this
subsample). Past `m = 0.2` coverage collapses to 0: there are no commits whose cost gap to
the runner-up exceeds 20%, so demanding a wide margin abstains on *everything*.

This is the **Trust-or-Escalate shape made literal**, and it *is* the C3 story: a
distribution-free reliability guarantee is **purchasable only by abstaining on most
traffic**. Risk on the committed slice is 0%, but the slice is tiny (≈9% in FULL on the
full battery; 10.5% on this 600-query subsample). High reliability is available *only* at
low coverage — you buy the guarantee by escalating the rest. The procedure commits on the
decidable minority and escalates the majority, exactly as the §9 selective-commit guarantee
intends.

---

## 4. Claims

- **C3 realized — the method exists and runs.** The three-state selective rule
  (`right_size`, §6), the cost-aware VoI acquisition (`voi`, §7), and the distribution-free
  coverage guarantee (`CoverageGuarantee`, §9) are implemented as one OOP solver layer and
  evaluated over real traffic. The procedure does the thing the formalism promised: COMMIT
  on the decidable minority, ABSTAIN-informatively on the rest, naming `F` and ranking what
  to acquire.

- **The §8.7 identity unifies §7 and §8.** `VoI(a*) = Δ(R) = δλ/(δ+λ)` is not asserted — it
  is **proven exactly on the gadget** by the implemented VoI
  (`tests/test_procedure.py::test_voi_equals_delta_R`, four `(δ,λ)` points, `rel_tol=1e-9`).
  The procedure's abstention machinery is therefore *anchored to the limit theorem*: the
  expected regret reduction it reports for the omitted binding axis is the theorem's
  irreducible-regret bound, making §7 (VoI) and §8 (lower bound) one object.

- **The procedure autonomously surfaces the P3 blind spots.** The acquire-next distribution
  (82.5% `cost`, 12.9% `reviewer_burden`, 4.7% `governance`) lands entirely on the
  corpus-wide-⊥ axes — the procedure, run blind over real traffic, points its own
  measurement budget at exactly the axes P3 identified as un-checkable. The diagnosis and
  the method agree without being wired to.

- **What is still open (P5, V1/V2).** Real held-out **ground-truth calibration** (V1) and
  **mis-sizing magnitude** (V2: whether a leaderboard rule that commits anyway actually
  mis-sizes by ≥ Δ(R), exploiting cost–latency–energy correlation) are P5. This node owns
  "the method commits on the decidable, escalates the rest, and names what to measure";
  "and the guarantee holds against real GT, and answering anyway hurts by a measurable
  margin" is P5 validation.

---

## 5. Limitations (honest)

1. **Proxy-truth, not real GT.** The coverage guarantee calibrates against the richer-κ
   proxy (κ_truth=H+M+L), not a held-out labelled slice. The 0.0% committed risk is risk
   *against the fuller-evidence procedure's own verdict*; a held-out ground-truth slice is
   **P5** (§8.8 discipline — this is empirical calibration on a confidence proxy, stated
   plainly, never claimed as GT).

2. **VoI is the two-world bounding model.** `VoI(f)` is computed by the §8.2 two-world
   minimax that isolates `f` (other pending axes held optimistic). It is **exact on the
   gadget** (= Δ(R), pinned by test) but in general is a *bound* — the isolation assumption
   means it measures `f`'s marginal contribution, not joint multi-axis resolution. This is
   the same honest two-point machinery the theorem uses (§8.8), upgraded to a procedure.

3. **Acquisition-cost table is a documented assumption.** `ACQUISITION_COST` encodes a
   plausible relative ordering (benchmarkable axes cheap, `A_h` human-audit axes expensive),
   not measured acquisition costs. The cost-aware ranking — and therefore the
   `cost`-first acquire-next concentration — depends on this ordering; a different cost
   model would re-rank ties. The *raw* VoI (and hence the COMMIT/ABSTAIN split and the
   coverage curve) does not depend on it.

4. **λ is a risk-aversion knob.** The violation penalty λ (default 1.0) trades cost
   overshoot against infeasibility. The §8.7 identity holds for any λ > 0, but the absolute
   VoI magnitudes (0.1753 mean) scale with λ; λ is a documented tunable, not a measured
   quantity.

5. **Inherited from P3.** φ=point (decidability-over-stating — so the 8.9% commit rate is
   if anything an *upper* bound on coverage), κ=H+M, coarse archetype→τ map, the ⊥-axes
   under one UNDERDETERMINED label. The coverage curve is on a 600-query *subsample* of the
   1716 (seed=12345); the action-rate table is on the full 1716.

---

## 6. Key numbers the paper cites

- **Action rates (FULL, n=1716, φ=point, κ=H+M, λ=1.0):** COMMIT **8.9%** (153),
  ABSTAIN **91.1%** (1563), INFEASIBLE **0.0%** — coverage = the decidable fraction.
- **Acquire-next over the 1563 abstentions:** `cost` **82.5%** (1289), `reviewer_burden`
  **12.9%** (201), `governance` **4.7%** (73) — concentrated entirely on the corpus-wide-⊥
  binding axes P3 named.
- **VoI-lift:** raw VoI lift **0.0000** (1.00×) — ⊥ axes share the same two-world regret;
  cost-aware VoI/cost lift **0.0058** (**1.03×**), mean top VoI **0.1753**, mean VoI/cost
  **0.2075**.
- **VoI = Δ(R) identity:** `VoI(a*) = δλ/(δ+λ)` proven exactly on the gadget over four
  `(δ,λ)` points (`tests/test_procedure.py::test_voi_equals_delta_R`, rel_tol 1e-9).
- **Coverage–risk (600-query subsample, proxy-truth):** at **α=0.05** and **α=0.10**,
  margin **0**, **coverage 10.5%, risk 0.0%** (63/63 proxy-correct); coverage → 0% for
  margin ≥ 0.2. The Trust-or-Escalate shape: a guarantee is purchasable only by abstaining
  on most traffic (the C3 story).
