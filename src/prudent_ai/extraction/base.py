"""Extraction scaffolding — the plug-in seam for paper-row evidence (P2 tail).

The current substrate is fed by *structured* sources (leaderboards, benchmark
JSON) via `substrate/<source>/seeder.py`. The master plan's long tail
(§13) is **paper-row extraction**: pulling (config, axis, value) tuples from PDFs
semi-automatically, with human review and an inter-annotator agreement (κ) check
(constraints C1/C4/C5). That content is deferred — but the *seam* is built here so
adding an extractor later is "just implement the ABC + register it", exactly like
adding a structured source.

An `Extractor` turns a raw document into `ExtractedObservation`s with provenance
and a confidence tier; `extraction/loader.py` writes them into the same
`observation`/`source` tables the seeders use (so nothing downstream changes).
`extraction/quality.py` computes the κ / error-rate QC the P2 gate requires once
two annotators exist.

Implementations to fill in later (each = one subclass):
  - GROBIDExtractor   (PDF → TEI structure)            grobidOrg/grobid
  - AXCELLExtractor   (table → (task,dataset,metric,value)) 2020.emnlp-main.692 (F1 25.8)
  - MOLEExtractor     (schema-driven LLM extraction)   arXiv 2505.19800 (~67%)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExtractionContext:
    """Provenance + comparison context carried with every extracted value (C2/C6)."""

    hardware_tier: str | None = None
    dataset: str | None = None
    split: str | None = None
    decoding_cfg: str | None = None
    obs_date: str | None = None


@dataclass(frozen=True)
class ExtractedObservation:
    """One (config, axis, value) tuple pulled from a document.

    Maps 1:1 onto an `observation` row. `annotator` records WHO extracted it, so
    `quality.py` can compute inter-annotator agreement (κ, constraint C5). A value
    becomes `confidence='H'` only after a second annotator confirms it (C5); a
    single-pass auto-extraction is `'L'`/`'M'` per the confidence policy (C4).
    """

    config_id: str
    axis: str
    value_num: float | None
    value_cat: str | None
    confidence: str                       # 'H' | 'M' | 'L'
    evidence_id: str                      # FK target in `source`
    annotator: str = "auto"               # who produced it (for κ); 'auto' = unreviewed
    context: ExtractionContext = field(default_factory=ExtractionContext)


@dataclass(frozen=True)
class SourceRecord:
    """Provenance row the extractor declares for its document (maps onto `source`)."""

    evidence_id: str
    source_type: str                      # e.g. 'paper_reported'
    citation: str
    snapshot_version: str


class Extractor(ABC):
    """A paper-row extractor: raw document → provenance + extracted observations.

    Subclass and implement `source_record()` + `extract()`. Then register it in
    `extraction/registry.py` (mirrors `substrate/registry.py`). The loader takes it
    from there — no schema or downstream change.
    """

    #: short id, e.g. "axcell"; set on the subclass.
    name: str = "extractor"

    @abstractmethod
    def source_record(self, document_id: str) -> SourceRecord:
        """Return the provenance row for *document_id* (one `source` row)."""

    @abstractmethod
    def extract(self, document_id: str, raw: object) -> list[ExtractedObservation]:
        """Parse *raw* (PDF bytes / TEI / table dict) into extracted observations.

        Implementations MUST NOT invent numbers (constraint C1): a value with no
        clear source is dropped, not guessed. Set confidence per C4 (auto → L/M;
        H only after review). Carry the comparison context (C6).
        """
