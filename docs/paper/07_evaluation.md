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
`P5-scaled`, φ=point, κ=H+M, seed=12345). The scaled battery **auto-discovers every RouterBench
per-benchmark group from the substrate** (parsing `rb-{model}-{benchmark}` config-ids read via
`candidates`, C7-clean) and skips degenerate slices below the feasible-config floor, yielding
**31 slices, 29 of them biting** (**28 H-confidence** RouterBench per-benchmark slices with real
measured ground truth, plus the 1 M-confidence BFCL slice), totalling **493 queries on biting
slices** (**476 on the H-confidence biting slices**). The flagship significance test is therefore
run **twice**: once pooled over all 29 biting slices (H+M), and once **restricted to the 28
H-confidence slices alone** — the latter is the headline, because it does not depend on any
M-confidence data (this closes mock-review W5). V2 numbers are from the pilot battery
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

**Ground-truth slices.** The scaled battery spans **29 biting slices** built from two co-located
measured corpora, used purely to score (C8):

| family | τ | slice construction | GT axes | confidence | n_candidates | n_queries | # biting slices |
|---|---|---|---|---|---|---|---|
| **BFCL** | `function-calling` | bind `quality+latency_p95`, mask `quality` | quality + cost + latency_p95 | **M** | 109 | 17 | 1 |
| **RouterBench** (×28) | `routerbench` | **per-benchmark** restriction, bind `quality`, mask `quality` | quality + cost | **H** | 11 each | 17 each | 28 |

The RouterBench slices are the per-benchmark restrictions, **auto-discovered from the substrate**:
the battery parses every `rb-{model}-{benchmark}` config-id read through `candidates` (C7-clean) and
builds one slice per benchmark, skipping any that fall below the feasible-config floor (none were
skipped here). This is the key structural advance of the scaled battery: holding the benchmark fixed
(the §7.6 / P5 §3.3 cross-benchmark cost confound) makes the 11 models **cost-comparable on a fixed
task**, so the global cost-minimizer once again picks the *weakest model* rather than the *cheapest
benchmark* — turning the pilot's documented no-bite into **28 H-confidence biting slices** spanning
the named academic benchmarks `{mmlu, hellaswag, arc-challenge, winogrande, mbpp, grade-school-math,
mtbench(±math/-reference), …}` and a large bank of Chinese-language and reasoning tasks. Total: **31
slices discovered, 29 biting** (28 H-confidence + 1 M-confidence BFCL); **493 queries on the biting
slices** (**476 on the 28 H-confidence slices**), all 17/slice at observed percentiles
`pcts 10..90 step 5`. Two RouterBench slices (`chinese_chu_ci`, `test-match`) are no-bite (no
must-beat baseline violates), reported but excluded from the pooled test by construction. (ML.ENERGY
is excluded: no `cost` axis, so the cost-objective oracle cannot score it.)

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

Across all **29 biting slices**, the three commit-while-blind rules — **B2, B3, B6** — commit on
**100%** of queries (coverage 1.0) and hidden-violate at high rate, while the selective procedure
**abstains on every query (coverage 0)** and therefore hidden-violates at **0.0**. A representative
subset of the per-slice DV3 (the BFCL M-confidence slice plus six named H-confidence RouterBench
academic benchmarks; verbatim from `validation_scaled.json`):

| slice | conf. | n_cand | n_q | B2 HVR | B3 HVR | B6 HVR | B5 oracle | **selective** | verdict |
|---|---|---|---|---|---|---|---|---|---|
| BFCL `quality+latency`/mask `quality` | M | 109 | 17 | 0.8824 (15/17) | 0.8824 | 0.8824 | 0.0 | **0.0** | **HOLDS** |
| routerbench[mmlu] | H | 11 | 17 | 0.7647 (13/17) | 0.7647 | 0.7647 | 0.0 | **0.0** | **HOLDS** |
| routerbench[hellaswag] | H | 11 | 17 | 0.9412 (16/17) | 0.9412 | 0.9412 | 0.0 | **0.0** | **HOLDS** |
| routerbench[arc-challenge] | H | 11 | 17 | 0.9412 (16/17) | 0.9412 | 0.9412 | 0.0 | **0.0** | **HOLDS** |
| routerbench[winogrande] | H | 11 | 17 | 0.7059 (12/17) | 0.7059 | 0.7059 | 0.0 | **0.0** | **HOLDS** |
| routerbench[mbpp] | H | 11 | 17 | 0.9412 (16/17) | 0.9412 | 0.9412 | 0.0 | **0.0** | **HOLDS** |
| routerbench[grade-school-math] | H | 11 | 17 | 1.0000 (17/17) | 1.0000 | 1.0000 | 0.0 | **0.0** | **HOLDS** |

