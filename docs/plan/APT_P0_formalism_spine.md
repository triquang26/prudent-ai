# APT — P0 Formalism Spine + P1 Build Spec

> **Status:** P0 deliverable, paper-grade. Consolidates §5–§11 of the master plan and adds the two
> things P0 *must* fix before P1 can start: the **observation/uncertainty model** (§3 here) and the
> **substrate interface contract** (§9 here). This file is the canonical text for **§3 Problem
> Formulation** of the paper and the build spec P1 implements against.
> *Pham Tri Quang · CS197 · ICLR track · 2026-06 · no code (formalism level).*

---

## 0. Anchor — the bit flip (so nothing below drifts)

Everyone in the evaluation literature is improving the *estimate*: better benchmarks (HELM), cost-aware
agent eval (HAL), more reliable judges (Trust-or-Escalate). The hidden assumption is that **the frontier
is estimate quality**. We flip it: the prior question is **sufficiency** — *given the evidence that exists,
is the deployment decision identifiable at all?* Every definition below exists to make that one flip precise
and measurable. If a construct does not serve "when does evidence identify the decision," it does not belong.

---

## 1. Objects and notation (§5)

- Task archetype `τ ∈ T` (e.g. clinical-summarization, web-navigation, code-assist).
- Configuration / AI Box `x ∈ X` = a configured assembly of components (model, context length, retrieval
  backend, decoding params, orchestration). `X(τ)` = configurations admissible for `τ`.
- **Right-sizing axes** `A = {quality, latency_p95, throughput, cost, energy, memory_hw, governance,
  reviewer_burden}`. Partition:
  - **measurable** `A_m = {quality, cost, latency, energy}` — ground truth obtainable;
  - **hard-to-observe** `A_h = {governance, reviewer_burden, memory_hw(partly), …}` — the worst blind spots.
- True value `θ_a(x) ∈ ℝ ∪ Cat` — **never observed directly**. Numeric axes live in `ℝ`; categorical axes
  (governance, hardware tier, privacy, human-review) live in a finite `Cat`.
- Query `q = (τ, c)` with **hard constraint bundle** `c`: each constraint is `(axis a, relation, target)`,
  e.g. `quality ≥ q*`, `latency_p95 ≤ L*`, `governance ⊇ G`, `hardware ∈ H`, `privacy = P`,
  `human_review = R`.

`bind(q) ⊆ A` denotes the **binding axes** of `q`: the axes whose constraint is active at the optimum
(the constraints that, if relaxed, change `x*`). Making `bind(q)` operational on real data is a P3 obligation
(see §11, Open Q2) — the whole framing presumes we can name which axis binds.

---

## 2. The oracle right-sizing problem (§6)

Under full knowledge of `θ`, right-sizing is a constrained min-cost selection:

> **x\*(q) = argmin₍ x ∈ X(τ) : feasible(x, c) ₎ cost(x)** , the **minimum-sufficient configuration**,
> where `feasible(x,c)` holds iff `θ_a(x)` satisfies every constraint in `c`.

This is the target every procedure is judged against. It is also the **oracle baseline B5**: the floor on
regret, i.e. how much could be saved *in principle* if all axes were known. Nothing here is novel — it is
deliberately a textbook constrained optimum. The novelty is everything that happens when `θ` is replaced by
*evidence about* `θ`.

---

## 3. ★ The observation model — what `B_E(x,a)` actually is (the P1 gate)

This is the one P0 decision the master plan left open ("interval **or** distribution") and the hinge the
whole substrate is built around. Resolving it dictates the schema shape, so it is fixed here.

### 3.1 The tension

The substrate must serve **three different solvers** without privileging any (constraint C7: substrate ⟂
solver):

| Solver | What it needs from a cell `(x,a)` |
|---|---|
| chance-constrained | a distribution → `P(a ⊨ constraint)` |
| robust / partial-identification | an interval `[ℓ, u]` |
| categorical certifier (gov/hw/privacy/review) | a certified category, or "unknown" |

If we store "belief = distribution," we have welded the substrate to the chance-constrained solver. If we
store "belief = interval," we have welded it to the robust one. Either choice violates C7 and forecloses
ablations across solvers.

### 3.2 Resolution — **store observations, derive beliefs**

The substrate stores **raw observations**. The **belief is a derived object**, computed at solve time by an
aggregation operator the *solver* chooses. Formally:

An **observation** for cell `(x,a)`:

