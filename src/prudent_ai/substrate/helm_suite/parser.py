"""Generalized HELM-suite parser — reuses helm_lite parsing, generalizes quality pick.

HELM Lite uses a curated `scenario → primary metric` map. Other suites (MedHELM, …) have
their own scenarios, but follow the HELM convention of a per-scenario primary metric named
`{scenario}_accuracy` (e.g. `aci_bench_accuracy`), with the usual accuracy-family metrics
as fallbacks. We override only `extract_quality`; run-name/stats parsing, latency, and
aggregation are inherited unchanged (suite-agnostic).
"""

from __future__ import annotations

from prudent_ai.substrate.helm_lite.models import StatEntry
from prudent_ai.substrate.helm_lite.parser import INFRA_METRICS, HelmLiteParser

# Accuracy-family fallbacks, tried in order after `{scenario}_accuracy`. Each is a real
# HELM metric name; we never invent a value, only select among reported metrics.
QUALITY_FALLBACKS: tuple[str, ...] = (
    "quasi_exact_match",
    "exact_match",
    "exact_match_indicator",
    "classification_macro_f1",
    "f1_score",
    "accuracy",
    "math_equiv_chain_of_thought",
    "BERTScore-F",
    "rouge_l",
    "bleu_4",
)


class HelmSuiteParser(HelmLiteParser):
    """HELM parser whose quality metric is `{scenario}_accuracy` then accuracy-family."""

    def extract_quality(
        self, scenario_type: str, stats: list[StatEntry]
    ) -> tuple[float, str] | tuple[None, None]:
        by_name = {s.name: s for s in stats}
        primary = f"{scenario_type}_accuracy"
        for metric in (primary, *QUALITY_FALLBACKS):
            if metric in INFRA_METRICS:
                continue
            entry = by_name.get(metric)
            if entry is not None:
                return entry.mean, metric
        return None, None