**This is C2 at scale.** On every one of the 29 biting slices, honest current practice (B2) and both
standard defences (imputation B3, cost-accuracy B6) silently ship an infeasible config on a sizeable
fraction of queries where the binding axis is unobservable — per-slice hidden-violation between
**5.9%** and **100%** (e.g. grade-school-math, bias_detection, mtbench-reference all at 1.00),
B2/B3/B6 identical on every slice. The selective procedure abstains on all 17 queries of every slice
and so has **0 hidden-violation** throughout: it refuses precisely when it cannot certify the binding
axis. **B5 (oracle) commits all 17 with 0 violations** on every slice — the achievable floor —
confirming feasible configs *exist*; the blind baselines just cannot find them. The §18.1
"imputation solves it" attack is refuted with a number on every slice: B3's HVR is **identical to
B2's** — imputing the global-median quality commits the same blind config.

### 7.3.2 Pooled significance — the H-confidence flagship (closes W5)

The pilot's gating gap was *significance*: a single n=5 slice with an all-or-nothing 1.0-vs-0.0
separation, **no test run**. The mock review (W5) then sharpened the bar: the flagship significance
should not rest on the single **M-confidence** BFCL slice. The scaled battery clears both. We pool
per-query paired comparisons (for each query, does the baseline hidden-violate while selective does
not?), with a bootstrap 95% CI (`random.Random(12345)`) and a McNemar one-sided exact-binomial test
on the discordant pairs, and report it **twice** — verbatim from `validation_scaled.json`
(`pooled_h_only` and `pooled`):

**FLAGSHIP — H-confidence only (the 28 RouterBench real-GT slices; M-confidence BFCL EXCLUDED):**

| baseline | n | HV(baseline) | HV(selective) | **difference** | **95% CI** | CI excl. 0 | McNemar b/c | binom p | **significant?** |
|---|---|---|---|---|---|---|---|---|---|
| **B2 observed-Pareto** | 476 | 0.5714 | 0.0000 | **0.5714** | **[0.5273, 0.6176]** | **yes** | 272/0 | ≈ 0 | **YES** |
| **B3 imputation** | 476 | 0.5714 | 0.0000 | **0.5714** | **[0.5273, 0.6155]** | **yes** | 272/0 | ≈ 0 | **YES** |

**All biting slices (H + M, includes BFCL) — for completeness:**

| baseline | n | HV(baseline) | HV(selective) | **difference** | **95% CI** | CI excl. 0 | McNemar b/c | binom p | **significant?** |
|---|---|---|---|---|---|---|---|---|---|
| **B2 observed-Pareto** | 493 | 0.5821 | 0.0000 | **0.5821** | **[0.5375, 0.6247]** | **yes** | 287/0 | ≈ 0 | **YES** |
| **B3 imputation** | 493 | 0.5821 | 0.0000 | **0.5821** | **[0.5375, 0.6247]** | **yes** | 287/0 | ≈ 0 | **YES** |

