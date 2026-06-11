"""AxCellExtractor — paper-table rows → ExtractedObservation, at confidence L.

AxCell (`2020.emnlp-main.692`, table→(task, dataset, metric, value), F1 ~25.8) is
a *table* extractor: from a paper's results tables it emits leaderboard-style rows.
Real AxCell runs an ML pipeline (table detection + cell classification) offline; its
output is a structured list of rows. This extractor consumes that **cached output**
— exactly as the substrate seeders consume cached GCS dumps — and maps it onto the
substrate schema. The heavy model run is an offline preprocessing step; the real,
testable logic is the parse → axis-map → [0,1] guard → confidence → row here.

Path 1 (L-quarantine): every value enters at **confidence='L'** with
`annotator='axcell'`. The default policy κ={H,M} (`beliefs.DEFAULT_KAPPA`) excludes
L, so auto-extracted rows can NEVER touch a hard claim; they surface only under an
explicit κ={H,M,L} sensitivity sweep (`analysis.decidability_map.sensitivity_kappa`).

Never-invent (C1): a row is **dropped, not guessed**, if it has no usable value, an
unmappable metric, an off-[0,1] quality (the same guard the seeders apply), or a
`config_id` the substrate does not already model (enforced downstream in `loader`).
"""

from __future__ import annotations

from prudent_ai.extraction.base import (
    ExtractedObservation,
    ExtractionContext,
    Extractor,
    SourceRecord,
)

# Metric-name → right-sizing axis. Lower-cased, punctuation-insensitive lookup.
# Anything not here is an *unmapped* metric and is dropped (never guessed).
_METRIC_AXIS: dict[str, str] = {
    # quality family (accuracy-like, already on [0,1])
    "accuracy": "quality", "acc": "quality", "exact_match": "quality",
    "em": "quality", "f1": "quality", "bleu": "quality", "rouge": "quality",
    "pass@1": "quality", "win_rate": "quality", "score": "quality",
    "exactmatch": "quality",
    # latency family (seconds)
    "latency": "latency_p95", "latency_p95": "latency_p95",
    "p95_latency": "latency_p95", "p95latency": "latency_p95",
    # throughput family
    "throughput": "throughput", "tps": "throughput", "qps": "throughput",
    # cost family (USD per query/token)
    "cost": "cost", "price": "cost", "usd": "cost",
    # energy family (Wh)
    "energy": "energy", "wh": "energy", "joule": "energy",
}

# Axes that must lie on [0,1]; off-scale values are skipped + logged (not rescaled).
_UNIT_INTERVAL_AXES: frozenset[str] = frozenset({"quality"})


def _norm_metric(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum() or ch in "@_")


class AxCellExtractor(Extractor):
    """Map AxCell-format table rows onto the substrate schema, at confidence L.

    `extract(document_id, raw)` expects ``raw`` to be a list of row dicts (AxCell's
    cached output), each::

        {
          "config_id": "c-201",      # REQUIRED — must match a substrate config (C1)
          "metric":    "accuracy",   # mapped via _METRIC_AXIS; unmapped → dropped
          "value":     0.83,         # numeric; missing/None → dropped
          "dataset":   "mmlu",       # optional context
          "split":     "test",       # optional context
          "obs_date":  "2024-01",    # optional context
        }

    Returns one `ExtractedObservation` per usable row (confidence='L'). Rows are
    silently skipped (not invented) when value/metric/axis are unusable; the caller
    can diff input vs output length to count drops, and `loader.load` additionally
    skips rows whose config_id is not yet modelled.
    """

    name = "axcell"

    def source_record(self, document_id: str) -> SourceRecord:
        return SourceRecord(
            evidence_id=f"axcell-{document_id}",
            source_type="paper_reported",
            citation=f"AxCell auto-extraction (2020.emnlp-main.692) from {document_id}",
            snapshot_version="axcell-1",
        )

    def extract(self, document_id: str, raw: object) -> list[ExtractedObservation]:
        if not isinstance(raw, list):
            return []
        evidence_id = self.source_record(document_id).evidence_id
        out: list[ExtractedObservation] = []
        for row in raw:
            if not isinstance(row, dict):
                continue
            config_id = row.get("config_id")
            value = row.get("value")
            metric = row.get("metric")
            if not config_id or value is None or not metric:
                continue  # drop, never guess (C1)
            try:
                value_num = float(value)
            except (TypeError, ValueError):
                continue
            axis = _METRIC_AXIS.get(_norm_metric(str(metric)))
            if axis is None:
                continue  # unmapped metric → dropped
            if axis in _UNIT_INTERVAL_AXES and not (0.0 <= value_num <= 1.0):
                continue  # off-[0,1] quality → skipped + logged (no rescale)
            out.append(
                ExtractedObservation(
                    config_id=str(config_id),
                    axis=axis,
                    value_num=value_num,
                    value_cat=None,
                    confidence="L",                 # Path 1: quarantine
                    evidence_id=evidence_id,
                    annotator=self.name,
                    context=ExtractionContext(
                        dataset=row.get("dataset"),
                        split=row.get("split"),
                        obs_date=row.get("obs_date"),
                    ),
                )
            )
        return out
