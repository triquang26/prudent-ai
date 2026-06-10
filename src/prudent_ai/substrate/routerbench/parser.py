"""Pure RouterBench DataFrame → RouterBenchConfig — aggregation only, no I/O.

Per (model, benchmark) we aggregate over prompts:
  quality = mean per-prompt correctness (0–1)
  cost    = mean per-prompt dollar cost

MMLU subtopics (`mmlu-*`) are collapsed into a single `mmlu` benchmark group so
each model contributes one mmlu config (mean over subtopics) rather than 57; all
other benchmarks are kept as-is.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .models import MODELS, RouterBenchConfig

if TYPE_CHECKING:
    import pandas as pd


def benchmark_group(eval_name: str) -> str:
    """Collapse mmlu-* subtopics into 'mmlu'; keep other benchmarks verbatim."""
    if eval_name.startswith("mmlu-"):
        return "mmlu"
    return eval_name


class RouterBenchParser:
    """Aggregate the per-prompt DataFrame into per-(model, benchmark) configs."""

    def parse(self, df: pd.DataFrame) -> list[RouterBenchConfig]:
        configs: list[RouterBenchConfig] = []
        # Work on a copy with a normalized benchmark-group column.
        groups = df["eval_name"].map(benchmark_group)

        for model in MODELS:
            cost_col = f"{model}|total_cost"
            if model not in df.columns or cost_col not in df.columns:
                continue
            perf = df[model].astype(float)
            cost = df[cost_col].astype(float)

            # Aggregate per benchmark group.
            for bench in sorted(groups.unique()):
                mask = (groups == bench) & perf.notna() & cost.notna()
                n = int(mask.sum())
                if n == 0:
                    continue
                q = float(perf[mask].mean())
                c = float(cost[mask].mean())
                configs.append(
                    RouterBenchConfig(
                        model=model,
                        benchmark=bench,
                        quality=round(q, 6),
                        cost=round(c, 8),
                        n_prompts=n,
                    )
                )
        return configs