```
o = ⟨ val_or_cat , confidence ∈ {H,M,L} , evidence_id , source_type , context ⟩
```

where `context = (hardware_tier, dataset, split, decoding_cfg, date)` — required to (i) keep comparison
context (C6) and (ii) decide whether two observations are even *commensurable*. The **observation set**
`O_E(x,a) = {o₁,…,o_k}` (possibly empty) is what the substrate physically holds.

The **belief** is *derived*, not stored:

> **B_E(x,a) = Agg_φ( O_E(x,a) | κ )**

- `κ` = **confidence filter** from the query's policy (default `H+M`; `L` opt-in). This *is* constraint C4,
  realized as a filter rather than a stored flag.
- `φ` = **aggregation mode chosen by the solver**:
  - `φ = interval`: `B_E = [ min_i ℓ_i , max_i u_i ]` over filtered, commensurable observations, each
    contributing `val ± width(confidence, source_type)`. (partial-identification / robust view)
  - `φ = distribution`: `B_E =` a confidence-weighted pooled posterior with a per-`source_type` noise model.
    (chance-constrained view)
  - `φ = categorical`: `B_E =` the agreed category if all filtered observations concur; **⊥** if they
    conflict or the set is empty.
- **Missingness is derived, and relative to the filter:**
  > **B_E(x,a) = ⊥  ⇔  the κ-filtered observation set is empty.**

  This is exactly right: a cell holding only low-confidence evidence is `⊥` under the default `H+M` policy
  but present under an `L`-opt-in policy. `is_missing` is therefore not a stored boolean but a *query*.

### 3.3 Why this is the correct design (three payoffs)

1. **C7 holds by construction.** The substrate never commits to interval-vs-distribution; the solver picks
   `φ`. Ablating "robust vs chance-constrained" becomes swapping `φ`, no re-extraction.
2. **It makes decidability well-defined** (§5 here) — completions `Comp(E)` are precisely the value
   assignments consistent with the per-cell observation intervals.
3. **It dictates the schema, with a reason.** Because a cell holds *many* observations with provenance and
   context, the storage unit is an **observation row**, not a flat `(x,a)→value` cell. This is the formal
   reason the substrate is relational/normalized — the answer to the advisor's "why SQL?" question is now
   *derivable*, not asserted (see §10).

---

## 4. Three feasibility states, operationalized (§7)

For candidate `x`, bundle `c`, risk `α`, chosen `(φ, κ)`. For each constraint `(a, rel, target) ∈ c`, evaluate
the predicate against `B_E(x,a)`:

- numeric, `φ=distribution`: **certified-sat** iff `P_{B_E}(a rel target) ≥ 1−α`; **certified-violated** iff
  `P_{B_E}(a rel target) < α`;
- numeric, `φ=interval`: **certified-sat** iff the whole interval satisfies `rel target`; **certified-violated**
  iff the whole interval violates it;
- categorical: **certified-sat** iff the certified category ⊨ constraint; **certified-violated** iff it ⊭;
- any axis with `B_E = ⊥`: **undetermined**.

Then:

| State | Condition |
|---|---|
| **provably-feasible** | every constraint certified-sat **and no required field is ⊥** |
| **provably-infeasible** | some constraint certified-violated |
| **possibly-feasible (pending F)** | neither holds; `F` = the required fields that are `⊥` or straddle the threshold. **Return F.** |

`F` is the object VoI ranks (§7 here) and the object abstention reports (§6 here). The classifier itself lives
in the **solver** layer and reads cells only through the interface in §9.

---

## 5. Evidence-decidability and non-identifiability (§8) — the anchor of C1

Let `Comp(E)` = the set of **completions** of `E`: every assignment of values to `⊥`/straddling cells that is
*consistent with the observation intervals* (a `⊥` cell with no bounding observation ranges over its admissible
domain; a straddling cell ranges within `[ℓ,u]`).

> **Decidable.** `q` is **evidence-decidable under E** ⇔ there exists a provably-feasible `x` whose
> `argmin cost` is **invariant across all completions** `e ∈ Comp(E)`. The optimal decision is *identified* by E.
>
> **Underdetermined.** `q` is **evidence-underdetermined** ⇔ the minimum-sufficient decision is
> **non-identifiable**: `∃ e₁, e₂ ∈ Comp(E)` with `x*(q | e₁) ≠ x*(q | e₂)`. Equivalently, **there is a missing
> field whose value flips the argmin.**
>
> **Infeasible-under-E.** No `x` is provably-feasible across all completions.

