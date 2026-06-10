"""MLEnergySeeder — download ML.ENERGY data and insert into APT substrate.

Pipeline:
  1. List all JSON files in public/data/models/ via GitHub API.
  2. Fetch each file in parallel (ThreadPoolExecutor).
  3. Parse into EnergyConfig objects (one per gpu+batch combination).
  4. Insert one obs per (config_id, axis, gpu_model, max_num_seqs).
  5. Return SeedReport.

Axes populated:
  energy      → energy_per_request_joules (confidence=M)
  throughput  → output_throughput_tokens_per_sec (confidence=M)
  latency_p95 → p95_itl_ms (inter-token latency, confidence=M)

Axes ⊥: quality, cost, memory_hw, governance, reviewer_burden

Note: p95_itl_ms is inter-token latency (time between tokens), NOT end-to-end
  request latency. Stored with decoding_cfg='p95-itl' to distinguish from
  request-level p95 (stored by MLPerf seeder).
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

from .client import MLEnergyClient
from .models import EnergyConfig, ModelTaskFile, SeedReport
from .parser import MLEnergyParser

SNAPSHOT = "2026-02-16"

SOURCE_ROW = {
    "evidence_id": f"mlenergy-{SNAPSHOT}",
    "source_type": "benchmark",
    "citation": (
        "ML.ENERGY Leaderboard. "
        f"https://ml.energy/leaderboard. "
        f"Last updated {SNAPSHOT}."
    ),
    "snapshot_version": SNAPSHOT,
}

DB_PATH = Path("data/apt_substrate.db")
TAU = "inference-serving"


class MLEnergySeeder:
    """Fetch ML.ENERGY data and insert into APT substrate.

    Args:
        substrate: Open Substrate instance (NOT closed by this class).
        verbose: Print progress to stdout.
        workers: Max threads for parallel file fetching.
    """

    def __init__(
        self,
        substrate: Substrate,
        verbose: bool = True,
        workers: int = 16,
    ) -> None:
        self.substrate = substrate
        self.verbose = verbose
        self.workers = workers
        self._client = MLEnergyClient()
        self._parser = MLEnergyParser()

    def seed(self) -> SeedReport:
        """Run full pipeline. Idempotent (INSERT OR IGNORE)."""
        report = SeedReport(snapshot=SNAPSHOT)
        session = self.substrate._session

        self._log("Listing ML.ENERGY model files …")
        filenames = self._client.list_model_files()
        self._log(f"  Found {len(filenames)} files")

        self._insert_source(session)

        # Fetch all files in parallel
        self._log(f"\nFetching {len(filenames)} model files …")
        model_files = self._fetch_all_parallel(filenames, report)
        report.files_fetched = len(model_files)
        self._log(f"  Fetched {report.files_fetched}, skipped {report.files_skipped}")

        # Deduplicate by model_id to count unique models
        model_ids = sorted({mf.model_id for mf in model_files})
        self._log(f"\nInserting {len(model_ids)} unique models …")

        # Insert per model (group model_files by model_id)
        by_model: dict[str, list[ModelTaskFile]] = {}
        for mf in model_files:
            by_model.setdefault(mf.model_id, []).append(mf)

        for model_id in sorted(by_model):
            mfs = by_model[model_id]
            inserted = self._seed_model(session, model_id, mfs, report)
            report.observations_inserted += inserted
            report.models_seeded += 1
            total_cfgs = sum(len(mf.configurations) for mf in mfs)
            report.configurations_total += total_cfgs
            if self.verbose:
                print(f"  {model_id:<55} +{inserted} obs ({total_cfgs} configs)")

        session.commit()
        return report

    # ------------------------------------------------------------------
    # Parallel fetch
    # ------------------------------------------------------------------

    def _fetch_all_parallel(
        self, filenames: list[str], report: SeedReport
    ) -> list[ModelTaskFile]:
        results: list[ModelTaskFile] = []

        def _fetch(fn: str) -> ModelTaskFile | None:
            try:
                raw = self._client.fetch_model_task(fn)
                return self._parser.parse_model_task(fn, raw)
            except FileNotFoundError:
                report.files_skipped += 1
                return None
            except Exception as exc:  # noqa: BLE001
                report.files_skipped += 1
                report.errors.append(f"fetch error {fn}: {exc}")
                return None

        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = {pool.submit(_fetch, fn): fn for fn in filenames}
            done = 0
            for future in as_completed(futures):
                mf = future.result()
                if mf is not None:
                    results.append(mf)
                done += 1
                if self.verbose and done % 10 == 0:
                    print(f"  [{done}/{len(filenames)}] fetched …")

        return results

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
        model_id: str,
        model_files: list[ModelTaskFile],
        report: SeedReport,
    ) -> int:
        # Derive provider (org) from HF model_id "org/model"
        provider = model_id.split("/")[0] if "/" in model_id else "unknown"
        model_slug = _slug(model_id)
        config_id = f"mlenergy-{model_slug}"
        evidence_id = SOURCE_ROW["evidence_id"]

        session.execute(
            sqlite_insert(Component)
            .values(id=f"provider-{_slug(provider)}", kind="provider", name=provider)
            .on_conflict_do_nothing()
        )
        session.execute(
            sqlite_insert(Component)
            .values(id=f"model-mlenergy-{model_slug}", kind="model", name=model_id)
            .on_conflict_do_nothing()
        )
        session.execute(
            sqlite_insert(Config)
            .values(id=config_id, tau=TAU)
            .on_conflict_do_nothing()
        )
        session.execute(
            sqlite_insert(ConfigComponent)
            .values(config_id=config_id, component_id=f"provider-{_slug(provider)}")
            .on_conflict_do_nothing()
        )
        session.execute(
            sqlite_insert(ConfigComponent)
            .values(config_id=config_id, component_id=f"model-mlenergy-{model_slug}")
            .on_conflict_do_nothing()
        )

        inserted = 0
        for mf in model_files:
            for cfg in mf.configurations:
                inserted += self._insert_config_obs(session, config_id, cfg, report, evidence_id)
        return inserted

    def _insert_config_obs(
        self,
        session: Session,
        config_id: str,
        cfg: EnergyConfig,
        report: SeedReport,
        evidence_id: str,
    ) -> int:
        hw_tag = f"{cfg.gpu_model}-x{cfg.num_gpus}"
        # task MUST be part of ctx so obs_ids are unique per (model, task, gpu, seqs)
        ctx = f"{cfg.task},gpu={cfg.gpu_model},seqs={cfg.max_num_seqs}"
        inserted = 0

        # energy
        obs_id = f"obs-{config_id}-energy-{_slug(ctx)}-{evidence_id}"
        session.execute(
            sqlite_insert(ObsORM)
            .values(
                obs_id=obs_id,
                config_id=config_id,
                axis="energy",
                value_num=round(cfg.energy_per_request_joules, 6),
                value_cat=None,
                confidence="M",
                evidence_id=evidence_id,
                hardware_tier=hw_tag,
                dataset=cfg.task,
                split="test",
                decoding_cfg=ctx,
                obs_date=SNAPSHOT,
            )
            .on_conflict_do_nothing()
        )
        report.axes_coverage["energy"] = report.axes_coverage.get("energy", 0) + 1
        inserted += 1

        # throughput
        obs_id = f"obs-{config_id}-throughput-{_slug(ctx)}-{evidence_id}"
        session.execute(
            sqlite_insert(ObsORM)
            .values(
                obs_id=obs_id,
                config_id=config_id,
                axis="throughput",
                value_num=round(cfg.output_throughput_tokens_per_sec, 6),
                value_cat=None,
                confidence="M",
                evidence_id=evidence_id,
                hardware_tier=hw_tag,
                dataset=cfg.task,
                split="test",
                decoding_cfg=ctx,
                obs_date=SNAPSHOT,
            )
            .on_conflict_do_nothing()
        )
        report.axes_coverage["throughput"] = report.axes_coverage.get("throughput", 0) + 1
        inserted += 1

        # latency_p95 (inter-token latency p95)
        obs_id = f"obs-{config_id}-latency_p95-{_slug(ctx)}-{evidence_id}"
        session.execute(
            sqlite_insert(ObsORM)
            .values(
                obs_id=obs_id,
                config_id=config_id,
                axis="latency_p95",
                value_num=round(cfg.p95_itl_ms, 6),
                value_cat=None,
                confidence="M",
                evidence_id=evidence_id,
                hardware_tier=hw_tag,
                dataset=cfg.task,
                split="test",
                decoding_cfg="p95-itl",
                obs_date=SNAPSHOT,
            )
            .on_conflict_do_nothing()
        )
        report.axes_coverage["latency_p95"] = report.axes_coverage.get("latency_p95", 0) + 1
        inserted += 1

        return inserted

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
    workers: int = 16,
) -> SeedReport:
    """Convenience: open substrate, seed, close, return report."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    sub = Substrate(db_path)
    try:
        seeder = MLEnergySeeder(sub, verbose=verbose, workers=workers)
        report = seeder.seed()
    finally:
        sub.close()

    report.print()
    return report


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Seed APT substrate with ML.ENERGY data")
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args()
    seed(db_path=Path(args.db), verbose=not args.quiet, workers=args.workers)
