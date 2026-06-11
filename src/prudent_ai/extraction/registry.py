"""Extractor registry — the plug-in point for paper-row extractors (mirror of substrate/registry).

To add another extractor:
  1. Subclass `Extractor` in `extraction/<name>.py` (implement source_record + extract).
  2. Append it to `EXTRACTOR_REGISTRY` below.
The loader (`extraction/loader.load`) and QC (`extraction/quality`) then apply
unchanged — extraction scales the same way structured sources do.
"""

from __future__ import annotations

from prudent_ai.extraction.axcell import AxCellExtractor
from prudent_ai.extraction.base import Extractor
from prudent_ai.extraction.mole import MOLEExtractor

# Two independent auto-extractors. Both emit at confidence L (Path 1 quarantine);
# `agreement.cross_agreement` cross-checks them to promote concurring cells to M
# (Path 2). Adding another extractor = subclass `Extractor` + append it here.
EXTRACTOR_REGISTRY: list[Extractor] = [AxCellExtractor(), MOLEExtractor()]


def registry_by_name() -> dict[str, Extractor]:
    return {e.name: e for e in EXTRACTOR_REGISTRY}
