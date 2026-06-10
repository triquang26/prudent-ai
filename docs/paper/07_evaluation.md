# §7. Evaluation — Does Current Practice Mis-Size, and Is the Abstention Informative?

> **Claims addressed: C2 and C3.** §5 (C1) *diagnosed* that real deployment traffic is
> overwhelmingly evidence-underdetermined; §6 (C3-method) *built* the selective procedure that
> commits on the decidable minority and abstains-informatively on the rest. This section is the
> **falsification test**. On ground-truth slices where a binding axis is hidden, (i) does the
> community's honest practice (B2 observed-Pareto) and its standard defences (B3 imputation, B6
> cost-accuracy) commit configurations that *silently violate the truth*, and does the selective
> procedure avoid that by abstaining (**C2 ← DV2+DV3, vs B2/B3**)? and (ii) when it abstains, is
> its silence *informative* — does the field it names actually unblock the decision better than
> a random field (**C3 ← DV5 VoI-lift**)? V1 answers (i) **at scale with significance**; V2
> answers (ii).

All V1 numbers are read verbatim from `outputs/p5/validation_scaled.{json,md}` (provenance
`P5-scaled`, φ=point, κ=H+M, seed=12345). V2 numbers are from the pilot battery
`outputs/p5/validation.{json,md}` (`v2_acquisition`, seed=12345). Every rule — baselines and the
selective procedure alike — reads the substrate **only** through the solver interface
(`candidates` / `cell` / `required_fields`, §3 / C7). The slice's own measured values are used
**only to score**, never to tune any rule (C8 — no leakage).

---

## 7.1 The validation question (C2/C3)

§5/C1 established that 91.1% of real right-sizing queries are evidence-underdetermined; §6 built
a procedure that COMMITs on the decidable minority and ABSTAINs-informatively on the rest. Both
are statements about *how much evidence is missing* and *what the procedure does about it*.
Neither yet shows the thing an Oral reviewer demands (§18.1, "Missing metrics is obvious"): that
**answering anyway is measurably wrong**, and that **the procedure's silence is the correct
action** in exactly those cases.

That is the C2 question, and it is sharp and falsifiable:

> Take a slice with co-located *ground-truth* axis values. Bind a query on its axes. **Mask one
> binding axis.** Let each decision rule commit a config from the visible evidence. Score the
> commit against the **true** (unmasked) value of the hidden axis. A rule that commits a config
> violating the hidden constraint has **mis-sized** — silently, because by construction it could
> not see the axis it violated.

The load-bearing metric is **DV3 hidden-violation rate** = fraction of a rule's *commits* that
violate the masked truth. The claim is hard (§14): we **MUST beat B2** (observed-Pareto = current
honest practice) **and B3** (imputation = "just fill it in"), and ideally B6 (cost-accuracy =
FrugalGPT-style). The selective procedure's answer to a masked binding axis should be to
**ABSTAIN** — coverage 0 on that mask, but **zero hidden-violation**. That is the §17.1
Trust-or-Escalate shape with measured violations now visible on the *other* side: the baselines
buy coverage by mis-sizing; the procedure buys zero mis-sizing by escalating.

DV2 (decision regret, cost overshoot vs the oracle minimum-sufficient) is reported alongside, but
it is **degenerate when violations dominate** (§7.6): a rule that commits an infeasible config
contributes a hidden-violation, not a regret-over-feasible sample. So on the biting slices DV3
carries the claim and DV2 is near-zero by construction.

The **C3 leg** asks the §10 / DV5 question on top: when the procedure abstains, is its silence
*informative* — does the field it names (its cost-aware VoI pick) actually unblock the decision,
better than measuring a random field? V2 answers this.

---

## 7.2 Setup

**Ground-truth slices.** The scaled battery spans **7 biting slices** built from two co-located
measured corpora, used purely to score (C8):

