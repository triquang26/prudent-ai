"""MLPerf Inference domain objects — no I/O, no side effects.

MLPerf Inference v5.0 provides:
  throughput  → Performance_Result (Tokens/s or Samples/s)
  latency_p95 → 95th-percentile end-to-end latency (ns → ms)

Source: https://mlcommons.org/benchmarks/inference-datacenter/
        mlcommons/inference_results_v5.0 summary_results.json
"""

from __future__ import annotations

from dataclasses import dataclass, field

# LLM models in MLPerf Inference (server + datacenter + closed subset)
LLM_MODELS: frozenset[str] = frozenset({
    "gptj-99", "gptj-99.9",
    "llama2-70b-99", "llama2-70b-99.9",
    "llama2-70b-interactive-99", "llama2-70b-interactive-99.9",
    "llama3.1-405b",
    "mixtral-8x7b",
})


@dataclass(frozen=True)
class MLPerfEntry:
    """One row from summary_results.json (already filtered Server+dc+closed)."""

    model: str              # e.g. "llama2-70b-99"
    submitter: str          # e.g. "AMD"
    system: str             # e.g. "8xMI325X_2xEPYC_9575F"
    accelerator: str        # e.g. "MI325X"
    performance_result: float
    performance_units: str  # e.g. "Tokens/s"
    accuracy: str           # raw accuracy string
    location: str           # GCS/GitHub path suffix


@dataclass(frozen=True)
class LogMetrics:
    """Parsed from mlperf_log_summary.txt."""

    latency_p95_ns: int | None      # 95th percentile end-to-end (ns)
    latency_p99_ns: int | None
    ttft_p95_ns: int | None         # first token latency p95 (ns)


@dataclass
class SeedReport:
    version: str = "v5.0"
    entries_found: int = 0
    entries_with_log: int = 0
    models_seeded: int = 0
    observations_inserted: int = 0
    axes_coverage: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def print(self) -> None:
        print(f"\n=== MLPerf Inference seed report ({self.version}) ===")
        print(f"Entries found      : {self.entries_found}")
        print(f"Entries with log   : {self.entries_with_log}")
        print(f"Models seeded      : {self.models_seeded}")
        print(f"Observations total : {self.observations_inserted}")
        print("\nAxis coverage (observations inserted):")
        for ax in ["quality", "latency_p95", "throughput", "cost",
                   "energy", "memory_hw", "governance", "reviewer_burden"]:
            cnt = self.axes_coverage.get(ax, 0)
            flag = "YES" if cnt > 0 else "⊥"
            print(f"  {ax:<22} {cnt:>5}   {flag}")
        if self.errors:
            print(f"\nErrors ({len(self.errors)}):")
            for e in self.errors[:10]:
                print(f"  {e}")
