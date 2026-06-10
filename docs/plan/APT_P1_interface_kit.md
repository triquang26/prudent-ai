# APT — P1 Interface Kit (entry spec for the evidential substrate)

> **What this is.** The detailed expansion of §9 of `APT_P0_formalism_spine.md`: the substrate↔solver
> **contract** (typed), the **Appendix-E baseline query**, **two solver stubs** that prove the contract is
> solver-agnostic, and the **week-1 vector test** that gates P1.
> **Fidelity.** Pseudocode + reference SQL — the *contract*, not the implementation. P1's real deliverable is
> the hardened SQLite schema + real solver code; this kit is what that code is built against and tested with.
> The contract here is **immutable once P1 starts** — that immutability is the whole point (C7 firewall).

---

## 1. Type vocabulary (the nouns the contract speaks in)

```
Confidence     = enum { H, M, L }
SourceType     = enum { leaderboard, paper_reported, paper_estimated, measured, vendor_doc }
AxisName       = enum over A  =  { quality, latency_p95, throughput, cost,
                                   energy, memory_hw, governance, reviewer_burden }
Value          = Numeric(float)  |  Categorical(str)          # tagged union; axis kind fixes which
Context        = { hardware_tier, dataset, split, decoding_cfg, date }   # C6: commensurability metadata

Observation    = { axis: AxisName,
                   value: Value,
                   confidence: Confidence,
                   evidence_id: EvidenceId,                   # FK -> source  (C2: provenance)
                   source_type: SourceType,
                   context: Context }
ObservationSet = list[Observation]                            # the O_E for a fixed (x, a)

ComponentRef   = { id, kind, name }
Candidate      = { id: ConfigId, tau: TaskArchetype, components: list[ComponentRef] }   # composition first-class

Relation       = enum { GE, LE, EQ, SUPSETEQ, IN }            # ≥  ≤  =  ⊇  ∈
Constraint     = { axis: AxisName, rel: Relation, target: Value | set[Value] }
Bundle         = list[Constraint]                             # the hard-constraint bundle c
Query          = { tau: TaskArchetype, c: Bundle }
```

---

## 2. The substrate interface — three functions (the contract)

Everything a solver is allowed to ask the substrate. **Nothing else.** All three are κ-free and φ-free:
confidence filtering and belief aggregation are solver-side (per §3.2 of the spine).

```
candidates(tau: TaskArchetype) -> list[Candidate]
    # Every configuration admissible for tau, with its components/lineage.
    # NO filtering by the constraint bundle — feasibility is the solver's job, not the store's.

cell(x: ConfigId, a: AxisName) -> ObservationSet
    # ALL observations for the (x, a) cell, every confidence level, untouched.
    # NO κ-filter, NO aggregation, NO certification. Returns [] iff zero observations exist at all.
    # The solver applies κ (confidence policy) then φ (interval | distribution | categorical) itself.

required_fields(c: Bundle) -> set[AxisName]
    # The axes the bundle CONSTRAINS. Pure function of c. No x, no solving.
```

### ★ Design note — `required_fields` is SYNTACTIC, not SEMANTIC (the leak to avoid)

There are two tempting readings; only one is contract-safe.

| Reading | Definition | Verdict |
|---|---|---|
| **syntactic** ✅ | `{ k.axis for k in c }` — axes that *appear* in the bundle | substrate-safe: pure function of `c` |
| semantic ✗ | axes that *bind* (active at the optimum `x*`) | requires solving → solver-side |

The syntactic reading is the contract: **`required_fields(c) := { k.axis for k in c }`**. If the substrate
returned *binding* axes, it would have to know `x*`, i.e. run the optimization — collapsing C7 and making the
§6 invariance test fail (two solvers can disagree on which axes bind). "Which constrained axes are `⊥`" is then
`required_fields(c) ∩ { a : is_missing(x, a | κ) }`, computed **solver-side**; that intersection is the blocking
set `F` the selective procedure reports. (This resolves Q2 of the spine at the interface level: *binding* is
deferred to the solver/P3; the substrate only knows *mentioned*.)

### What is explicitly NOT in the substrate

`κ` (confidence policy), `φ` (aggregation mode), `α` (risk), the three-state certifier, VoI, the guarantee
calibration, and the Pareto frontier — all solver-side. The substrate stores observations and answers the three
calls above; it never decides anything. (The one extra thing the substrate *also* supports is the descriptive
reportability query in §4 — retrieval+filter only, still no decision.)

---

## 3. Minimal reference schema (P1 finalizes — this is the *requirement*, instantiated)

Just enough to make §2 and §4 concrete. P1 hardens (indices, constraints, the full component graph).

