"""Generalized HELM-suite ingester — any crfm-helm-public GCS suite by prefix.

The HELM family publishes many leaderboard suites on the same GCS bucket
(`crfm-helm-public`) with an identical run layout to HELM Lite: medhelm/, capabilities/,
classic/, mmlu/, safety/, air-bench/, reasoning/, finance/, … This package reuses the
proven HELM-Lite client/parser/seeder shape, parameterized by the suite prefix, so adding
a structured source is `SuiteSpec(...)` + one `SOURCE_REGISTRY` line.

Axis mapping (honest, same convention as helm_lite):
  quality     → the per-scenario primary accuracy-family metric (M confidence)
  latency_p95 → inference_runtime mean (L confidence; note `mean-not-p95`, NOT a true p95)
  every other axis stays ⊥ (never imputed) — including governance/reviewer_burden, which
  no HELM suite reports (the C1 structural-blind-spot, now testable on MedHELM).
"""

from prudent_ai.substrate.helm_suite.seeder import SUITES, SuiteSpec, seed

__all__ = ["SUITES", "SuiteSpec", "seed"]
