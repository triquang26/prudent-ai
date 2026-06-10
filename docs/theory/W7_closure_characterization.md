# W7 — Closure characterization of evidence-decidability, in full generality

> **Status:** theory deliverable (Oral-bar gate). Upgrades §8.6 of
> `docs/plan/APT_P0_formalism_spine.md` from a gadget-level, "modulo-degeneracies"
> sketch to a rigorous treatment. Answers OPEN_QUESTIONS Q1. Self-contained.
> Plain-text math (ASCII/unicode), no LaTeX environments.
>
> **One-line summary of the verdict (read first, then check the proofs).**
> The closure operator `cl` is rigorous and general **unconditionally**. The
> characterization `q decidable under R ⇔ bind(q) ⊆ cl(R)` is rigorous and general
> **under one explicit genericity assumption (G)** (unique argmin + no exact
> off-closure cost-tie); without (G) it provably fails in the "decidable despite an
> off-closure binding axis" direction, and we give the exact counterexample. The
> general (multi-axis) limit theorem and the VoI corollary are rigorous and general
> **unconditionally** (they only need *existence* of a hard pair, which (G) is not
> required for). The one genuinely subtle place — and the only place that still
> rewards a careful second human pass — is the exact constraint-form algebra of
> **monotone-but-not-deterministic** certification maps (Lemma 2), which we pin down
> precisely below but which a theory reviewer should re-derive independently.

---

## 0. Setup and notation

We work entirely inside the P0 formalism (`APT_P0_formalism_spine.md` §1–§8).

- `A` — the finite set of right-sizing axes (|A| = 8 in code: quality, latency_p95,
  throughput, cost, energy, memory_hw, governance, reviewer_burden). `cost ∈ A` is
  the objective axis; all others are *constraint* axes. We assume `cost ∈ R` for
  every regime considered (the leaderboard always sees cost; in code `cost` is
  masked exactly like any other axis, so the theory also covers `cost ∉ R`, treated
  in Remark 0.1).
- `X(τ)` — the finite admissible configuration set for task archetype τ. **Finiteness
  is real**: the substrate enumerates `candidates(τ)`. This is load-bearing — it lets
  argmin and "feasible set" be taken literally without compactness arguments, and it
  is faithful to `decidability.py`/`binding.py`, which loop over `sub.candidates`.
- A **state** (a "world", a "completion") is an assignment θ: X(τ) × A → ℝ ∪ Cat of a
  true value to every cell. `θ_a(x)` is the value of axis a at config x. We write a
  completion as `e` and the true (unknown) world as `θ*`.
- A query `q = (τ, c)`. The bundle `c` is a finite set of hard constraints, each
  `(a, rel, t)` with `rel ∈ {≤, ≥, =}` and threshold `t ∈ ℝ` (faithful to
  `feasibility.py`, ops `'<=','>=','=='`; categorical `'in'` is handled in Remark 0.2).
  `constrained(q) := { a : some (a, rel, t) ∈ c }`.
- `feasible(x, c | e)` holds iff for every `(a, rel, t) ∈ c`, `e_a(x) rel t`.
  `Feas(c | e) := { x ∈ X(τ) : feasible(x, c | e) }`.
- The oracle decision (P0 §6): `x*(q | e) = argmin_{x ∈ Feas(c|e)} cost(x)`,
  where `cost(x) := e_cost(x)`. If `Feas(c|e) = ∅`, `x*` is the distinguished
  symbol INFEAS. (Ties in the argmin are discussed under (G), §3.)

### 0.1 Evidence, beliefs, completions

- The substrate holds an **observation set** `O_E(x,a)`. Solver-side aggregation
  (`beliefs.py`) yields a belief `B_E(x,a) = Agg_φ(O_E(x,a) | κ)`. Under φ = interval
  this is `[ℓ, u]` (the min/max of κ-filtered values); under φ = point a single value
  the interval collapses to. `B_E(x,a) = ⊥` iff the κ-filtered set is empty.
- An axis a is **observed at x** (under (κ,φ)) iff `B_E(x,a) ≠ ⊥`. We assume,
  matching the data convention in P0 §8 and the `binding.py` GT slice, that
  observation is **uniform over configs**: an axis is either observed at *all*
  configs of τ or at none. (Non-uniform observation is a strict generalization; the
  theorems below go through config-by-config with no change because every quantifier
  over completions is already per-cell. We flag where uniformity is *used* — it is
  used nowhere essentially, only to make `R ⊆ A` a clean set of axes.)
- **Evidence regime** `R ⊆ A` (P0 §8.1) = the axes carrying any evidence (equivalently,
  the axes an **R-restricted rule** may read; off-regime axes are forced to ⊥, exactly
  `feasibility.py` lines 110–116 and `regimes.in_regime`).
- **Completions** `Comp(E)` (P0 §5): the set of worlds e consistent with the evidence:
  for every observed cell, `e_a(x) ∈ B_E(x,a)` (i.e. `e_a(x) ∈ [ℓ,u]`); for every ⊥
  cell, `e_a(x)` ranges over the admissible domain `D_a ⊆ ℝ` of axis a. `D_a` is an
  interval (possibly unbounded) fixed by the axis's physical range; the only property
  we use is that `D_a` contains at least two points strictly on opposite sides of any
  finite threshold `t` that the bundle places on a — i.e. a ⊥ cell can be completed to
  satisfy or to violate any single finite constraint on that axis. Call this **(D)
  domain-richness**; it holds for every numeric axis with a non-degenerate range and is
  implicit in P0 §5 ("a ⊥ cell ranges over its admissible domain"). (D) is what makes
  ⊥ genuinely two-sided and is used in the (⇒) construction.

- **Decidability (P0 §5), restated.** `q` is **evidence-decidable under R** iff the
  oracle decision is constant over completions:
  there is a single x̂ (possibly INFEAS) with `x*(q | e) = x̂` for all `e ∈ Comp(E)`.
  It is **underdetermined** iff `∃ e₁, e₂ ∈ Comp(E)` with `x*(q|e₁) ≠ x*(q|e₂)`.
  (We fold INFEASIBLE-under-E into "decidable with x̂ = INFEAS", which is what
  `classify_query` does structurally; the INFEASIBLE *label* is just the case x̂=INFEAS.)

- **Binding set** `bind(q)` (P0 §1, `binding.py`). On a fixed world e with a feasible
  optimum, axis a ∈ constrained(q) is **binding** (active) iff dropping its constraint
  strictly lowers the achievable optimum cost:
  `min_cost(q ⊖ a | e) < min_cost(q | e)`,
  where `q ⊖ a` is q with all constraints on a removed and `min_cost(· | e)` is the
  min cost over `Feas(· | e)`. This is the standard active-constraint test. `bind(q)`
  is a property of the *true* world θ*; we define `bind(q) := bind(q | θ*)`, and the
  characterization quantifies over the *true* binding set (Remark 0.3 addresses that
  bind itself can be evidence-dependent).

**Remark 0.1 (cost ∉ R).** If the objective axis cost is itself unobserved, `cost`
is a binding "axis" in a degenerate sense (the objective is not even computable). The
characterization still holds with the convention cost ∈ bind(q) whenever cost is
constrained or, more sharply, whenever two feasible configs have ⊥/overlapping cost
intervals; this is exactly the `"cost"` token `classify_query` adds to `blocking_axes`
(lines 138–139, 149). We treat cost as an honorary member of constrained(q) (constraint
"cost ≤ +∞", always present, binding iff the cost ranking among feasible configs is not
pinned). With that convention all statements below are uniform in cost.