```sql
CREATE TABLE component (id TEXT PRIMARY KEY, kind TEXT, name TEXT);

CREATE TABLE config   (id TEXT PRIMARY KEY, tau TEXT);                       -- a candidate x

CREATE TABLE config_component (                                             -- composition (many-to-many)
    config_id    TEXT REFERENCES config(id),                               -- lineage: which parts make x
    component_id TEXT REFERENCES component(id),
    PRIMARY KEY (config_id, component_id));

CREATE TABLE source (                                                       -- evidence provenance
    evidence_id      TEXT PRIMARY KEY,
    source_type      TEXT,                                                  -- leaderboard / paper_* / measured
    citation         TEXT,
    snapshot_version TEXT);                                                 -- C3: reproducibility

CREATE TABLE observation (                                                  -- THE atomic unit: many per (x,a)
    obs_id       TEXT PRIMARY KEY,
    config_id    TEXT REFERENCES config(id),                               -- FK
    axis         TEXT,                                                      -- one of the 8
    value_num    REAL,                                                      -- exactly one of num/cat non-null
    value_cat    TEXT,
    confidence   TEXT CHECK (confidence IN ('H','M','L')),                 -- C4
    evidence_id  TEXT REFERENCES source(evidence_id),                      -- FK = provenance guarantee (∃ source)
    hardware_tier TEXT, dataset TEXT, split TEXT, decoding_cfg TEXT,        -- C6: context
    obs_date     TEXT);
```

The FK from `observation.evidence_id` to `source` is the master plan's claim made executable: **referential
integrity *is* the provenance guarantee** — an observation cannot exist without a source it points to.

---

## 4. Appendix-E baseline query = the reportability map (and why it *is* the input to DV1)

The one descriptive query the substrate must support. It is **retrieve + filter only** — no feasibility, no
optimization (C7). For task `τ` under confidence policy `κ`, it emits, per `(candidate × axis)`: how many
observations survive `κ`, whether the cell is `⊥`, and a crude descriptive `[lo, hi]` hint.

```sql
-- params: :tau , :kappa   (e.g. :kappa = ('H','M') for the default policy)
WITH axes(axis) AS (VALUES ('quality'),('latency_p95'),('throughput'),('cost'),
                          ('energy'),('memory_hw'),('governance'),('reviewer_burden')),
     cand AS (SELECT id AS config_id FROM config WHERE tau = :tau)
SELECT  c.config_id,
        a.axis,
        COUNT(o.obs_id)                       AS n_obs_under_kappa,
        (COUNT(o.obs_id) = 0)                 AS is_missing,        -- ⊥ relative to κ  (the missingness map)
        MIN(o.value_num)                      AS lo,                -- descriptive hint ONLY, not the belief
        MAX(o.value_num)                      AS hi,                -- (B_E lives solver-side via Agg_φ)
        GROUP_CONCAT(DISTINCT o.source_type)  AS source_types
FROM        cand c
CROSS JOIN  axes a
LEFT JOIN   observation o
       ON   o.config_id = c.config_id
      AND   o.axis      = a.axis
      AND   o.confidence IN (:kappa)
GROUP BY    c.config_id, a.axis
ORDER BY    c.config_id, a.axis;
```

**Why this query, not `SELECT *`.** Its `is_missing` column is exactly the per-cell missingness map. P3's
**decidability map (DV1)** is computed by feeding *this* output — the raw presence/⊥ picture under κ — together
with the solver's three-state certification, into the §5 `decidable / underdetermined / infeasible` labeling.
So the baseline query is not arbitrary plumbing: **it is the empirical substrate of DV1**, and the reason the
interface surfaces presence/⊥ at all. The `[lo, hi]` columns are eyeballing hints (min/max of raw values), not
`B_E` — the belief is the solver's `Agg_φ`, deliberately absent here.

---

## 5. Two solver stubs reading the identical interface

The point of the stubs is not to solve well — it is to **prove the contract is solver-agnostic**. Both call
only `candidates` / `cell` / `required_fields`, and choose their own `κ`, `φ`, certifier.

