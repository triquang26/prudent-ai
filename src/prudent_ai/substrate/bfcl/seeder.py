"""BFCLSeeder — download BFCL leaderboard and insert into APT substrate.

Axes populated:
  quality     → Overall Acc (leaderboard accuracy, confidence=M)
  cost        → Total Cost USD (confidence=M)
  latency_p95 → 95th-percentile latency in ms (confidence=M)

Axes ⊥: throughput, energy, memory_hw, governance, reviewer_burden
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

from .client import BFCLClient
from .models import BFCLRow, SeedReport
from .parser import BFCLParser

SNAPSHOT = "2026-06"

SOURCE_ROW = {
    "evidence_id": f"bfcl-{SNAPSHOT}",
    "source_type": "leaderboard",
    "citation": (
        "Berkeley Function-Calling Leaderboard (BFCL). "
        "ShishirPatil et al., https://gorilla.cs.berkeley.edu/leaderboard.html. "
        f"Snapshot {SNAPSHOT}."
    ),
    "snapshot_version": SNAPSHOT,
}

DB_PATH = Path("data/apt_substrate.db")
TAU = "function-calling"


class BFCLSeeder:
    """Download BFCL CSV and insert into APT substrate.

    Args:
        substrate: Open Substrate instance (NOT closed by this class).
        verbose: Print progress to stdout.
    """

    def __init__(self, substrate: Substrate, verbose: bool = True) -> None:
        self.substrate = substrate
        self.verbose = verbose
        self._client = BFCLClient()
        self._parser = BFCLParser()

    def seed(self) -> SeedReport:
        """Run full pipeline. Idempotent (INSERT OR IGNORE)."""
        report = SeedReport(source="bfcl", snapshot=SNAPSHOT)
        session = self.substrate._session

        self._log("Fetching BFCL leaderboard CSV …")
        csv_text = self._client.fetch_csv()

        rows = self._parser.parse(csv_text)
        report.rows_parsed = len(rows)
        self._log(f"  Parsed {len(rows)} model rows")

        self._insert_source(session)

        self._log(f"\nInserting {len(rows)} models …")
        for row in rows:
            inserted = self._seed_row(session, row, report)
            report.observations_inserted += inserted
            report.models_seeded += 1
            if self.verbose:
                print(f"  {row.model_name:<55} +{inserted} obs")

        session.commit()
        return report

    # ------------------------------------------------------------------
    # DB helpers
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

    def _seed_row(
        self, session: Session, row: BFCLRow, report: SeedReport
    ) -> int:
        slug = row.slug
        provider = row.provider
        evidence_id = SOURCE_ROW["evidence_id"]

        session.execute(
            sqlite_insert(Component)
            .values(id=f"provider-{provider}", kind="provider", name=provider)
            .on_conflict_do_nothing()
        )
        session.execute(
            sqlite_insert(Component)
            .values(id=f"model-bfcl-{slug}", kind="model", name=slug)
            .on_conflict_do_nothing()
        )
        config_id = f"bfcl-{slug}"
        session.execute(
            sqlite_insert(Config)
            .values(id=config_id, tau=TAU)
            .on_conflict_do_nothing()
        )
        session.execute(
            sqlite_insert(ConfigComponent)
            .values(config_id=config_id, component_id=f"provider-{provider}")
            .on_conflict_do_nothing()
        )
        session.execute(
            sqlite_insert(ConfigComponent)
            .values(config_id=config_id, component_id=f"model-bfcl-{slug}")
            .on_conflict_do_nothing()
        )

        inserted = 0

        # quality
        inserted += self._insert_obs(
            session, report,
            obs_id=f"obs-{config_id}-quality-{evidence_id}",
            config_id=config_id,
            axis="quality",
            value_num=round(row.overall_acc, 6),
            confidence="M",
            evidence_id=evidence_id,
            hardware_tier="vendor-api",
            dataset="bfcl-v3",
            decoding_cfg="function-calling",
        )

        # cost (if present)
        if row.total_cost_usd is not None:
            inserted += self._insert_obs(
                session, report,
                obs_id=f"obs-{config_id}-cost-{evidence_id}",
                config_id=config_id,
                axis="cost",
                value_num=round(row.total_cost_usd, 6),
                confidence="M",
                evidence_id=evidence_id,
                hardware_tier="vendor-api",
                dataset="bfcl-v3",
                decoding_cfg="function-calling",
            )

        # latency_p95 (s → ms)
        if row.latency_p95_s is not None:
            inserted += self._insert_obs(
                session, report,
                obs_id=f"obs-{config_id}-latency_p95-{evidence_id}",
                config_id=config_id,
                axis="latency_p95",
                value_num=round(row.latency_p95_s * 1000.0, 3),
                confidence="M",
                evidence_id=evidence_id,
                hardware_tier="vendor-api",
                dataset="bfcl-v3",
                decoding_cfg="function-calling",
            )

        return inserted

    def _insert_obs(
        self,
        session: Session,
        report: SeedReport,
        *,
        obs_id: str,
        config_id: str,
        axis: str,
        value_num: float,
        confidence: str,
        evidence_id: str,
        hardware_tier: str,
        dataset: str,
        decoding_cfg: str,
    ) -> int:
        session.execute(
            sqlite_insert(ObsORM)
            .values(
                obs_id=obs_id,
                config_id=config_id,
                axis=axis,
                value_num=value_num,
                value_cat=None,
                confidence=confidence,
                evidence_id=evidence_id,
                hardware_tier=hardware_tier,
                dataset=dataset,
                split="test",
                decoding_cfg=decoding_cfg,
                obs_date=SNAPSHOT,
            )
            .on_conflict_do_nothing()
        )
        report.axes_coverage[axis] = report.axes_coverage.get(axis, 0) + 1
        return 1

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def seed(
    db_path: Path = DB_PATH,
    verbose: bool = True,
) -> SeedReport:
    """Convenience: open substrate, seed, close, return report."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    sub = Substrate(db_path)
    try:
        seeder = BFCLSeeder(sub, verbose=verbose)
        report = seeder.seed()
    finally:
        sub.close()

    report.print()
    return report


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Seed APT substrate with BFCL data")
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    seed(db_path=Path(args.db), verbose=not args.quiet)
