"""Write extracted observations into the substrate — same tables, same contract.

The loader is the bridge from `ExtractedObservation` (extractor output) to the
`source` / `observation` rows the seeders already use. It uses the same
`sqlite_insert(...).on_conflict_do_nothing()` idempotency, so extraction and
structured ingestion are interchangeable downstream (C7 unaffected — this only
populates the substrate, it never aggregates or certifies).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from prudent_ai.substrate.orm import Observation as ObsORM
from prudent_ai.substrate.orm import Source

if TYPE_CHECKING:
    from prudent_ai.extraction.base import ExtractedObservation, SourceRecord
    from prudent_ai.substrate import Substrate


@dataclass
class LoadReport:
    source: str = ""
    inserted: int = 0
    skipped_unknown_config: int = 0
    skipped_no_value: int = 0


def load(
    substrate: Substrate,
    source_record: SourceRecord,
    observations: list[ExtractedObservation],
) -> LoadReport:
    """Insert the provenance row + extracted observations into the substrate.

    Observations whose `config_id` is not yet a known config are skipped (counted),
    not auto-created: a paper-row value must attach to a config the substrate
    already models, or the config must be seeded first — never invented (C1).
    """
    session = substrate._session
    report = LoadReport(source=source_record.evidence_id)

    session.execute(
        sqlite_insert(Source).values(
            evidence_id=source_record.evidence_id,
            source_type=source_record.source_type,
            citation=source_record.citation,
            snapshot_version=source_record.snapshot_version,
        ).on_conflict_do_nothing()
    )

    known = {c.id for c in _all_config_ids(substrate)}
    for o in observations:
        if o.value_num is None and o.value_cat is None:
            report.skipped_no_value += 1
            continue
        if o.config_id not in known:
            report.skipped_unknown_config += 1
            continue
        obs_id = f"obs-{o.config_id}-{o.axis}-{o.evidence_id}-{o.annotator}"
        session.execute(
            sqlite_insert(ObsORM).values(
                obs_id=obs_id, config_id=o.config_id, axis=o.axis,
                value_num=o.value_num, value_cat=o.value_cat,
                confidence=o.confidence, evidence_id=o.evidence_id,
                hardware_tier=o.context.hardware_tier, dataset=o.context.dataset,
                split=o.context.split, decoding_cfg=o.context.decoding_cfg,
                obs_date=o.context.obs_date,
            ).on_conflict_do_nothing()
        )
        report.inserted += 1

    session.commit()
    return report


def _all_config_ids(substrate: Substrate):
    from sqlalchemy import select

    from prudent_ai.substrate.orm import Config
    return substrate._session.execute(select(Config)).scalars().all()
