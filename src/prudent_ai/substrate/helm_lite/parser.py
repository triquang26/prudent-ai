"""Pure transformation logic — no I/O, no DB.

HelmLiteParser converts:
  raw GCS JSON  →  RunDirectory / StatEntry / ParsedRun
  list[ParsedRun]  →  aggregated per-scenario scores

Design:
  - All methods are stateless (could be static; kept as instance methods for testability).
  - Raises ValueError for fundamentally unparseable input; returns None for missing optional data.
"""

from __future__ import annotations

from .models import ModelRuns, ParsedRun, RunDirectory, StatEntry

# ---------------------------------------------------------------------------
# Scenario → primary quality metric
# ---------------------------------------------------------------------------

# The metric name used for the leaderboard score per scenario type.
# Where multiple subsets exist (math × 7, legalbench × 5, mmlu × 5, wmt_14 × 5),
# this is the per-subset metric; the parser aggregates across subsets automatically.
SCENARIO_PRIMARY_METRIC: dict[str, str] = {
    "gsm": "exact_match_indicator",
    "math": "math_equiv_chain_of_thought",
    "commonsense": "quasi_exact_match",
    "mmlu": "quasi_exact_match",
    "med_qa": "quasi_exact_match",
    "legalbench": "quasi_exact_match",
    "narrative_qa": "f1_score",
    "natural_qa": "quasi_exact_match",
    "wmt_14": "bleu_4",
}

# Scenarios that have multiple subset runs per model (need aggregation)
MULTI_SUBSET_SCENARIOS = {"math", "mmlu", "legalbench", "wmt_14", "natural_qa"}

# Infrastructure metric names in stats.json that are not quality scores
INFRA_METRICS = frozenset({
    "num_instances",
    "num_prompt_tokens",
    "num_completion_tokens",
    "num_output_tokens",
    "num_requests",
    "num_train_instances",
    "num_prompt_tokens_budget",
    "finish_reason_length",
    "finish_reason_stop",
    "finish_reason_endoftext",
    "finish_reason_unknown",
    "training_co2_cost",
    "training_energy_cost",
    "inference_runtime",
})


