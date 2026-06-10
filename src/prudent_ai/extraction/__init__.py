"""Extraction scaffolding — the plug-in seam for paper-row evidence (deferred content).

Adding an extractor later = subclass `Extractor`, register it, done. `loader.load`
writes into the same substrate tables; `quality` computes the κ / error-rate QC.
"""

from prudent_ai.extraction.base import (
    ExtractedObservation,
    ExtractionContext,
    Extractor,
    SourceRecord,
)
from prudent_ai.extraction.loader import LoadReport, load
from prudent_ai.extraction.quality import (
    ErrorRateReport,
    KappaReport,
    cohen_kappa,
    extraction_error_rate,
)
from prudent_ai.extraction.registry import EXTRACTOR_REGISTRY

__all__ = [
    "EXTRACTOR_REGISTRY",
    "ErrorRateReport",
    "ExtractedObservation",
    "ExtractionContext",
    "Extractor",
    "KappaReport",
    "LoadReport",
    "SourceRecord",
    "cohen_kappa",
    "extraction_error_rate",
    "load",
]