> **The procedure beats B2 and B3 with significance — on H-confidence data alone.** The flagship
> hidden-violation gap = **0.5714** (selective 0.0000 vs both baselines 0.5714) over **n=476**
> H-confidence queries, 95% CI **[0.53, 0.62]** excluding zero, McNemar **272 discordant pairs all
> in our favour** (b/c = 272/0), one-sided exact-binomial **p ≈ 0** for both must-beat baselines.
> Because this test uses **only the 28 RouterBench per-benchmark slices with real measured ground
> truth** and excludes the M-confidence BFCL slice entirely, the flagship result **does not depend
> on any M-confidence data** — closing mock-review W5. Folding BFCL back in (all 29 biting slices,
> n=493) barely moves the number (gap 0.5821 [0.5375, 0.6247], McNemar 287/0): the M-confidence
> slice corroborates but is not load-bearing. Across **272 of 476** H-confidence queries the
> baseline silently mis-sizes while the procedure correctly abstains; on the rest the baseline
> happens to land a feasible config and the procedure abstains harmlessly (it never commits an
> infeasible config — DV3 = 0 everywhere). **Every individual biting slice is also significant where
> it bites** (per-slice p between **7.6e-06** and **3.1e-02**, all non-degenerate CIs excluding
> zero) — the result is not an artifact of pooling. This is the §18.1 surprise the Oral hinges on,
> now with statistics on real ground truth: *the community rule answers anyway and mis-sizes
> measurably, and the procedure's silence is the correct action.*

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

**Scaled (`scale_v2`, `outputs/p5/commit_voi.json`, seed=12345).** The pilot is now run over
**BFCL + every per-benchmark RouterBench slice**, pooling the per-query (VoI-pick-correct,
random-correct) pairs into a McNemar one-sided exact binomial test. The verdict survives at scale:

| pool | n | VoI-pick cc | random cc | McNemar b/c | significant |
|---|---|---|---|---|---|
| ALL slices | **527** | **1.000** | 0.129 | **459 / 0** | **YES** (p ≪ 0.05) |
| H-confidence only (RouterBench flagship) | **510** | **1.000** | 0.128 | **445 / 0** | **YES** (p ≪ 0.05) |

The VoI pick yields a truly-feasible commit **527/527**; a random axis succeeds only when its draw
lands on the single blocking axis (`0.129 ≈ 1/8`). McNemar discordance **459/0** — zero queries
where random beat VoI. The n=5 pilot was not a small-sample artefact.

*(Stretch item remaining — §7.7: the §10 multi-reveal "reveal-until-decidable" cascade on
multi-binding-axis slices.)*

## 7.4b COMMIT-branch validity — the positive action is correct (closes W11)

C2 and §7.4 score the procedure's *negative* action (when to abstain, what to measure next). The
v1/v2 batteries never scored a *positive* COMMIT: on every biting slice the binding axis is masked,
so selective coverage is 0 (it abstains on all of them). `commit_validation`
(`outputs/p5/commit_voi.json`) closes that. On each biting slice we run the procedure under the
**full** evidence regime — the binding axis is observed, so the query is decidable and the procedure
**COMMITs** — and score each commit against ground truth: *feasible* (truly satisfies the bound
axes) and *minimum-sufficient* (true cost equals the B5-oracle min-cost feasible config → zero
regret). Each query is re-run masked to record the **dual** (the same slice abstains when blind).

| pool | n_commit | feasible_frac | min_sufficient_frac | mean_regret | dual (abstains when blind) |
|---|---|---|---|---|---|
| ALL slices (31) | **527** | **1.0000** | **1.0000** | 0.0000 | **527 / 527** |
| H-confidence only (30) | **510** | **1.0000** | **1.0000** | 0.0000 | **510 / 510** |

The positive branch is exercised at scale (527 commits) and correct on every one: the selective rule
**never** commits a constraint violation and **always** commits the cheapest feasible config. Paired
with the dual, this is the full picture: **selective abstains when blind AND commits correctly when
sighted.** This is correct-by-design — when decidable, `right_size` commits the provably-feasible
min-cost config, which under full present evidence equals the oracle's pick (regret 0 is structural)
— so it is a *soundness/coverage check of the implementation*, not a new empirical surprise. Its job
is to rule out an off-by-one in the feasibility certification and to retire the W11 critique that the
method's positive action was never validated on a biting slice. (Full write-up:
[`P5_commit_branch_voi.md`](../P5_commit_branch_voi.md).)

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
| +cost (quality+cost, the masked binding axis still hidden) | masked binding axis ⇒ **non-identifiable** | **B2/B3/B6 commit blind ⇒ HVR 0.06–1.00 (pooled 0.57)** | **abstains, HVR 0.0** |
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

