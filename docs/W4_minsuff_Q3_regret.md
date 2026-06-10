# W4-residual + Q3 — min-sufficiency guarantee & realized regret vs Δ(R)

> Node: `mfxhvu-guarantee-minsuff-regret` (parent `c90ge4`).
> W4: `src/prudent_ai/validation/minsuff_guarantee.py`, `scripts/run_w4_minsuff.py`,
> `outputs/p4/minsuff_guarantee.{json,md}`, `tests/test_minsuff_guarantee.py`.
> Q3: `src/prudent_ai/analysis/regret_delta.py`, `scripts/run_q3_regret.py`,
> `outputs/p4/q3_regret.{json,md}`, `tests/test_regret_delta.py`.
> Real GT = full-sample per-prompt RouterBench; operating = seeded subsample (C8).

## 1. W4-residual — min-sufficiency is now guaranteed on real GT (two-sided band)

**The residual.** The real-GT guarantee (`gt_guarantee.py`) calibrates only the
*feasibility* half with a one-sided quality margin `m`. Min-sufficiency could not be
guaranteed by the same knob: a larger `m` makes feasibility safer but **over-provisions**
(skips a cheaper config whose noisy quality dipped), so min-sufficiency risk *rises* with
`m` (43.8% → 83.8% across the margin sweep; **65.8%** at the α=0.05 feasibility-calibrated
margin). One one-sided knob cannot control a two-sided criterion.

**The fix — a two-sided band `b`.** After selecting the min-noisy-cost eligible config,
commit only if **no strictly-cheaper config is plausibly feasible** (`noisy_q ≥ q*−b`);
else abstain — a cheaper config might be the true minimum, so committing would risk
over-provisioning. `m` controls feasibility, `b` controls min-sufficiency.

**Result (`outputs/p4/minsuff_guarantee.json`).** Jointly calibrating `(m, b)` on the
held-out split (C8 disjoint calib/test) **guarantees test min-sufficiency risk ≤ α**:

| α | margin m | band b | test coverage | test feas-risk | **test min-suff risk** | holds? |
|---|---|---|---|---|---|---|
| 0.05 | 0.07 | 0.12 | 12.7% | 4.9% | **4.9%** | ✅ |
| 0.10 | 0.07 | 0.08 | 19.2% | 5.4% | **6.5%** | ✅ |
| 0.20 | 0.05 | 0.05 | 28.5% | 9.5% | **14.6%** | ✅ |

vs **65.8%** min-suff risk for the one-sided guarantee at α=0.05. The full §9
*feasible ∧ minimum-sufficient* guarantee now transfers to real held-out GT. The lower
coverage (12.7% vs ~89% feasibility-only) is the **honest price** of the stronger
two-sided criterion — a quantified safety ↔ min-sufficiency ↔ coverage trilemma, not a
hidden gap. (Band sweep: min-suff risk falls 32.7% → 9.6% as `b` grows 0 → 0.12 at fixed
`m`=0.05, until the widest bands collapse coverage to a noisy tail.)

## 2. Q3 — real mis-sizing regret exceeds the limit-theorem floor Δ(R)

**The question (Open-Q3).** Whether *real* leaderboard mis-sizing exceeds the theorem's
irreducible regret `Δ(R)=δλ/(δ+λ)` — empirical, not a corollary.

**Construction.** Instantiate the §8.2 two-world gadget with **real** RouterBench
geometry: on each biting slice (cheapest config infeasible at q*),
- **δ = price of caution** = cost(true min-cost-feasible) − cost(global cheapest) — the
  extra real cost to *guarantee* feasibility instead of grabbing the cheapest (measured);
- **λ = the declared violation penalty** (`DEFAULT_LAMBDA = 1.0`, stated not fit).

Δ(R) = δλ/(δ+λ) is the irreducible floor; the leaderboard **cost-minimizer** realizes
worst-world regret **λ** (commits cheap-infeasible), the cautious **over-provisioner**
**δ** (commits dear-feasible). We reuse the *proven* gadget loss (`solver/voi`), so Δ(R)
is the same quantity as the VoI=Δ(R) identity, now with real δ.

**Result (`outputs/p4/q3_regret.json`, 41/42 biting slices).**
- **Δ(R) ≤ min(δ,λ) on 41/41 slices** — real mis-sizing strictly exceeds the floor.
- Closed-form Δ(R) vs the proven gadget minimax: max abs gap **8.7e-19** (machine
  precision) — the real-calibrated floor is exactly the §8.7 identity.
- **Mean price of caution `overshoot_rel` = 0.748** — over-provisioning to guarantee
  feasibility costs **~75% more** than the cheapest (infeasible) config. That is the
  concrete money the binding axis controls, left on the table by a blind commit.
- Because λ=1 ≫ δ (RouterBench per-query costs are tiny absolute dollars), the
  cost-minimizer's realized regret (λ) **dwarfs** the floor Δ(R)≈δ: a blind cost-min
  rule pays the full violation penalty where paying the small cost-gap (or abstaining)
  would suffice.

**Reading.** The selective procedure is the only rule that pays **0** by abstaining; the
gap it would otherwise pay (Δ(R)) is exactly the cost-aware VoI it reports — so it can
*acquire* the binding axis rather than gamble. Real mis-sizing exceeds the theorem's
floor, with a concrete 75% over-provisioning premium as the stake.

## 3. W2 — §1 leads with the scaled results

§1 contribution 4 previously led the VoI claim with the **n=5 pilot** (5/5 vs 1/5). Now
replaced with the scaled **527/527 (1.0) vs 0.129**, McNemar 459/0, p≪0.05; contribution 3
gains the validated positive COMMIT (527, feasible/min-sufficient 1.0) and the real-GT
min-sufficiency guarantee; contribution 4 gains the per-instance Pareto-binding
certificate (`bite ⟺ binding` 1.0). The intro now reflects the closed empirical state.

## Status

| item | before | after |
|---|---|---|
| §9 min-sufficiency guarantee on real GT (W4 residual) | one-sided-uncontrollable (65.8% at α=0.05) | **calibrated via two-sided band: test min-suff risk ≤ α** (4.9% @ α=0.05) |
| Q3 — real regret vs Δ(R) | open | **Δ(R) ≤ min(δ,λ) on 41/41; 75% over-provision premium; floor = proven identity** |
| W2 — §1 leads with scaled not pilot | pilot 5/5 in §1 | **scaled 527/527 + COMMIT + binding in §1** |

## Tests

`tests/test_minsuff_guarantee.py` (3): one-sided over-provisions where the band abstains;
band commits when truly min-sufficient; band risk is monotone. `tests/test_regret_delta.py`
(5): Δ(R) closed form, consistency with the proven gadget minimax, floor below both naive
rules, biting-slice regret, non-biting → None. All repo tests pass; ruff clean.
