# 3 Problem Formulation

We study a single question that the evaluation literature has left implicit:
**given the evidence that actually exists, is a deployment right-sizing decision identified at
all?** Every construct in this section exists to make that question precise and measurable.
The community improves the *estimate* — better benchmarks, cost-aware agent harnesses, more
reliable judges — under the tacit assumption that the frontier is estimate quality. We flip
the prior question to **sufficiency**: not *how precise is the belief about an axis* but
*does the belief identify the minimum-sufficient configuration*. The formalism below is
deliberately conservative — a textbook constrained optimum stated under partial observation —
because the novelty is not the optimization but the regime in which the optimization becomes
*non-identifiable*, and the measurement of how often that regime occurs.

## 3.1 Objects and notation

A **task archetype** $\tau \in \mathcal{T}$ names a workload (clinical summarization,
web navigation, code assist). A **configuration**, or **AI Box**,
$x \in \mathcal{X}$ is a fully configured assembly of components — model, context length,
retrieval backend, decoding parameters, orchestration — and $\mathcal{X}(\tau)$ is the set of
configurations admissible for $\tau$. A configuration is not atomic: it decomposes into reusable
components with lineage, a structure the substrate records as first-class (§4) and the formalism
relies on only insofar as two configurations may share evidence through shared components.

Right-sizing is judged on **eight axes**

$$
A = \{\,\text{quality},\ \text{latency\_p95},\ \text{throughput},\ \text{cost},\
\text{energy},\ \text{memory\_hw},\ \text{governance},\ \text{reviewer\_burden}\,\}.
$$

The axes split into two classes whose asymmetry is the empirical heart of the paper:

- **Measurable axes** $A_m = \{\text{quality},\ \text{cost},\ \text{latency\_p95},\ \text{energy}\}$,
  for which ground truth is in principle obtainable from a benchmark or a measurement;
- **Hard-to-observe axes** $A_h = \{\text{governance},\ \text{reviewer\_burden},\ \text{memory\_hw}\}$,
  the operational constraints that gate real deployments — regulatory admissibility, the human
  review budget, the on-device hardware envelope — and that no public evaluation corpus reports.

For each axis $a$ and configuration $x$ there is a **true value** $\theta_a(x) \in \mathbb{R} \cup \mathrm{Cat}$:
numeric for the metric axes, categorical (a finite set $\mathrm{Cat}$) for governance, hardware
tier, privacy, and human-review status. **The true value $\theta$ is never observed directly.**
A right-sizing procedure sees only *evidence about* $\theta$; the entire formulation is an account
of what that evidence does and does not determine.

A **query** is $q = (\tau, c)$ with a **hard constraint bundle** $c$: a list of constraints, each
of the form $(\text{axis } a,\ \text{relation},\ \text{target})$, e.g.
$\text{quality} \ge q^\*$, $\text{latency\_p95} \le L^\*$, $\text{governance} \supseteq G$,
$\text{hardware} \in H$, $\text{privacy} = P$, $\text{human\_review} = R$. We write
$\mathrm{bind}(q) \subseteq A$ for the **binding axes** of $q$: the axes whose constraint is active
at the optimum — those that, if relaxed, would change the chosen configuration. Making
$\mathrm{bind}(q)$ operational on real data is a measurement obligation, not a definitional
convenience; §4 records the substrate-side over-approximation (the *mentioned* axes) and §5 of the
empirical study recovers the *binding* axes from a real-deployment query prior.

## 3.2 The oracle right-sizing problem

Under full knowledge of $\theta$, right-sizing is a constrained minimum-cost selection. Writing
$\mathrm{feasible}(x, c)$ for the predicate that holds iff $\theta_a(x)$ satisfies every constraint
in $c$,

$$
x^\*(q) \;=\; \operatorname*{arg\,min}_{x \in \mathcal{X}(\tau)\,:\,\mathrm{feasible}(x, c)} \; \mathrm{cost}(x),
$$

