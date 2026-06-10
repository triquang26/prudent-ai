"""BFCL domain objects — no I/O, no side effects.

Berkeley Function-Calling Leaderboard (BFCL) data:
  quality     → Overall Acc (%)
  cost        → Total Cost ($) for full eval run
  latency_p95 → 95th-percentile latency (s → ms stored)

Source: https://gorilla.cs.berkeley.edu/leaderboard.html
        ShishirPatil/gorilla gh-pages data_overall.csv
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BFCLRow:
    """One row from data_overall.csv."""

    rank: int
    model_name: str        # raw name, e.g. "Claude-Opus-4-5-20251101 (FC)"
    model_link: str        # e.g. "https://www.anthropic.com/..."
    overall_acc: float     # 0–1
    total_cost_usd: float | None
    latency_mean_s: float | None
    latency_stddev_s: float | None
    latency_p95_s: float | None

    @property
    def slug(self) -> str:
        """Normalize model name → kebab-case slug for use as DB identifiers.

        Preserves mode variants: "(FC)" → "-fc", "(Prompt)" → "-prompt", etc.
        This ensures e.g. "Qwen3-32B (FC)" and "Qwen3-32B (Prompt)" get
        distinct config_ids instead of colliding on "bfcl-qwen3-32b".
        """
        import re
        s = self.model_name
        # Normalise parenthesised mode suffix to dash-separated text
        # "(FC)" → " fc", "(Prompt + Thinking)" → " prompt thinking"
        s = re.sub(r"\s*\(([^)]*)\)", lambda m: " " + m.group(1), s)
        s = s.lower().strip()
        s = re.sub(r"[^a-z0-9]+", "-", s)
        s = s.strip("-")
        return s

    @property
    def provider(self) -> str:
        """Infer provider from model_link domain."""
        _DOMAIN_MAP = {
            "anthropic.com": "anthropic",
            "openai.com": "openai",
            "ai.google": "google",
            "deepmind.google": "google",
            "mistral.ai": "mistral",
            "meta.com": "meta",
            "llama.meta.com": "meta",
            "cohere.com": "cohere",
            "deepseek.com": "deepseek",
            "amazon.com": "amazon",
            "aws.amazon.com": "amazon",
            "azure.microsoft.com": "microsoft",
            "microsoft.com": "microsoft",
            "x.ai": "xai",
            "01.ai": "01-ai",
            "together.ai": "together",
            "fireworks.ai": "fireworks",
            "nexusflow.ai": "nexusflow",
        }
        link = self.model_link or ""
        for domain, provider in _DOMAIN_MAP.items():
            if domain in link:
                return provider
        if "huggingface.co" in link:
            # e.g. https://huggingface.co/meta-llama/...
            parts = link.split("/")
            idx = next((i for i, p in enumerate(parts) if "huggingface.co" in p), -1)
            if idx >= 0 and idx + 1 < len(parts):
                return parts[idx + 1]
        return "unknown"


@dataclass
class SeedReport:
    source: str = "bfcl"
    snapshot: str = ""
    rows_parsed: int = 0
    models_seeded: int = 0
    observations_inserted: int = 0
    axes_coverage: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def print(self) -> None:
        print(f"\n=== BFCL seed report ({self.snapshot}) ===")
        print(f"Rows parsed        : {self.rows_parsed}")
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
