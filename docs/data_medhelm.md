# Structured data — MedHELM ingest + the generalized HELM-suite seam

> Node: `zdnpkh-fulfill-structured-helm-suites` (parent `2o35sq`).
> Code: `src/prudent_ai/substrate/helm_suite/` (generalized ingester) +
> `SOURCE_REGISTRY` (medhelm). Real data from `crfm-helm-public` GCS.

## What was done

1. **Consolidated the plug-in seam** (registry + extraction scaffolding) from the
   `feat/data-source-registry` branch into the working lineage — adding a structured
   source is now one package + one `SourceSpec` line.
2. **Generalized HELM-suite ingester** (`substrate/helm_suite/`): the HELM family
   publishes many leaderboard suites on the *same* `crfm-helm-public` GCS bucket
   (medhelm, capabilities, classic, mmlu, safety, air-bench, reasoning, finance, …) with
   an identical run layout to HELM Lite. `helm_suite` reuses the proven HELM-Lite
   client/parser/seeder shape, parameterized by suite prefix — so each new suite is a
   `SuiteSpec` + a `SourceSpec` line.
3. **Ingested MedHELM** (arXiv 2505.23802, v2.0.0) — REAL data, no stubs.

## Result (substrate after ingest)

- **6 sources** (was 5); **+505 observations** (total 4052 → 4557).
- New archetype **`medical-qa`** with **9 model configs** (claude-3.5/3.7-sonnet,
  gemini-1.5-pro/2.0-flash, llama-3.3-70b, gpt-4o, deepseek-r1, … on Stanford Health
  Care deployments).
- **198 quality** observations + **307 latency_p95** observations.

## Two honest engineering decisions (verified, not papered over)

1. **Quality kept strictly on the [0,1] accuracy scale.** A spot-check caught that
   MedHELM's `{scenario}_accuracy` metrics are **heterogeneous in scale**: closed-form
   scenarios (e.g. `clear`) report `quasi_exact_match ∈ [0,1]`, but open-ended clinical
   generation (e.g. `aci_bench`, `mimic_bhc`) reports a **1–5 LLM-jury rating**. Mixing
   scales under one `quality` axis would corrupt the C1/C2 findings (the plan's
   "extraction noise" risk). The seeder therefore **stores quality only when the value is
   in [0,1]** and **skips off-scale jury ratings** (108 skipped, logged), recording the
   metric name in the obs context for audit. Global stored-quality range = **[0.00,
   1.00]**, consistent with every other source.
2. **Latency is `inference_runtime` mean at L confidence**, flagged `mean-not-p95` —
   the same honest convention HELM Lite uses (it is NOT a true p95).

## The §13 governance blind-spot test — confirmed

MedHELM is the most **governance-heavy** corpus available (clinical, HIPAA-adjacent,
Stanford Health Care deployments). The plan (§13) lists it precisely to test whether the
governance/reviewer_burden blind-spot is real or an artifact of general leaderboards.

**Finding:** even MedHELM reports **0 governance, 0 reviewer_burden, 0 memory_hw**
observations — only quality + latency. So the three hard-to-observe axes stay
**structurally ⊥ even in the domain where governance matters most**. This *strengthens*
C1: the blind spot is not because general benchmarks ignore governance, but because *no
leaderboard, even a clinical one, instruments it*. (Substrate axis coverage now: quality
885, latency_p95 1600, throughput 936, energy 697, cost 439 populated; memory_hw,
governance, reviewer_burden = ⊥.)

## How to add the next suite (the recipe this unlocks)

Append a `SuiteSpec` to `helm_suite.seeder.SUITES` (name + GCS prefix + version + tau +
citation) and a `SourceSpec` line with `extra_kwargs={"suite": "<name>"}` in
`SOURCE_REGISTRY`. Candidates already confirmed present on the bucket: `capabilities/`,
`classic/`, `mmlu/`, `reasoning/`, `finance/` (quality breadth); `safety/`, `air-bench/`
(safety/governance-adjacent); `efficient_helm/` (probe for latency/throughput). Each is
`PYTHONNOUSERSITE=1 uv run python -c "from prudent_ai.substrate.helm_suite import seed;
seed(suite='<name>')"` after registration.

## Tests

`tests/test_helm_suite.py` (4): quality prefers `{scenario}_accuracy`, falls back to the
accuracy-family, skips infra metrics, and the MedHELM suite is registered.
`tests/test_registry_extraction.py` updated to 6 sources. 73/73 pass; ruff clean.