```python
# ---- shared, solver-side: apply κ (filter) then φ (aggregate) to one cell ----
def belief(x, a, kappa, phi):
    obs = [o for o in cell(x, a) if o.confidence in kappa]   # κ-filter  (solver-side, NOT substrate)
    if not obs:
        return BOT                                            # ⊥ relative to κ
    return phi(obs)                                           # Agg_φ : interval | distribution | categorical

# ================= STUB 1 — lexicographic (φ = interval; ⊥ treated as fail) =================
def solve_lexicographic(q, kappa):
    feas = []
    for x in candidates(q.tau):                               # <-- substrate call
        ok = True
        for k in q.c:                                         # k = (axis, rel, target)
            iv = belief(x, k.axis, kappa, phi=interval)       # <-- cell() underneath
            if iv is BOT or not interval_satisfies(iv, k.rel, k.target):
                ok = False; break
        if ok: feas.append(x)
    if not feas:
        return ABSTAIN(reason="no provably-feasible candidate")
    return min(feas, key=lambda x: point_of(belief(x, 'cost', kappa, phi=interval)))

# ================= STUB 2 — chance-constrained (φ = distribution; certify P ≥ 1−α) =================
def solve_chance_constrained(q, kappa, alpha):
    feas = []
    for x in candidates(q.tau):                               # <-- IDENTICAL substrate call
        ok = True
        for k in q.c:
            d = belief(x, k.axis, kappa, phi=distribution)    # <-- IDENTICAL cell() underneath
            if d is BOT or prob_satisfies(d, k.rel, k.target) < 1 - alpha:
                ok = False; break
        if ok: feas.append(x)
    if not feas:
        return ABSTAIN(reason="no candidate certifiable at alpha")
    return min(feas, key=lambda x: expected_cost(belief(x, 'cost', kappa, phi=distribution)))
```

**The diff (what changes vs what doesn't).**

| | Stub 1 lexicographic | Stub 2 chance-constrained |
|---|---|---|
| substrate calls | `candidates`, `cell` | **byte-identical** |
| `φ` | `interval` | `distribution` |
| certifier | `interval_satisfies` | `prob_satisfies ≥ 1−α` |
| cost objective | interval midpoint | expected cost |

Everything that touches the **substrate** is identical; everything that differs is **solver-side** (`φ`,
predicate, objective). That is the C7 firewall, visible in the diff.

**Where `required_fields` lands (the selective wrapper, P4 — same interface).** The two stubs above are
non-selective. The real selective procedure (§6 of spine) wraps either stub and is the *only* place
`required_fields` is used — and it, too, calls nothing new:

```python
def solve_selective(q, kappa, alpha):
    blocking = {a for a in required_fields(q.c)               # syntactic axes of the bundle
                  if all(o.confidence not in kappa for o in cell(q.x_under_test, a))}  # ⊥ under κ
    if blocking:
        f_star = argmax(blocking, key=voi_per_cost)           # VoI ranking, solver-side
        return ABSTAIN(blocking=blocking, acquire=f_star)
    return solve_chance_constrained(q, kappa, alpha)          # else commit (with the guarantee)
```

---

## 6. The week-1 vector test (piloting) — falsifiable interface-invariance check

This is P1's opening vector, scoped to one week: *does the contract survive a solver swap?* Make it a real,
failable experiment, not a demo.

```python
# Property: on the same query, the MULTISET of substrate calls is identical across solvers.
def test_interface_invariance(queries):
    for q in queries:
        sig1 = record_substrate_calls(lambda: solve_lexicographic(q, kappa=('H','M')))
        sig2 = record_substrate_calls(lambda: solve_chance_constrained(q, kappa=('H','M'), alpha=0.1))
        assert sig1 == sig2     # sig = sequence of (fn, args) hitting candidates/cell/required_fields
```

- **PASS** → the interface is solver-agnostic; C7 holds; the schema is safe to harden. Proceed in P1.
- **FAIL** → a solver concern has leaked into the substrate. **Fix the interface now (cheap); a leak found at
  P4 is expensive** (re-extraction, schema migration).

**What a FAIL would look like (the leaks this test catches):**
1. a solver asks the substrate for cells *pre-filtered to high-confidence* → `κ` leaked into the store (κ must
   stay solver-side, per §3.2 of spine);
2. a solver asks the substrate *which axes bind* → semantic `required_fields` leaked (binding is solver-side,
   §2 design note);
3. a solver asks the substrate for an *aggregated value* instead of the observation set → `φ` leaked
   (aggregation is solver-side).

If none of these appear and `sig1 == sig2`, the contract is clean.

---

## 7. P1 done-when (gate, from master plan §15·P1 — now concrete)

- [ ] reference schema (§3) instantiated in SQLite; FKs enforced;
- [ ] seeded with **HELM Lite only** (breadth across 4 regimes is P2 — periphery for P1);
- [ ] one cell demonstrably holds **multiple observations** with differing confidence/context;
- [ ] `is_missing(x, a | κ)` returns the correct `⊥` under both `κ = (H,M)` and `κ = (H,M,L)`;
- [ ] Appendix-E baseline query (§4) runs and the `is_missing` column is non-degenerate;
- [ ] **`test_interface_invariance` PASSES** with the two stubs (§5–§6) — the gating result;
- [ ] data dictionary committed.

When the invariance test passes, P0→P1 is closed and P4's solvers can be built without touching storage.
