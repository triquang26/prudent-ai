"""Data-source registry — the single place that lists every evidence source.

Scaling the substrate to a new source is **one package + one line here**:
  1. Write `substrate/<source>/` (models.py + client.py + parser.py + seeder.py),
     exposing a module-level `seed(db_path, verbose) -> SeedReport` (the uniform
     contract every existing seeder already follows).
  2. Append a `SourceSpec(...)` to `SOURCE_REGISTRY` below.
That is the whole change — `scripts/seed_all.py` then ingests it automatically and
the coverage report picks it up. Nothing else in the pipeline needs editing.

Each spec is documentation *and* execution: `tau`, `axes`, and `confidence` record
what the source contributes (so the missingness map is self-describing), while
`seed_fn` is the callable the runner invokes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from prudent_ai.substrate.bfcl import seed as _seed_bfcl
from prudent_ai.substrate.helm_lite import seed as _seed_helm
from prudent_ai.substrate.mlenergy import seed as _seed_mlenergy
from prudent_ai.substrate.mlperf import seed as _seed_mlperf
from prudent_ai.substrate.routerbench import seed as _seed_routerbench


@dataclass(frozen=True)
class SourceSpec:
    """One evidence source: how to seed it + what it contributes."""

    name: str                          # short id, e.g. "bfcl"
    seed_fn: Callable[..., Any]        # module seed(db_path=..., verbose=...) -> SeedReport
    tau: str                           # the deployment-context tag its configs use
    axes: tuple[str, ...]              # axes it populates
    confidence: str                    # dominant confidence tier (H/M/L)
    note: str = ""                     # one-line provenance note
    extra_kwargs: dict[str, Any] = field(default_factory=dict)  # source-specific opts

    def seed(self, db_path: Path | str, verbose: bool = True):
        """Invoke the source's seeder with the uniform (db_path, verbose) contract."""
        return self.seed_fn(db_path=Path(db_path), verbose=verbose, **self.extra_kwargs)


# ---------------------------------------------------------------------------
# THE REGISTRY — add a SourceSpec here to scale the substrate to a new source.
# Order matters only for re-seed determinism; SQLite is a single writer, so the
# runner ingests these sequentially (never in parallel — concurrent writes corrupt).
# ---------------------------------------------------------------------------
SOURCE_REGISTRY: list[SourceSpec] = [
    SourceSpec(
        name="helm_lite", seed_fn=_seed_helm, tau="general-qa",
        axes=("quality", "latency_p95"), confidence="M",
        note="HELM Lite leaderboard (arXiv 2211.09110), GCS stats.json.",
    ),
    SourceSpec(
        name="bfcl", seed_fn=_seed_bfcl, tau="function-calling",
        axes=("quality", "cost", "latency_p95"), confidence="M",
        note="Berkeley Function-Calling Leaderboard, gh-pages CSV.",
    ),
    SourceSpec(
        name="mlperf", seed_fn=_seed_mlperf, tau="inference-serving",
        axes=("throughput", "latency_p95"), confidence="M",
        note="MLPerf Inference v5.0 (datacenter/closed/Server), summary + logs.",
    ),
    SourceSpec(
        name="mlenergy", seed_fn=_seed_mlenergy, tau="inference-serving",
        axes=("energy", "throughput", "latency_p95"), confidence="M",
        note="ML.ENERGY leaderboard, per-model GitHub JSON.",
    ),
    SourceSpec(
        name="routerbench", seed_fn=_seed_routerbench, tau="routerbench",
        axes=("quality", "cost"), confidence="H",
        note="RouterBench (arXiv 2403.12031) — co-located measured quality+cost (GT slice).",
    ),
    # --- To add a source: implement substrate/<name>/ then append a SourceSpec here. ---
    # SourceSpec(name="hal", seed_fn=_seed_hal, tau="agent",
    #            axes=("quality", "cost"), confidence="H",
    #            note="HAL agent traces (2510.11977) — decrypt + aggregate."),
]


def registry_by_name() -> dict[str, SourceSpec]:
    return {s.name: s for s in SOURCE_REGISTRY}
