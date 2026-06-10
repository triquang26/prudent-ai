"""MLPerfSeeder — download MLPerf v5.0 results and insert into APT substrate.

Pipeline:
  1. Fetch summary_results.json from GitHub.
  2. Filter: Server + datacenter + closed + LLM models.
  3. For each entry: insert throughput observation.
  4. Try to fetch mlperf_log_summary.txt → insert latency_p95 observation.
  5. Return SeedReport.

Axes populated:
  throughput  → Performance_Result (Tokens/s), confidence=H
  latency_p95 → 95th-percentile end-to-end latency (ms), confidence=H

Confidence = H: MLCommons benchmarks are audited and reproducible.
Axes ⊥: quality, cost, energy, memory_hw, governance, reviewer_burden
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
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

from .client import MLPERF_VERSION, MLPerfClient
from .models import LogMetrics, MLPerfEntry, SeedReport
from .parser import MLPerfParser

SNAPSHOT = "2025"   # MLPerf Inference v5.0 results

SOURCE_ROW = {
    "evidence_id": f"mlperf-inference-{MLPERF_VERSION}",
    "source_type": "benchmark",
    "citation": (
        "MLCommons MLPerf Inference Benchmark, "
        f"version {MLPERF_VERSION}. "
        "https://mlcommons.org/benchmarks/inference-datacenter/. "
        "Scenario: Server, Suite: datacenter, Category: closed."
    ),
    "snapshot_version": f"mlperf-inference-{MLPERF_VERSION}",
}

DB_PATH = Path("data/apt_substrate.db")
TAU = "inference-serving"


class MLPerfSeeder:
    """Fetch MLPerf Inference results and insert into APT substrate.

    Args:
        substrate: Open Substrate instance (NOT closed by this class).
        verbose: Print progress to stdout.
        log_workers: Max threads for parallel log fetching (default 16).
    """

    def __init__(
        self,
        substrate: Substrate,
        verbose: bool = True,
        log_workers: int = 16,
    ) -> None:
        self.substrate = substrate
        self.verbose = verbose
        self.log_workers = log_workers
        self._client = MLPerfClient()
        self._parser = MLPerfParser()

    def seed(self) -> SeedReport:
        """Run full pipeline. Idempotent (INSERT OR IGNORE)."""
        report = SeedReport(version=MLPERF_VERSION)
        session = self.substrate._session

        self._log(f"Fetching MLPerf Inference {MLPERF_VERSION} summary …")
        raw = self._client.fetch_summary()

        entries = self._parser.filter_entries(raw)
        report.entries_found = len(entries)
        self._log(f"  Filtered to {len(entries)} LLM server entries")

        self._insert_source(session)

        # Fetch logs in parallel
        self._log(f"\nFetching {len(entries)} log files (up to {self.log_workers} parallel) …")
        log_map = self._fetch_logs_parallel(entries, report)
        report.entries_with_log = sum(1 for v in log_map.values() if v is not None)
        self._log(f"  Got logs for {report.entries_with_log}/{len(entries)} entries")

        # Insert by model group
        model_groups = self._parser.group_by_model(entries)
        self._log(f"\nInserting {len(model_groups)} models …")
        for model, model_entries in sorted(model_groups.items()):
            inserted = self._seed_model(session, model, model_entries, log_map, report)
            report.observations_inserted += inserted
            report.models_seeded += 1
            if self.verbose:
                print(f"  {model:<45} +{inserted} obs ({len(model_entries)} submissions)")

        session.commit()
        return report

    # ------------------------------------------------------------------
    # Log fetching
    # ------------------------------------------------------------------

    def _fetch_logs_parallel(
        self, entries: list[MLPerfEntry], report: SeedReport
    ) -> dict[str, LogMetrics | None]:
        """Fetch logs concurrently; returns location → LogMetrics | None."""
        log_map: dict[str, LogMetrics | None] = {}
        unique_locations = {e.location for e in entries if e.location}

        def _fetch(location: str) -> tuple[str, LogMetrics | None]:
            try:
                text = self._client.fetch_log(location)
                return location, self._parser.parse_log(text)
            except FileNotFoundError:
                return location, None
            except Exception as exc:  # noqa: BLE001
                report.errors.append(f"log error {location}: {exc}")
                return location, None

        with ThreadPoolExecutor(max_workers=self.log_workers) as pool:
            futures = {pool.submit(_fetch, loc): loc for loc in unique_locations}
            done = 0
            for future in as_completed(futures):
                loc, metrics = future.result()
                log_map[loc] = metrics
                done += 1
                if self.verbose and done % 20 == 0:
                    print(f"  [{done}/{len(unique_locations)}] logs fetched …")

        return log_map

    # ------------------------------------------------------------------
    # DB insertion
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

    def _seed_model(
        self,
        session: Session,
        model: str,
        entries: list[MLPerfEntry],
        log_map: dict[str, LogMetrics | None],
        report: SeedReport,
    ) -> int:
        config_id = f"mlperf-{model}"
        evidence_id = SOURCE_ROW["evidence_id"]

        # Component rows (mlcommons as provider, model as model)
        session.execute(
            sqlite_insert(Component)
            .values(id="provider-mlcommons", kind="provider", name="mlcommons")
            .on_conflict_do_nothing()
        )
        session.execute(
            sqlite_insert(Component)
            .values(id=f"model-mlperf-{model}", kind="model", name=model)
            .on_conflict_do_nothing()
        )
        session.execute(
            sqlite_insert(Config)
            .values(id=config_id, tau=TAU)
            .on_conflict_do_nothing()
        )
        session.execute(
            sqlite_insert(ConfigComponent)
            .values(config_id=config_id, component_id="provider-mlcommons")
            .on_conflict_do_nothing()
        )
        session.execute(
            sqlite_insert(ConfigComponent)
            .values(config_id=config_id, component_id=f"model-mlperf-{model}")
            .on_conflict_do_nothing()
        )

        inserted = 0
        for entry in entries:
            hw_tag = self._hw_tag(entry)

            # throughput observation
            obs_id = f"obs-{config_id}-throughput-{_slug(hw_tag)}-{evidence_id}"
            session.execute(
                sqlite_insert(ObsORM)
                .values(
                    obs_id=obs_id,
                    config_id=config_id,
                    axis="throughput",
                    value_num=round(entry.performance_result, 3),
                    value_cat=None,
                    confidence="H",
                    evidence_id=evidence_id,
                    hardware_tier=hw_tag,
                    dataset=model,
                    split="test",
                    decoding_cfg="mlperf-server",
                    obs_date=SNAPSHOT,
                )
                .on_conflict_do_nothing()
            )
            report.axes_coverage["throughput"] = report.axes_coverage.get("throughput", 0) + 1
            inserted += 1

            # latency_p95 from log (if available)
            metrics = log_map.get(entry.location)
            if metrics and metrics.latency_p95_ns:
                latency_ms = round(metrics.latency_p95_ns / 1_000_000.0, 3)
                obs_id_lat = f"obs-{config_id}-latency_p95-{_slug(hw_tag)}-{evidence_id}"
                session.execute(
                    sqlite_insert(ObsORM)
                    .values(
                        obs_id=obs_id_lat,
                        config_id=config_id,
                        axis="latency_p95",
                        value_num=latency_ms,
                        value_cat=None,
                        confidence="H",
                        evidence_id=evidence_id,
                        hardware_tier=hw_tag,
                        dataset=model,
                        split="test",
                        decoding_cfg="mlperf-server",
                        obs_date=SNAPSHOT,
                    )
                    .on_conflict_do_nothing()
                )
                report.axes_coverage["latency_p95"] = report.axes_coverage.get("latency_p95", 0) + 1
                inserted += 1

        return inserted

    @staticmethod
    def _hw_tag(entry: MLPerfEntry) -> str:
        """Build hardware identifier for hardware_tier column and obs_id.

        Uses the last two path segments of Location as the system fingerprint
        so that different AMD MI325X systems (same submitter+accelerator but
        different node configs) get distinct obs_ids.
        e.g. "closed/AMD/results/8xMI325X_2xEPYC/llama2-70b-99/Server"
             → hardware_tier = "AMD-MI325X"
             → key          = "AMD-MI325X-8xMI325X_2xEPYC"
        """
        # Extract system-level segment from Location path (4th path component)
        parts = entry.location.strip("/").split("/")
        # parts: [category, submitter, "results", system, model, scenario]
        system_seg = parts[3] if len(parts) > 3 else entry.system
        accel = entry.accelerator or ""
        return f"{entry.submitter}-{accel}-{system_seg}"[:80]

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg)


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:48]


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def seed(
    db_path: Path = DB_PATH,
    verbose: bool = True,
    log_workers: int = 16,
) -> SeedReport:
    """Convenience: open substrate, seed, close, return report."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    sub = Substrate(db_path)
    try:
        seeder = MLPerfSeeder(sub, verbose=verbose, log_workers=log_workers)
        report = seeder.seed()
    finally:
        sub.close()

    report.print()
    return report


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Seed APT substrate with MLPerf data")
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args()
    seed(db_path=Path(args.db), verbose=not args.quiet, log_workers=args.workers)
