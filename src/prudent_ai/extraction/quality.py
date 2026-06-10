"""Extraction QC — inter-annotator agreement (κ) + error rate (the P2 gate, C5).

The master plan's P2 gate (§15) requires an **IAA / κ** report and an
**extraction error-rate** before paper-row evidence counts. Those need annotated
data (two annotators, a gold set) that does not exist yet — so this module is the
ready-to-use computation, written against `ExtractedObservation` lists so it works
the moment annotation data arrives, with no schema change.

  - cohen_kappa(a, b): agreement between two annotators on the cells they both
    extracted (categorical match on the rounded value), corrected for chance (C5).
  - extraction_error_rate(pred, gold): fraction of predicted values that disagree
    with the gold set, per axis and overall (the precision-on-gold check, §15-P2).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prudent_ai.extraction.base import ExtractedObservation


def _cell_key(o: ExtractedObservation) -> tuple[str, str]:
    return (o.config_id, o.axis)


def _value_token(o: ExtractedObservation, ndigits: int = 4) -> str:
    if o.value_cat is not None:
        return f"cat:{o.value_cat}"
    if o.value_num is not None:
        return f"num:{round(o.value_num, ndigits)}"
    return "⊥"


@dataclass(frozen=True)
class KappaReport:
    n_shared_cells: int
    observed_agreement: float
    expected_agreement: float
    kappa: float


def cohen_kappa(
    annotator_a: list[ExtractedObservation],
    annotator_b: list[ExtractedObservation],
    ndigits: int = 4,
) -> KappaReport:
    """Cohen's κ between two annotators over the cells they both extracted.

    Agreement = identical value token on a shared (config, axis) cell. Returns κ=1.0
    on perfect agreement, 0.0 at chance, <0 below chance. C5: report κ; a cell is
    `reviewed`/H only where annotators concur.
    """
    a = {_cell_key(o): _value_token(o, ndigits) for o in annotator_a}
    b = {_cell_key(o): _value_token(o, ndigits) for o in annotator_b}
    shared = sorted(set(a) & set(b))
    n = len(shared)
    if n == 0:
        return KappaReport(0, 0.0, 0.0, 0.0)

    agree = sum(1 for k in shared if a[k] == b[k])
    p_o = agree / n

    # chance agreement from each annotator's marginal token distribution
    da: dict[str, int] = defaultdict(int)
    db: dict[str, int] = defaultdict(int)
    for k in shared:
        da[a[k]] += 1
        db[b[k]] += 1
    p_e = sum((da[t] / n) * (db.get(t, 0) / n) for t in da)

    kappa = 1.0 if p_e == 1.0 else (p_o - p_e) / (1.0 - p_e)
    return KappaReport(n, p_o, p_e, kappa)


@dataclass(frozen=True)
class ErrorRateReport:
    n_gold: int
    n_matched: int
    n_wrong: int
    overall_error_rate: float
    per_axis: dict[str, float]


def extraction_error_rate(
    predicted: list[ExtractedObservation],
    gold: list[ExtractedObservation],
    ndigits: int = 4,
) -> ErrorRateReport:
    """Fraction of gold cells the extractor got wrong (value mismatch or missed).

    The §15-P2 precision-on-gold check: over the gold set, a predicted value is
    correct iff it matches the gold token on the same (config, axis) cell.
    """
    pred = {_cell_key(o): _value_token(o, ndigits) for o in predicted}
    gold_map = {_cell_key(o): _value_token(o, ndigits) for o in gold}

    axis_total: dict[str, int] = defaultdict(int)
    axis_wrong: dict[str, int] = defaultdict(int)
    wrong = 0
    for k, gtok in gold_map.items():
        axis = k[1]
        axis_total[axis] += 1
        if pred.get(k) != gtok:        # missed (None) or mismatched
            wrong += 1
            axis_wrong[axis] += 1

    n = len(gold_map)
    per_axis = {ax: axis_wrong[ax] / axis_total[ax] for ax in axis_total}
    return ErrorRateReport(
        n_gold=n, n_matched=n - wrong, n_wrong=wrong,
        overall_error_rate=(wrong / n if n else 0.0), per_axis=per_axis,
    )
