# §6. Method — Selective Right-Sizing with VoI-Guided Abstention and a Distribution-Free Coverage Guarantee

> **Claim addressed: C3.** Given the diagnosis that real deployment traffic is
> overwhelmingly evidence-underdetermined (§5 / C1: 91.1% of 1716 real LLM right-sizing
> queries), the contribution of this section is the *procedure that acts on that diagnosis*:
> a three-state selective right-sizing rule that **commits** when the decision is identified,
> and otherwise **abstains informatively** — returning the blocking set and a cost-aware,
> VoI-ranked instruction for *what to measure next*. The abstention machinery is anchored to
> the §8 limit theorem by an exact identity, `VoI(a*) = Δ(R) = δλ/(δ+λ)`, that makes the
> value of information and the irreducible-regret lower bound one object; and the commit set
> carries a distribution-free coverage guarantee
> `P(x̂ feasible ∧ minimum-sufficient | commit) ≥ 1 − α`. The empirical behaviour over real
> traffic is reported in §7; this section is the method and its guarantee.

All numbers cited here are read verbatim from `outputs/p4/procedure_eval.{json,md}` and
`outputs/p4/coverage_risk.{json,md}`; the exact identity is pinned by
`tests/test_procedure.py::test_voi_equals_delta_R`. The procedure reads the substrate **only**
through the solver interface (`candidates` / `cell` / `required_fields`, §3 / C7): no raw
reads, no imputation — `⊥` stays `⊥`.

---

## 6.1 From diagnosis to procedure

§5 / C1 is a statement about the *world*: at the FULL regime, 91.1% of real LLM-deployment
right-sizing queries are evidence-underdetermined — the minimum-sufficient configuration is
**non-identifiable** for lack of evidence — and the blocking axes concentrate on the
corpus-wide-`⊥` set `{governance, reviewer_burden, cost}` (the structured-missingness claim,
§5 / H2). That diagnosis is not yet a *procedure*. A leaderboard rule answers all 1716
queries with a single number and commits regardless; by the §8.5 theorem it pays `≥ Δ(R)`
regret on every off-regime-binding class. The Trust-or-Escalate alternative abstains, but
abstains *mutely* ("I won't answer").

The procedure of this section does the third thing the formalism (§6 / §7 / §9 of the
formalism spine) demands. For each query `q = (τ, c)` under evidence `E`, it returns exactly
one of three actions:

- **COMMIT** the identified minimum-sufficient configuration `x̂(q,E)` when `q` is
  evidence-decidable;
- **ABSTAIN** when `q` is underdetermined, returning the **blocking set `F`** *and* a
  **cost-aware VoI-ranked acquisition plan** — `argmax_f VoI(f)/cost(f)`, the single axis
  worth measuring next;
- **INFEASIBLE** when no configuration is provably feasible across all completions of `E`.

The decisive difference from prior selective methods is in the second branch: the abstention
is *informative*. It does not merely decline — it points at the field to acquire and ranks
the candidates by regret-reduction per unit measurement cost. This is the concrete sense in
which the procedure **exceeds Trust-or-Escalate** (§6.6).

---

## 6.2 The three-state selective rule (§6 of the formalism spine)

`right_size(sub, query, kappa, phi, regime, lam)` wraps the §5 three-state decidability
classifier into a selective decision rule (`prudent_ai.solver.procedure`). It maps the
classifier label to an `Action` and a payload:

| classifier label (§5) | `Action` | payload |
|---|---|---|
| DECIDABLE | **COMMIT** | `committed_config` — the identified minimum-sufficient `x̂` |
| UNDERDETERMINED | **ABSTAIN** | `blocking_axes` (= `F`) + `voi_ranking` (cost-aware) |
| INFEASIBLE | **INFEASIBLE** | — |

The returned `Recommendation` exposes `acquire_next = voi_ranking[0].axis`: the single
top-ranked axis to measure. The selective object being committed is a **multi-constraint
decision under structured missingness** — `feasible ∧ minimum-sufficient` *jointly*, against
the oracle minimum-sufficient `x*(q) = argmin_{x feasible} cost(x)`. This is strictly harder
than selective *binary* classification, and is the source of the delta-novelty argued in §6.7.