| family | τ | slice construction | GT axes | n_candidates | n_queries |
|---|---|---|---|---|---|
| **BFCL** | `function-calling` | bind `quality+latency_p95`, mask `quality` | quality + cost + latency_p95 | 109 | 17 |
| **RouterBench** (×6) | `routerbench` | **per-benchmark** restriction, bind `quality`, mask `quality` | quality + cost | 11 each | 17 each |

The six RouterBench slices are the per-benchmark restrictions `{mmlu, hellaswag, arc-challenge,
winogrande, mbpp, grade-school-math}`. This is the key structural advance of the scaled battery:
holding the benchmark fixed (the §7.6 / P5 §3.3 cross-benchmark cost confound) makes the 11 models
**cost-comparable on a fixed task**, so the global cost-minimizer once again picks the *weakest
model* rather than the *cheapest benchmark* — turning the pilot's documented no-bite into six new
biting slices. Total: **119 queries** across 7 biting slices, all 17/slice at observed percentiles
`pcts 10..90 step 5`. (ML.ENERGY is excluded: no `cost` axis, so the cost-objective oracle cannot
score it.)

**Mask-and-predict** (`validation.harness.MaskAndPredict`). For each slice we generate queries that
*bind* the slice's `bind_axes` at matched observed percentiles, then mask one binding axis and, per
rule, read the prediction under the visible regime and score it against truth: `true_feasible(q,
pred)` checks the commit against the **full-regime** measured values; a commit that fails it is a
hidden violation; a feasible commit contributes `max(0, cost(pred) − oracle_cost(q))` to regret.

**Masking is enforced uniformly at the read level.** `MaskedSubstrate(sub, masked_axis)` returns
`[]` for the masked axis's `cell(...)`, so *no* rule can see the hidden axis regardless of how it
reads; only B5 (the oracle, `sees_masked=True`) is handed the unmasked substrate and so defines the
regret floor. This is the C7-shaped ablation: same interface, one axis silenced — a faithful
simulation of structural missingness. `⊥` stays `⊥`; nothing is imputed at the read level (C8 — the
oracle is the *only* leakage path, and it exists solely to score, never to decide).

**The baseline lattice B1–B6** (§14, `validation.baselines`) — one line each:

