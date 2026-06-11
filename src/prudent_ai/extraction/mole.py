"""MOLEExtractor — schema-driven record extraction → ExtractedObservation, at L.

MOLE (arXiv `2505.19800`, schema-driven LLM extraction + validation, best ~67%) is
a *schema-driven* extractor: given a target schema it pulls the named fields from a
document. Real MOLE calls an LLM offline and validates; its output is a structured
record per document. This extractor consumes that **cached record** and maps the
schema fields onto right-sizing axes — the real, testable logic being the
schema→axis projection, the [0,1] guard, and the confidence assignment.

Like `AxCellExtractor`, every value enters at **confidence='L'** with
`annotator='mole'` (Path 1 quarantine). Two independent extractors (axcell + mole)
are what Path 2 (`agreement.cross_agreement`) cross-checks to promote concurring
cells to M — a machine inter-annotator proxy, weaker than the human κ-gate (C5).

Never-invent (C1): a field with no usable value, no axis mapping, or an off-[0,1]
quality is dropped, not guessed.
"""

from __future__ import annotations

from prudent_ai.extraction.base import (
    ExtractedObservation,
    ExtractionContext,
    Extractor,
    SourceRecord,
)

# Default schema-field → axis projection. A caller may pass a custom `schema`
# mapping to extract(); unmapped fields are dropped (never guessed).
_DEFAULT_SCHEMA: dict[str, str] = {
    "quality": "quality",
    "accuracy": "quality",
    "latency": "latency_p95",
    "latency_p95": "latency_p95",
    "throughput": "throughput",
    "cost": "cost",
    "price": "cost",
    "energy": "energy",
}

_UNIT_INTERVAL_AXES: frozenset[str] = frozenset({"quality"})


class MOLEExtractor(Extractor):
    """Project MOLE-format schema records onto the substrate schema, at confidence L.

    `extract(document_id, raw)` expects ``raw`` to be a list of record dicts::

        {
          "config_id": "c-201",                 # REQUIRED — must match a config (C1)
          "fields": {"quality": 0.82, "cost": 1.1},  # field → value (schema-driven)
          "dataset": "mmlu", "split": "test", "obs_date": "2024-01",  # optional ctx
        }

    The field→axis projection is `schema` (defaults to `_DEFAULT_SCHEMA`). Returns
    one `ExtractedObservation` per usable (record, field) pair at confidence='L'.
    """

    name = "mole"

    def source_record(self, document_id: str) -> SourceRecord:
        return SourceRecord(
            evidence_id=f"mole-{document_id}",
            source_type="paper_reported",
            citation=f"MOLE schema-driven extraction (arXiv 2505.19800) from {document_id}",
            snapshot_version="mole-1",
        )

    def extract(
        self,
        document_id: str,
        raw: object,
        schema: dict[str, str] | None = None,
    ) -> list[ExtractedObservation]:
        if not isinstance(raw, list):
            return []
        projection = schema or _DEFAULT_SCHEMA
        evidence_id = self.source_record(document_id).evidence_id
        out: list[ExtractedObservation] = []
        for rec in raw:
            if not isinstance(rec, dict):
                continue
            config_id = rec.get("config_id")
            fields = rec.get("fields")
            if not config_id or not isinstance(fields, dict):
                continue
            ctx = ExtractionContext(
                dataset=rec.get("dataset"),
                split=rec.get("split"),
                obs_date=rec.get("obs_date"),
            )
            for field, value in fields.items():
                axis = projection.get(field)
                if axis is None or value is None:
                    continue  # unmapped field / no value → dropped (C1)
                try:
                    value_num = float(value)
                except (TypeError, ValueError):
                    continue
                if axis in _UNIT_INTERVAL_AXES and not (0.0 <= value_num <= 1.0):
                    continue  # off-[0,1] quality → skipped (no rescale)
                out.append(
                    ExtractedObservation(
                        config_id=str(config_id),
                        axis=axis,
                        value_num=value_num,
                        value_cat=None,
                        confidence="L",             # Path 1: quarantine
                        evidence_id=evidence_id,
                        annotator=self.name,
                        context=ctx,
                    )
                )
        return out