class HelmLiteParser:
    """Parse HELM Lite GCS data into domain objects."""

    # ------------------------------------------------------------------
    # Run directory parsing
    # ------------------------------------------------------------------

    def parse_run_directory(self, version: str, run_name: str) -> RunDirectory:
        """Parse a GCS run name into a structured RunDirectory.

        Run name format: ``scenario_type:key=val[,key=val,...],model=provider_model``

        Examples:
          ``gsm:model=openai_gpt-4-0613``
          ``math:subject=algebra,model=openai_gpt-4-0613``
          ``legalbench:task=abercrombie,model=anthropic_claude-2``
          ``wmt_14:language_pair=de-en,model=meta_llama-2-70b``

        The first token before ":" is the scenario type; everything after is
        comma-separated key=value pairs including "model=...".
        """
        if ":" not in run_name:
            raise ValueError(f"Cannot parse run_name (no colon): {run_name!r}")

        scenario_type, params_str = run_name.split(":", 1)
        params = dict(kv.split("=", 1) for kv in params_str.split(",") if "=" in kv)

        model_id = params.pop("model", None)
        if not model_id:
            raise ValueError(f"Cannot find model= in run_name: {run_name!r}")

        return RunDirectory(
            version=version,
            run_name=run_name,
            scenario_type=scenario_type,
            scenario_params=params,
            model_id=model_id,
        )

    # ------------------------------------------------------------------
    # Stats parsing
    # ------------------------------------------------------------------

    def parse_stats(self, raw: list[dict]) -> list[StatEntry]:
        """Convert raw stats.json array into StatEntry objects.

        Keeps only entries with split=="test" and no perturbation (clean eval).
        Skips entries with count==0 (metrics not measured for this run).
        """
        entries: list[StatEntry] = []
        for item in raw:
            name_block = item.get("name", {})
            split = name_block.get("split", "")
            perturbation = name_block.get("perturbation")
            count = int(item.get("count", 0))

            if split != "test":
                continue
            if perturbation:
                continue
            if count == 0:
                continue

            entries.append(
                StatEntry(
                    name=name_block.get("name", ""),
                    split=split,
                    perturbation=None,
                    count=count,
                    mean=float(item.get("mean", 0.0)),
                    min=float(item.get("min", 0.0)),
                    max=float(item.get("max", 0.0)),
                    stddev=float(item.get("stddev", 0.0)),
                )
            )
        return entries

    # ------------------------------------------------------------------
    # Metric extraction
    # ------------------------------------------------------------------

    def extract_quality(
        self, scenario_type: str, stats: list[StatEntry]
    ) -> tuple[float, str] | tuple[None, None]:
        """Return (score, metric_name) for the primary quality metric, or (None, None)."""
        primary = SCENARIO_PRIMARY_METRIC.get(scenario_type)
        if not primary:
            return None, None

        # Try primary metric first, then fallbacks
        fallbacks = ["exact_match", "quasi_exact_match", "f1_score", "bleu_4", "rouge_l"]
        candidates = [primary] + [f for f in fallbacks if f != primary]

        by_name = {s.name: s for s in stats}
        for metric in candidates:
            if metric in by_name:
                return by_name[metric].mean, metric

        return None, None

    def extract_latency(self, stats: list[StatEntry]) -> float | None:
        """Return mean inference latency in seconds/instance, or None."""
        by_name = {s.name: s for s in stats}
        entry = by_name.get("inference_runtime")
        if entry and entry.mean > 0:
            return entry.mean
        return None

    def extract_token_counts(
        self, stats: list[StatEntry]
    ) -> tuple[float | None, float | None]:
        """Return (num_prompt_tokens, num_completion_tokens) per instance, or (None, None)."""
        by_name = {s.name: s for s in stats}
        prompt = by_name.get("num_prompt_tokens")
        completion = by_name.get("num_completion_tokens")
        return (
            prompt.mean if prompt else None,
            completion.mean if completion else None,
        )

    # ------------------------------------------------------------------
    # Full run parsing
    # ------------------------------------------------------------------

    def parse_run(self, version: str, run_name: str, raw_stats: list[dict]) -> ParsedRun:
        """Parse a run directory name + raw stats.json into a ParsedRun."""
        directory = self.parse_run_directory(version, run_name)
        stats = self.parse_stats(raw_stats)

        quality, metric_name = self.extract_quality(directory.scenario_type, stats)
        latency = self.extract_latency(stats)
        prompt_toks, completion_toks = self.extract_token_counts(stats)

        return ParsedRun(
            directory=directory,
            stats=stats,
            quality_score=quality,
            quality_metric_name=metric_name,
            latency_mean_s=latency,
            num_prompt_tokens=prompt_toks,
            num_completion_tokens=completion_toks,
        )

    # ------------------------------------------------------------------
    # Grouping and aggregation
    # ------------------------------------------------------------------

    def group_by_model(self, runs: list[ParsedRun]) -> dict[str, ModelRuns]:
        """Group ParsedRun list by model_id."""
        groups: dict[str, ModelRuns] = {}
        for run in runs:
            mid = run.directory.model_id
            if mid not in groups:
                groups[mid] = ModelRuns(model_id=mid)
            groups[mid].add(run)
        return groups

    def aggregate_quality(self, model_runs: ModelRuns, scenario_type: str) -> float | None:
        """Mean quality score across all subsets for a multi-subset scenario."""
        runs = model_runs.runs_by_scenario.get(scenario_type, [])
        scores = [r.quality_score for r in runs if r.quality_score is not None]
        if not scores:
            return None
        return sum(scores) / len(scores)

    def aggregate_latency(self, model_runs: ModelRuns, scenario_type: str) -> float | None:
        """Mean latency across all subsets for a scenario type."""
        runs = model_runs.runs_by_scenario.get(scenario_type, [])
        latencies = [r.latency_mean_s for r in runs if r.latency_mean_s is not None]
        if not latencies:
            return None
        return sum(latencies) / len(latencies)
