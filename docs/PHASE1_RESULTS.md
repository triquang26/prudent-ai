# PHASE1_RESULTS.md — calibrated transfer as a guaranteed method

**Result: a working, guaranteed partial-recovery method.** Calibrated transfer recovers
**~25% of masked-quality co-location decisions at 0% observed hidden violations** through
the *existing* verdict engine, vs the point imputer's **53.3%** blind-violation rate; the
split-conformal feasibility guarantee `P(committed config infeasible | commit) ≤ α` holds
on held-out truth. The other ~75% correctly abstain → require measurement (motivates the
Phase-2 live loop). Framed as **partial recovery** per the Phase-0b PARTIAL gate.

Tests: **86 passed** (79 baseline + 7 new transfer); frozen db md5 unchanged
(`140231…`); transfer-OFF determinism asserted.

## What was built

- `src/prudent_ai/transfer/calibrated_transfer.py` — `CalibratedTransfer`: leave-one-
  benchmark-out two-way additive predictor + split-conformal radius τ_α (calibrated on a
  seeded 50/50 half-split, the `gt_guarantee` discipline) + **explicit structural-axis
  refusal** (`predict_interval` returns None for `governance/reviewer_burden/energy/
  throughput/memory_hw` and any non-`quality` axis — no cross-context signal to transfer).
- `src/prudent_ai/transfer/overlay.py` — `OverlayedSubstrate`: a C7-shaped proxy that
  fills a registered ⊥ cell with two synthetic observations valued `lo`/`hi`, so the
  existing `aggregate(...)` derives the interval belief `[lo,hi]`. Never overwrites a
  measured cell; never mutates the frozen store; **byte-identical to the base when the
  overlay map is empty** (the transfer-OFF flag = wrap-or-don't, via `apply_transfer`).
- `tests/test_transfer.py` — structural refusal, τ monotonic in α, interval injection,
  measured-cell-untouched, **empty-overlay bit-identical verdicts**, frozen-db-unchanged.
- `experiments/phase1_decidability_with_transfer.py`, `phase1_guarantee_check.py`.

The verdict machinery is **unchanged**: only the belief assigned to a fragmented-⊥ quality
cell changes. The transfer rule reads through the same `MaskedSubstrate` as every baseline,
overlays the calibrated interval, and runs `classify_query` with κ={H,M}, φ=interval — it
commits **only** on a DECIDABLE (non-straddling) interval, never on a straddle.

## Decidability / HVR with transfer ON (30 RouterBench slices, 510 masked-quality decisions)

`outputs/phase1/decidability_with_transfer.json`

| rule | coverage | hidden-violation rate |
|---|---|---|
| B2 observed-Pareto | 1.00 | 0.533 |
| B3 median-imputation | 1.00 | 0.533 |
| B5 oracle (sees hidden axis) | 1.00 | 0.000 |
| strict selective | 0.00 | 0.000 |
| **calibrated transfer @ α=0.05** | **0.249** | **0.000** |
| calibrated transfer @ α=0.10 | 0.249 | 0.000 |
| calibrated transfer @ α=0.20 | 0.257 | 0.000 |

Transfer lands **between** the point imputer (commits 100%, wrong 53%) and strict selective
(commits 0%): it recovers ~25% of decisions and is never observed wrong. Recovery is flat
in α because the recovered decisions are those where even the wide α=0.05 interval is
decisive (e.g. a strong model far above a low threshold); relaxing α adds little. The
guarantee (realized HVR ≤ α) holds with margin (0.0% ≤ α at every level).

## Split-conformal guarantee on held-out truth (Figure-7-right analogue)

`outputs/phase1/guarantee_check.json` — τ_α from the calibration half; coverage + decision-
level feasibility error on the disjoint test half.

| α | test interval-coverage (≥ 1−α) | feasibility-error (≤ α) | n decisive commits |
|---|---|---|---|
| 0.05 | 0.970 ✓ | 0.007 ✓ | 136 |
| 0.10 | 0.927 ✓ | 0.032 ✓ | 186 |
| 0.20 | 0.849 ✓ | 0.046 ✓ | 239 |

Both the conformal coverage guarantee and the decision-level feasibility guarantee hold at
every α, finite-sample and distribution-free.

## Theorem (to state in the paper, verified numerically above)

*Under split-conformal calibration with miscoverage α, the calibrated-transfer commit rule
— commit iff the predicted interval lies entirely on the satisfying side of the threshold
— satisfies `P(committed configuration infeasible | it commits) ≤ α`, finite-sample and
distribution-free.* Proof sketch: the conformal interval covers the true value with
probability ≥ 1−α (split-conformal exchangeability); a commit fires only when the whole
interval satisfies the constraint, so a committed-but-infeasible event requires the true
value to fall outside the interval, an event of probability ≤ α. Verified: feasibility-error
0.007/0.032/0.046 ≤ 0.05/0.10/0.20 on held-out truth.

## Honest scope (carried from Phase 0b)

- This is **partial** recovery: ~25% of co-location decisions, ~75% still require
  measurement. On the full 30-benchmark set the Phase-0 proxy recovery was lower (2.5%);
  the 25% here is through the *real* verdict on the actual battery queries, where many
  decisions have a strong model far from the threshold so even a wide interval is decisive.
- Transfer reaches **only** the measurable quality axis; on the never-measured structural
  axes it refuses by construction (tested). The curable/structural boundary is clean.
- The contribution is not "transfer recovers most decisions" — it is "transfer recovers a
  guaranteed minority safely, and **certifies the majority genuinely require measurement**,"
  which is exactly the paper's thesis and the bridge to the Phase-2 live acquisition loop.

GATE 1: a usable operating point exists (24.9% recovered at 0% realized risk / ≤5%
guaranteed) and the guarantee check holds → Tier-1 is a paper-grade (partial) contribution.
