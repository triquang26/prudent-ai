"""Extractor registry — the plug-in point for paper-row extractors (mirror of substrate/registry).

Empty by design until the first extractor is implemented. To add one:
  1. Subclass `Extractor` in `extraction/<name>.py` (implement source_record + extract).
  2. Append it to `EXTRACTOR_REGISTRY` below.
The loader (`extraction/loader.load`) and QC (`extraction/quality`) then apply
unchanged — extraction scales the same way structured sources do.
"""

from __future__ import annotations

from prudent_ai.extraction.base import Extractor

# To register: EXTRACTOR_REGISTRY.append(AXCELLExtractor())
EXTRACTOR_REGISTRY: list[Extractor] = []


def registry_by_name() -> dict[str, Extractor]:
    return {e.name: e for e in EXTRACTOR_REGISTRY}
