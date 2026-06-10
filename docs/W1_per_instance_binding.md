# W1 — Per-instance binding, Pareto-recovered (closes the empirical half of Open-Q2)

> Node: `c90ge4-w1-per-instance-binding` (parent `zh6apu`).
> Code: `src/prudent_ai/validation/binding.py` + `ValidationRunner.binding_certification`.
> Runner: `scripts/run_w1_binding.py`. Outputs: `outputs/p5/w1_binding.{json,md}`.
> Tests: `tests/test_binding.py`. κ=H+M, φ=point, db=`data/apt_substrate.db`.

## The attack (mock-review W1, "CRITICAL for Oral")

The validation treats a query's *constrained* axes as its binding set, and `bind(q)`
is otherwise **declared** from the ZenML tag→axis taxonomy. A reviewer's sharpest
objection: a *declared* constraint need not be **active at the realized optimum** — if
relaxing it does not change `x*`, masking it should not bite, and the C2 result would
ride on an over-approximation of binding ("declared ≠ binding"). The reviewer named the
fix precisely: *"a Pareto-recovered or hand-audited `bind(q)` lower bound that keeps
underdetermination high on truly-binding axes."*

## What we did — recover bind(q) from Pareto structure, not tags

On a ground-truth slice (true measured values), define an axis `a` as **Pareto-binding**
at query `q` iff dropping its constraint **strictly lowers** the achievable minimum cost
over truly-feasible configs:

```
bind(q) = { a ∈ constrained(q) :  min_cost(q without a)  <  min_cost(q) }.
```

This is the standard **active-constraint** test: a slack constraint can be removed
without moving the optimum; an active one cannot. It needs no tags and no declaration —
only the slice's own realized Pareto frontier (`binding.py`, reading via the C7
interface; the GT slice SCOREs, never tunes, C8).

We then test the **C2 mechanism per instance**: the blind baseline B2 should
hidden-violate **iff** the masked axis is Pareto-binding. Run over all V1 biting slices
(mask the binding axis) **plus a non-binding control** (BFCL mask=`latency_p95`, where
cheap==fast so latency is slack), 17 queries each.

## Result — bite ⟺ binding, exactly (`outputs/p5/w1_binding.json`)

Confusion over **544** queries (certified Pareto-binding × B2 bites):

| | B2 bites | B2 no-bite |
|---|---|---|
| **Pareto-binding** | **287** | 0 |
| **non-binding** | 0 | **257** |

- **`bite ⟺ binding` agreement = 1.0000** — zero off-diagonal. Every query where the
  blind baseline mis-sizes is one where the masked axis is *certifiably* the active
  constraint at the optimum; every certified-binding query is one where it bites; and
  every slack query (loose thresholds, and the entire latency control) correctly neither
  binds nor bites.
- **C2 restricted to the certified-binding subset (n=287):** B2 hidden-violation
  **1.000** vs selective **0.000**. The C2 gap is **undiminished** on the truly-binding
  queries — it is not an artefact of counting slack constraints as binding.
- The **control** slice (mask=latency) certifies **0.0** binding and **0** bites:
  declared-but-slack ⇒ no mis-sizing, as the no-bite control already hinted, now proven
  by the active-constraint test rather than asserted.
- Within a biting slice the certified-binding fraction ranges 0→1 (mean ≈0.53): the test
  **discriminates** — at loose percentile thresholds the cheapest config already meets
  the floor (quality slack, no bite); at tight thresholds it binds and bites. The
  agreement holds query-by-query, not just in aggregate.

## What this closes — and what it honestly does not

**Closes (empirical, on the GT/measurable axes).** The C2 biting axes are **certified
binding per instance** from Pareto structure, independent of tags. The reviewer's
"declared ≠ binding, so the bite is inflated" objection is answered where it can be
checked: where B2 bites, the axis is provably active; where it is slack, B2 provably
does not bite. `bind(q)` is now a **recovered lower bound**, not a declaration.

**Does not close (and we do not claim it).**
- The **C1 91.1% underdetermination headline** counts queries that bind on **corpus-wide
  ⊥** axes (governance, reviewer_burden, memory_hw) — exactly the axes with **no GT**, so
  their per-instance binding is **unrecoverable** by this (or any data) test. C1 therefore
  continues to lead with the **binding-INDEPENDENT** attribution (72.4% blocked by a
  corpus-wide-⊥ axis, 16.0% blocked *only* by unmeasurable axes), per the v1 W1 fix. This
  node strengthens **C2/C3** (where GT exists), not the C1 magnitude.
- The **general closure operator `cl(R)`** (Open-Q1) — the clean theorem
  *q decidable ⇔ bind(q) ⊆ cl(R)* for arbitrary closure operators and multi-axis binding
  — remains the theory-collaborator task in [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md). The
  active-constraint test is the *empirical* operationalization of binding, not the
  *theoretical* characterization.

## Status

| item | before | after |
|---|---|---|
| C2 biting axes are *truly* binding (not just declared) | asserted from tags; reviewer attack open (W1) | **Pareto-certified per instance, bite⟺binding agreement 1.0** |
| C2 gap on the truly-binding subset | unmeasured | **B2 1.0 vs selective 0.0, n=287** |
| Open-Q2 (per-instance binding) | open | **empirical half closed on GT axes**; corpus-wide-⊥ stays unrecoverable |
| Open-Q1 (general `cl(R)` theorem) | open | **still open** (collaborator) |

## Tests

`tests/test_binding.py` (3): quality **binds** at a tight threshold (q≥0.8, drop → cost
5→1), is **slack** at a loose one (q≥0.4, drop → no change), and an infeasible query
yields no binding axis. All 50 repo tests pass; ruff clean; C7 interface untouched.