| | rule | what it does under the mask | role |
|---|---|---|---|
| B1 | accuracy-only | argmax quality, ignores cost & every constraint | strawman |
| **B2** | **observed-Pareto** | min visible-cost s.t. *visible* constraints; treats the masked axis as satisfied | **honest current practice — MUST beat** |
| **B3** | **imputation** | impute the masked axis (global median over τ's configs) then decide as B2 | **"just fill it in" — MUST beat** |
| B4 | missing-as-fail | a masked *binding* axis ⇒ abstain | conservative upper bound (0 violations) |
| B5 | oracle | sees the true masked values ⇒ true min-cost feasible | **regret floor** |
| B6 | cost-accuracy | min cost s.t. the quality constraint only; drops latency/energy/gov | FrugalGPT-style domain rival |
| — | **selective (ours)** | §6 `right_size` under the visible regime — COMMIT iff decidable, else ABSTAIN | the procedure |

---

## 7.3 V1 results — C2 at scale, with significance

### 7.3.1 Every biting slice HOLDS

Across all **7 biting slices**, the three commit-while-blind rules — **B2, B3, B6** — commit on
**100%** of queries (coverage 1.0) and hidden-violate at high rate, while the selective procedure
**abstains on every query (coverage 0)** and therefore hidden-violates at **0.0**. The per-slice
DV3 (verbatim from `validation_scaled.json`):

| slice | n_cand | n_q | B2 HVR | B3 HVR | B6 HVR | B5 oracle | **selective** | verdict |
|---|---|---|---|---|---|---|---|---|
| BFCL `quality+latency`/mask `quality` | 109 | 17 | 0.8824 (15/17) | 0.8824 | 0.8824 | 0.0 | **0.0** | **HOLDS** |
| routerbench[mmlu] | 11 | 17 | 0.7647 (13/17) | 0.7647 | 0.7647 | 0.0 | **0.0** | **HOLDS** |
| routerbench[hellaswag] | 11 | 17 | 0.9412 (16/17) | 0.9412 | 0.9412 | 0.0 | **0.0** | **HOLDS** |
| routerbench[arc-challenge] | 11 | 17 | 0.9412 (16/17) | 0.9412 | 0.9412 | 0.0 | **0.0** | **HOLDS** |
| routerbench[winogrande] | 11 | 17 | 0.7059 (12/17) | 0.7059 | 0.7059 | 0.0 | **0.0** | **HOLDS** |
| routerbench[mbpp] | 11 | 17 | 0.9412 (16/17) | 0.9412 | 0.9412 | 0.0 | **0.0** | **HOLDS** |
| routerbench[grade-school-math] | 11 | 17 | 1.0000 (17/17) | 1.0000 | 1.0000 | 0.0 | **0.0** | **HOLDS** |

**This is C2 at scale.** On every one of the 7 slices, honest current practice (B2) and both
standard defences (imputation B3, cost-accuracy B6) silently ship an infeasible config on the large
majority of queries the binding axis is unobservable — between **70.6%** (winogrande) and **100%**
(grade-school-math), B2/B3/B6 identical on every slice. The selective procedure abstains on all 17
queries of every slice and so has **0 hidden-violation** throughout: it refuses precisely when it
cannot certify the binding axis. **B5 (oracle) commits all 17 with 0 violations** on every slice —
the achievable floor — confirming feasible configs *exist*; the blind baselines just cannot find
them. The §18.1 "imputation solves it" attack is refuted with a number on every slice: B3's HVR is
**identical to B2's** — imputing the global-median quality commits the same blind config.

### 7.3.2 Pooled significance across the biting slices

The pilot's gating gap was *significance*: a single n=5 slice with an all-or-nothing 1.0-vs-0.0
separation, **no test run**. The scaled battery closes it. Pooling per-query paired comparisons
across all 7 biting slices (n=119), with a bootstrap 95% CI (`random.Random(12345)`) and a
McNemar one-sided exact-binomial test on the discordant pairs — verbatim from
`validation_scaled.json` (`pooled`):

| baseline | n | HV(baseline) | HV(selective) | **difference** | **95% CI** | CI excl. 0 | McNemar b/c | binom p | **significant?** |
|---|---|---|---|---|---|---|---|---|---|
| **B2 observed-Pareto** | 119 | 0.8824 | 0.0000 | **0.8824** | **[0.8235, 0.9412]** | **yes** | 105/0 | ≈ 0 | **YES** |
| **B3 imputation** | 119 | 0.8824 | 0.0000 | **0.8824** | **[0.8235, 0.9328]** | **yes** | 105/0 | ≈ 0 | **YES** |

> **The procedure beats B2 and B3 with significance.** Pooled hidden-violation gap = **0.8824**
> (selective 0.0000 vs both baselines 0.8824), 95% CI **[0.82, 0.94]** excluding zero, McNemar
> 105 discordant pairs all in our favour (b/c = 105/0), one-sided exact-binomial **p ≈ 0** for
> both must-beat baselines. Across **105 of 119** queries the baseline silently mis-sizes while
> the procedure correctly abstains; on the other 14 the baseline happens to land a feasible config
> and the procedure abstains harmlessly (it never commits an infeasible config — DV3 = 0
> everywhere). **Every individual slice is also significant** (per-slice p between 7.6e-06 and
> 2.4e-04, all CIs excluding zero) — the result is not an artifact of pooling. This is the §18.1
> surprise the Oral hinges on, now with statistics: *the community rule answers anyway and
> mis-sizes measurably, and the procedure's silence is the correct action.*

---

## 7.4 V2 results — VoI-guided acquisition (§10, DV5): informative abstention

C2 shows the abstention is *safe*. V2 shows it is *informative* — the §10 / DV5 question. On the
biting BFCL bind (`quality+latency_p95`, mask the single binding axis `quality`; latency stays
visible) the blocking set is exactly `{quality}`, so the procedure ABSTAINs on all queries; for
each abstention we simulate "measuring one field": (i) measure the procedure's **VoI pick**
(`acquire_next`, which is `quality`) → un-mask it → re-run selective; vs (ii) measure a **random
axis** (seeded, drawn from all 8 axes) → only unblocks if the draw *is* `quality`. Each
re-decision is scored COMMIT-and-*truly-feasible*. Verbatim from `outputs/p5/validation.json`
(`v2_acquisition`, seed=12345, 5 abstentions):

| measured field | commit-correct | commit-correct frac |
|---|---|---|
| **VoI pick (`acquire_next` = quality)** | **5/5** | **1.0** |
| random axis | 1/5 | 0.2 |

**The VoI pick wins decisively: 1.0 vs 0.2.** On every abstention the procedure's VoI ranking names
`quality` (raw VoI ≈ 1.0, `voi_per_cost` ≈ 3.33) as the field worth measuring — and measuring it
yields a truly-feasible commit **every time** (5/5). The random baseline succeeds only on the one
query (`@p60`) where the seeded draw happened to land on `quality` (1/5 = 0.2); on the other four it
drew `reviewer_burden`, `cost`, `memory_hw`, `latency_p95` — none of which unblocks the decision.
**The abstention is INFORMATIVE**: it does not merely decline, it *names the field that actually
unblocks*, right 5/5 vs 1/5 for a blind guess. This cashes out the **VoI = Δ(R)** identity proven in
§6 / P4 (`tests/test_procedure.py::test_voi_equals_delta_R`): the axis with the highest VoI is
exactly the one whose measurement converts an abstention into a correct commit.

*(Scope note: V2 is the pilot construction (n=5 abstentions on the BFCL biting bind); scaling the
VoI-lift across the 7 biting slices, and the §10 multi-reveal "reveal-until-decidable" cascade,
remain V2 stretch items — §7.7.)*

---

## 7.5 Ablation by evidence regime — tying decidability to the limit theorem

The C2 bite is not a quirk of one masking choice; it is the empirical shadow of the §8 limit
theorem. The masking ablation *is* an evidence-regime ablation: each masked regime omits one
binding axis, and the limit theorem says any rule that commits under a regime missing a binding
axis pays `≥ Δ(R) = δλ/(δ+λ)` — here cashed out as a hidden violation rather than a feasible
overshoot.

| evidence regime (visible axes) | decision status | blind-baseline DV3 | selective |
|---|---|---|---|
| accuracy-only (quality only, cost/latency hidden) | binding axis hidden ⇒ **non-identifiable** | violates (B1 chases quality, ignores cost) | abstains |
| +cost (quality+cost, the masked binding axis still hidden) | masked binding axis ⇒ **non-identifiable** | **B2/B3/B6 commit blind ⇒ HVR 0.71–1.00** | **abstains, HVR 0.0** |
| +latency (BFCL control: mask latency instead, cheap⇒fast) | hidden axis *co-satisfied* ⇒ **identifiable** | HVR 0.0 (no bite) | abstains |
| full (oracle B5 sees the masked axis) | **decidable** | HVR 0.0, regret 0.0 (floor) | (commits) |

Reading down the ladder: when the regime hides a **binding** axis that cheap configs trade off (the
+cost rows: BFCL cheap⇒low-quality, per-benchmark RouterBench cheap⇒weak-model), the decision is
non-identifiable and every blind baseline mis-sizes — exactly the regime where the procedure
abstains. When the regime hides an axis the cheapest config *happens to satisfy* (the +latency
control: cheap⇒fast, so the latency floor is met by accident), the decision becomes identifiable
from the visible evidence alone and there is no bite. At full evidence the oracle is decidable and
pays the floor (HVR 0, regret 0). This is the limit theorem made operational: **decidability rises
monotonically as the evidence regime covers the binding axes**, and the hidden-violation rate of
blind commitment is the irreducible regret `Δ(R)` of the regime that omits one — DV3 is the
limit-theorem penalty *observed*, not assumed.

---

## 7.6 Relation to claims

**C2 (DV2 + DV3) — demonstrated at scale, with significance.** Across 7 biting slices and 119
queries, current honest practice (B2) and its defences (B3, B6) hidden-violate at a pooled
**88.2%** while the procedure hidden-violates at **0%**; the gap **0.8824 [0.8235, 0.9412]** is
significant against **both** must-beat baselines (McNemar 105/0, p ≈ 0), and significant on **every
individual slice**. The per-benchmark RouterBench restriction resolved the pilot's documented
cross-benchmark cost confound (§7.2): six new biting slices beyond BFCL, so the result no longer
rests on a single corpus. DV2 regret is degenerate-by-violation on the biting slices (§7.7.3), so
DV3 is the load-bearing metric and it passes the "beat B2 and B3 with significance" bar.

**C3 — informative abstention + VoI — supported by V2.** The selective procedure's
coverage-0/violation-0 column *is* the safe action: it escalates exactly the queries where it
cannot certify the binding axis, instead of shipping a blind commit. V2 shows the escalation is
*informative* — the field it names unblocks the decision 5/5 (1.0) vs 1/5 (0.2) random. This is the
**Trust-or-Escalate shape** (§17.1) now with **measured violations on the other side** and a
**measured VoI lift** on the abstention: §6/P4 showed reliability is purchasable only by abstaining
on most traffic (commit ≈ 8.9% coverage at 0 committed risk); §7 shows *what the alternative costs*
(blind rules hidden-violate at 88% pooled on the biting axis) *and* that the abstention pays back
(VoI names the unblocking field).

---

## 7.7 Honest limitations

1. **"Truth" is the slice's own measured values, not an independent oracle.** Ground-truth here =
   the substrate's co-located H/M-confidence measurements; **BFCL is M-confidence** (RouterBench is
   H-confidence). This is calibration against the richest evidence we have on each slice, not an
   external held-out oracle (the §8.8 / P4-§5 discipline).

