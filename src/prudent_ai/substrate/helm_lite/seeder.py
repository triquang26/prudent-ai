"""HelmLiteSeeder — orchestrates download → parse → DB insertion.

Pipeline:
  1. List all run directories for a given version via GCS API.
  2. For each run, fetch stats.json and parse into ParsedRun.
  3. Group runs by model_id.
  4. For each model, aggregate per-scenario scores and insert into substrate.
  5. Return SeedReport with coverage summary.

Axis mapping (what HELM Lite can populate):
  quality    → per-scenario accuracy / F1 / BLEU (scenario stored in obs.dataset)
  latency_p95 → inference_runtime mean (s/instance) — NOTE: this is mean, not true
                 p95, but the best available from HELM. Stored with a note in context.
  (all other axes remain ⊥)

Confidence policy (from data_dictionary.md):
  leaderboard → M
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from prudent_ai.substrate import Substrate

from .client import HelmLiteClient
from .models import ModelRuns, ParsedRun, SeedReport
from .parser import MULTI_SUBSET_SCENARIOS, SCENARIO_PRIMARY_METRIC, HelmLiteParser

HELM_LITE_VERSION = "v1.0.0"
DB_PATH = Path("data/apt_substrate.db")

# Task archetype for all HELM Lite configs
TAU = "general-qa"

# Snapshot date used for obs_date and evidence provenance
SNAPSHOT_DATE = "2023-11"

SOURCE_ROW = {
    "evidence_id": f"helm-lite-{HELM_LITE_VERSION}-{SNAPSHOT_DATE}",
    "source_type": "leaderboard",
    "citation": (
        "Liang et al. 2022, HELM, arxiv 2211.09110. "
        f"HELM Lite leaderboard {SNAPSHOT_DATE}, version {HELM_LITE_VERSION}. "
        "https://crfm.stanford.edu/helm/lite/"
    ),
    "snapshot_version": f"{HELM_LITE_VERSION}-{SNAPSHOT_DATE}",
}


class HelmLiteSeeder:
    """Download real HELM Lite data and insert into the APT substrate.

    Args:
        substrate: An open Substrate instance (will NOT be closed by this class).
        version: HELM Lite GCS version tag (default v1.0.0).
        limit: If set, fetch at most this many run directories (useful for testing).
        verbose: Print progress to stdout.
    """

    def __init__(
        self,
        substrate: Substrate,
        version: str = HELM_LITE_VERSION,
        limit: int | None = None,
        verbose: bool = True,
    ) -> None:
        self.substrate = substrate
        self.version = version
        self.limit = limit
        self.verbose = verbose
        self._client = HelmLiteClient()
        self._parser = HelmLiteParser()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def seed(self) -> SeedReport:
        """Run the full pipeline. Idempotent (INSERT OR IGNORE throughout)."""
        report = SeedReport(version=self.version)
        conn = self.substrate._conn
        conn.execute("PRAGMA foreign_keys = ON")

        self._log("Fetching run list from GCS …")
        run_names = self._client.list_run_names(self.version)
        if self.limit:
            run_names = run_names[: self.limit]
        self._log(f"  Found {len(run_names)} run directories")

        # Insert source provenance row before any observations
        self._insert_source(conn)

        # Fetch + parse all runs
        parsed_runs = self._fetch_and_parse(run_names, report)
        report.runs_fetched = len(parsed_runs)

        # Group by model and insert
        model_groups = self._parser.group_by_model(parsed_runs)
        self._log(f"\nInserting {len(model_groups)} models …")
        for model_id, model_runs in sorted(model_groups.items()):
            inserted = self._seed_model(conn, model_id, model_runs, report)
            report.observations_inserted += inserted
            if self.verbose:
                print(f"  {model_id:<45} +{inserted} obs")
            report.models_seeded += 1

        conn.commit()
        return report

    # ------------------------------------------------------------------
    # Fetch + parse
    # ------------------------------------------------------------------

    def _fetch_and_parse(
        self, run_names: list[str], report: SeedReport
    ) -> list[ParsedRun]:
        """Download stats.json for each run and parse. Skips on error."""
        parsed: list[ParsedRun] = []
        total = len(run_names)
        for i, run_name in enumerate(run_names, 1):
            if self.verbose and i % 50 == 0:
                print(f"  [{i}/{total}] fetching …")
            try:
                raw = self._client.fetch_stats(self.version, run_name)
                run = self._parser.parse_run(self.version, run_name, raw)
                parsed.append(run)
            except FileNotFoundError:
                report.runs_skipped += 1
                report.errors.append(f"stats.json missing: {run_name}")
            except Exception as exc:  # noqa: BLE001
                report.runs_skipped += 1
                report.errors.append(f"error {run_name}: {exc}")
        return parsed

    # ------------------------------------------------------------------
    # DB insertion
    # ------------------------------------------------------------------

    def _insert_source(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            "INSERT OR IGNORE INTO source (evidence_id, source_type, citation, snapshot_version) "
            "VALUES (?, ?, ?, ?)",
            (
                SOURCE_ROW["evidence_id"],
                SOURCE_ROW["source_type"],
                SOURCE_ROW["citation"],
                SOURCE_ROW["snapshot_version"],
            ),
        )

    def _seed_model(
        self,
        conn: sqlite3.Connection,
        model_id: str,
        model_runs: ModelRuns,
        report: SeedReport,
    ) -> int:
        """Insert component, config, and all observations for one model. Returns obs count."""
        canonical = model_runs.all_runs[0].directory.canonical_model_id
        provider, model_name = canonical.split("/", 1)

        # Component rows
        conn.execute(
            "INSERT OR IGNORE INTO component (id, kind, name) VALUES (?, ?, ?)",
            (f"provider-{provider}", "provider", provider),
        )
        conn.execute(
            "INSERT OR IGNORE INTO component (id, kind, name) VALUES (?, ?, ?)",
            (f"model-{model_id}", "model", model_name),
        )

        # Config row (one per model — tau = general-qa for P1)
        config_id = model_id
        conn.execute(
            "INSERT OR IGNORE INTO config (id, tau) VALUES (?, ?)",
            (config_id, TAU),
        )
        conn.execute(
            "INSERT OR IGNORE INTO config_component (config_id, component_id) VALUES (?, ?)",
            (config_id, f"provider-{provider}"),
        )
        conn.execute(
            "INSERT OR IGNORE INTO config_component (config_id, component_id) VALUES (?, ?)",
            (config_id, f"model-{model_id}"),
        )

        inserted = 0
        inserted += self._insert_quality_obs(conn, config_id, model_runs, report)
        inserted += self._insert_latency_obs(conn, config_id, model_runs, report)
        return inserted

    def _insert_quality_obs(
        self,
        conn: sqlite3.Connection,
        config_id: str,
        model_runs: ModelRuns,
        report: SeedReport,
    ) -> int:
        """Insert one quality observation per scenario type (aggregated across subsets)."""
        inserted = 0
        evidence_id = SOURCE_ROW["evidence_id"]

        for scenario_type in SCENARIO_PRIMARY_METRIC:
            if scenario_type not in model_runs.runs_by_scenario:
                continue  # ⊥ — no data for this model+scenario

            if scenario_type in MULTI_SUBSET_SCENARIOS:
                score = self._parser.aggregate_quality(model_runs, scenario_type)
            else:
                runs = model_runs.runs_by_scenario[scenario_type]
                score = runs[0].quality_score if runs else None

            if score is None:
                continue

            obs_id = f"obs-{config_id}-quality-{scenario_type}-{evidence_id}"
            conn.execute(
                """
                INSERT OR IGNORE INTO observation
                    (obs_id, config_id, axis, value_num, value_cat,
                     confidence, evidence_id,
                     hardware_tier, dataset, split, decoding_cfg, obs_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    obs_id,
                    config_id,
                    "quality",
                    round(score, 6),
                    None,
                    "M",             # leaderboard → M
                    evidence_id,
                    "vendor-api",    # HELM Lite calls go through vendor APIs
                    scenario_type,   # e.g. "mmlu", "gsm", "math"
                    "test",
                    "greedy",        # HELM Lite default: temperature=0
                    SNAPSHOT_DATE,
                ),
            )
            report.axes_coverage["quality"] = report.axes_coverage.get("quality", 0) + 1
            inserted += 1

        return inserted

    def _insert_latency_obs(
        self,
        conn: sqlite3.Connection,
        config_id: str,
        model_runs: ModelRuns,
        report: SeedReport,
    ) -> int:
        """Insert one latency observation per scenario type (inference_runtime mean)."""
        inserted = 0
        evidence_id = SOURCE_ROW["evidence_id"]

        for scenario_type, _runs in model_runs.runs_by_scenario.items():
            latency = self._parser.aggregate_latency(model_runs, scenario_type)
            if latency is None:
                continue

            # Convert seconds → milliseconds; store as latency_p95 with a note in decoding_cfg
            latency_ms = round(latency * 1000, 3)
            obs_id = f"obs-{config_id}-latency_p95-{scenario_type}-{evidence_id}"
            conn.execute(
                """
                INSERT OR IGNORE INTO observation
                    (obs_id, config_id, axis, value_num, value_cat,
                     confidence, evidence_id,
                     hardware_tier, dataset, split, decoding_cfg, obs_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    obs_id,
                    config_id,
                    "latency_p95",
                    latency_ms,
                    None,
                    "L",             # inference_runtime is mean not p95; L confidence
                    evidence_id,
                    "vendor-api",
                    scenario_type,
                    "test",
                    "mean-not-p95",  # note: HELM reports mean inference time, not p95
                    SNAPSHOT_DATE,
                ),
            )
            report.axes_coverage["latency_p95"] = (
                report.axes_coverage.get("latency_p95", 0) + 1
            )
            inserted += 1

        return inserted

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def seed(
    db_path: Path = DB_PATH,
    version: str = HELM_LITE_VERSION,
    limit: int | None = None,
    verbose: bool = True,
) -> SeedReport:
    """Convenience function: open substrate, seed, close, return report."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    sub = Substrate(db_path)
    try:
        seeder = HelmLiteSeeder(sub, version=version, limit=limit, verbose=verbose)
        report = seeder.seed()
    finally:
        sub.close()

    report.print()
    return report


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Seed APT substrate with HELM Lite data")
    ap.add_argument("--db", default=str(DB_PATH), help="SQLite DB path")
    ap.add_argument("--version", default=HELM_LITE_VERSION, help="HELM Lite version")
    ap.add_argument("--limit", type=int, default=None, help="Limit run count (for testing)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    seed(
        db_path=Path(args.db),
        version=args.version,
        limit=args.limit,
        verbose=not args.quiet,
    )
