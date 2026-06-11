"""Extraction — paper-row evidence ingested at confidence L, promoted to M by consensus.

Two independent auto-extractors (`AxCellExtractor`, `MOLEExtractor`) turn cached
extractor output into `ExtractedObservation`s at **confidence L** (Path 1 quarantine
— excluded by the default κ={H,M}, so hard claims stay clean). `cross_agreement`
promotes cells the two concur on to **M** (Path 2 — a machine inter-annotator proxy,
weaker than the human κ-gate C5). `loader.load` writes both into the same
`source`/`observation` tables; `quality` computes the κ / error-rate QC.
"""

from prudent_ai.extraction.agreement import (
    AgreementReport,
    cross_agreement,
    per_axis_promotion,
)
from prudent_ai.extraction.axcell import AxCellExtractor
from prudent_ai.extraction.base import (
    ExtractedObservation,
    ExtractionContext,
    Extractor,
    SourceRecord,
)
from prudent_ai.extraction.loader import LoadReport, load
from prudent_ai.extraction.mole import MOLEExtractor
from prudent_ai.extraction.quality import (
    ErrorRateReport,
    KappaReport,
    cohen_kappa,
    extraction_error_rate,
)
from prudent_ai.extraction.registry import EXTRACTOR_REGISTRY, registry_by_name

__all__ = [
    "EXTRACTOR_REGISTRY",
    "AgreementReport",
    "AxCellExtractor",
    "ErrorRateReport",
    "ExtractedObservation",
    "ExtractionContext",
    "Extractor",
    "KappaReport",
    "LoadReport",
    "MOLEExtractor",
    "SourceRecord",
    "cohen_kappa",
    "cross_agreement",
    "extraction_error_rate",
    "load",
    "per_axis_promotion",
    "registry_by_name",
]