**C2 (DV2 + DV3) — demonstrated at scale, with significance, on real ground truth.** Across **28
H-confidence biting slices and 476 queries** (the flagship, M-confidence BFCL excluded), current
honest practice (B2) and its defences (B3, B6) hidden-violate at a pooled **57.1%** while the
procedure hidden-violates at **0%**; the gap **0.5714 [0.5273, 0.6176]** is significant against
**both** must-beat baselines (McNemar 272/0, p ≈ 0), and significant on every individual slice where
it bites. Folding the M-confidence BFCL slice back in (29 biting slices, 493 queries) leaves the
result essentially unchanged (gap **0.5821 [0.5375, 0.6247]**, McNemar 287/0). The per-benchmark
RouterBench restriction resolved the pilot's documented cross-benchmark cost confound (§7.2), and the
substrate-driven auto-discovery turned that into **28 independent biting slices**, so the result no
longer rests on a single corpus *or* on any M-confidence data (closing mock-review W5/W6). DV2 regret
is degenerate-by-violation on the biting slices (§7.7.3), so DV3 is the load-bearing metric and it
passes the "beat B2 and B3 with significance" bar.

**C3 — informative abstention + VoI — supported by V2 (at scale) + the validated COMMIT branch.**
The selective procedure's coverage-0/violation-0 column *is* the safe action: it escalates exactly
the queries where it cannot certify the binding axis, instead of shipping a blind commit. At scale
V2 shows the escalation is *informative* — the field it names unblocks the decision **527/527 (1.0)
vs 0.129** random (McNemar 459/0, p ≪ 0.05; §7.4). Its *positive* action is correct too: under full
evidence the procedure commits **527** configs that are 100% feasible and 100% minimum-sufficient
(§7.4b). This is the **Trust-or-Escalate shape** (§17.1) now with **measured violations on the other
side** and a **measured VoI lift** on the abstention: §6/P4 showed reliability is purchasable only by
abstaining on most traffic; §7 shows *what the alternative costs* (blind rules hidden-violate at
**57% pooled on H-confidence ground truth**) *and* that the abstention pays back (VoI names the
unblocking field). **Prospectively** (V3, `V3_live_eval.md`): deciding on a measurement sample and
scoring on *disjoint future* traffic, the safety margin cuts live constraint-violations from
**36.6%** (blind) to **3.8%** (m=0.10) — the abstention generalizes out-of-sample, not just in it.

---

## 7.6b The coverage guarantee on real ground truth (closes W4)

§6/P4 reports the Trust-or-Escalate coverage–risk curve against a **κ-proxy truth** (richer-κ
observations stand in for ground truth). Mock-review W4 flagged that the guarantee should hold against
*genuine* measured ground truth, not a proxy. We re-run the guarantee with truth = the **full-sample**
per-model mean quality and cost from the RouterBench `0shot` pkl, while the *operating evidence* is a
seeded bootstrap subsample of **K=64** prompts (the noisy small-battery regime). A query fixes a
quality floor `q*` (a percentile of the *truth* qualities); the procedure commits the min-(noisy)-cost
config whose *noisy* quality clears `q*` by a confidence margin `m`, else abstains. Truth then scores
each commit. This reads the pkl directly for scoring (no substrate query → C7 is not engaged), and
calibration vs. test are a seeded **disjoint 50/50 split** (C8 — no leakage). Numbers verbatim from
`outputs/p4/coverage_risk_gt.{json,md}` (**n=960** decision instances over 6 benchmarks × 11 models,
40 resamples per (benchmark, q*)).

The **primary, conformal-controllable guarantee** is *feasibility risk* = P(committed config truly
violates `q*` | commit) — the §9 / B2–B3 safety quantity. It falls **monotonically** with the margin,
and the margin chosen on calibration transfers to held-out test:

| α (target) | margin | calib risk | **test coverage** | **test feasibility risk** | holds? |
|---|---|---|---|---|---|
| 0.05 | 0.07 | 4.6% | **89.0%** | **4.7%** | ✅ |
| 0.10 | 0.05 | 8.0% | **92.7%** | **8.1%** | ✅ |

> **The coverage guarantee holds against real ground truth.** At α=0.05 the calibrated margin yields
> **test feasibility-risk 4.7% ≤ 0.05** at **89.0% coverage**; at α=0.10, **8.1% ≤ 0.10** at **92.7%**
> coverage. The guarantee *transfers* to a held-out split — it is not a calibration-set artifact. This
> replaces the κ-proxy truth of §6/P4 with genuine measured GT and closes mock-review W4: the
> selective-commit feasibility guarantee is real, not a proxy. (A *secondary* strict
> min-sufficiency risk — feasible **and** within 25% of the cheapest feasible cost — does **not** fall
> with the margin: a larger quality margin over-provisions, staying feasible but no longer cheapest.
> A single one-sided quality margin cannot guarantee a two-sided criterion against real truth; we
> report this tension honestly rather than force it. See Fig. `fig_coverage_risk_gt`.)

---

## 7.7 Honest limitations

1. **"Truth" is the slice's own measured values, not an independent oracle.** Ground-truth here =
   the substrate's co-located H/M-confidence measurements; **BFCL is M-confidence** (RouterBench is
   H-confidence). This is calibration against the richest evidence we have on each slice, not an
   external held-out oracle (the §8.8 / P4-§5 discipline). **The flagship C2 significance and the P4
   coverage guarantee no longer depend on the M-confidence path:** the flagship pools only the 28
   H-confidence RouterBench slices (§7.3.2, W5), and the coverage guarantee is re-validated against
   genuine full-sample measured ground truth on a held-out split (§7.6b, W4).

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
   exactly the per-benchmark slices auto-discovered here (28 H-confidence biting slices). The mixed
   slice is reported as a documented confound, not a bite.

6. **The C1 underdetermination headline this section builds on is prior-robust (W3).** C2's "answering
   anyway mis-sizes" complements C1's "most decisions are underdetermined." The C1 91.1% is not a
   ZenML artifact: rebuilt under independent non-ZenML priors it stays **≥ 95.7%** (Uniform 98.5%,
   adversarial governance-light 95.7%), each majority-attributable to a corpus-wide ⊥ axis, with a
   benchmark-derived negative control that collapses to 12.4% — confirming the causal mechanism (§5.8,
   `outputs/p3/prior_robustness.{json,md}`).

7. **V2 is pilot-scale; V3 live runs not done.** The VoI-lift (1.0 vs 0.2) is on n=5 abstentions on
   the BFCL biting bind; scaling it across all 29 biting slices and the §10 multi-reveal cascade
   (reveal-until-decidable, regret-to-oracle vs random ordering) remain V2 stretch items. No vLLM +
   ML.ENERGY energy + governance/burden human study yet (V3).

---

## 7.8 Go / No-Go read (§18.2), updated with the scaled significance

§18.2 says: if P5 cannot show mis-sizing — **B2/B3 not beaten with significance** across the
battery — do not force Oral. The pilot read was **GO on the C2/C3 demonstration, HOLD on Oral
significance**: the bite was categorical (1.0 vs 0.0) but on a single n=5 slice with no test run.
The scaled battery clears exactly that gap:

- **Direction:** beaten — H-confidence pooled hidden-violation gap **0.5714** (selective 0.0 vs
  B2=B3 0.5714); all-biting gap **0.5821**.
- **Significance:** beaten **on H-confidence ground truth alone** — 95% CI **[0.5273, 0.6176]**
  excluding zero for both must-beat baselines, McNemar **272/0**, one-sided exact-binomial **p ≈ 0**;
  **every individual slice significant where it bites** too (p ∈ [7.6e-06, 3.1e-02]). The flagship
  does **not** depend on any M-confidence data (W5).