the **minimum-sufficient configuration**: the cheapest box that meets every hard requirement. This
is the target against which every procedure — and every leaderboard heuristic — is judged, and it is
the **oracle baseline**, the floor on regret, the most that could be saved if all axes were known.
Nothing here is novel; it is deliberately a textbook constrained optimum. The content is everything
that happens when $\theta$ is replaced by the evidence about $\theta$ that a substrate physically
holds.

## 3.3 The observation model

The substrate stores **observations**, not beliefs; the belief is a derived object computed at
solve time. This separation is the hinge of the whole system, because it is what keeps the storage
layer from privileging any one solver (constraint C7, §4). An **observation** for a cell $(x, a)$ is

$$
o \;=\; \langle\,\text{val\_or\_cat},\ \text{confidence} \in \{H, M, L\},\ \text{evidence\_id},\ \text{source\_type},\ \text{context}\,\rangle,
$$

where $\text{context} = (\text{hardware\_tier},\ \text{dataset},\ \text{split},\ \text{decoding\_cfg},\ \text{date})$
records exactly what is needed to (i) preserve comparison context and (ii) decide whether two
observations are even *commensurable*. The **observation set**
$O_E(x, a) = \{o_1, \dots, o_k\}$ — possibly empty — is what the substrate physically holds for the
cell. We write $E$ for the full evidence base (the union of all observation sets).

The **belief** is *derived*, not stored:

$$
B_E(x, a) \;=\; \mathrm{Agg}_\varphi\!\big(\,O_E(x, a)\ \big|\ \kappa\,\big),
$$

with two solver-chosen parameters and no stored aggregate:

- $\kappa$ is the **confidence filter** carried by the query's policy (default $H{+}M$; $L$ is
  opt-in). Filtering by confidence is a property of the *belief*, not of the store.
- $\varphi$ is the **aggregation mode**, and it is the solver — not the substrate — that picks it:
  $\varphi = \text{interval}$ yields $[\min_i \ell_i,\ \max_i u_i]$ over the filtered commensurable
  observations (the partial-identification / robust reading); $\varphi = \text{distribution}$ yields
  a confidence-weighted pooled posterior with a per-source noise model (the chance-constrained
  reading); $\varphi = \text{categorical}$ yields the agreed category if the filtered observations
  concur, and $\bot$ if they conflict or the set is empty.

**Missingness is derived and relative to the filter.** The cardinal definition of the paper is

$$
B_E(x, a) = \bot \quad\Longleftrightarrow\quad \text{the } \kappa\text{-filtered observation set is empty}.
$$

A cell holding only low-confidence evidence is $\bot$ under the default $H{+}M$ policy but present
under an $L$-opt-in policy: $\text{is\_missing}$ is therefore not a stored boolean but a *query*
against $E$ under $\kappa$. This is the single design decision that makes decidability well-defined
(§3.5) and that forces the relational, observation-as-atom schema of §4: because a cell holds many
provenanced, contextualized observations, the unit of storage is an observation row, not a flat
$(x, a) \mapsto \text{value}$ cell. Critically, $\bot$ is **never imputed** — a missing axis stays
missing; we do not fill it with a prior, a median, or a guess (constraint C1).

## 3.4 Three feasibility states

Fix a candidate $x$, bundle $c$, risk level $\alpha$, and a solver choice $(\varphi, \kappa)$. For
each constraint $(a, \text{rel}, \text{target}) \in c$, certify the predicate against $B_E(x, a)$:

- **numeric, $\varphi = \text{distribution}$:** *certified-sat* iff
  $P_{B_E}(a\ \text{rel}\ \text{target}) \ge 1 - \alpha$; *certified-violated* iff $< \alpha$;
- **numeric, $\varphi = \text{interval}$:** *certified-sat* iff the whole interval satisfies the
  relation; *certified-violated* iff the whole interval violates it;
- **categorical:** *certified-sat* iff the certified category entails the constraint,
  *certified-violated* iff it contradicts it;
