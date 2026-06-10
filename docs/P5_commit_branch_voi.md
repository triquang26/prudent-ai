# P5 — COMMIT-branch validity + scaled VoI acquisition (W11 / C3)

> Node: `zh6apu-commit-branch-voi-scale` (parent `eyfl2u-final-hardening`).
> Code: `ValidationRunner.commit_validation` + `ValidationRunner.scale_v2`
> (`src/prudent_ai/analysis/validation_run.py`). Runner: `scripts/run_commit_voi.py`.
> Outputs: `outputs/p5/commit_voi.{json,md}`. Tests: `tests/test_commit_voi.py`.
> κ=H+M, φ=point, seed=12345, db=`data/apt_substrate.db`.

## Why

The V1 battery validates the selective procedure's **negative** action only: on
every biting slice the binding axis is masked → every query is underdetermined →
selective **ABSTAINs** (coverage 0). So the lattice proved *when to abstain* (C2)
but never scored a **positive COMMIT** — exactly the residual the v2 mock review
flagged (W11/W6-residual: "selective coverage = 0 on every biting slice"). And the
§10 VoI-lift (C3) was a single **n=5** BFCL pilot (VoI-pick 1.0 vs random 0.2) —
suggestive, not significance-backed.

Both are addressed here **without new data**, reading only through the C7 interface;
the GT slice SCOREs, never tunes (C8).

## 1. COMMIT-branch validity — the positive action is correct (closes W11)

**Construction.** On each biting slice (BFCL + every per-benchmark RouterBench
group), run the selective procedure under the **FULL** evidence regime — the binding
axis IS observed, so the query is *decidable* and the procedure **COMMITs**. Score
each commit against ground truth:
- **feasible** — the committed config truly satisfies the bound axes
  (`true_feasible`); the procedure must never commit a violation;
- **minimum-sufficient** — its true cost equals the B5-oracle min-cost feasible
  config → **zero decision-regret**; the commit is not merely feasible but the
  *cheapest* feasible config.

Each query is also re-run **masked** to record the **dual**: the same slice forces
ABSTAIN when the binding axis is hidden.

**Result (`outputs/p5/commit_voi.json`, `commit_validation`).**

| pool | n_commit | coverage | feasible_frac | min_sufficient_frac | mean_regret | masked-abstains (dual) |
|---|---|---|---|---|---|---|
| ALL slices (31) | **527** | 1.0000 | **1.0000** | **1.0000** | 0.0000 | **527 / 527** |
| H-confidence only (30 RouterBench) | **510** | 1.0000 | **1.0000** | **1.0000** | 0.0000 | **510 / 510** |

Per slice (all 31): 17/17 commits, `feasible_frac=1.0`, `min_sufficient_frac=1.0`,
`mean_regret=0.0`, `dual=YES`.

**Reading.** The positive branch is now **exercised at scale (527 commits)** and is
correct on every one: the selective rule never commits a constraint violation
(`feasible_frac=1.0`) and always commits the cheapest feasible config
(`min_sufficient_frac=1.0`, regret 0). Paired with the dual — the *same* 527 queries
all ABSTAIN under the masked regime — this is the full picture the v1 battery was
missing: **selective abstains when blind AND commits correctly when sighted.**

**Honest framing.** This is by design: when a query is decidable, `right_size`
commits `best_sure` = the provably-feasible min-cost config, which under full present
point-evidence equals the oracle's true min-cost feasible config (regret 0 is
structural, see `decidability.py`). So this is a **soundness/coverage check of the
implementation**, not a surprising empirical finding: it confirms the procedure
*realizes* "decidable ⇒ correct commit" on 527 real biting-slice queries and rules
out an off-by-one in the feasibility certification. The empirical surprise lives in
C2 (baselines mis-size) and C1 (91.1% underdetermined); this closes the loop by
showing the method's *positive* action is reliable, not just its refusals.

## 2. Scaled VoI acquisition — VoI-pick beats random with significance (DV5)

**Construction.** The `v2_acquisition` setup (mask the biting binding axis → procedure
ABSTAINs → "measure" the top-VoI axis vs a seeded random axis → re-decide; score
COMMIT-and-truly-feasible), now run over **BFCL + every per-benchmark RouterBench
slice** (discovered from the substrate, C7). Per-query `(VoI-pick-correct,
random-correct)` pairs are pooled into a **McNemar one-sided exact binomial** test —
pooled and H-confidence-only (the RouterBench flagship), mirroring `scale_v1`'s W5
discipline.

**Result (`outputs/p5/commit_voi.json`, `scale_v2`, seed=12345).**

| pool | n | VoI-pick cc | random cc | McNemar b/c | binom p (1-sided) | significant |
|---|---|---|---|---|---|---|
| ALL slices | **527** | **1.000** | 0.129 | **459 / 0** | < 1e-100 | **YES** |
| H-confidence only | **510** | **1.000** | 0.128 | **445 / 0** | < 1e-100 | **YES** |

**Reading.** The n=5 pilot (1.0 vs 0.2) is now an **n=527** result with the same
verdict and overwhelming significance. The VoI pick yields a truly-feasible commit
**every time** (527/527); a random axis succeeds only when the seeded draw happens to
land on the single blocking axis — `0.129 ≈ 1/8`, exactly the chance of drawing the
right axis out of 8. McNemar discordance is **459/0** (zero queries where random beat
VoI): the abstention is not just safe, it is **informative** — it names the field
that actually unblocks the decision. This cashes out the **VoI = Δ(R)** identity
(proven exact on the §8.2 gadget, `tests/test_procedure.py::test_voi_equals_delta_R`)
on the full battery: the highest-VoI axis is exactly the one whose measurement
converts an abstention into a correct commit.

## C3 status after this node

| sub-claim | before | after |
|---|---|---|
| Method's positive COMMIT is feasible + min-sufficient | never scored (coverage 0 on biting slices, W11 open) | **527 commits, 1.0 feasible, 1.0 min-sufficient** |
| VoI predicts the field worth measuring (DV5) | n=5 pilot (1.0 vs 0.2) | **n=527, 1.0 vs 0.129, McNemar 459/0, p≪0.05, H-only flagship** |

W11 (positive COMMIT never validated on a biting slice) and the V2-lift residual are
**closed**. The remaining Oral gate is the theory item **W1/Q2** (per-instance
binding), still deferred in [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).

## Tests

`tests/test_commit_voi.py` (4): selective commits feasible + min-sufficient on a
decidable slice; the dual abstains when the axis is masked; the VoI pick unblocks a
correct commit where a random non-blocking axis does not; the McNemar/binomial helper.
All 47 repo tests pass; the C7 interface-invariance gate is untouched.