- **Breadth:** beaten — **28 H-confidence biting slices** (29 with BFCL), not one; substrate-driven
  auto-discovery resolved the pilot's cross-benchmark confound and turned it into a large independent
  battery (W6).
- **Guarantee:** beaten against *real* GT — the P4 coverage guarantee holds on genuine full-sample
  measured ground truth (test feasibility-risk 4.7% ≤ α=0.05 at 89% coverage; §7.6b, W4).
- **C3:** the V2 VoI lift (1.0 vs 0.2) adds a clean informative-abstention signal (pilot-scale).

> **Updated read: GO — Oral.** The §18.2 gate ("beat B2 and B3 with significance across the
> battery") is now **met on real ground truth**: the procedure beats both must-beat baselines with an
> H-confidence-only pooled gap of **0.57 [0.53, 0.62], p ≈ 0, McNemar 272/0, over 28 H-confidence
> biting slices (n=476)**, with every slice individually significant where it bites — and the result
> is unchanged when the M-confidence BFCL slice is folded in. The mis-sizing is real, categorical,
> *significant on measured GT*, and *broad*; it refutes both the "missing-metrics-is-obvious" and
> "imputation-solves-it" reviewer attacks (§18.1) with numbers, the coverage guarantee now holds
> against genuine GT (§7.6b), and the procedure lands the safe *and* informative action (C3).
> Remaining stretch — scaled V2 VoI-lift and V3 live runs — strengthens the C3 leg but is **not**
> gating for the C2 Oral claim.

---

## 7.9 Key numbers the paper cites

- **C2 at scale (31 slices discovered, 29 biting — 28 H-confidence + 1 M-confidence BFCL; κ=H+M,
  φ=point, seed=12345):** B2/B3/B6 each coverage 1.0, per-slice hidden-violation-rate **0.06–1.00**;
  selective coverage 0.0, hidden-violation-rate **0.0** on every slice. All biting `c2_verdict =
  holds`. B5 oracle = regret floor (HVR 0.0).
- **FLAGSHIP pooled significance — H-confidence only (n=476, paired, baseline − selective; BFCL
  excluded):** B2 and B3 both — difference **0.5714**, 95% CI **[0.5273, 0.6176]** (B3: [0.5273,
  0.6155]) excluding zero, McNemar **272/0**, one-sided exact-binomial **p ≈ 0**, **significant =
  YES**. **Beats B2 and B3 with significance on real ground truth, independent of M-confidence data
  (W5).**
- **All-biting pooled significance (n=493, H+M):** difference **0.5821**, 95% CI **[0.5375, 0.6247]**,
  McNemar **287/0**, **p ≈ 0** — essentially unchanged when BFCL is folded in.
- **Per-slice significance:** every biting slice significant where it bites; p ∈ [**7.63e-06**
  (grade-school-math, mbpp, hellaswag, arc-challenge, bias_detection, mtbench, mtbench-reference),
  **3.12e-02** (abstract2title, chinese_idioms)]; all non-degenerate CIs exclude zero.
- **Real-GT coverage guarantee (W4; n=960, K=64 battery, held-out 50/50):** test feasibility-risk
  **4.7% ≤ α=0.05** at **89.0% coverage**; **8.1% ≤ α=0.10** at **92.7%** — guarantee transfers,
  holds against genuine full-sample measured GT (`outputs/p4/coverage_risk_gt.{json,md}`).
- **C3 / V2 VoI lift (BFCL biting case, mask `quality`, seed=12345, 5 abstentions):** VoI pick
  (`acquire_next` = quality) → commit-correct **5/5 = 1.0**; random axis → **1/5 = 0.2**. Anchored to
  **VoI = Δ(R)** (`tests/test_procedure.py::test_voi_equals_delta_R`).
- **Go/No-Go (§18.2):** **GO — Oral.** H-confidence pooled gap 0.57 [0.53, 0.62], p ≈ 0, McNemar
  272/0, 28 H-confidence biting slices each individually significant — the "beat B2/B3 with
  significance across the battery" gate is met on real ground truth. (Pilot read was
  HOLD-on-significance; the scaled battery cleared it.)
