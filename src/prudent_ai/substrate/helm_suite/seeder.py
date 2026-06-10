"""Generalized HELM-suite seeder — download → parse → insert, for any suite by spec.

Mirrors `helm_lite.seeder` but (a) takes a `SuiteSpec` (prefix/version/tau/citation) and
(b) iterates the scenarios actually present per model (HELM Lite hardcodes a scenario map;
other suites have their own scenarios). Quality → M; latency_p95 ← inference_runtime mean
→ L (note `mean-not-p95`); every other axis stays ⊥ (never imputed).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from prudent_ai.substrate import Substrate
from prudent_ai.substrate.helm_lite.models import ModelRuns, ParsedRun, SeedReport
from prudent_ai.substrate.helm_suite.client import HelmSuiteClient
from prudent_ai.substrate.helm_suite.parser import HelmSuiteParser
from prudent_ai.substrate.orm import (
    Component,
    Config,
    ConfigComponent,
    Source,
)
from prudent_ai.substrate.orm import (
    Observation as ObsORM,
)

DB_PATH = Path("data/apt_substrate.db")


@dataclass(frozen=True)
class SuiteSpec:
    """A HELM-family suite to ingest (one structured source)."""

    name: str            # short id, e.g. "medhelm"
    suite_prefix: str    # GCS run prefix, e.g. "medhelm/benchmark_output/runs"
    version: str         # e.g. "v2.0.0"
    tau: str             # task archetype, e.g. "medical-qa"
    snapshot_date: str   # e.g. "2025-05"
    citation: str
    hardware_tier: str = "vendor-api"

    @property
    def evidence_id(self) -> str:
        return f"{self.name}-{self.version}-{self.snapshot_date}"


# The suites this package can ingest. Add one line to scale (master-plan §13 breadth).
# MedHELM is the §13 governance blind-spot probe: a clinical/Stanford-Health-Care
# benchmark that — being a leaderboard — still reports NO governance/reviewer_burden axis,
# strengthening the structural-⊥ claim while broadening the quality corpus.
def _helm_spec(name: str, tau: str, version: str = "latest") -> SuiteSpec:
    """A HELM-family suite on crfm-helm-public with the standard run layout."""
    return SuiteSpec(
        name=name,
        suite_prefix=f"{name}/benchmark_output/runs",
        version=version,
        tau=tau,
        snapshot_date="2025",
        citation=(
            f"HELM '{name}' leaderboard, Stanford CRFM (Liang et al. 2022, "
            f"arXiv 2211.09110). https://crfm.stanford.edu/helm/{name}/"
        ),
    )


# Every auto-ingestible text/LLM HELM suite on crfm-helm-public (one config archetype
# each). Quality kept strictly on the [0,1] accuracy scale; off-scale jury ratings
# skipped. Multimodal (vhelm/heim/audio/image2struct) and non-LLM (robo-reward-bench)
# suites are excluded (different schema). `version="latest"` auto-resolves on GCS.
SUITES: list[SuiteSpec] = [
    SuiteSpec(
        name="medhelm", suite_prefix="medhelm/benchmark_output/runs",
        version="v2.0.0", tau="medical-qa", snapshot_date="2025-05",
        citation=(
            "Bedi et al. 2025, MedHELM, arXiv 2505.23802. "
            "HELM medical leaderboard v2.0.0, Stanford CRFM. "
            "https://crfm.stanford.edu/helm/medhelm/"
        ),
    ),
    _helm_spec("classic", "general-qa-classic"),
    _helm_spec("mmlu", "mmlu"),
    _helm_spec("reasoning", "reasoning"),
    _helm_spec("finance", "finance-qa"),
    _helm_spec("long-context", "long-context"),
    _helm_spec("thaiexam", "thai-exam"),
    _helm_spec("cleva", "chinese-eval"),
    _helm_spec("ewok", "world-knowledge"),
    _helm_spec("mmlu-winogrande-afr", "african-lang"),
    _helm_spec("capabilities", "capabilities"),
    _helm_spec("safety", "safety"),
    _helm_spec("air-bench", "air-safety"),
    _helm_spec("arabic-enterprise", "arabic-enterprise"),
    _helm_spec("torr", "torr"),
]


class HelmSuiteSeeder:
    """Download a HELM suite's real data and insert into the APT substrate."""

    def __init__(
        self,
        substrate: Substrate,
        spec: SuiteSpec,
        limit: int | None = None,
        verbose: bool = True,
    ) -> None:
        self.substrate = substrate
        self.spec = spec
        self.limit = limit
        self.verbose = verbose
        self._client = HelmSuiteClient(spec.suite_prefix)
        self._parser = HelmSuiteParser()

    def _resolve_version(self) -> str:
        """Return the spec version, resolving 'latest' to the max version on GCS."""
        if self.spec.version != "latest":
            return self.spec.version
        versions = self._client.list_versions()
        if not versions:
            raise ValueError(f"no versions found for suite {self.spec.name!r}")
        return versions[-1]  # list_versions returns sorted ascending

    def seed(self) -> SeedReport:
        # Resolve 'latest' to a concrete version and reassign the spec so every
        # downstream reference (fetch, evidence_id, snapshot) uses the same version.
        version = self._resolve_version()
        if version != self.spec.version:
            self.spec = SuiteSpec(**{**self.spec.__dict__, "version": version})
        report = SeedReport(version=f"{self.spec.name}-{version}")
        session = self.substrate._session

        self._log(f"Fetching {self.spec.name} run list ({version}) …")
        run_names = self._client.list_run_names(version)
        if self.limit:
            run_names = run_names[: self.limit]
        self._log(f"  Found {len(run_names)} run directories")

        self._insert_source(session)
        parsed = self._fetch_and_parse(run_names, report)
        report.runs_fetched = len(parsed)

        groups = self._parser.group_by_model(parsed)
        self._log(f"\nInserting {len(groups)} models …")
        for model_id, model_runs in sorted(groups.items()):
            inserted = self._seed_model(session, model_id, model_runs, report)
            report.observations_inserted += inserted
            if self.verbose:
                print(f"  {model_id:<48} +{inserted} obs")
            report.models_seeded += 1

        session.commit()
        return report

    def _fetch_and_parse(
        self, run_names: list[str], report: SeedReport
    ) -> list[ParsedRun]:
        parsed: list[ParsedRun] = []
        total = len(run_names)
        for i, run_name in enumerate(run_names, 1):
            if self.verbose and i % 50 == 0:
                print(f"  [{i}/{total}] fetching …")
            try:
                raw = self._client.fetch_stats(self.spec.version, run_name)
                parsed.append(self._parser.parse_run(self.spec.version, run_name, raw))
            except FileNotFoundError:
                report.runs_skipped += 1
            except Exception as exc:  # noqa: BLE001
                report.runs_skipped += 1
                report.errors.append(f"error {run_name}: {exc}")
        return parsed

    def _insert_source(self, session: Session) -> None:
        session.execute(
            sqlite_insert(Source).values(
                evidence_id=self.spec.evidence_id,
                source_type="leaderboard",
                citation=self.spec.citation,
                snapshot_version=f"{self.spec.version}-{self.spec.snapshot_date}",
            ).on_conflict_do_nothing()
        )

    def _seed_model(
        self, session: Session, model_id: str, model_runs: ModelRuns, report: SeedReport
    ) -> int:
        canonical = model_runs.all_runs[0].directory.canonical_model_id
        provider, model_name = canonical.split("/", 1)
        config_id = f"{self.spec.name}-{model_id}"

        session.execute(sqlite_insert(Component).values(
            id=f"provider-{provider}", kind="provider", name=provider
        ).on_conflict_do_nothing())
        session.execute(sqlite_insert(Component).values(
            id=f"model-{model_id}", kind="model", name=model_name
        ).on_conflict_do_nothing())
        session.execute(sqlite_insert(Config).values(
            id=config_id, tau=self.spec.tau
        ).on_conflict_do_nothing())
        session.execute(sqlite_insert(ConfigComponent).values(
            config_id=config_id, component_id=f"provider-{provider}"
        ).on_conflict_do_nothing())
        session.execute(sqlite_insert(ConfigComponent).values(
            config_id=config_id, component_id=f"model-{model_id}"
        ).on_conflict_do_nothing())

        inserted = 0
        ev = self.spec.evidence_id
        for scenario_type, runs in model_runs.runs_by_scenario.items():
            # quality (M) — aggregate across any subset runs of this scenario.
            # GUARD: only store metrics on the canonical [0,1] accuracy scale, to keep the
            # quality axis comparable with every other source. MedHELM open-ended scenarios
            # use 1–5 LLM-jury "accuracy" — different scale — so we SKIP them (logged) rather
            # than corrupt the axis. The metric name is recorded for audit.
            scored = [
                (r.quality_score, r.quality_metric_name)
                for r in runs if r.quality_score is not None
            ]
            if scored:
                score = sum(s for s, _ in scored) / len(scored)
                metric = scored[0][1]
                if 0.0 <= score <= 1.0:
                    session.execute(sqlite_insert(ObsORM).values(
                        obs_id=f"obs-{config_id}-quality-{scenario_type}-{ev}",
                        config_id=config_id, axis="quality",
                        value_num=round(score, 6), value_cat=None, confidence="M",
                        evidence_id=ev, hardware_tier=self.spec.hardware_tier,
                        dataset=scenario_type, split="test",
                        decoding_cfg=f"greedy;metric={metric}",
                        obs_date=self.spec.snapshot_date,
                    ).on_conflict_do_nothing())
                    report.axes_coverage["quality"] = (
                        report.axes_coverage.get("quality", 0) + 1
                    )
                    inserted += 1
                else:
                    report.errors.append(
                        f"skip non-[0,1] quality {config_id}/{scenario_type}="
                        f"{score:.3f} (metric={metric}, off-scale jury rating)"
                    )
            # latency_p95 (L) — inference_runtime mean, honestly flagged not-p95
            lats = [r.latency_mean_s for r in runs if r.latency_mean_s is not None]
            if lats:
                latency_ms = round((sum(lats) / len(lats)) * 1000, 3)
                session.execute(sqlite_insert(ObsORM).values(
                    obs_id=f"obs-{config_id}-latency_p95-{scenario_type}-{ev}",
                    config_id=config_id, axis="latency_p95",
                    value_num=latency_ms, value_cat=None, confidence="L",
                    evidence_id=ev, hardware_tier=self.spec.hardware_tier,
                    dataset=scenario_type, split="test", decoding_cfg="mean-not-p95",
                    obs_date=self.spec.snapshot_date,
                ).on_conflict_do_nothing())
                report.axes_coverage["latency_p95"] = (
                    report.axes_coverage.get("latency_p95", 0) + 1
                )
                inserted += 1
        return inserted

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg)


def seed(
    db_path: Path = DB_PATH,
    suite: str = "medhelm",
    version: str | None = None,
    limit: int | None = None,
    verbose: bool = True,
) -> SeedReport:
    """Seed one suite by name (from SUITES). Idempotent."""
    spec = next((s for s in SUITES if s.name == suite), None)
    if spec is None:
        raise ValueError(f"unknown suite {suite!r}; known: {[s.name for s in SUITES]}")
    if version is not None:
        spec = SuiteSpec(**{**spec.__dict__, "version": version})

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    sub = Substrate(db_path)
    try:
        report = HelmSuiteSeeder(sub, spec, limit=limit, verbose=verbose).seed()
    finally:
        sub.close()
    report.print()
    return report
