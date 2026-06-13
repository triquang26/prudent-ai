# PHASE0_RESULTS.md — transfer-signal pilot (the Tier-1 GO/NO-GO gate)

**Verdict: NO-GO on Tier-1 (calibrated transfer as a guaranteed recovery method).**
Do not build Phase 1. The fallback (Tier-3 live loop + Phase-3 reframing) stands and is
unaffected. **The negative result is itself evidence FOR the paper's thesis** (see below).

Artifact: `outputs/phase0/transfer_signal.json` · Script: `experiments/phase0_transfer_signal.py`
(seeded, deterministic). RouterBench quality matrix: 11 models × 30 benchmarks = 330 cells,
quality ∈ [0,1].

## What was measured

Leave-one-benchmark-out (LOBO) two-way **additive** predictor (column-effect = benchmark
difficulty from other models; row-residual = model skill from its other benchmarks; no
leakage of the target cell). Then **split-conformal** intervals (calib/eval 50/50, seed
2024, the gt_guarantee split discipline). `recovery_rate@α` = over eval cells × grounded
query thresholds (p10..p90 of each benchmark's quality), the fraction whose calibrated
interval is **decisive** (does not straddle the threshold → the decision resolves with no
new measurement).

## Results

**Point prediction is good:** R² = **0.810**, MAE = **0.096** (≈10 accuracy points).
Quality *is* predictable cross-benchmark on average.

**But the guaranteed intervals are too wide to recover decisions:**

| α | variant | interval width | eval coverage | **recovery_rate** | decisive feas-error |
|---|---|---|---|---|---|
| 0.05 | global | 0.611 | 0.970 (t .95) | **2.5%** | 2.7% |
| 0.05 | normalized | 0.784 (mean) | 0.958 | **7.3%** | 22.2% |
| 0.10 | global | 0.451 | 0.927 | 10.4% | 7.1% |
| 0.10 | normalized | 0.501 (mean) | 0.897 | 16.5% | 20.4% |
| 0.20 | global | 0.304 | 0.849 | 28.1% | 11.2% |
| 0.20 | normalized | 0.359 (mean) | 0.824 | 27.5% | 17.6% |

- **recovery_rate@0.05 = 2.5% (global) / 7.3% (normalized)** — both ≪ the ~15% NO-GO line.
- Conformal coverage holds (≥ 1−α), so the method is *correct* — just not *useful*: the
  honest interval that guarantees ≤5% feasibility error has width 0.61 on a [0,1] axis and
  straddles 97.5% of grounded thresholds.
- The **normalized (heteroskedastic) diagnostic does not rescue it**: it buys recovery by
  tightening intervals on low-variance benchmarks, but its decisive commits are wrong
  **22%** of the time — it breaks the guarantee rather than honoring it.
- The only place recovery is non-trivial (α=0.20, ~28%) has 11–22% feasibility error — i.e.
  no operating point delivers **non-trivial recovery AND ≤5% risk**.

**Why:** residuals are heavy-tailed. Most benchmarks transfer well (small residual), but a
cluster (the Chinese-language riddle/poetry benchmarks) is near-unpredictable, and a
distribution-free interval that must cover 95% of residuals is dominated by that tail.

**Structural-axis refusal: confirmed.** The predictor emits no interval for
`{governance, reviewer_burden, energy, throughput, memory_hw}` (no cross-context signal),
and does emit one for `quality`. The curable/structural boundary is clean.

## Interpretation — the NO-GO confirms the thesis

This is not a dead end for the paper; it is a sharper statement of its central claim. The
point imputer (B3) commits blind on a single number and is wrong **30.6%** of the time. An
**honest** belief that respects the cross-benchmark uncertainty is an interval too wide to
commit safely → the procedure must **abstain and measure**. "Evidence on the wrong
granularity cannot be substituted for measuring the blocking cell" is exactly what the
co-location gap predicts — now demonstrated quantitatively for the strongest principled
imputer-with-a-guarantee. Calibrated transfer does not *recover* the co-location decisions;
it *certifies that they genuinely require measurement*, at a controlled risk level.

## Phase 0b — scoped / stratified follow-up (transparent)

Artifact: `outputs/phase0/transfer_stratified.json` · Script: `experiments/phase0b_transfer_stratified.py`.
Asked transparently whether the full-set NO-GO is a heavy-tail artifact.

**Predictor check:** a kNN-in-benchmark-space predictor is **worse** (R²=0.26 vs additive
0.81); full-set recovery 8.5% at 55.6% feasibility error. The additive model was already
the right choice — the limiter is not the predictor.

**Stratified recovery@0.05** (keep the K lowest-LOBO-MAE benchmarks; Mondrian split-conformal
*within* the kept stratum so the ≤α guarantee still holds):

| keep | pop share | interval width | eval cov | **recovery** | feas-error |
|---|---|---|---|---|---|
| 30 (all) | 1.00 | 0.519 | 0.933 | 7.6% | 5.3% |
| 25 | 0.83 | 0.418 | 0.957 | 11.6% | 4.2% |
| **20** | **0.67** | 0.303 | 0.900 | **21.0%** | 4.8% |
| 18 | 0.60 | 0.312 | 0.950 | 17.1% | 2.0% |
| 15 | 0.50 | 0.304 | 0.964 | 16.9% | 0.8% |
| 12 | 0.40 | 0.310 | 1.000 | 19.9% | 0.0% |

(The per-α full table value at keep=30 differs slightly from §Results because 0b uses a
single Mondrian split; both are NO-GO on the full set.)

**Read of 0b:**
- On the **20 best-transferring benchmarks (67% of the population)**, recovery@0.05 = **21.0%**
  at **4.8%** feasibility error — the guarantee holds, and this is in the **PARTIAL** band
  (15–40%). Recovery **saturates** there (keeping fewer benchmarks does not raise it): the
  width floor ≈0.30 even on easy benchmarks is set by genuine across-model quality spread,
  not by predictor error.
- **Honesty check — the hard benchmarks are NOT just OOD Chinese tasks.** The 8 hardest by
  transfer MAE are: `test-match (.235)`, `accounting_audit (.192)`, `mmlu (.176)`,
  `chinese_homonym (.169)`, `chinese_ancient_masterpieces_dynasty (.164)`,
  `chinese_zodiac (.154)`, `hellaswag (.122)`, `arc-challenge (.114)`. **MMLU, ARC-challenge,
  HellaSwag** — core English reasoning benchmarks — are among the least transferable. So the
  recoverable stratum is a real but **not cleanly characterizable** 2/3 subset; we cannot
  claim "drop the weird tasks and it works."

## Gate decision (per spec)

Full set: `recovery@0.05 = 2.5%` → NO-GO. Scoped to the transferable 2/3 of benchmarks:
`recovery@0.05 = 21.0%` at ≤5% risk → **PARTIAL**. Per spec, PARTIAL → *may* proceed to a
Phase 1 framed as **partial recovery with a lowered headline**, honestly scoped to the
transferable stratum; OR take the fallback (Tier-3 + reframing). **Even in the best case,
~79% of co-location decisions on transferable tasks still require measurement**, so either
path keeps the paper's "measurement is usually necessary" thesis intact. Phase 0 stops here
for human sign-off on which path.