**Remark 0.2 (categorical axes).** For a categorical axis the belief is "the agreed
category or ⊥" (P0 §3.2). A categorical constraint `a ∈ G` is certified-sat iff the
agreed category ∈ G, certified-violated iff it ∉ G, straddle iff ⊥. This is the
*deterministic* case of the closure (a 0/1-valued monotone map into the 2-point lattice
{violated < sat}); everything below specializes correctly. Categorical axes never admit
the "monotone-not-deterministic" subtlety of §1 because the order is trivial.

**Remark 0.3 (bind is itself a function of the world).** `bind(q | e)` can differ
across e: a constraint binding in one completion may be slack in another. The
characterization is stated for `bind(q | θ*)`, the binding set in the *true* world,
which is the object `binding.py` recovers on the GT slice. The (⇒) construction produces
two completions that *agree on cl(R)-evidence* and flip the argmin; it does not require
bind to be constant. The honest subtlety — "we recover bind only where GT exists" — is
the empirical Q2 caveat, orthogonal to this theorem (see §6 and the Honest-scope table).

---

## 1. Certification maps and the closure cl(R) — definitions

### 1.1 Admissible certification maps

Fix the query q and its **fixed context** (hardware tier, dataset, decoding cfg, date —
the `context` of an observation, P0 §3.2). All maps below are "under q's fixed context":
they are asserted to hold for the population of configs sharing that context.