DV1 (the decidability map, P3) is the empirical distribution of these three labels over
`{archetype × evidence-regime × confidence}`. This is the measurement that improving `B_E` (HAL/HELM) does not
produce — they sharpen completions; we ask **when E suffices to identify the decision**.

**Structured missingness (claim, not description).** The framing's force depends on `⊥` concentrating on the
*same* axes across sources (H2 of P3). If missingness were random, completions would rarely flip the argmin and
underdetermination would be rare. Proving the missingness is structured is therefore load-bearing, not cosmetic.

---

## 6. Selective right-sizing + distribution-free guarantee (§9)

The procedure returns either **(i)** a committed recommendation `x̂(q,E)`, or **(ii) ABSTAIN** + blocking set
`F` + a VoI-ranked acquisition suggestion.

> **Guarantee (distribution-free).** For a user-set risk `α`, the commit set `C` satisfies
> **P( x̂ feasible ∧ x̂ minimum-sufficient | q ∈ C ) ≥ 1 − α**,
> calibrated by fixed-sequence testing / conformal thresholds on a held-out **ground-truth slice**.
> **Coverage** `= |C| / |queries|`; we report the full **coverage–risk curve** (mirroring Trust-or-Escalate's
> coverage-at-agreement reporting).

**Delta-novelty (vs "ported selective classification").** The selected object is a **multi-constraint decision
under structured missingness** — `feasible ∧ minimum-sufficient` *jointly* — strictly harder than selective
*binary* classification, and the guarantee is indexed by **evidence regime**, not by sample size. That binding
to the evidence regime is what connects the guarantee to the limit theorem (§8 here).

---

## 7. Value of information (§10) — abstention that *names what to measure*

For `q` under `E` with blocking set `F`, decision loss
`L(x̂) = max(0, cost(x̂) − cost(x*)) + λ · violation(x̂)`.

> **VoI(f) = E[ L(x̂_E) ] − E₍observe f₎[ L(x̂_{E ∪ {f}}) ]** — expected regret reduction from measuring field `f`.

- Abstention recommends `argmax_f VoI(f)`.
- **Cost-aware:** rank by `VoI(f) / cost(measure f)` — the acquisition cascade (cheap axes first; pay to
  measure an expensive axis only when it earns its cost), paralleling Cascaded Selective Evaluation.
- This is the concrete way the procedure **exceeds Trust-or-Escalate**: its abstention is *informative* — it
  points at the field to acquire, not merely "I won't answer."

The link to §8 (here): the VoI of the binding axis is exactly the theorem's irreducible bound — proved next.

---

## 8. ★ Limit theorem (§11) — full statement and proof

Style: Limits-to-scalable-evaluation. This is the necessity backbone, not the sole contribution; the
machinery is standard two-point (Le Cam) indistinguishability, and its job is to make the negative result
*provable* rather than merely observed.

### 8.1 Setup

An **evidence regime** `R ⊆ A` is the set of axes on which `E` carries *any* evidence. A rule is
**R-restricted** if it depends on `B_E` only through axes in `R`. Let `Q_R(a*)` be the query class whose
binding axis is `a* ∉ R`.

### 8.2 The gadget (two indistinguishable worlds)

Take `R = {cost}`, binding axis `latency ∉ R`, constraint `latency_p95 ≤ L*`. Two configurations:
`x_cheap` (cost 1), `x_safe` (cost 1+δ), δ > 0.

| | cost (∈R, **identical**) | latency (∉R) | feasible | x* | opt cost |
|---|---|---|---|---|---|
| **W₁** | 1 / 1+δ | `L*−ε / L*−ε` | both | `x_cheap` | 1 |
| **W₂** | 1 / 1+δ | `L*+ε / L*−ε` | safe only | `x_safe` | 1+δ |

W₁ and W₂ are **identical on R** (same costs; no latency evidence in either). Any R-restricted rule sees the
same input in both → must emit the same action. But the optima differ. That gap is the entire lower bound.

### 8.3 Regret of each action, worst-cased over `{W₁, W₂}`

A randomized R-restricted rule is a distribution `(p_c, p_s, p_a)` over `{commit x_cheap, commit x_safe,
abstain}`, `p_c+p_s+p_a = 1`. Per world:

- W₁: `x_cheap`→0, `x_safe`→δ, abstain→0  ⇒ regret `= p_s·δ`
- W₂: `x_cheap`→λ (infeasible), `x_safe`→0, abstain→0  ⇒ regret `= p_c·λ`