2. **Masking is an ablation simulating missingness.** We *withhold* an axis we actually measured, to
   model the structural missingness §5/C1 found in the wild. It is a faithful simulation, not a
   naturally-missing slice — V3 live runs (real missing axes on local AI boxes) remain the stretch.

3. **Regret-over-feasible is degenerate when violations dominate.** On the biting slices nearly every
   blind-baseline commit is *infeasible*, so it contributes a hidden-violation, not a regret sample —
   hence `mean_regret = 0.0` across the board. **DV3 hidden-violation-rate is the load-bearing
   metric**, not DV2 regret, on exactly the slices where C2 bites.

4. **Axis-specificity is a feature, reported as a caveat.** The bite is on `mask=quality` where cheap
   configs trade quality off; the BFCL `mask=latency_p95` control does **not** bite (cheap⇒fast, so
   the blind commit co-satisfies the hidden latency floor — only B1 violates there). The claim is
   "current practice mis-sizes *where multiple axes truly bind and cheap trades off the hidden one*",
   not a universal claim — and the no-bite control keeps it falsifiable.

5. **RouterBench requires the per-benchmark restriction.** The mixed-benchmark slice is ill-posed for
   right-sizing (cost varies by *benchmark* not *model*; the global cost-minimizer picks the cheapest
   benchmark, not the weakest model). The valid experiment holds the benchmark fixed — which is
   exactly the 6 per-benchmark slices used here. The mixed slice is reported as a documented confound,
   not a bite.