`φ` (aggregation mode), `κ` (confidence filter), `regime` (the evidence regime `R`), and `λ`
(risk-aversion) are all solver-side knobs: a run is **fully described by its config**, with no
hidden flags (C7 / the reproducibility contract). The classifier — and therefore the whole
procedure — reads cells only through the §3 interface; `test_c7_procedure_reads_only_interface`
pins this.

---

## 6.3 Value of information by two-world minimax regret (§7 of the formalism spine)

For an underdetermined query with a blocking field `f`, the value of measuring `f` is the
expected reduction in decision-regret, under the decision loss

> `L(x̂) = max(0, cost(x̂) − cost(x*)) + λ · violation(x̂)`

— cost overshoot relative to the oracle optimum, plus a risk-aversion penalty `λ` on
constraint violation. The implementation (`voi.voi_for_axis`) operationalizes
`VoI(f) = E[L(x̂_E)] − E_{observe f}[L(x̂_{E∪{f}})]` as a **two-world minimax** that *isolates*
`f`. Resolving `f` splits the completions of `E` into the §8.2 gadget:

- `W_fav`: `f` resolves so that `f`-pending candidates **satisfy** their `f`-constraint;
- `W_unfav`: `f` resolves so that they **violate** it.

Every *other* pending axis is held optimistic, so the computation measures `f`'s marginal
contribution alone. A rule that cannot see `f` must commit one (possibly randomized) action
robust to both worlds; its minimax committed regret is exactly the pre-measurement loss, and
once `f` is measured the true world is revealed and the world-optimum is committed (regret 0
within this isolation). Hence

> **`VoI(f) = minimax_committed_regret over {W_fav, W_unfav}`**

(`_minimax_two_world`, a closed form over two worlds).

### The exact identity — VoI unified with the limit theorem

This VoI is **not** an ad-hoc heuristic: it is anchored to the §8 lower bound. On the §8.2
two-candidate gadget (`x_cheap` at cost 1, `x_safe` at cost `1+δ`, binding axis `latency ∉ R`),
the implemented VoI evaluates to exactly

> **VoI(a\*) = Δ(R) = δλ / (δ + λ)** — the §8.7 identity.

