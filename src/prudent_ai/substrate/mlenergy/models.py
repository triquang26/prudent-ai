"""ML.ENERGY Leaderboard domain objects — no I/O, no side effects.

ML.ENERGY provides per-(model, task, gpu, batch_size) measurements:
  energy      → energy_per_request_joules
  throughput  → output_throughput_tokens_per_sec
  latency_p95 → p95_itl_ms (inter-token latency p95, milliseconds)

Source: https://ml.energy/leaderboard
        ml-energy/leaderboard public/data/
Last updated: 2026-02-16
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EnergyConfig:
    """One hardware configuration for a (model, task) combination."""

    model_id: str           # HuggingFace model ID, e.g. "Qwen/Qwen3-14B"
    task: str               # e.g. "gpqa", "lm-arena-chat"
    gpu_model: str          # e.g. "B200", "H100"
    max_num_seqs: int       # batch size

    # Energy metrics
    energy_per_request_joules: float
    energy_per_token_joules: float

    # Throughput
    output_throughput_tokens_per_sec: float

    # Latency
    p95_itl_ms: float       # 95th percentile inter-token latency (ms)
    p99_itl_ms: float | None

    # Context
    num_gpus: int
    avg_power_watts: float


@dataclass
class ModelTaskFile:
    """Contents of one {model}__{task}.json file."""

    filename: str           # e.g. "Qwen__Qwen3-14B__gpqa.json"
    model_id: str           # e.g. "Qwen/Qwen3-14B"
    task: str               # e.g. "gpqa"
    configurations: list[EnergyConfig] = field(default_factory=list)


@dataclass
class SeedReport:
    snapshot: str = "2026-02-16"
    files_fetched: int = 0
    files_skipped: int = 0
    models_seeded: int = 0
    configurations_total: int = 0
    observations_inserted: int = 0
    axes_coverage: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def print(self) -> None:
        print(f"\n=== ML.ENERGY seed report ({self.snapshot}) ===")
        print(f"Files fetched      : {self.files_fetched}")
        print(f"Files skipped      : {self.files_skipped}")
        print(f"Models seeded      : {self.models_seeded}")
        print(f"Configurations     : {self.configurations_total}")
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