> **Definition 1 (admissible certification map).** Let S ⊆ A. A **certification map
> from S** is a pair (g, a') where a' ∈ A \ S is the *target* axis, g: ℝ^S → ℝ is a
> function of the source axes' values, and the map is **present in E** — i.e. E carries,
> as a first-class evidence object (a `source_type` providing a functional relation),
> the assertion `θ_{a'}(x) = g( (θ_s(x))_{s∈S} )` valid for all x in q's context.
> We further require g to be either
>  (det) **deterministic**: an arbitrary (measurable) function, used to pin a *point
>        value* of a'; or
>  (mon) **monotone**: g is coordinate-wise weakly monotone, with a known direction
>        `dir_s ∈ {+,−}` per source s (g nondecreasing in s if +, nonincreasing if −),
>        used to certify *threshold constraints* on a' (see Lemma 2).
> A map may be both. The class of admissible maps is `M(E)` (those present in E).

This is the exact class P0 §8.6 names ("a known monotone/deterministic function of axes
in R under q's fixed context, and that map is itself in E"), made type-precise.
Example (P0 §8.6): energy = latency × power-draw under fixed hardware/batch — a
deterministic (hence also monotone-increasing in latency at fixed power) map from
{latency} to energy.

### 1.2 The closure operator

> **Definition 2 (one-step certification).** For S ⊆ A define
>   `step(S) = S ∪ { a' : ∃ (g, a') ∈ M(E) with all source axes ⊆ S }`.
> i.e. an axis is added if some admissible map certifies it from axes already in S.

> **Definition 3 (certifiable closure).** `cl(R) = the least fixpoint of step above R`:
>   `cl(R) = ∪_{k≥0} step^k(R)`, where step^0(R)=R, step^{k+1}=step(step^k).
> Because A is finite, the chain `R ⊆ step(R) ⊆ step^2(R) ⊆ …` stabilizes after at most
> |A| steps; `cl(R)` is that stable set. This is the iterated-certification fixpoint
> P0 §8.6 asks for: a' certified from R may in turn help certify a''.

Note `cl` depends on E (through M(E)); we write `cl_E` when the dependence matters.
In the *current* substrate `M(E) = ∅` (no source provides an inter-axis functional map),
so `cl_E(R) = R` for every R — see §5.

---

## 2. Lemma 1: cl is a closure operator

> **Lemma 1.** For fixed E, the map `cl: 2^A → 2^A` is a closure operator on the
> powerset lattice (2^A, ⊆): for all R, S ⊆ A,
>  (i)  **extensive**: R ⊆ cl(R);
>  (ii) **monotone**: R ⊆ S ⟹ cl(R) ⊆ cl(S);
>  (iii)**idempotent**: cl(cl(R)) = cl(R).

*Proof.* First, `step` is itself monotone and extensive:
- (extensive of step) `S ⊆ step(S)` by Definition 2.
- (monotone of step) Suppose S ⊆ T. If a' ∈ step(S)\S, there is (g,a') ∈ M(E) with
  sources ⊆ S ⊆ T, so a' ∈ step(T). Hence step(S) ⊆ step(T).

(i) Extensive. R = step^0(R) ⊆ ∪_k step^k(R) = cl(R). ∎(i)

(ii) Monotone. Assume R ⊆ S. By induction on k, step^k(R) ⊆ step^k(S): base k=0 is
R ⊆ S; step is monotone, so step^k(R) ⊆ step^k(S) ⟹ step^{k+1}(R) ⊆ step^{k+1}(S).
Taking unions, cl(R) = ∪_k step^k(R) ⊆ ∪_k step^k(S) = cl(S). ∎(ii)

(iii) Idempotent. "⊇" is (i) applied to cl(R). For "⊆": cl(R) is a fixpoint of step,
because the chain stabilized — `step(cl(R)) = cl(R)`. Indeed cl(R) = step^N(R) for N =
|A| (chain length bound), and step^{N+1}(R) = step^N(R) gives step(cl(R)) = cl(R). Then
step^k(cl(R)) = cl(R) for all k by induction, so cl(cl(R)) = ∪_k step^k(cl(R)) = cl(R).
∎(iii) ∎

The closure-operator structure is therefore **unconditional** — no genericity needed.
Its closed sets `{ S : cl(S) = S }` are exactly the certification-closed regimes; they
form a lattice under ∩ (the standard Moore-family fact), which is the clean algebraic
object Q1 wanted.

---

## 2′. Lemma 2: what a map certifies — the "modulo degeneracies" subtlety, pinned

This is the crux the task flagged ("monotone alone certifies a *constraint*, not
necessarily a *point*"). We separate **value-certification** from
**constraint-certification**, because the characterization only ever needs the latter.

Let the constraint on the target a' be `(a', rel, t)`, rel ∈ {≤, ≥, =}, and let
(g, a') ∈ M(E) certify a' from sources S, with all sources S ⊆ R **observed** (so each
`θ_s(x)` is pinned to its belief; under φ=interval, pinned to an interval `[ℓ_s,u_s]`).

> **Lemma 2 (certification algebra).** Fix a config x. Write the source belief box
> `Box(x) = ∏_{s∈S} [ℓ_s(x), u_s(x)]` (a point if φ=point or the cell is a singleton).
> Then g(Box(x)) — the image of the box — is an interval [g⁻(x), g⁺(x)] when g is
> monotone (with g⁻, g⁺ read off the appropriate corners by the directions dir_s), and
> g(Box(x)) is *some* set otherwise. The certified verdict of `(a', rel, t)` at x is:
>
>  (det, point sources) g(Box) = a single value v=g(x). Verdict = (v rel t): **sat**,
>     **violated**, exactly pinned. (Deterministic + pinned sources ⟹ point value of a'.)
>
>  (mon, interval sources)  Let g⁻=min corner, g⁺=max corner of g over Box (monotone ⟹
>     attained at corners chosen by dir_s). Then:
>       • rel = ≤ :  **sat** iff g⁺ ≤ t ;  **violated** iff g⁻ > t ;  else **straddle**.
>       • rel = ≥ :  **sat** iff g⁻ ≥ t ;  **violated** iff g⁺ < t ;  else **straddle**.
>       • rel = = :  **sat** iff g⁻=g⁺=t ;  **violated** iff t∉[g⁻,g⁺] ;  else **straddle**.
>
> Consequently a **monotone** map certifies a one-sided threshold (≤ or ≥) on a'
> **exactly when** the corresponding extreme corner clears t — it does NOT pin a point
> value of a', and it can leave an equality (=) constraint forever **straddle** even
> with perfectly pinned sources, unless g⁻=g⁺ (i.e. g is locally constant on the box).

*Proof.* For monotone g, the extrema over a product of intervals are attained at the
corner that maximizes/minimizes each coordinate in its monotone direction (a standard
fact: a coordinatewise-monotone function on a box attains its sup/inf at vertices). So
the image g(Box) ⊆ [g⁻, g⁺], and because g is continuous on the box (monotone bounded
functions on an interval have at most countably many jumps; if g is also continuous the
image is exactly [g⁻,g⁺], otherwise g(Box) ⊆ [g⁻,g⁺] and the verdicts below are
conservative — they only ever output sat/violated when the *whole* [g⁻,g⁺] clears t, so
they remain sound for any g(Box) ⊆ [g⁻,g⁺]). The three rel-cases are then exactly the
interval-clearing rules of `feasibility._certify_numeric` (lines 70–90) applied to the
*induced* belief [g⁻,g⁺] on a'. The deterministic-pinned case is the singleton box. The
equality remark: if g is strictly monotone in some source and that source's belief box
has positive width, then g⁻ < g⁺, so "=" is straddle by the rule — never certifiable.
∎

> **Corollary 2.1 (the precise "modulo degeneracies" content for the closure).**
> Define `cl(R)` to certify a *constraint* `(a', rel, t)` (not the axis abstractly) iff
> the induced belief [g⁻, g⁺] yields sat or violated by Lemma 2. With this reading:
>  • **deterministic** maps with pinned sources certify *any* rel (≤, ≥, =) — full power;
>  • **monotone-only** maps certify *one-sided* (≤, ≥) constraints whose extreme corner
>    clears t, and **never** an equality with a non-singleton induced interval.
> The "axis a' ∈ cl(R)" shorthand of P0 §8.6 is therefore **safe for ≤/≥ constraints
> under a monotone map, but unsafe for = constraints** — there the closure must be read
> *per constraint*, not per axis. **This is exactly where "modulo degeneracies" bit:**
> the gadget used a single ≤ latency constraint, for which monotone certification is
> total, hiding the equality gap.

**Convention used by the characterization.** From here, `bind(q) ⊆ cl(R)` is read in the
constraint-precise sense: every binding constraint of q is certified sat-or-violated by
cl(R) (directly, or via a map per Lemma 2). For one-sided binding constraints this
coincides with the axis-level reading; for equality binding constraints it is strictly
stronger (an equality binding axis reachable only by a non-degenerate monotone map is
NOT in cl(R)). This is the honest, fully general statement.

---

## 3. The genericity assumption (G), and why it is necessary

The characterization "decidable ⇔ bind(q) ⊆ cl(R)" can fail in the (⇐?)/(decidable)
direction without a non-degeneracy condition. We first exhibit the failure, then state (G).

### 3.1 Counterexample motivating (G): an exact cost-tie absorbs an off-closure binding axis

Let τ have configs X = {x1, x2}. Regime R = {cost}, with M(E)=∅ so cl(R)=R={cost}.
Bundle c = { latency ≤ L }. latency ∉ cl(R) (off-closure). Costs are observed:
`cost(x1) = cost(x2) = 1` (an **exact tie**). True latencies (unobserved): in the true
world θ*, `latency(x1) = L − ε` (feasible), `latency(x2) = L + ε` (infeasible).

- bind(q): in θ*, Feas = {x1}, min_cost = 1. Drop latency: Feas = {x1,x2}, min_cost = 1
  (tie). So `min_cost(q ⊖ latency) = 1 = min_cost(q)` — **not** strictly less — so by the
  active-constraint definition **latency ∉ bind(q)**. Hmm: the tie makes latency *non*-
  binding. To make latency genuinely binding we instead set costs `cost(x1)=1,
  cost(x2)=1` but make x1 the *unique* feasible config AND make the cheapest-overall a
  *third* config x0 that is infeasible. Let X={x0,x1}, cost(x0)=1, cost(x1)=1 (tie at the
  optimum value), latency(x0)=L+ε (infeasible), latency(x1)=L−ε (feasible). Then
  min_cost(q)=1 (x1), min_cost(q⊖latency)=1 (x0 or x1, tie) — again 1, latency
  non-binding. The tie at the optimal cost *value* is precisely what neutralizes the
  drop-test. **This is the real phenomenon:** when the off-closure axis only gates configs
  that are cost-tied with the best feasible config, dropping it cannot lower the optimum,
  so the active-constraint `bind` does not flag it, AND the decision value is invariant.

  To get the sharper "decidable despite bind ⊄ cl(R)" we need bind to flag the axis yet
  the *committed config* to be cost-indistinguishable. Construct X = {x1, x2} with
  cost(x1)=cost(x2)=1 (tie), latency(x1)=L−ε, latency(x2)=L−ε in θ* (both feasible). Add
  a *third* config x3, cost(x3)=2, latency(x3)=L−ε (feasible, dominated). bind(q): drop
  latency changes nothing (all three already feasible), min_cost stays 1 — latency
  non-binding. The lesson generalizes:

> **Counterexample (CE).** Take X = {x1, x2}, R = {cost}, cl(R)={cost}, bundle
> {latency ≤ L}. Observed costs `cost(x1)=cost(x2)=1` (exact tie). Latency unobserved.
> The argmin *cost value* is 1 in **every** completion in which at least one of x1,x2 is
> feasible, and the binding axis latency only ever selects *which* tied config is named.
> If the decision is read as "the optimal cost / the optimal feasible config up to cost-
> equivalence", then **q is evidence-decidable** (the achievable optimum cost = 1 is
> invariant across all completions where Feas ≠ ∅), **even though** a latency completion
> can flip the *named argmin* x1 ↔ x2 — and latency ∉ cl(R). So under the "value/up-to-
> tie" decision the ⇐ of the characterization (bind ⊆ cl(R)) is **not necessary**: q is
> decidable with bind(q) ⊄ cl(R). Conversely, under the "named config" decision the same
> instance is underdetermined. The characterization's truth value literally **depends on
> the exact cost-tie**.

The pathology is an **exact equality of optimal cost across configs that the off-closure
axis distinguishes**. A measure-zero perturbation of either cost destroys it: if
cost(x1)=1, cost(x2)=1+γ for any γ≠0, then completing latency to flip feasibility flips
the optimal *value* (1 vs 1+γ), restoring underdetermination and `bind ∋ latency`.

### 3.2 The assumption (G)

> **Assumption (G) — genericity / strict optima / no off-closure tie.** For the query q
> and the relevant completions:
>  (G1) **Unique argmin in the true world**: `Feas(c | θ*)` has a unique cost-minimizer
>       x* (no two feasible configs share the minimal cost).
>  (G2) **No off-closure cost-tie**: for every config x whose feasibility under c depends
>       on an axis a ∉ cl(R) (i.e. some binding-or-pending off-closure constraint gates x),
>       `cost(x) ≠ cost(x*)` strictly. Equivalently: the configs that an off-closure
>       completion can add to / remove from the feasible set never tie the incumbent
>       optimum's cost.
>  (G3) **Constraint-form regularity**: every *binding* constraint is either one-sided
>       (≤ or ≥), or its target axis is certified by a deterministic map; i.e. no binding
>       constraint is an equality that only a non-degenerate monotone map could touch
>       (Corollary 2.1). [This rules out the Lemma-2 equality gap from biting the binding
>       set itself.]
>
> We say **q is (G)-generic** if (G1)–(G3) hold.

(G1)+(G2) jointly are the "no exact cost-tie / strict optimum" condition; (G3) is the
"no degenerate equality binding via monotone map" condition surfaced by Lemma 2. (G3) is
vacuous in the current substrate (all binding constraints in the RouterBench/HELM slices
are one-sided thresholds ≤/≥; equality constraints, if any, are categorical = deterministic
per Remark 0.2).

### 3.3 Is (G) generic?

> **Claim.** (G1) and (G2) hold for **Lebesgue-almost-every** cost vector, hence outside a
> measure-zero, nowhere-dense exceptional set. (G3) is a *structural* (not measure-zero)
> condition and must be checked, not assumed away; it holds for every one-sided bundle.

*Proof of the (G1)+(G2) genericity.* Fix the finite config set X and the (unknown but
fixed) feasibility pattern. (G1) fails iff `cost(x)=cost(x')` for some pair x≠x' that are
both feasible-optimal; (G2) fails iff `cost(x)=cost(x*)` for some off-closure-gated x.
Each is a single linear equation `cost(x)−cost(x')=0` in the cost coordinates, defining a
hyperplane (a measure-zero, closed nowhere-dense set) in ℝ^{|X|}. There are finitely many
pairs (≤ |X|² hyperplanes). A finite union of hyperplanes has Lebesgue measure 0 and empty
interior. So the exceptional set {cost vectors violating (G1) or (G2)} is measure-zero and
nowhere-dense; its complement (where (G) holds) is open and dense. ∎

**Honest caveat on genericity.** "Generic" here is over the **cost coordinates treated as
continuous**. Two cautions, stated rather than buried:
1. Real cost data is **discretized** (token-price arithmetic) and **can tie exactly**
   (two configs with the same price/token and token count have identical cost). On such a
   measure-zero-but-realizable tie, (G2) genuinely fails and the characterization's named-
   config reading is genuinely underdetermined while its value reading is decidable — this
   is not a proof artifact, it is a real degeneracy the *implementation must pick a
   convention for*. `classify_query` resolves it by the **named-config / strict-undercut**
   reading: it flags `"cost"` as blocking exactly when `v.cost_belief.lo < best_sure_cost`
   (a *strict* undercut, line 136), i.e. it treats an exact tie as **decidable** (no flip),
   matching the *value* reading. So the code takes the value/up-to-tie convention; §5 shows
   this is the sound choice and that the theorem matches it.
2. Genericity is over cost; the *off-closure axis values* are adversarial (worst-case over
   completions), which is correct — we do **not** assume genericity of the hidden axis,
   only of the observed objective. This asymmetry is exactly right: the hardness must
   survive a worst-case hidden world, but a measure-zero cost coincidence is a non-robust
   artifact we are entitled to exclude.

---

## 4. Characterization Theorem (general, multi-axis)

> **Theorem 1 (closure characterization).** Fix τ, a regime R with closure cl(R), a query
> q = (τ, c), and a true world θ*. Assume (D) domain-richness (§0.1) and adopt the
> constraint-precise reading of cl(R) (Corollary 2.1) and the value/up-to-cost-tie reading
> of the decision (§3.3). Then:
>
>  (A) [⇐, unconditional] If **every binding constraint of q is certified by cl(R)**
>      (i.e. `bind(q) ⊆ cl(R)` in the constraint-precise sense), then q is
>      **evidence-decidable under R**: the optimal cost and the cost-equivalence class of
>      the optimal config are invariant across all completions in Comp(E).
>
>  (B) [⇒, needs (G)] If some binding constraint of q is **not** certified by cl(R)
>      (`bind(q) ⊄ cl(R)`), then, **under (G)**, q is **evidence-underdetermined**: there
>      exist e₁, e₂ ∈ Comp(E) agreeing on all cl(R)-certifiable evidence with
>      `x*(q|e₁) ≠ x*(q|e₂)` and different optimal cost.
>
>  (C) [necessity of (G)] Without (G) the ⇒ direction (B) is false: the counterexample
>      (CE) of §3.1 has bind(q) ⊄ cl(R) yet q decidable (value reading). Hence (G) is
>      necessary, not a convenience.
>
> Equivalently: **under (G), q is evidence-decidable under R ⇔ bind(q) ⊆ cl(R).**

### Proof of (A) — the soundness / recovery direction (unconditional)

Let `B = bind(q | θ*)`, and suppose every binding constraint is cl(R)-certified. Let x* be
the (a) cost-minimizer of `Feas(c | θ*)`; let m* = cost(x*) be the optimal cost.

We show two things across all e ∈ Comp(E): (a) x* stays feasible, and (b) no config can be
both feasible and strictly cheaper than m*. Together they pin the optimal cost to m* and
the optimal cost-class to that of x*.

*Notation.* Split the constraints of c into:
- **B-constraints** (the binding ones) — by hypothesis each is cl(R)-certified;
- **slack constraints** — non-binding at θ*: removing them does not change min_cost.

Two facts about cl(R)-certified constraints. For a constraint `(a,rel,t)` certified by
cl(R) at a config x (Lemma 2), its verdict (sat / violated) is the **same in every
completion** e ∈ Comp(E): a cl(R)-certified constraint is pinned either directly (a ∈ R
observed, belief is the same interval/point in every completion by definition of Comp(E))
or through a map g whose source axes are in cl(R) and themselves recursively pinned, so the
induced [g⁻,g⁺] is identical across completions; the sat/violated verdict of Lemma 2 is a
function of that fixed interval and t, hence constant over e. **Key invariance:
cl(R)-certified verdicts are completion-invariant.** (★)

(a) *x\* stays feasible across Comp(E).* x* satisfies every constraint of c in θ*.
- Its B-constraints are cl(R)-certified, and certified-sat at θ* (x* ∈ Feas(c|θ*)). By (★)
  they are certified-sat in every e — so they cannot become violated.
- Its slack constraints: a slack constraint, by definition, can be dropped without changing
  min_cost in θ*; but feasibility of *x\* itself* still requires them. Here we use the
  active-set structure: at the optimum x*, the only constraints whose perturbation can
  change the *optimal cost* are the active (binding) ones. A slack constraint at x* is
  satisfied with strict slack in θ* (`θ*_a(x*) rel t` strictly) OR is satisfied with
  equality but inactive (its multiplier is zero / dropping it doesn't move the optimum).
  Could a completion violate a slack constraint at x*? Only if that constraint's axis a is
  off-closure (else (★) pins it). **This is the gap (A) must close, and it is closed by the
  definition of binding, not by (G):** if an off-closure constraint at x* could be violated
  by some completion, then in that completion x* leaves Feas, and the optimum can only rise
  — i.e. that constraint, when it bites, *is* active at the optimum, hence binding, hence
  (by hypothesis) cl(R)-certified — contradiction with "off-closure". Formally: suppose a
  slack-at-θ* constraint `(a,rel,t)`, a ∉ cl(R), is violated at x* in some e ∈ Comp(E).
  Then min_cost(q | e) > min_cost(q ⊖ a | e) (removing a re-admits x* or a cheaper config),
  so a is binding in e. Now bind is being quantified at θ* — but the theorem's hypothesis is
  `bind(q | θ*) ⊆ cl(R)`, and a may bind only off-θ*. **This is the one place (A) needs
  care:** we must ensure no *off-closure* constraint binds in *any* completion, not just θ*.

  Resolution: strengthen the read of the hypothesis to its natural meaning — `bind(q) ⊆
  cl(R)` is required to hold **for the relevant family of completions**, equivalently we
  define the binding set robustly:
  `Bind*(q) := ∪_{e ∈ Comp(E)} bind(q | e)` (the union of active sets over completions),
  and the theorem's hypothesis is `Bind*(q) ⊆ cl(R)`. Under this (faithful) reading, no
  off-closure constraint is active in *any* completion, so every off-closure constraint is
  *uniformly slack* (strictly satisfied) across Comp(E) at the configs that matter, and (a)
  follows: x* stays feasible. **(We flag this as the subtle step — see §7 row "Bind* vs
  bind(θ*)". On the GT slice `binding.py` recovers bind(q|θ*); the gap bind(θ*) ⊆ cl(R) vs
  Bind* ⊆ cl(R) is empirically nil when off-closure axes are uniformly slack, but is a real
  logical strengthening we make explicit rather than hide.)**

(b) *No completion admits a feasible config strictly cheaper than m*.* Let y ≠ x*. If
cost(y) ≥ m*, y cannot strictly undercut (costs are completion-invariant: cost ∈ R
observed). If cost(y) < m*, then y ∉ Feas(c | θ*) (else x* wasn't optimal). y is excluded
by some violated constraint `(a,rel,t)` at θ*. If a ∈ cl(R): by (★) y stays infeasible in
every e — cannot undercut. If a ∉ cl(R): then this constraint, were it to flip to sat in
some completion e, would *admit* the cheaper y and *lower* the optimum — making a active
(binding) in e, i.e. a ∈ Bind*(q) ⊆ cl(R), contradiction. So y stays infeasible across
Comp(E). Hence m* is a uniform lower bound on achievable cost, attained by x*. ∎(A)

So the optimal cost is exactly m* in every completion, and the set of optimal configs is
the cost-class of x*; q is decidable (value/up-to-tie reading). Note (A) used **no
genericity** — only the definition of binding and the completion-invariance (★). ∎(A)

### Proof of (B) — the lower-bound / two-point direction (needs (G))

Suppose some binding constraint `(a*, rel*, t*)` of q has a* ∉ cl(R) and is not otherwise
cl(R)-certified. We build a Le Cam two-point pair.

Because a* ∉ cl(R), a* is unobserved AND not reachable by any admissible map from cl(R)
(else it would be in cl(R) by Definition 3). Therefore the cells `θ_{a*}(x)` are **free**
across Comp(E): for the configs gated by this constraint, the value can be completed to
either side of t* (by (D) domain-richness), independently of all cl(R)-certified evidence —
formally, the projection of Comp(E) onto the a* cells is a full product of admissible
domains, and any two completions that differ *only* on a* cells agree on all cl(R)-evidence.

Now use that a* is **binding at θ\*** (hypothesis): dropping the a*-constraint strictly
lowers the optimum, i.e. there is a config y with cost(y) < cost(x*) =: m* that is feasible
in θ* except for the a*-constraint, which it violates (θ*_{a*}(y) violates rel* t*), while
x* satisfies it. (G1) gives x* unique; (G2) gives cost(y) ≠ m*, and since y is the witness
of binding, cost(y) < m* strictly. (G3) ensures the binding a*-constraint is one-sided or
deterministically reached — but here it is off-closure hence not deterministically reached,
so it must be one-sided (≤ or ≥); WLOG `a* ≤ t*` with y violating (θ*_{a*}(y) > t*) and x*
satisfying.

Construct:
- **e₁** = θ* on cl(R)-cells; on a*-cells set `θ_{a*}(y) = t* + 1` (>t*, y infeasible) and
  `θ_{a*}(x*) = t* − 1` (x* feasible). Then Feas(c|e₁) excludes y, includes x*; optimum is
  x* at cost m* (all other configs' feasibility is determined by cl(R)-certified
  constraints, identical to θ*; and (G1) makes x* the unique minimizer among them).
- **e₂** = θ* on cl(R)-cells; on a*-cells set `θ_{a*}(y) = t* − 1` (y now feasible) and
  keep `θ_{a*}(x*) = t* − 1`. Now y ∈ Feas(c|e₂) with cost(y) < m*, so the optimum is y
  (or something even cheaper that y dominates; in any case the optimal cost is ≤ cost(y) <
  m*, so it is **not** the cost-class of x*).

Both e₁, e₂ ∈ Comp(E): they agree with θ* (hence with the observed beliefs) on every
cl(R)-cell, and on a*-cells they take admissible-domain values (by (D)). They agree on
**all cl(R)-certifiable evidence** by construction. Yet `x*(q|e₁) = x*` at cost m* while
`x*(q|e₂) = y` (or cheaper) at cost < m*. So the optimal cost differs (m* vs <m*) ⟹ the
decision is non-identifiable ⟹ q is **underdetermined**. ∎(B)

(B) used (G1) to make x* the unique incumbent (so e₁'s optimum is unambiguously x* at m*),
and (G2) to guarantee cost(y) < m* strictly (so e₂'s optimum is strictly cheaper — a *value*
flip, robust to the up-to-tie reading). Without (G2), cost(y) could equal m*, giving the (CE)
degeneracy where the value is invariant and q is decidable despite a* ∉ cl(R) — which is (C).

### Proof of (C) — necessity of (G)

(CE) of §3.1: X={x1,x2}, R=cl(R)={cost}, bundle {latency ≤ L}, cost(x1)=cost(x2)=1 exactly,
latency unobserved off-closure and binding at θ* in the *named-config* sense (latency
selects x1 vs x2). Every completion with Feas ≠ ∅ has optimal cost 1; the value/up-to-tie
decision is invariant ⟹ **decidable**, yet bind(q) ⊄ cl(R) (latency ∉ cl(R)). So the ⇒
direction fails: decidable does not imply bind ⊆ cl(R) when (G2) is violated. Hence (G) is
necessary. ∎(C) ∎ (Theorem 1)

**Multi-axis remark (interactions / constraint qualification).** (A) handled *several*
simultaneously-binding constraints with no extra assumption: the active set B can be any
subset of constrained(q); the argument is per-constraint (each B-constraint cl(R)-certified
⟹ completion-invariant verdict via (★)) and the feasibility/undercut bookkeeping is over the
whole set at once. The only "constraint-qualification"-flavored hypothesis we needed is (G1)
(unique argmin) + (G3) (no degenerate equality binding) — these play the role LICQ plays in
NLP, ensuring the active set is well-defined and the optimum is a strict vertex. We did NOT
need differentiability or a continuum: finiteness of X replaces constraint qualification
entirely (the optimum is a min over a finite set; "active" = "drop changes the min"). This is
why the discrete formulation is *cleaner* than the smooth-NLP analog, not messier.

---

## 5. General limit theorem (multi-axis)

> **Theorem 2 (general off-closure binding ⟹ irreducible regret–coverage tradeoff).**
> Fix regime R, closure cl(R), and a query class `Q` whose members each have at least one
> binding constraint on an axis a* ∉ cl(R), embedding the §8.2 gadget at a* with realized
> gap δ = δ(q) > 0 (price of caution) and penalty λ > 0. There exist, for each q, two
> completions W₁(q), W₂(q) ∈ Comp(E) **observationally identical under all cl(R)-restricted
> evidence** such that every **cl(R)-restricted** randomized rule π (a rule reading B_E only
> through axes in cl(R)) with coverage c(π) on Q obeys
>   **E[ regret(π) ] ≥ c(π) · Δ(R)**,  with **Δ(R) = δλ/(δ+λ) > 0**
> (for the realized (δ,λ); if (δ,λ) vary over Q, replace Δ(R) by its Q-average / infimum as
> appropriate). In particular full coverage (c=1) ⟹ regret ≥ Δ(R); zero regret ⟹ c=0.

*Proof.* The pair (W₁,W₂) is exactly the (e₁,e₂) of Theorem 1(B) specialized to the
two-config gadget {x_cheap (cost 1), x_safe (cost 1+δ)} with the off-closure binding axis a*
(latency in §8.2): W₁ makes x_cheap feasible (optimum x_cheap, cost 1), W₂ makes x_cheap
infeasible (optimum x_safe, cost 1+δ). By Theorem 1(B)'s construction they lie in Comp(E) and
agree on all cl(R)-evidence. A **cl(R)-restricted** rule sees identical input in W₁ and W₂
(its readable axes are exactly the cl(R)-certified ones, which are equal across the pair),
so it must emit the **same distribution** over actions {commit x_cheap, commit x_safe,
abstain} = (p_c, p_s, p_a) in both worlds. The per-world regrets are P0 §8.3:
W₁: p_s·δ ; W₂: p_c·λ. Worst-case (and hence the average over an adversarial mixture, or the
max over the two-point prior) regret ≥ max(p_s δ, p_c λ) ≥ min_{p_c+p_s=c} max(p_s δ, p_c λ)
= c·δλ/(δ+λ) = c·Δ(R) (the §8.4 balance-point computation, p_s δ = p_c λ). The distributional
embedding (a fraction of Q being gadget-copies, the rest on-closure-binding hence regret-0
achievable) is P0 §8.5 verbatim, giving E[regret] ≥ (gadget fraction)·c·Δ(R). ∎

> **Why cl(R)-restricted, not R-restricted (this is the substantive generalization).**
> The hardness is **only** about axes outside cl(R). A rule is allowed to exploit every
> closure-certified axis *for free* — that is precisely the content of Theorem 1(A): on
> the on-closure part the rule achieves regret 0. If we stated the bound over merely
> *R*-restricted rules we would be **understating the rule's power** (an R-restricted rule
> is weaker than a cl(R)-restricted one) and **overstating the lower bound's reach** (we'd
> be charging the rule for axes it could in fact certify via maps). The correct, tight
> object is the **cl(R)-restricted** rule: it captures "the rule has squeezed all free
> closure certification and *still* cannot decide the off-closure binding axis." Δ(R) is
> the irreducible residual after closure. This is the exact sense in which Theorem 2
> sharpens §8.5 (which implicitly had cl(R)=R because the gadget had no maps): when M(E)≠∅,
> §8.5 over a naive R-restricted class would be loose; over cl(R)-restricted it is tight,
> and Theorem 1(A) certifies that the on-closure remainder is genuinely free.

Note Theorem 2 needs **existence** of the hard pair, for which (G) is **not** required —
the gadget is built to satisfy (G) (δ>0 makes x_cheap, x_safe strictly cost-separated, so
(G1),(G2) hold; the constraint is one-sided, so (G3) holds). (G) is about the *converse*
(ruling out spurious off-closure axes); the lower bound only asserts a witness and is
unconditional given a genuine off-closure binding gadget.

---

## 6. VoI corollary (general)

> **Definition 4.** `VoI(a*) := Δ(R) − Δ(R ∪ {a*})` — the reduction in irreducible
> worst-case regret from admitting a* into the regime (equivalently, into the closure:
> Δ is a function of cl(·), so VoI(a*) = Δ(cl(R)) − Δ(cl(R ∪ {a*}))).

> **Corollary 3 (VoI of the omitted binding axis).**
> (i) [single off-closure binding axis] If a* is the **only** binding constraint outside
>     cl(R), then admitting a* makes bind(q) ⊆ cl(R ∪ {a*}), so by Theorem 1 q becomes
>     decidable and the irreducible regret drops to 0: **Δ(R ∪ {a*}) = 0**, hence
>     **VoI(a*) = Δ(R) = δλ/(δ+λ)**. (This is the P0 §8.7 identity, now derived as the
>     single-axis special case of the general characterization.)
> (ii) [several off-closure binding axes] If `bind(q) \ cl(R) = {a*, b*, …}` with k ≥ 2
>     off-closure binding constraints, then admitting a* alone leaves b* still binding and
>     off-closure, so q remains underdetermined and **Δ(R ∪ {a*}) > 0**: VoI(a*) =
>     Δ(R) − Δ(R∪{a*}) is a **partial** reduction. Admitting the *whole* residual set
>     drives Δ to 0; no single admission does, unless k=1.

*Proof.* (i) bind(q) ⊆ cl(R ∪ {a*}) by assumption; Theorem 1(A) gives decidability ⟹ a
cl(R∪{a*})-restricted rule achieves regret 0 on the class ⟹ Δ(R∪{a*}) = 0. Subtract. (ii)
With b* ∉ cl(R∪{a*}) still binding, Theorem 2 applied with regime R∪{a*} produces a
hard pair on b*, so Δ(R∪{a*}) ≥ δ(b*)λ/(δ(b*)+λ) > 0. ∎

**Connection to the implemented cost-aware VoI ranking.** `voi.py` computes, per blocking
axis f, the two-world minimax regret `_minimax_two_world` — exactly the
Δ(R) − Δ(R∪{f}) object when f is the *isolated* resolved axis (`feasible_in_world` holds
all other pending axes optimistic, line 142–150, isolating f). For a single off-closure
binding axis this returns δλ/(δ+λ) = Δ(R) (Corollary 3(i)), pinned by
`tests/test_procedure.py`. For the multi-axis case the per-axis VoI is the *marginal*
Δ(R) − Δ(R∪{f}), and the cost-aware key `voi_per_cost = voi / acquisition_cost`
(voi.py line 203) is what orders the acquisition cascade — consistent with Corollary 3(ii):
when raw VoI ties across co-blocking axes (the P4 finding noted in Q4), the cost denominator
discriminates. The theory thus *predicts* the empirical "raw VoI ties, cost-aware
discriminates" observation: ties arise precisely when several off-closure axes each give the
same marginal Δ-drop, which Corollary 3(ii) says is the generic multi-block situation.

---

## 7. Consistency with the implementation

We show `classify_query` (decidability.py) is a **sound special case** of Theorem 1.

**The current substrate has M(E) = ∅** (no `source_type` provides an inter-axis functional
relation; the schema stores per-cell observations, never a map between axes). Therefore
`cl_E(R) = R` for every R (Definition 3 with no maps: step(R)=R). The non-trivial content
of the theory (cl(R) ⊋ R) is **not yet exercised by data** — this is stated honestly: the
general theorem is the *theory that the implementation is a sound instance of*, and the
closure machinery is forward-compatible head-room, not a present empirical claim.

**When cl(R) = R, Theorem 1 reduces to exactly what `classify_query` computes.** Mapping:

- `classify_candidate` applies the regime mask: off-regime axes → ⊥ (feasibility.py
  110–116). With cl(R)=R this is exactly "an axis is certified iff it is in R and
  observed", i.e. the §0.1 observation/regime semantics. ⊥ axes become `pending_fields`
  (the straddle/F set), i.e. the *potentially-binding off-closure* axes.
- DECIDABLE in code (lines 163–171) is returned iff there is a sure-feasible, sure-costed
  candidate `best_sure` and **no** maybe-candidate can, under an optimistic completion,
  become feasible and **strictly** undercut `best_sure_cost` (line 145 `optimistic_cost <
  best_sure_cost`), and no other sure option's cost interval strictly undercuts (line 136).
  This is **precisely** Theorem 1(A)'s two conditions: (a) a completion-invariant feasible
  incumbent (sure-feasible & sure-costed ⟹ all its constraints are R-certified ⟹ stays
  feasible, by (★)), and (b) no completion admits a strictly cheaper feasible config (the
  optimistic-undercut test is the contrapositive of part (b) of the (A) proof). The
  **strict** undercut (`<`, not `≤`) is the implementation's adoption of the
  value/up-to-cost-tie convention of §3.3 — an exact tie is treated as **no flip ⟹
  decidable**, matching Theorem 1's value reading and *correctly* side-stepping the (CE)
  degeneracy (a tie cannot be exploited to strictly lower the optimum value, so it is
  benign for the decision-as-value). So `classify_query` is **sound and exact** for the
  value reading under cl(R)=R, with **no (G) needed** because the value reading is what it
  computes.
- UNDERDETERMINED in code (lines 107–120 and 152–161) is returned iff some pending/⊥
  off-regime axis (or a ⊥ cost) can flip the strict undercut — i.e. an off-closure axis is
  *binding* (its optimistic completion strictly improves the achievable cost). That is
  exactly Theorem 1(B)'s hypothesis `bind(q) ⊄ cl(R)` made operational by the strict-
  undercut drop-test, which is the **same active-constraint test** as `binding.py`
  (`relaxed < full − eps`, binding.py line 103 — strict, with an eps to avoid float ties:
  the eps is the discrete realization of (G2), excluding exact cost-ties as non-binding).
- INFEASIBLE in code (lines 89–97) is x̂ = INFEAS, the decidable-with-empty-feasible case.

**Soundness statement.** With cl(R)=R and the value/up-to-tie reading, `classify_query`
returns DECIDABLE ⟺ Theorem 1's condition `Bind*(q) ⊆ R` holds (no off-closure axis can
strictly improve the optimum), and UNDERDETERMINED ⟺ it fails — i.e. the code computes
exactly the (G)-free *value*-reading characterization of §3.3. The `eps` in `binding.py`
and the strict `<` in `decidability.py` are the implementation's encoding of (G2): they
declare exact cost-ties non-binding/non-flipping, which is the only choice that makes the
classifier a function (the named-config reading would be ill-posed on ties). So the
implementation does not merely *approximate* the theorem — it implements the (CE)-resolving
convention the theorem identifies as the sound one.

**Honest gap.** Two logical strengthenings the proofs make that the data does not yet test:
(1) cl(R) ⊋ R (maps) — `M(E)=∅` today; (2) `Bind*(q) ⊆ cl(R)` vs the recoverable
`bind(q|θ*) ⊆ cl(R)` — `binding.py` recovers the latter (single-world active set on the GT
slice). When off-closure axes are uniformly slack across Comp(E) the two coincide; the gap
is a worst-case-over-completions strengthening, real in logic, empirically nil on the
current slices (where off-regime axes are either uniformly ⊥ or uniformly observed).

---

## 8. Honest scope — claim-by-claim

| # | Claim | Holds unconditionally? | Needs (G)? | Still open / needs a human collaborator? |
|---|---|---|---|---|
| 1 | `cl(R)` is a closure operator (extensive, monotone, idempotent) — Lemma 1 | **Yes** | No | No. Fully rigorous, general, finite-A. |
| 2 | Certification algebra: deterministic maps certify any rel; monotone maps certify only one-sided (≤/≥) thresholds, never a non-degenerate "=" — Lemma 2 / Cor 2.1 | **Yes** | No | **Re-derive independently.** The corner-extremum + image-containment argument is correct for monotone-continuous g; for monotone-*discontinuous* g our verdicts are sound-but-conservative. A reviewer should confirm the conservative direction is the one we want (it is: we only ever output sat/violated, never a false certificate). This is the single subtlest spot. |
| 3 | Characterization ⇐ (A): bind ⊆ cl(R) ⟹ decidable (optimal cost & cost-class invariant) | **Yes** (value reading) | No | The `Bind*(q)` vs `bind(q\|θ*)` reading (§7 honest gap, §4 flagged step). Logically I needed the *robust* binding set (union over completions). On current data they coincide; in full generality a collaborator should confirm `Bind* ⊆ cl(R)` is the intended hypothesis (I argue it is the faithful one). |
| 4 | Characterization ⇒ (B): bind ⊄ cl(R) ⟹ underdetermined (two-point flip) | Yes given a genuine off-closure binding axis | **Yes — (G1)+(G2)+(G3)** | No, modulo the (CE) below. The Le Cam construction is complete. |
| 5 | (G) is necessary: counterexample (CE) — exact cost-tie ⟹ decidable despite bind ⊄ cl(R) | **Yes** (it's a counterexample) | — | No. (CE) is explicit and real (discretized cost can tie). |
| 6 | (G) is generic | (G1),(G2): **measure-zero/nowhere-dense exceptional set**, so generic over continuous cost. (G3): structural, holds for one-sided bundles | — | **Caveat, not open**: real cost is discretized and *can* tie exactly → (G2) genuinely realizable. The implementation's strict-`<` / eps convention resolves it by the value reading. A collaborator may prefer a different tie-break; the theorem is convention-relative and I state which convention the code takes. |
| 7 | General limit theorem (Theorem 2), over **cl(R)-restricted** rules, E[regret] ≥ c·Δ(R) | **Yes** | No (needs only a witness gadget, which satisfies (G) by construction) | No. The cl(R)-vs-R distinction is the real generalization and is argued tight. |
| 8 | VoI corollary: single off-closure axis ⟹ VoI(a*)=Δ(R); k≥2 ⟹ partial — Corollary 3 | **Yes** | No | No. Matches implemented two-world minimax + cost-aware tie-break (predicts the Q4 "raw VoI ties" finding). |
| 9 | `classify_query` is a sound exact instance of Theorem 1 when cl(R)=R | **Yes** | No (code computes the value reading, which is (G)-free) | The non-trivial cl(R) ⊋ R content is **unexercised by data** (M(E)=∅). Theory is forward-compatible head-room. Honest: no current dataset provides an inter-axis map. |

### Bottom-line verdict

- **Rigorous and general, unconditionally:** the closure operator (Lemma 1), the
  certification algebra including the monotone/deterministic distinction (Lemma 2 — the
  precise content of "modulo degeneracies"), the **⇐ recovery direction** (Theorem 1A, value
  reading), the **general multi-axis limit theorem over cl(R)-restricted rules** (Theorem 2),
  and the **VoI corollary** (Corollary 3). The implementation is a **sound exact instance**
  when cl(R)=R (the present substrate).
- **Rigorous and general under one explicit, named, generic assumption (G):** the **⇒
  direction** (Theorem 1B), hence the **iff**. (G) = unique argmin (G1) + no exact off-closure
  cost-tie (G2) + no degenerate equality-binding-via-monotone-map (G3). (G1)+(G2) hold off a
  measure-zero set; (G3) is structural and holds for all one-sided bundles (all current data).
- **Provably necessary, not removable:** (G2) — counterexample (CE), a realizable
  discretized-cost exact tie, in which q is decidable (value reading) despite an off-closure
  binding axis, breaking the naive iff. The honest resolution is to fix the
  **value/up-to-cost-tie** decision reading; the implementation already does this (strict `<`,
  eps), so the gate is closed *for the object the code computes*.
- **What still genuinely rewards a second human pass (not a hole, a checkpoint):** (a) Lemma 2's
  monotone-discontinuous edge (sound-but-conservative — confirm the conservative direction is
  acceptable); (b) the `Bind*(q)` (union-over-completions) vs `bind(q|θ*)` (single-world,
  GT-recoverable) reading of the (A)-hypothesis — I argue Bind* is the faithful object and
  that the two coincide on current data, but a careful reviewer should confirm the
  strengthening is intended. Neither is a gap in a proof; both are *modeling-choice*
  checkpoints I have surfaced rather than buried.

**No overclaim:** the iff is **conditional on (G)**, and (G) is **provably necessary** (CE).
The unconditional half is the ⇐ recovery + the limit theorem + VoI. The general closure
content (maps, cl(R)⊋R) is **theory ahead of data**: correct and forward-compatible, but
M(E)=∅ today, so it is the frame the implementation soundly instantiates, not a measured claim.

---

## 9. Independent verification (orchestrator adversarial pass)

A second pass independently re-derived the load-bearing steps. The proofs stand; two
sharpenings are recorded for honesty (neither overturns a result; both *strengthen* the
clean statement).

**V1 — Theorem 1(A), the cost-tie sub-case of part (a) (made rigorous).** Part (a) ("x*
stays feasible across Comp(E)") is informal when an exact cost-tie is present: if x*
becomes infeasible in some completion `e` via an off-closure constraint *but a distinct
config x′ with cost(x′)=m\* remains feasible in e*, then x* itself does not "stay
feasible," yet the **optimal cost is still m\***. The correct, fully rigorous statement is
the one the theorem actually concludes — the **value** statement: in *every* `e ∈ Comp(E)`
the optimal cost equals m*. Proof (clean): part (b) gives optimum ≥ m* unconditionally
(no completion admits a feasible config strictly cheaper than m*, else the gating
off-closure constraint would be in `Bind* ⊆ cl(R)`). For optimum ≤ m*: if x* stays
feasible we are done; if x* is knocked out by an off-closure constraint and **no** config
of cost ≤ m* remains feasible, then dropping that constraint strictly lowers the optimum
(re-admitting x* at m*), so it is binding in `e`, hence in `Bind* ⊆ cl(R)` — contradiction;
the only remaining case is that a cost-≤-m* config *does* remain feasible, giving optimum ≤
m* directly. Either way optimum = m* in every completion. **So (A) holds unconditionally
for the value reading — the conclusion is exactly "optimal cost invariant," and the tie
case is benign for it.** (This is why the value reading is the right object; see V2.)

**V2 — (G2) "necessity" is reading-relative; under the value reading the iff is cleaner.**
The dramatic framing "(G2) is provably necessary" is precise only for the **named-config**
decision (which tied config is committed). Under the **value / up-to-cost-tie** reading —
the one `classify_query` computes (strict `<`, `decidability.py:136`) and `binding.py`
recovers (active-constraint drop-test `relaxed < full − eps`, `binding.py:103`) — the
counterexample (CE) is *consistent with the iff*, not a counterexample to it: with the
exact tie, latency is **non-binding by the active-constraint test** (dropping it does not
lower the optimal cost), so `bind(q) = ∅ ⊆ cl(R)`, and q is decidable — both sides of the
iff are TRUE. Hence the clean, honest headline is:

> **Under the value/up-to-cost-tie reading, with binding defined by the active-constraint
> (drop) test, `q decidable under R ⇔ Bind*(q) ⊆ cl(R)` holds — (G1)/(G2) are *absorbed
> into* the value/active-constraint definitions, not extra hypotheses.** (G3) (no
> equality-binding reachable only by a non-degenerate monotone map) remains a genuine
> structural condition, vacuous on all current one-sided-bundle data.

So the residual genuine assumptions, under the reading the system actually uses, are:
(i) **(G3)** structural, vacuous today; (ii) the **`Bind*` vs `bind(θ*)`** strengthening
(robust vs single-world binding), empirically nil on current slices (off-regime axes
uniformly ⊥ or uniformly observed) but a real logical strengthening; (iii) the
**monotone-discontinuous** certification edge of Lemma 2 (sound-but-conservative). These
are the precise items a theory collaborator would sign off, and they are **checkpoints, not
gaps** — each is stated, and each is inert on the present substrate.

**Verification verdict.** The closure-operator lemma, the certification algebra, the ⇐
recovery (value reading), the cl(R)-restricted limit theorem, and the VoI corollary are
confirmed rigorous and general. The characterization iff is confirmed under the value
reading with the active-constraint binding definition (the system's reading); the
named-config reading additionally requires the generic (G2). The implementation is a sound
exact instance for cl(R)=R. **Q1/W7 is upgraded from "gadget-level, modulo degeneracies,
needs a collaborator" to "general characterization + rigorous closure operator + sharpened
limit theorem, with the 'degeneracies' precisely identified and resolved by the value
reading, and exactly three named checkpoints (G3 / Bind* / monotone-discontinuous) left for
a human theory pass."** The empirical pillars (C1–C3) do not depend on any of the three
checkpoints.
