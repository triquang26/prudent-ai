"""RouterBench domain objects — pure dataclasses, no I/O.

RouterBench (arXiv 2403.12031): 11 LLMs × ~36k prompts across 86 benchmarks
(MMLU subtopics, GSM-8k, MBPP, Hellaswag, Winogrande, MT-Bench, …), each prompt
carrying per-model measured correctness (0/1) and computed dollar cost.

Aggregated per (model, benchmark) this yields a config whose **quality and cost
are co-located** and measured — the high-confidence ground-truth slice the
leaderboard sources lacked (P3 fragmentation). Used by P5 validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# The 11 model columns in routerbench_0shot.pkl.
MODELS: tuple[str, ...] = (
    "WizardLM/WizardLM-13B-V1.2",
    "claude-instant-v1",
    "claude-v1",
    "claude-v2",
    "gpt-3.5-turbo-1106",
    "gpt-4-1106-preview",
    "meta/code-llama-instruct-34b-chat",
    "meta/llama-2-70b-chat",
    "mistralai/mistral-7b-chat",
    "mistralai/mixtral-8x7b-chat",
    "zero-one-ai/Yi-34B-Chat",
)


@dataclass(frozen=True)
class RouterBenchConfig:
    """One (model, benchmark) config with co-located measured quality + cost."""

    model: str            # raw model id, e.g. "gpt-4-1106-preview"
    benchmark: str        # benchmark group, e.g. "mmlu", "grade-school-math"
    quality: float        # mean correctness over prompts (0–1)
    cost: float           # mean dollar cost per query
    n_prompts: int        # prompts the aggregate was computed from

    @property
    def provider(self) -> str:
        m = self.model
        if m.startswith("claude"):
            return "anthropic"
        if m.startswith("gpt"):
            return "openai"
        if m.startswith("meta/"):
            return "meta"
        if m.startswith("mistralai/"):
            return "mistral"
        if m.startswith("zero-one-ai/"):
            return "01-ai"
        if m.startswith("WizardLM/"):
            return "wizardlm"
        return "unknown"

    @property
    def model_slug(self) -> str:
        import re
        return re.sub(r"[^a-z0-9]+", "-", self.model.lower()).strip("-")


@dataclass
class SeedReport:
    source: str = "routerbench"
    snapshot: str = ""
    configs_parsed: int = 0
    models_seeded: int = 0
    observations_inserted: int = 0
    axes_coverage: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def print(self) -> None:
        print(f"\n=== RouterBench seed report ({self.snapshot}) ===")
        print(f"Configs parsed     : {self.configs_parsed}")
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