6. **V2 is pilot-scale; V3 live runs not done.** The VoI-lift (1.0 vs 0.2) is on n=5 abstentions on
   the BFCL biting bind; scaling it across all 7 biting slices and the §10 multi-reveal cascade
   (reveal-until-decidable, regret-to-oracle vs random ordering) remain V2 stretch items. No vLLM +
   ML.ENERGY energy + governance/burden human study yet (V3).

---

## 7.8 Go / No-Go read (§18.2), updated with the scaled significance

§18.2 says: if P5 cannot show mis-sizing — **B2/B3 not beaten with significance** across the
battery — do not force Oral. The pilot read was **GO on the C2/C3 demonstration, HOLD on Oral
significance**: the bite was categorical (1.0 vs 0.0) but on a single n=5 slice with no test run.
The scaled battery clears exactly that gap:

- **Direction:** beaten — pooled hidden-violation gap **0.8824** (selective 0.0 vs B2=B3 0.8824).
- **Significance:** beaten — 95% CI **[0.8235, 0.9412]** excluding zero for both must-beat
  baselines, McNemar **105/0**, one-sided exact-binomial **p ≈ 0**; **every individual slice
  significant** too (p ∈ [7.6e-06, 2.4e-04]).
- **Breadth:** beaten — **7 biting slices**, not one; the per-benchmark RouterBench restriction
  resolved the pilot's cross-benchmark confound and added 6 independent biting slices.
