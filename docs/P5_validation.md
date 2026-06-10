# P5 — Validation (§7 Evaluation, the Oral pillar)

**Status:** P5 V1+V2 finding, paper-grade feed for **§7 Evaluation**. Realizes constraint
**C2** (current practice *mis-sizes measurably*) and corroborates **C3** (the selective
procedure's abstention is the safe action *and* names the field worth measuring). Where P3
*diagnosed* underdetermination and P4 *built the procedure that acts on it*, **P5 is the
falsification test**: on a ground-truth slice where a binding axis is hidden, does the
community's honest practice (B2 observed-Pareto) and its standard defences (B3 imputation,
B6 cost-accuracy) commit configs that *silently violate the truth* — and does the selective
procedure avoid that by abstaining? This is the DV2 (regret) + DV3 (hidden-violation) leg of
the §16 claim map: **C2 ← DV2 + DV3, vs B2/B3**; plus the **DV5 VoI-lift** leg of **C3**.

**Substrate & interface (unchanged, C7).** `data/apt_substrate.db`. Every rule — baselines and
the selective procedure alike — reads the substrate **only** through the solver/classifier
interface (`candidates / cell / required_fields`). Masking is realized at the read level by
`MaskedSubstrate`: it returns `[]` for the masked axis's `cell(...)`, so *no* rule can see the
hidden axis regardless of how it reads. The oracle (B5, `sees_masked=True`) is the sole
exception — it is handed the real substrate and so defines the regret floor. `⊥` stays `⊥`;
nothing is imputed at the read level.

**How the numbers were produced (reproducible).** φ=point, κ_operating=H+M, masking via
`validation.harness.MaskAndPredict` / `MaskedSubstrate`, orchestrated by
`analysis.validation_run.ValidationRunner`, V2 seed=12345. All numbers below are read
verbatim from `outputs/p5/validation.{json,md}` (provenance `P5-V1V2`). The slice's own
measured values are used **only to score**, never to tune any rule (C8 — no leakage).

---

## 1. The validation question (C2/C3)

P3 established that 91.1% of real right-sizing queries are evidence-underdetermined; P4 built a
procedure that COMMITs on the decidable minority and ABSTAINs-informatively on the rest. Both
are statements about *how much evidence is missing* and *what the procedure does about it*.
Neither yet shows the thing an Oral reviewer demands (§18.1, "Missing metrics is obvious"):
that **answering anyway is measurably wrong**, and that **the procedure's silence is the
correct action** in exactly those cases.

That is the C2 question, and it is sharp and falsifiable:

> Take a slice with co-located *ground-truth* axis values. Bind a query on two axes. **Mask one
> binding axis.** Let each decision rule commit a config from the visible evidence. Score the
> commit against the **true** (unmasked) value of the hidden axis. A rule that commits a config
> violating the hidden constraint has **mis-sized** — silently, because by construction it could
> not see the axis it violated.

The load-bearing metric is **DV3 hidden-violation rate** = fraction of a rule's *commits* that
violate the masked truth. The claim is hard (§14): we **MUST beat B2** (observed-Pareto =
current honest practice) **and B3** (imputation = "just fill it in"), and ideally B6
(cost-accuracy = FrugalGPT-style, drops latency/energy/governance). The selective procedure's
answer to a masked binding axis should be to **ABSTAIN** — coverage 0 on that mask, but **zero
hidden-violation**. That is the §17.1 Trust-or-Escalate shape with measured violations now
visible on the *other* side: the baselines buy coverage by mis-sizing; the procedure buys zero
mis-sizing by escalating.

DV2 (decision regret, cost overshoot vs the oracle minimum-sufficient) is reported alongside,
but it is **degenerate when violations dominate** (§6 below): a rule that commits an infeasible
config contributes a hidden-violation, not a regret-over-feasible sample. So on the biting case
DV3 carries the claim and DV2 is near-zero by construction.

The **C3 leg** asks the §10 / DV5 question on top: when the procedure abstains, is its silence
*informative* — does the field it names (its cost-aware VoI pick) actually unblock the decision,
better than measuring a random field? V2 answers this.

---

## 2. Setup

**Ground-truth slices.** Two co-located measured slices, used purely to score (C8):