- **any axis with $B_E = \bot$:** *undetermined*.

A candidate is then sorted into one of three states:

| State | Condition |
|---|---|
| **provably-feasible** | every constraint certified-sat **and** no required field is $\bot$ |
| **provably-infeasible** | some constraint certified-violated |
| **possibly-feasible (pending $F$)** | neither holds; $F$ is the set of required fields that are $\bot$ or straddle the threshold — **return $F$** |

The returned set $F$ is the object that value-of-information ranks and that the selective procedure
reports when it abstains; it is the formal content of an honest "I don't know yet, and here is what
would resolve it." The classifier lives entirely in the solver layer and reads cells only through
the substrate interface of §4 — it never touches storage directly.

## 3.5 Evidence-decidability versus underdetermination

The certifier above acts per-candidate; the decision verdict is a property of the whole query, and
it is defined through **completions**. Let $\mathrm{Comp}(E)$ be the set of completions of $E$:
every assignment of values to the $\bot$ and straddling cells that is *consistent with the
observation intervals* — a $\bot$ cell with no bounding observation ranges over its admissible
domain, a straddling cell ranges within its $[\ell, u]$. A completion is a possible world the
evidence cannot rule out.

> **Decidable.** $q$ is **evidence-decidable under $E$** iff there exists a provably-feasible $x$
> whose $\arg\min \mathrm{cost}$ is **invariant across all completions** $e \in \mathrm{Comp}(E)$.
> The optimal decision is *identified* by the evidence.
>
> **Underdetermined.** $q$ is **evidence-underdetermined** iff the minimum-sufficient decision is
> **non-identifiable**: there exist $e_1, e_2 \in \mathrm{Comp}(E)$ with
> $x^\*(q \mid e_1) \ne x^\*(q \mid e_2)$. Equivalently, **there is a missing field whose value
> flips the $\arg\min$.**
>
> **Infeasible-under-$E$.** No $x$ is provably-feasible across all completions.

These three labels are exactly the dependent variable of the empirical study: the **decidability
map** is their distribution over $\{\text{archetype} \times \text{evidence-regime} \times
\text{confidence}\}$. This is the measurement that sharpening $B_E$ does *not* produce — better
benchmarks shrink the per-cell intervals and so prune completions, but they cannot tell us whether
$E$ suffices to identify the decision; that is a different axis entirely, and it is the one we
measure.

Two operational notes tie the definition to what is computed. First, completion bounding is
best-/worst-case and conservative: a pending candidate is taken optimistically feasible-and-cheapest
and a $\bot$-cost candidate optimistically costs zero (costs are non-negative), so a query is called
DECIDABLE only when a *sure* winner exists that *no* optimistic completion of any rival can beat.
This makes the point-estimate reading **over-state** decidability, so every reported
underdetermination fraction is a floor. Second, an **evidence regime** $R \subseteq A$ is the set of
axes on which $E$ carries any evidence (or, in the masked ladder, the axes a rule is permitted to
see); a rule restricted to $R$ treats every off-regime cell as $\bot$ regardless of what the
substrate holds. Decidability is then characterized by closure: $q$ is decidable under $R$ iff
$\mathrm{bind}(q) \subseteq \mathrm{cl}(R)$, where $\mathrm{cl}(R)$ adds any axis that is a known
deterministic function of $R$-axes under the query's fixed context. This is what the regime ladder
measures rung by rung.

**Structured missingness is a claim, not a description.** The force of the whole framing rests on
$\bot$ concentrating on the *same* axes across sources. If missingness were random, completions
would rarely flip the $\arg\min$ and underdetermination would be rare; it is precisely because the
hard-to-observe axes $A_h$ are absent *everywhere* — and because even the measurable axes are
fragmented so that no single configuration carries quality and cost and energy together — that the
$\arg\min$ flips so often. Proving the missingness is structured rather than incidental is therefore
load-bearing, and it is what §4's corpus and the per-axis miss-rate measurement are built to settle.
