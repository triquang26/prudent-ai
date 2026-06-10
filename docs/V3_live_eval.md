# V3 — Prospective LIVE evaluation on held-out future traffic

> Node: `ksmbut-v3-live-prospective-eval` (parent `mfxhvu`).
> Code: `src/prudent_ai/validation/live_eval.py`. Runner: `scripts/run_v3_live.py`.
> Outputs: `outputs/p5/v3_live.{json,md}`. Tests: `tests/test_live_eval.py`.

## Why — a real prospective test, not masking

P5 V1 validates by *masking* an axis on a fixed slice; the guarantee (W4) calibrates on
seeded subsamples *of the same population*. V3 asks the harder, deployment question: a
config is committed from the evidence available **now** — does it hold up on the traffic
that arrives **next**? With no model-serving stack, the honest realization is a **disjoint
prompt-split** of real RouterBench per-prompt data:

- **MEASURE** = the first `K=64` prompts (seeded shuffle): the noisy evidence at decision
  time. The procedure decides here.
- **LIVE** = the remaining, **disjoint** prompts: subsequent traffic the committed config
  actually serves. The realized outcome is scored here.

The decision is genuinely out-of-sample — the procedure never sees the LIVE prompts
(C8, no leakage). We compare, on the **same** live traffic:

- **blind cost-min (margin 0)** — leaderboard practice: commit the cheapest config that
  clears `q*` on the noisy sample, no safety buffer;
- **selective(m)** — commit the cheapest config whose MEASURE quality clears `q*` by a
  safety margin `m`, else ABSTAIN.

## Result (`outputs/p5/v3_live.json`; 6 benchmarks × 4 q* × 40 splits = 960 queries)

| rule | coverage | **live-feasibility** | live-violation | mean live regret (rel) |
|---|---|---|---|---|
| blind cost-min (m=0) | 99.4% | 63.4% | **36.6%** | 1.567 |
| selective (m=0.05) | 93.0% | 85.6% | **14.4%** | 3.786 |
| selective (m=0.10) | 81.4% | 96.2% | **3.8%** | 6.355 |

- **The blind cost-minimizer over-fits the measurement sample.** It commits on 99.4% of
  queries, but **36.6% of those commits FAIL on live traffic** — the committed config
  looked feasible on the K-prompt sample yet truly violates `q*` on the disjoint future
  prompts. Leaderboard right-sizing does not generalize prospectively.
- **The safety margin transfers to genuinely future traffic.** Live-violation falls
  **monotonically** — 36.6% → 14.4% → 3.8% — as the margin grows, because the procedure
  *abstains* on the queries it cannot yet certify. This is a prospective coverage–risk
  tradeoff on traffic the decision **never saw**: the operator dials live-violation down
  to 3.8% by trading coverage (99.4% → 81.4%).
- **The price is over-provisioning.** Mean live cost-regret rises with the margin
  (1.6 → 6.4× the live-optimal) — the same safety↔cost tension the W4 two-sided band
  quantifies, here on future traffic. Reported honestly, not hidden.

## What this is — and is not

**Is:** a genuine **out-of-sample, prospective** evaluation on **real** per-prompt
RouterBench traffic — the committed config is scored on prompts disjoint from those it
was chosen on. It validates the core deployment claim: the selective procedure's
abstention is not just safe in-sample, it **generalizes** — its commits hold on future
traffic far more often than blind practice (63.4% → 96.2% live-feasibility).

**Is not:** a live model-serving run (no inference stack on this host). The prompt-split
is the achievable surrogate for V3; a true vLLM-energy + human-governance live study
remains the resource-gated stretch (`docs/OPEN_QUESTIONS.md`).

## Status

| item | before | after |
|---|---|---|
| V3 live / prospective evaluation | stretch, not started | **prospective prompt-split done**: blind 36.6% live-violation vs selective 3.8% @ m=0.10 |

## Tests

`tests/test_live_eval.py` (4): `_commit` cheapest-eligible + margin abstention,
`_live_optimum_cost`, and an end-to-end injected benchmark where a config that looks
feasible on MEASURE fails on LIVE so the blind rule violates while the margin does not.
All repo tests pass; ruff clean.