| slice | τ | GT axes | confidence | κ |
|---|---|---|---|---|
| **BFCL** (function-calling) | `function-calling` | quality + cost + latency_p95 | M | H+M |
| **RouterBench** | `routerbench` | quality + cost | H | H+M |

(ML.ENERGY is excluded: it has no `cost` axis, so the cost-objective oracle cannot score it.)

**Mask-and-predict** (`validation.harness.MaskAndPredict`). For each slice we generate a battery
of queries that *bind* both axes in `bind_axes` at matched observed percentiles (pcts
30/40/50/60/70, **n=5** per slice/mask). Then we mask one binding axis and, per rule, read the
prediction under the visible regime and score it against truth: `true_feasible(q, pred)` checks
the commit against the **full-regime** measured values; a commit that fails it is a hidden
violation; a feasible commit contributes `max(0, cost(pred) − oracle_cost(q))` to regret.

**Masking is enforced uniformly at the read level.** `MaskedSubstrate(sub, masked_axis)`
withholds the one axis for every rule; only B5 (the oracle, `sees_masked=True`) is handed the
unmasked substrate. This is the C7-shaped ablation: same interface, one axis silenced — a
faithful simulation of structural missingness.

**The baseline lattice B1–B6** (§14, `validation.baselines`) — one line each:

| | rule | what it does under the mask | role |
|---|---|---|---|
| B1 | accuracy-only | argmax quality, ignores cost & every constraint | strawman |
| **B2** | **observed-Pareto** | min visible-cost s.t. *visible* constraints; treats the masked axis as satisfied | **honest current practice — MUST beat** |
| **B3** | **imputation** | impute the masked axis (global median over τ's configs) then decide as B2 | **"just fill it in" — MUST beat** |
| B4 | missing-as-fail | a masked *binding* axis ⇒ abstain | conservative upper bound (0 violations) |
| B5 | oracle | sees the true masked values ⇒ true min-cost feasible | **regret floor** |
| B6 | cost-accuracy | min cost s.t. the quality constraint only; drops latency/energy/gov | FrugalGPT-style domain rival |
| — | **selective (ours)** | P4 `right_size` under the visible regime — COMMIT iff decidable, else ABSTAIN | the procedure |

---

## 3. V1 results — the C2 demonstration (actual numbers)

### 3.1 The biting case: BFCL, bind `quality+latency_p95`, **mask `quality`**

This is the slice chosen *because* it binds (§18.2: pick where multiple axes truly bind). In
BFCL, cheap configs are *low-quality* — so a cost-minimizer that cannot see quality commits the
cheapest config and silently violates the quality floor. Verbatim from
`outputs/p5/validation.json`:

| rule | coverage | hidden_violation_rate | n_hidden_violation | mean_regret |
|---|---|---|---|---|
| B1 accuracy-only | 0.0 | 0.0 | 0 | 0.0 |
| **B2 observed-Pareto** | **1.0** | **1.0** | **5/5** | 0.0 |
| **B3 imputation** | **1.0** | **1.0** | **5/5** | 0.0 |
| B4 missing-as-fail | 0.0 | 0.0 | 0 | 0.0 |
| B5 oracle | 1.0 | 0.0 | 0 | 0.0 |
| **B6 cost-accuracy** | **1.0** | **1.0** | **5/5** | 0.0 |
| **selective (ours)** | **0.0** | **0.0** | **0** | 0.0 |

**This is C2.** The three commit-while-blind rules — **B2, B3, B6** — commit on **100%** of
queries and **hidden-violate on 100%** of those commits (5/5 each). The honest current practice
(B2) and both standard defences (imputation B3, cost-accuracy B6) *silently ship an infeasible
config every single time the quality axis is unobservable*. The **selective procedure abstains
on all 5** (coverage 0) and therefore has **0 hidden-violation** — it refuses precisely when it
cannot certify the binding axis.

State the must-beat result plainly:

> **hidden-violation(selective) = 0.0  ≪  hidden-violation(B2) = hidden-violation(B3) = 1.0.**

Note that B3 imputation does **not** rescue the case: imputing the global-median quality still
commits the same blind config (the §18.1 "imputation solves it" attack, answered with a number —
imputation's hidden-violation = 1.0, identical to B2). B5 (oracle) commits all 5 with 0
violations — the achievable regret floor — confirming the configs *exist* that satisfy both axes;
the blind baselines just cannot find them. The harness verdict: **`c2_verdict: "holds"`** —
selective HVR 0.0 vs {B2, B3, B6} = 1.0. A clean "**must beat B2 and B3**" pass on DV3.

### 3.2 The honest control: same slice, **mask `latency_p95`** (does NOT bite)

The finding is **axis-specific, and we report it as such** (§18.2). When we instead mask
*latency* on the same BFCL bind, the phenomenon vanishes:

| rule | coverage | hidden_violation_rate | mean_regret |
|---|---|---|---|
| B1 accuracy-only | 1.0 | 0.2 | 84.625 |
| B2 observed-Pareto | 1.0 | **0.0** | 0.0 |
| B3 imputation | 1.0 | **0.0** | 0.0 |
| B6 cost-accuracy | 1.0 | **0.0** | 0.0 |
| selective (ours) | 0.0 | 0.0 | 0.0 |

**`c2_verdict: "no-bite"`.** Because in BFCL *cheap ⇒ fast* (cost and latency are positively
aligned), the cost-minimizer's blind commit happens to satisfy the hidden latency floor too — so
there is nothing to beat. B1 (which ignores cost entirely) is the only rule that violates here,
because chasing max-quality picks a slow config (HVR 0.2, regret 84.6). This is the honest face
of C2: the mis-sizing is a property of *which* axis is hidden and *whether cheap configs trade it
off* — not a universal claim. We show the biting case **and** the control, exactly as §18.2's
"choose the slice where it binds" discipline requires — this is **not p-hacking**, it is reporting
where the phenomenon does and does not occur.

### 3.3 RouterBench: bind `quality`, **mask `quality`** — a *documented confound*, not a second bite

| rule | coverage | hidden_violation_rate | mean_regret |
|---|---|---|---|
| B2 / B3 / B6 | 1.0 | **0.0** | 0.0 |
| selective (ours) | 0.0 | 0.0 | 0.0 |

**`c2_verdict: "no-bite"` — but for a structural reason we name explicitly.** RouterBench's `cost`
varies primarily **by benchmark**, not by model: an easy/short benchmark is cheap *regardless of
which model runs it*. So the global cost-minimizer that B2/B3/B6 implement picks the **cheapest
benchmark** — which happens to be a high-quality one (e.g. `mistral-7b` on `test-match` at quality
0.667) — rather than the *weakest model*. Because cross-benchmark cost is **not comparable**, the
mixed-benchmark slice is **ill-posed for right-sizing**: minimizing cost across benchmarks is not
the same decision as right-sizing a model on a fixed task. The baselines are therefore *not*
silently violating a quality floor — they are answering a different (and confounded) question, so
there is no bite to demonstrate here.

This is recorded directly in the runner (`V1_CASES`, `is_biting=False` with the confound note),
not discovered post hoc. The valid RouterBench experiment is a **per-benchmark restriction** (hold
the benchmark fixed, vary the model, then cost *is* comparable) — that is **future work**. **BFCL
carries the C2 result**; RouterBench and BFCL/mask-latency are the two honest no-bite cases that
keep the claim falsifiable.

---

## 4. V2 results — VoI-guided acquisition (§10, DV5)

V2 asks the §10 / DV5 question on the biting BFCL bind, with the **corrected construction** that
isolates the VoI signal cleanly. Bind `quality+latency_p95`, but **mask only the single binding
axis `quality`** (latency stays visible). The blocking set is therefore exactly `{quality}`, the
procedure ABSTAINs on all 5 queries, and for each abstention we simulate "measuring one field":

- **measure the procedure's VoI pick** (`acquire_next`, which is `quality`) → un-mask it → re-run
  selective → it can now certify both axes and commit;
- **measure a RANDOM axis** (seeded, drawn from all 8 axes) → only unblocks the decision in the
  rare case the draw happens to *be* `quality`; otherwise quality stays `⊥` and selective abstains
  again.

Score each re-decision as COMMIT and *truly-feasible* (`true_feasible`). Verbatim from
`outputs/p5/validation.json` (`v2_acquisition`, seed=12345, n_abstained=5):

| measured field | commit-correct | commit-correct frac |
|---|---|---|
| **VoI pick (`acquire_next`)** | **5/5** | **1.0** |
| random axis | 1/5 | 0.2 |

**The VoI pick wins decisively: 1.0 vs 0.2.** On all 5 abstentions the procedure's VoI ranking
names `quality` (raw VoI ≈ 1.0, `voi_per_cost` ≈ 3.33) as the field worth measuring — and
measuring it yields a truly-feasible commit **every time** (5/5). The random baseline succeeds
only on the **single** query (`@p60`) where the seeded draw happened to land on `quality` (1/5 =
0.2); on the other four it drew `reviewer_burden`, `cost`, `memory_hw`, `latency_p95` — none of
which unblocks the decision, so selective abstained again. **VoI correctly identifies that
measuring `quality` (not reviewer_burden / cost / memory_hw / latency) is what unblocks the
decision.**

**The abstention is INFORMATIVE.** This is the §17.1 / §10 claim realized at the acquisition
level: the procedure's silence is not a bare refusal — it *names the field that actually
unblocks*, and that named field is right 5/5 of the time versus 1/5 for a blind guess. This ties
to the **VoI = Δ(R) identity proven in P4**: the implemented VoI of a binding axis equals the
irreducible regret of the evidence regime that omits it (§8.7), pinned by
`tests/test_procedure.py::test_voi_equals_delta_R`. Here that identity cashes out empirically —
the axis with the highest VoI is exactly the one whose measurement converts an abstention into a
correct commit.

---

## 5. Relation to claims & Go/No-Go (§18.2)

**C2 (DV2 + DV3) — demonstrated decisively on BFCL.** On BFCL/mask-quality, current honest
practice and its defences hidden-violate at **100%** while the procedure hidden-violates at
**0%** (`hidden-violation(selective)=0.0 ≪ hidden-violation(B2,B3)=1.0`). That is the §18.1
surprise the Oral hinges on: *the community rule answers anyway and mis-sizes measurably*, and
"imputation solves it" is refuted with a number (B3 HVR = 1.0). DV2 regret is
degenerate-by-violation here (§6), so DV3 is the load-bearing metric and it passes the "beat B2
and B3" bar cleanly.

**C3 — informative abstention + VoI — supported by V2.** The selective procedure's
coverage-0/violation-0 column *is* the safe action: it escalates exactly the queries where it
cannot certify the binding axis, instead of shipping a blind commit. And V2 shows the escalation
is *informative* — the field it names unblocks the decision 5/5 (1.0) vs 1/5 (0.2) random. This
ties directly to the P4 coverage story — selective trades coverage for zero hidden-violation, the
**Trust-or-Escalate shape** (§17.1) — but now with **measured violations on the other side** and a
**measured VoI lift** on the abstention. P4 showed reliability is purchasable only by abstaining
on most traffic (commit ≈ 8.9% coverage at 0 committed risk); P5 shows *what the alternative
costs* (blind rules hidden-violate at 100% on the biting axis) *and* that the abstention pays back
(VoI names the unblocking field).

**Honest Go / No-Go read (§18.2).** §18.2 says: if P5 cannot show mis-sizing (B2/B3 not beaten
with significance) → do not force Oral. Here:

- The **hidden-violation gap is categorical** — **1.0 vs 0.0** on the biting slice, with both
  must-beat baselines (B2, B3) and the domain rival (B6) at the ceiling and the procedure at the
  floor. This is a **strong C2 signal** and clears the *direction* of the gate decisively; the V2
  VoI lift (1.0 vs 0.2) adds a clean C3 signal.
- What is **not yet cleared** is the *significance* bar. The bite is on a **single small slice
  (n=5)** with an all-or-nothing (1.0 vs 0.0) separation, **no significance test** has been run,
  and the BFCL data is **M-confidence**. §18.2's Oral gate requires beating B2/B3 *with
  significance* across the battery.

> **Provisional read: GO on the C2/C3 demonstration, HOLD on Oral significance.** The mis-sizing
> is real, categorical, and refutes both the "obvious" and "imputation solves it" reviewer
> attacks (§18.1) with the procedure landing the safe *and informative* action (C3). Before
> claiming Oral we need: scaling the battery + a significance test on hidden-violation-rate; more
> biting slices (a **per-benchmark RouterBench** restriction, **on-prem / energy-bound** slices
> where multiple axes truly bind); and ideally V3 live runs. Direction: decisively right.
> Statistics: not yet run.

---

## 6. Honest limitations

1. **"Truth" is the slice's own measured values, not an independent oracle.** Ground-truth here =
   the substrate's co-located H/M-confidence measurements; **BFCL is M-confidence**. This is
   calibration against the richest evidence we have on the slice, not an external held-out oracle
   (the §8.8 / P4-§5 discipline, restated). RouterBench is H-confidence but is confounded (below).

2. **Masking is an ablation simulating missingness.** We *withhold* an axis we actually measured,
   to model the structural missingness P3 found in the wild. It is a faithful simulation, not a
   naturally-missing slice — V3 live runs (real missing axes on local AI boxes) remain the
   stretch.

3. **Regret-over-feasible is degenerate when violations dominate.** On the biting case every
   blind-baseline commit is *infeasible*, so it contributes a hidden-violation, not a regret
   sample — hence `mean_regret = 0.0` across the board there. **DV3 hidden-violation-rate is the
   load-bearing metric**, not DV2 regret, on exactly the slice where C2 bites. DV2 is informative
   only on the control (B1 mean_regret 84.6 on mask-latency).

4. **Small query batteries.** n=5 per slice/mask and n=5 abstentions for V2. The 1.0-vs-0.0 (C2)
   and 1.0-vs-0.2 (C3) separations are descriptively decisive but statistically thin; **no
   significance test has been run. This is the gating gap.**

5. **Axis-specificity is a feature, reported as a caveat.** The bite is BFCL/mask-quality only;
   BFCL/mask-latency does not bite (cheap ⇒ fast). The claim is "current practice mis-sizes *where
   multiple axes truly bind and cheap trades off the hidden one*", not a universal claim — and we
   show the no-bite controls to keep it falsifiable.

6. **RouterBench cross-benchmark confound.** RouterBench `cost` varies by *benchmark* not by
   *model*, so the mixed-benchmark slice is ill-posed for right-sizing (the global cost-minimizer
   picks the cheapest benchmark, not the weakest model). The valid experiment — a per-benchmark
   restriction (fix benchmark, vary model) — is future work. RouterBench therefore does **not**
   currently supply a second bite.

7. **V3 live runs not done.** No vLLM + ML.ENERGY energy + governance/burden human study yet;
   the §10 multi-reveal cascade (reveal-until-decidable, regret-to-oracle vs random ordering) is
   also a remaining V2 stretch.

---

## 7. Key numbers the paper cites

- **C2 bite (BFCL, bind `quality+latency_p95`, mask `quality`, κ=H+M, φ=point, n=5):**
  B2 observed-Pareto, B3 imputation, B6 cost-accuracy each **coverage 1.0, hidden-violation-rate
  1.0 (5/5 commits silently infeasible)**; selective **coverage 0.0, hidden-violation-rate 0.0**.
  `c2_verdict = holds`. **Must-beat-B2-and-B3: passed (1.0 → 0.0).** B5 oracle = regret floor
  (HVR 0.0, regret 0.0).
- **Honest controls / no bite:** BFCL mask `latency_p95` → B2/B3/B6 HVR **0.0** (cheap ⇒ fast;
  only B1 violates, HVR 0.2, regret 84.625); RouterBench mask `quality` → B2/B3/B6 HVR **0.0**, a
  **documented cross-benchmark cost confound** (cost varies by benchmark, not model), not a
  genuine no-bite. Both `c2_verdict = no-bite`.
- **C3 / V2 VoI lift (BFCL biting case, mask `quality` only, seed=12345, 5 abstentions):**
  measuring the procedure's **VoI pick (`acquire_next` = quality) → commit-correct 5/5 = 1.0**;
  measuring a **random axis → 1/5 = 0.2** (only when the draw lands on quality). VoI correctly
  names the field that unblocks the decision; the abstention is *informative*. Anchored to the
  **VoI = Δ(R)** identity (`tests/test_procedure.py::test_voi_equals_delta_R`).
- **Go/No-Go:** **GO on the C2/C3 demonstration** (categorical 1.0 vs 0.0 hidden-violation; 1.0 vs
  0.2 VoI lift), **HOLD on Oral significance** (single slice, n=5, M-confidence BFCL, no
  significance test). Next gate-closing step = scale the battery + significance test + more biting
  slices (per-benchmark RouterBench, on-prem/energy-bound), then V3.
