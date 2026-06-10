"""RouterBenchSeeder — insert the co-located quality+cost GT slice into the substrate.

Pipeline: download/load DataFrame → aggregate per (model, benchmark) →
insert config + quality + cost observations.

Axes populated:
  quality → mean correctness (0–1), confidence **H** (measured against gold answers)
  cost    → mean dollar cost per query, confidence **H** (computed from real token usage)

Both axes are co-located on every (model, benchmark) config under tau='routerbench'
— a high-confidence ground-truth slice for P5 validation. Axes left ⊥:
latency_p95, throughput, energy, memory_hw, governance, reviewer_burden.

Confidence H here (vs M for leaderboards) is deliberate: RouterBench correctness is
measured per prompt against known answers and cost is computed from actual tokens —
this is the ground-truth tier the validation needs, distinct from reported leaderboard
numbers (C2/C4).
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from prudent_ai.substrate import Substrate
from prudent_ai.substrate.orm import (
    Component,
    Config,
    ConfigComponent,
    Source,
)
from prudent_ai.substrate.orm import (
    Observation as ObsORM,
)

from .client import RouterBenchClient
from .models import RouterBenchConfig, SeedReport
from .parser import RouterBenchParser

SNAPSHOT = "2024-03"
TAU = "routerbench"

SOURCE_ROW = {
    "evidence_id": "routerbench-2403.12031",
    "source_type": "benchmark",
    "citation": (
        "RouterBench: A Benchmark for Multi-LLM Routing Systems, "
        "arXiv 2403.12031. HuggingFace withmartian/routerbench (0-shot). "
        "Per-prompt measured correctness + computed dollar cost."
    ),
    "snapshot_version": f"routerbench-0shot-{SNAPSHOT}",
}

DB_PATH = Path("data/apt_substrate.db")


class RouterBenchSeeder:
    """Download RouterBench, aggregate, and insert the GT slice."""

    def __init__(self, substrate: Substrate, verbose: bool = True) -> None:
        self.substrate = substrate
        self.verbose = verbose
        self._client = RouterBenchClient()
        self._parser = RouterBenchParser()

    def seed(self) -> SeedReport:
        report = SeedReport(source="routerbench", snapshot=SNAPSHOT)
        session = self.substrate._session

        self._log("Loading RouterBench DataFrame (downloads ~99MB on first run) …")
        df = self._client.load_dataframe()
        configs = self._parser.parse(df)
        report.configs_parsed = len(configs)
        self._log(f"  Aggregated {len(configs)} (model, benchmark) configs")

        self._insert_source(session)

        models_seen: set[str] = set()
        self._log(f"\nInserting {len(configs)} configs …")
        for cfg in configs:
            inserted = self._seed_config(session, cfg, report)
            report.observations_inserted += inserted
            models_seen.add(cfg.model)
        report.models_seeded = len(models_seen)

        session.commit()
        if self.verbose:
            print(f"  Seeded {report.configs_parsed} configs over {report.models_seeded} models")
        return report

    # ------------------------------------------------------------------

    def _insert_source(self, session: Session) -> None:
        session.execute(
            sqlite_insert(Source)
            .values(
                evidence_id=SOURCE_ROW["evidence_id"],
                source_type=SOURCE_ROW["source_type"],
                citation=SOURCE_ROW["citation"],
                snapshot_version=SOURCE_ROW["snapshot_version"],
            )
            .on_conflict_do_nothing()
        )

    def _seed_config(
        self, session: Session, cfg: RouterBenchConfig, report: SeedReport
    ) -> int:
        provider = cfg.provider
        model_slug = cfg.model_slug
        config_id = f"rb-{model_slug}-{cfg.benchmark}"
        evidence_id = SOURCE_ROW["evidence_id"]

        session.execute(
            sqlite_insert(Component)
            .values(id=f"provider-{provider}", kind="provider", name=provider)
            .on_conflict_do_nothing()
        )
        session.execute(
            sqlite_insert(Component)
            .values(id=f"model-rb-{model_slug}", kind="model", name=cfg.model)
            .on_conflict_do_nothing()
        )
        session.execute(
            sqlite_insert(Config).values(id=config_id, tau=TAU).on_conflict_do_nothing()
        )
        session.execute(
            sqlite_insert(ConfigComponent)
            .values(config_id=config_id, component_id=f"provider-{provider}")
            .on_conflict_do_nothing()
        )
        session.execute(
            sqlite_insert(ConfigComponent)
            .values(config_id=config_id, component_id=f"model-rb-{model_slug}")
            .on_conflict_do_nothing()
        )

        inserted = 0
        inserted += self._insert_obs(
            session, report, f"obs-{config_id}-quality-{evidence_id}",
            config_id, "quality", cfg.quality, cfg.benchmark,
        )
        inserted += self._insert_obs(
            session, report, f"obs-{config_id}-cost-{evidence_id}",
            config_id, "cost", cfg.cost, cfg.benchmark,
        )
        return inserted

    def _insert_obs(
        self, session: Session, report: SeedReport, obs_id: str,
        config_id: str, axis: str, value: float, dataset: str,
    ) -> int:
        session.execute(
            sqlite_insert(ObsORM)
            .values(
                obs_id=obs_id, config_id=config_id, axis=axis,
                value_num=value, value_cat=None,
                confidence="H",                       # measured ground truth
                evidence_id=SOURCE_ROW["evidence_id"],
                hardware_tier="vendor-api", dataset=dataset, split="test",
                decoding_cfg="0shot", obs_date=SNAPSHOT,
            )
            .on_conflict_do_nothing()
        )
        report.axes_coverage[axis] = report.axes_coverage.get(axis, 0) + 1
        return 1

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg)


def seed(db_path: Path = DB_PATH, verbose: bool = True) -> SeedReport:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    sub = Substrate(db_path)
    try:
        report = RouterBenchSeeder(sub, verbose=verbose).seed()
    finally:
        sub.close()
    report.print()
    return report


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Seed APT substrate with RouterBench GT slice")
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    seed(db_path=Path(args.db), verbose=not args.quiet)
