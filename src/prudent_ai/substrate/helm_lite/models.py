"""Pure dataclasses — no I/O, no side effects.

Represents the HELM Lite domain objects at three levels:
  raw     → RunDirectory, StatEntry          (parsed from GCS JSON)
  derived → ParsedRun, ModelRuns             (after metric extraction)
  report  → SeedReport                       (after DB insertion)
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Raw layer — parsed directly from GCS API responses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunDirectory:
    """One run directory in GCS, e.g. gsm:model=openai_gpt-4-0613."""

    version: str
    run_name: str                      # full GCS suffix, e.g. "gsm:model=openai_gpt-4-0613"
    scenario_type: str                 # e.g. "gsm", "mmlu", "math", "wmt_14"
    scenario_params: dict[str, str]    # e.g. {"subject": "algebra"} for math subsets
    model_id: str                      # e.g. "openai_gpt-4-0613" (GCS encoding, _ not /)

    @property
    def canonical_model_id(self) -> str:
        """Convert GCS encoding (openai_gpt-4) → canonical (openai/gpt-4)."""
        # Only the first underscore is the provider separator.
        idx = self.model_id.index("_")
        return self.model_id[:idx] + "/" + self.model_id[idx + 1 :]

    @property
    def subset_key(self) -> str | None:
        """Return the subset identifier for multi-subset scenarios, else None."""
        # math subsets: {"subject": "algebra"}
        # legalbench: {"task": "abercrombie"}
        # mmlu: {"subject": "abstract_algebra"}
        # wmt_14: {"language_pair": "cs-en"}
        # natural_qa: {"mode": "closedbook"}
        for k in ("subject", "task", "language_pair", "mode"):
            if k in self.scenario_params:
                return self.scenario_params[k]
        return None


@dataclass(frozen=True)
class StatEntry:
    """One entry from stats.json (aggregated metric over a run)."""

    name: str               # e.g. "exact_match", "inference_runtime"
    split: str              # "test" | "train" | "valid"
    perturbation: str | None  # None → clean eval; "robustness" | "fairness" → skip
    count: int
    mean: float
    min: float
    max: float
    stddev: float


# ---------------------------------------------------------------------------
# Derived layer — after metric extraction
# ---------------------------------------------------------------------------


@dataclass
class ParsedRun:
    """A single run with its primary scores extracted."""

    directory: RunDirectory
    stats: list[StatEntry]

    # Derived by HelmLiteParser
    quality_score: float | None = None       # primary metric for this scenario type
    quality_metric_name: str | None = None   # which stat was used
    latency_mean_s: float | None = None      # inference_runtime mean (seconds/instance)
    num_prompt_tokens: float | None = None   # avg prompt tokens per instance
    num_completion_tokens: float | None = None


@dataclass
class ModelRuns:
    """All runs for a single model_id, grouped by scenario type."""

    model_id: str                                      # GCS encoding
    runs_by_scenario: dict[str, list[ParsedRun]] = field(default_factory=dict)

    def add(self, run: ParsedRun) -> None:
        s = run.directory.scenario_type
        self.runs_by_scenario.setdefault(s, []).append(run)

    @property
    def all_runs(self) -> list[ParsedRun]:
        return [r for runs in self.runs_by_scenario.values() for r in runs]


# ---------------------------------------------------------------------------
# Seed report
# ---------------------------------------------------------------------------


@dataclass
class SeedReport:
    """Summary of what was inserted into the APT substrate."""

    version: str
    models_seeded: int = 0
    runs_fetched: int = 0
    runs_skipped: int = 0
    observations_inserted: int = 0
    axes_coverage: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def print(self) -> None:
        print(f"\n=== HELM Lite seed report (version {self.version}) ===")
        print(f"Models seeded      : {self.models_seeded}")
        print(f"Runs fetched       : {self.runs_fetched}")
        print(f"Runs skipped       : {self.runs_skipped}")
        print(f"Observations total : {self.observations_inserted}")
        print("\nAxis coverage (observations inserted):")
        axes = [
            "quality", "latency_p95", "throughput", "cost",
            "energy", "memory_hw", "governance", "reviewer_burden",
        ]
        for ax in axes:
            cnt = self.axes_coverage.get(ax, 0)
            flag = "YES" if cnt > 0 else "⊥"
            print(f"  {ax:<22} {cnt:>5}   {flag}")
        if self.errors:
            print(f"\nErrors ({len(self.errors)}):")
            for e in self.errors[:10]:
                print(f"  {e}")