- **C3:** the V2 VoI lift (1.0 vs 0.2) adds a clean informative-abstention signal (pilot-scale).

> **Updated read: GO — Oral.** The §18.2 gate ("beat B2 and B3 with significance across the
> battery") is now **met**: the procedure beats both must-beat baselines with a pooled gap of 0.88
> [0.82, 0.94], p ≈ 0, McNemar 105/0, on 7 biting slices, with every slice individually
> significant. The mis-sizing is real, categorical, *significant*, and *broad*; it refutes both the
> "missing-metrics-is-obvious" and "imputation-solves-it" reviewer attacks (§18.1) with numbers,
> and the procedure lands the safe *and* informative action (C3). Remaining stretch — scaled V2
> VoI-lift and V3 live runs — strengthens the C3 leg but is **not** gating for the C2 Oral claim.

---

## 7.9 Key numbers the paper cites

- **C2 at scale (7 biting slices, 119 queries, κ=H+M, φ=point, seed=12345):** B2/B3/B6 each
  coverage 1.0, per-slice hidden-violation-rate **0.71–1.00**; selective coverage 0.0,
  hidden-violation-rate **0.0** on every slice. All 7 `c2_verdict = holds`. B5 oracle = regret floor
  (HVR 0.0).
- **Pooled significance (n=119, paired, baseline − selective):** B2 and B3 both — difference
  **0.8824**, 95% CI **[0.8235, 0.9412]** (B3: [0.8235, 0.9328]) excluding zero, McNemar **105/0**,
  one-sided exact-binomial **p ≈ 0**, **significant = YES**. **Beats B2 and B3 with significance.**
- **Per-slice significance:** all 7 significant; p ∈ [7.63e-06 (grade-school-math, mbpp,
  hellaswag, arc-challenge), 2.44e-04 (winogrande)]; every CI excludes zero.
- **C3 / V2 VoI lift (BFCL biting case, mask `quality`, seed=12345, 5 abstentions):** VoI pick
  (`acquire_next` = quality) → commit-correct **5/5 = 1.0**; random axis → **1/5 = 0.2**. Anchored to
  **VoI = Δ(R)** (`tests/test_procedure.py::test_voi_equals_delta_R`).
- **Go/No-Go (§18.2):** **GO — Oral.** Pooled gap 0.88 [0.82, 0.94], p ≈ 0, McNemar 105/0, 7 biting
  slices each individually significant — the "beat B2/B3 with significance across the battery" gate
  is met. (Pilot read was HOLD-on-significance; the scaled battery cleared it.)