So worst-case regret `= max(p_s·δ, p_c·λ)`, and **coverage** `c = p_c + p_s = 1 − p_a`.

### 8.4 Minimizing worst-case regret at fixed coverage

Distribute committed mass `c` between cheap and safe: `min_{p_c+p_s=c} max(p_s δ, p_c λ)`. The min is at the
balance point `p_s δ = p_c λ`, giving `p_c = c·δ/(δ+λ)`, `p_s = c·λ/(δ+λ)`, value `= c · δλ/(δ+λ)`. Define

> **Δ(R) := δλ / (δ + λ) > 0.**

### 8.5 Theorem

> **Theorem (off-regime binding ⇒ irreducible regret–coverage tradeoff).** For regime `R ⊊ A` and axis
> `a* ∉ R`, there exist instances `W₁, W₂` observationally identical under all R-restricted evidence such that
> **every** R-restricted rule `π` (including randomized) with coverage `c(π)` on `Q_R(a*)` obeys
> **E[ regret(π) ] ≥ c(π) · Δ(R)**, with `Δ(R) > 0`.
> Hence: full coverage (`c=1`) ⇒ regret `≥ Δ(R)`; zero regret ⇒ `c=0` (abstain on the whole class). A
> leaderboard-regime rule (`R = {quality, cost}`, **never abstains**, `c=1`) pays `≥ Δ(R)` on **every**
> off-regime-binding class.

*Proof.* §8.2–§8.4 give the per-instance bound `max(p_s δ, p_c λ) ≥ c·Δ(R)` for the gadget. For a
*distributional* statement over `Q_R(a*)`, embed: let a fraction `η` of `Q_R(a*)` be gadget-copies and `1−η`
be on-regime-binding (regret 0 achievable); since a single R-restricted rule must act on the indistinguishable
gadget inputs identically, `E[regret] ≥ η · c · Δ(R)`. ∎

### 8.6 Upgrade — characterization (the part with teeth)

The bound's converse is constructive and is the more interesting half (it shows some off-regime axes *are*
recoverable). Define the **certifiable closure**
`cl(R) = R ∪ { a' : a' is a known monotone/deterministic function of axes in R under q's fixed context, and
that map is itself in E }`. Example: under fixed hardware and batch, energy may be a source-provided function
of latency × power-draw; then latency-evidence certifies energy even though energy ∉ R.

> **Characterization (modulo degeneracies).** `q` is evidence-decidable under `R`  ⇔  `bind(q) ⊆ cl(R)`.

(⇐) if every binding axis lies in `cl(R)`, `B_E` certifies each binding constraint — directly or via the
closure map — so `argmin cost` is determined, hence decidable. (⇒) is the gadget: if `bind(q) ⊄ cl(R)`,
build `W₁,W₂` differing on a binding axis outside `cl(R)` → underdetermined. The non-obvious content is
`cl(R) ⊋ R`. **This is the piece that benefits from a theory collaborator** if pushed to full generality
(general closure operators, multi-axis binding); the gadget-level version above stands alone.

### 8.7 Corollary — **irreducible regret = value of information of the omitted binding axis**

Define `VoI(a*) =` reduction in achievable worst-case regret from admitting `a*` into the regime
`= Δ(R) − Δ(R ∪ {a*})`. For the gadget, observing `a*` certifies the constraint, so `Δ(R ∪ {a*}) = 0`, giving

> **VoI(a*) = Δ(R).**

The irreducible regret of an evidence regime on `Q_R(a*)` **equals** the value of information of the binding
axis it omits. This single identity unifies §7 and §8 here and is the candidate Oral-line of the paper. It
also imposes a hard obligation on P4: the implemented VoI must *empirically match* `Δ(R)` on the slice, or the
intro's paragraph 4 overclaims.

### 8.8 Honest scope (do not overclaim)

- The two-point machinery is **standard**; a theory-pure reviewer will find the gadget elementary. The defense
  is that the theorem is **one of three co-equal contributions** (decidability map + theorem + procedure), and
  that §8.6–§8.7 (closure characterization + VoI identity) are the non-routine parts.
- "Real mis-sizing exceeds `Δ(R)` because cost–latency–energy are correlated / heavy-tailed" is a **conjecture
  until P5 measures it.** In the paper it is *empirical confirmation*, never a corollary of the theorem.