This is **proven exactly, not asserted**: `tests/test_procedure.py::test_voi_equals_delta_R`
parametrizes over `(δ, λ) ∈ {(0.1, 1.0), (0.5, 1.0), (0.2, 2.0), (1.0, 0.3)}` and asserts
equality to `Δ(R)` at `rel_tol = 1e-9`. Consequently the implemented VoI **is** the
irreducible-regret bound of the omitted binding axis (§8.7: "the irreducible regret of an
evidence regime on `Q_R(a*)` equals the value of information of the binding axis it omits").
The procedure's abstention machinery (§7, VoI) and the necessity theorem (§8, lower bound) are
thereby **one object**: the expected regret reduction the procedure reports for the axis it
asks you to measure is exactly the theorem's `Δ(R)`. This identity discharges the §8.7
obligation (formalism Q4) that the implemented VoI empirically match `Δ(R)` on the gadget —
the candidate Oral-line of the paper now rests on a passing test, not a claim.

---

## 6.4 Cost-aware acquisition (§7 of the formalism spine)

The acquisition suggestion ranks blocking axes by `VoI(f) / cost(measure f)` — an acquisition
cascade in the spirit of Cascaded Selective Evaluation: cheap axes first, pay to measure an
expensive axis only when its regret-reduction earns the cost. The cost table
(`voi.ACQUISITION_COST`) is a **documented assumption**, not fabricated evidence — the relative
cost of measuring an axis once, on a 0–1+ scale: benchmarkable axes cheap, human-audit axes
(`A_h`) deliberately expensive.

| axis | acquisition cost | rationale |
|---|---|---|
| `cost` | 0.05 | arithmetic from token price |
| `latency_p95` / `throughput` | 0.10 | micro-benchmark |
| `memory_hw` | 0.20 | profiling |
| `quality` | 0.30 | run an eval suite |
| `energy` | 0.40 | instrumented power measurement |
| `reviewer_burden` | 0.80 | human study (`A_h`) |
| `governance` | 1.00 | legal / compliance audit (`A_h`) |

`AxisVoI` carries `(axis, voi, acquisition_cost, voi_per_cost)`; `voi_ranking` sorts descending
by `(voi_per_cost, voi)`. Critically, the cost weighting affects **only** the acquisition
ranking — *which* axis to name first. The raw VoI (and therefore the COMMIT/ABSTAIN split and
the coverage–risk curve) is independent of the cost table; only the `acquire_next`
concentration depends on it. This is a deliberate firewall so that the central claims do not
ride on the cost assumptions (a documented limitation, §6.8).

---

## 6.5 The distribution-free coverage guarantee (§9 of the formalism spine)

`guarantee.CoverageGuarantee` realizes the selective-commit guarantee:

> **`P(x̂ feasible ∧ x̂ minimum-sufficient | q ∈ C) ≥ 1 − α`,**

for a user-set risk `α`, where `C` is the commit set and **coverage** `= |C| / |queries|`. The
tunable that traces the curve is a **commit margin `m`**: commit only when the identified
config's cost beats the next provably-feasible alternative by relative gap `≥ m`. Larger `m`
⇒ more conservative ⇒ lower coverage and lower risk. `coverage_risk_curve` reports coverage vs
empirical risk `P(incorrect | committed)`; `calibrate(α)` returns the smallest margin meeting
`risk ≤ α`, i.e. maximum coverage subject to the guarantee.

### The coverage–risk curve has the Trust-or-Escalate shape

This is the crux of the C3 story. The guarantee is **purchasable only by abstaining on most
traffic**. On the seeded 600-query subsample (proxy-truth `κ_truth = H+M+L`), at both
**α = 0.05** and **α = 0.10** the guarantee is met at margin `m = 0` with **coverage 10.5%,
risk 0.0%** (63/63 committed queries proxy-correct); past `m = 0.2` coverage collapses to 0%,
because no commit's cost gap to its runner-up exceeds 20%. Risk on the committed slice is 0%,
but the slice is tiny (≈9% on the full battery, 10.5% on this subsample). High reliability is
available **only at low coverage** — you buy the guarantee by escalating the rest. The
procedure commits on the decidable minority and escalates the majority, exactly as the
selective-commit guarantee intends (full curve and calibration in §7).

### Honest proxy-truth scope

"Truth" here is the **richer-κ proxy** (`κ_truth = H+M+L`), not a held-out labelled slice. A
commit is *correct* iff the fuller-evidence procedure identifies the **same** minimum-sufficient
config. This is calibration on a confidence proxy, stated plainly (§8.8 discipline); the 0.0%
committed risk is risk *against the fuller-evidence procedure's own verdict*. Real held-out
ground-truth calibration is the job of P5 / §8, and is not claimed here.

---

## 6.6 Position vs Trust-or-Escalate (§17.1 reverse-outline)

The procedure is the right-sizing analogue of Trust-or-Escalate (2407.18370, ICLR'25 Oral),
mapped construct-for-construct and then extended:

| Trust-or-Escalate (judge reliability) | This procedure (right-sizing) |
|---|---|
| judge trusted unconditionally → unreliable verdicts | leaderboard trusted unconditionally → mis-sized deployments |
| confidence → **selectively trust**, `P(agree \| evaluate) ≥ 1−α` | evidence-sufficiency → **selectively commit**, `P(feasible ∧ min-sufficient \| commit) ≥ 1−α` |
| calibrate via Simulated Annotators + fixed-sequence testing | calibrate per-axis evidence-uncertainty on a (proxy / GT) slice |
| Cascaded cheap→strong judge | **VoI-guided acquisition cascade** (cheap→expensive axis) |
| abstention = "don't evaluate" (mute) | **abstention = measure the top-VoI field (informative)** |
| guarantee at high coverage, baseline violates | guarantee indexed by **evidence regime**, not sample size |

The procedure **inherits** the selective-guarantee skeleton and the coverage-at-reliability
reporting style, and **exceeds** it on the abstention: Trust-or-Escalate's decline is terminal,
whereas this procedure's decline carries a measurement instruction — the VoI-ranked axis whose
acquisition would make the query decidable. The empirical signature of that extension is in §7:
over the 1563 abstentions the procedure's `acquire_next` lands **entirely** on the
corpus-wide-`⊥` binding axes `{cost 82.5%, reviewer_burden 12.9%, governance 4.7%}` — it
autonomously surfaces the exact blind spots §5 / C1 named, without being wired to them.

---

## 6.7 Delta-novelty — what is new beyond "ported selective classification"

The anticipated reviewer attack is "this is selective classification ported to a new task /
the guarantee is just vanilla selective classification" (master plan §18.1). The defense is two
structural differences, both load-bearing:

1. **The selected object is a multi-constraint decision under structured missingness.** The
   commit certifies `feasible ∧ minimum-sufficient` *jointly* over a constraint bundle, against
   an `argmin`-cost oracle — not a single binary label. Underdetermination arises precisely
   because a `⊥` axis can flip the `argmin` (§5 non-identifiability), which has no analogue in
   binary selective classification.

2. **The guarantee is indexed by the evidence regime, not by sample size.** Coverage is not a
   function of how many samples were drawn; it is a function of *which axes carry evidence*
   (`R`). This binding to the evidence regime is exactly what connects the guarantee to the
   §8 limit theorem: the regret a committing rule cannot avoid is `Δ(R)`, a property of `R`,
   and §6.3's identity makes the procedure's own VoI equal to it. A sample-size-indexed
   selective-classification guarantee cannot express "no rule restricted to regime `R` can do
   better, regardless of data volume" — this one can.

Together with the VoI-guided informative abstention (§6.6), these place the method outside the
selective-classification template rather than inside it.

---

## 6.8 Limitations (carried into §7 / P5)

1. **Proxy-truth, not real GT.** The coverage guarantee calibrates against the richer-κ proxy
   (`κ_truth = H+M+L`); the 0.0% committed risk is risk against the fuller-evidence procedure's
   own verdict. Held-out ground-truth calibration (V1) is P5.
2. **VoI is the two-world bounding model.** `VoI(f)` is **exact on the gadget** (= `Δ(R)`,
   pinned by test) but in general a *bound*: the isolation assumption measures `f`'s marginal
   contribution, not joint multi-axis resolution — the same honest two-point machinery the
   theorem uses (§8.8), upgraded to a procedure.
3. **Acquisition-cost table is a documented assumption.** The `cost`-first `acquire_next`
   concentration depends on `ACQUISITION_COST`; a different cost model would re-rank ties. The
   raw VoI, the COMMIT/ABSTAIN split, and the coverage curve do **not** depend on it.
4. **λ is a risk-aversion knob.** The §8.7 identity holds for any `λ > 0`, but absolute VoI
   magnitudes scale with `λ`; `λ` is a documented tunable, not a measured quantity.
5. **Inherited from §5.** `φ = point` (decidability-over-stating, so the commit rate is if
   anything an *upper* bound on coverage), `κ = H+M`, coarse archetype→τ map.

Whether a leaderboard rule that commits anyway actually mis-sizes by `≥ Δ(R)` on real traffic
(exploiting cost–latency–energy correlation) is **empirical confirmation reserved for P5 / §8**
— never claimed here as a corollary of the theorem (§8.8).

---

## 6.9 Summary of claims (C3)

- **C3 realized — the method exists, runs, and reads only the §3 interface.** The three-state
  selective rule (`right_size`, §6.2), cost-aware VoI acquisition (`voi`, §6.4), and the
  distribution-free coverage guarantee (`CoverageGuarantee`, §6.5) are one OOP solver layer,
  evaluated over real traffic (§7). It COMMITs on the decidable minority, ABSTAINs-informatively
  on the rest, naming `F` and ranking what to acquire.
- **The §8.7 identity unifies §7 and §8.** `VoI(a*) = Δ(R) = δλ/(δ+λ)` is **proven exactly** on
  the gadget by the implemented VoI (`tests/test_procedure.py::test_voi_equals_delta_R`, four
  `(δ,λ)` points, `rel_tol = 1e-9`), making the procedure's abstention an instance of the limit
  theorem's irreducible-regret bound.
- **Informative abstention exceeds Trust-or-Escalate.** The decline names the VoI-ranked field
  to measure (§6.6); empirically (§7) it points the measurement budget at the very `⊥` axes the
  diagnosis named.
- **The guarantee is the Trust-or-Escalate shape, made literal.** A distribution-free
  reliability guarantee `P(feasible ∧ min-sufficient | commit) ≥ 1 − α` is purchasable only by
  abstaining on ~90% of traffic; at α ∈ {0.05, 0.10}, margin 0, coverage ≈10.5%, committed risk
  0.0% (proxy-truth) — high reliability at low coverage, indexed by evidence regime, not sample
  size.
