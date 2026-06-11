"""Cross-extractor agreement — a machine inter-annotator proxy (Path 2).

The human κ-gate (C5, `quality.cohen_kappa`) promotes auto-extracted evidence to
trustworthy only where **two human annotators** concur. When humans are not
available, this module offers a *weaker, explicitly-flagged* substitute: run two
**independent** extractors (e.g. AxCell + MOLE) and promote a cell to confidence
**M** only where both extracted it and their numeric values agree within tolerance.

This is genuinely weaker than human IAA — two extractors can share a failure mode
(both misread the same malformed table), which two independent humans would not.
So a promoted value is **M, never H**: it can participate in the default policy
κ={H,M}, but the strongest (H-only) analyses still exclude it. Callers MUST surface
the `AgreementReport` so the promotion rate and its caveat are auditable.

Cells extracted by only one extractor, or where the two disagree, are **not**
promoted: their original L rows remain (quarantined, Path 1). Nothing is invented —
promotion only ever *re-grades* a value both extractors already reported (C1).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace

from prudent_ai.extraction.base import ExtractedObservation


@dataclass(frozen=True)
class AgreementReport:
    """Audit trail for a cross-extractor promotion pass.

    n_shared_cells   — (config, axis) cells both extractors reported.
    n_agreed         — shared cells whose values agree within tolerance → promoted.
    n_disagreed      — shared cells whose values differ beyond tolerance → NOT promoted.
    promotion_rate   — n_agreed / n_shared_cells (0.0 if no shared cells).
    rel_tol          — the relative tolerance used.
    """

    n_shared_cells: int
    n_agreed: int
    n_disagreed: int
    promotion_rate: float
    rel_tol: float


def _cell_key(o: ExtractedObservation) -> tuple[str, str]:
    return (o.config_id, o.axis)


def _agree(a: float, b: float, rel_tol: float) -> bool:
    """Relative agreement: |a-b| <= rel_tol * max(|a|,|b|), with an exact-zero case."""
    if a == b:
        return True
    scale = max(abs(a), abs(b))
    if scale == 0.0:
        return True
    return abs(a - b) <= rel_tol * scale


def cross_agreement(
    extractor_a: list[ExtractedObservation],
    extractor_b: list[ExtractedObservation],
    rel_tol: float = 0.05,
    consensus_id: str = "consensus",
) -> tuple[list[ExtractedObservation], AgreementReport]:
    """Promote cells two extractors agree on to confidence M (Path 2).

    For every (config, axis) cell present in BOTH inputs with numeric values that
    agree within `rel_tol`, emit one promoted `ExtractedObservation` at
    confidence='M', value = mean of the two, `annotator='consensus'`,
    `evidence_id=consensus_id`. Disagreements and single-extractor cells are not
    promoted (their L rows, loaded separately, stand).

    Returns ``(promoted, report)``. `promoted` is safe to `loader.load` alongside
    the original L rows; the consensus rows are what the default κ={H,M} policy will
    actually see. Determinism: cells are processed in sorted key order.
    """
    a_by_cell: dict[tuple[str, str], ExtractedObservation] = {}
    for o in extractor_a:
        if o.value_num is not None:
            a_by_cell.setdefault(_cell_key(o), o)
    b_by_cell: dict[tuple[str, str], ExtractedObservation] = {}
    for o in extractor_b:
        if o.value_num is not None:
            b_by_cell.setdefault(_cell_key(o), o)

    shared = sorted(set(a_by_cell) & set(b_by_cell))
    promoted: list[ExtractedObservation] = []
    n_agreed = 0
    for key in shared:
        a, b = a_by_cell[key], b_by_cell[key]
        if _agree(a.value_num, b.value_num, rel_tol):
            n_agreed += 1
            promoted.append(
                replace(
                    a,
                    value_num=(a.value_num + b.value_num) / 2.0,
                    confidence="M",                 # consensus → M (never H)
                    evidence_id=consensus_id,
                    annotator=consensus_id,
                )
            )

    n_shared = len(shared)
    report = AgreementReport(
        n_shared_cells=n_shared,
        n_agreed=n_agreed,
        n_disagreed=n_shared - n_agreed,
        promotion_rate=(n_agreed / n_shared if n_shared else 0.0),
        rel_tol=rel_tol,
    )
    return promoted, report


def per_axis_promotion(
    promoted: list[ExtractedObservation],
) -> dict[str, int]:
    """Count promoted (consensus → M) cells per axis — a descriptive breakdown."""
    out: dict[str, int] = defaultdict(int)
    for o in promoted:
        out[o.axis] += 1
    return dict(out)