- If §8.6 cannot be made clean and non-trivial **and** the §6 guarantee turns out no stronger than vanilla
  selective classification → drop the theorem, fall back to NeurIPS-ED (measurement-as-thesis needs no
  theorem). Gate noted in master plan §18.2.

---

## 9. ★ What P0 fixes that P1 depends on — the substrate interface contract (the handoff)

P1 builds the substrate **against this fixed interface**. Everything to the *left* is substrate (P1);
everything to the *right* is solver (P4). The interface is the C7 firewall made concrete and must not change
once P1 starts — that immutability is what lets P4 swap solvers without touching storage.

```
SUBSTRATE  (P1: relational, SQLite)                 |  SOLVER  (P4: separate layer)
----------------------------------------------------|--------------------------------------------
candidates(τ)        → set of x ∈ X(τ)              |  Agg_φ(·|κ)        — derive B_E from O_E
cell(x, a)           → O_E(x,a) : observation set,  |  certify_*(x,c,α)  — three-state classifier
                       each o = ⟨val/cat, conf,     |  VoI(f) / cost     — acquisition ranking
                       evidence_id, source_type,    |  calibrate(α)      — guarantee on GT slice
                       context⟩                     |  pareto_under_unc  — frontier under B_E
required_fields(c)   → axes that bundle c binds on  |
```

**Invariant (the contract):** the substrate returns **observation sets with provenance and context**, and
*nothing else* — no aggregation, no certification, no optimization. Aggregation mode `φ`, confidence filter
`κ`, risk `α`, and every decision predicate are solver-side. Concretely: changing the solver from
lexicographic → chance-constrained → selective must require **zero** change to the substrate.

---

## 10. P1 build spec (requirements, not implementation)

The schema is P1's deliverable; below is what §3 (here) *requires* it to hold. Stating requirements now is the
P0→P1 bridge — it is not the schema itself.

**The schema must hold:**
1. an **observation** as the atomic storage unit — many observations per `(x,a)` cell, each carrying
   `{val_or_cat, confidence∈{H,M,L}, evidence_id, source_type, context}` (C2: provenance + uncertainty
   first-class; no bare points);
2. **composition as a first-class entity** — `x` decomposes into reusable components with lineage; a flat table
   cannot express component reuse or where a value came from;
3. **referential integrity (FK)** linking every observation to its evidence source — this *is* the provenance
   guarantee (`∃ source`) enforced at the storage layer, i.e. auditability as an executable constraint;
4. **`⊥` via absence**, queried under a confidence filter — `is_missing` is `COUNT(observations WHERE
   confidence ∈ κ) = 0`, not a stored boolean (§3.2 here);
5. **comparison context retained** on every observation (metric name/direction/unit/dataset/split/hardware) so
   commensurability is checkable (C6).

**The "why relational / SQL" answer, now derivable (for the advisor question):** requirements (1)–(4) are
*precisely* what normalization + foreign keys + NULL-semantics provide and what a flat table cannot — so the
relational choice is forced by the observation model, not by preference. SQLite gives zero-config, offline,
reproducible snapshots (C3). **C7 caveat:** SQL is substrate + baseline retrieval only; all aggregation,
certification, VoI, and the guarantee live in the separate solver layer per §9.

**Minimal seed (velocity, not coverage):** start with **HELM Lite** only — enough to exercise the interface
end-to-end (`candidates → cell → required_fields`) and run the Appendix-E baseline query. Breadth across the
4 regimes is P2's job, deliberately *periphery* for P1.

---

## 11. Open formal questions carried forward (honest flags)

- **Q1 (theorem depth).** Can §8.6's closure characterization be made clean and non-trivial in full generality?
  If yes, it is the theorem's real contribution; if no, the gadget-level version still backs the necessity
  claim. Candidate collaborator task; not P1-blocking.
- **Q2 (binding axis operational).** The whole framing presumes `bind(q)` is recoverable on real data. P3 must
  define "binding" concretely from the constraint bundle + observed Pareto structure — an unstated dependency
  of paragraph 3 of the intro.
- **Q3 (empirical vs Δ(R)).** Whether real leaderboard mis-sizing exceeds `Δ(R)` is open until P5. Until then it
  is empirical confirmation, never theorem corollary (§8.8).
- **Q4 (VoI = Δ(R) on data).** §8.7 is exact on the gadget; P4 must show the implemented VoI tracks `Δ(R)` on
  the ground-truth slice, or paragraph 4 of the intro overclaims.
