"""Min-sufficiency guarantee via a two-sided commit band (W4 residual, real GT).

The real-GT feasibility guarantee (`gt_guarantee.py`) calibrates the §9 *safety* half —
P(committed feasible) ≥ 1−α — with a one-sided quality margin `m`. It cannot calibrate
the *min-sufficiency* half: a larger `m` makes feasibility safer but pushes the procedure
to **over-provision** (skip a cheaper config whose noisy quality dipped below the
margin), so min-sufficiency risk *rises* with `m` (43.8% → 83.8% across the margin
sweep). A single one-sided knob cannot control a two-sided (feasible ∧ cheapest)
criterion — the documented W4 residual.

This module closes it with a **second, two-sided knob**: a commit **band** `b`. After
selecting the min-noisy-cost eligible config `x` (noisy_q ≥ q*+m), commit only if **no
strictly-cheaper config is plausibly feasible** (noisy_q ≥ q*−b); otherwise ABSTAIN —
we cannot rule out that a cheaper config is the true minimum-sufficient choice, so
committing `x` would risk over-provisioning. Larger `b` ⇒ abstain whenever a cheaper
config is even borderline-feasible ⇒ the commits that remain are confidently
min-sufficient (lower min-suff risk, lower coverage). `m` controls feasibility, `b`
controls min-sufficiency — two knobs for the two-sided criterion.

Jointly calibrating `(m, b)` on a held-out real-GT split (C8, disjoint calib/test) then
*guarantees* min-sufficiency risk ≤ α on TEST, at a quantified coverage cost. Truth =
full-sample per-prompt RouterBench; operating = seeded subsample. Direct pkl scoring →
C7 not engaged (same posture as `gt_guarantee.py`).
"""

from __future__ import annotations

from dataclasses import dataclass

from prudent_ai.validation.gt_guarantee import (
    COST_TOL,
    MODELS,
    Decision,
    GTCoverageGuarantee,
    Outcome,
)

# (margin, band) grids. margin = one-sided feasibility knob; band = two-sided
# min-sufficiency knob (abstain when a cheaper config is within `band` below q*).
DEFAULT_MARGINS: tuple[float, ...] = (0.0, 0.01, 0.02, 0.03, 0.05, 0.07, 0.10)
DEFAULT_BANDS: tuple[float, ...] = (0.0, 0.02, 0.05, 0.08, 0.12, 0.18, 0.25, 0.35)


def decide_two_sided(
    o: Outcome, margin: float, band: float, cost_tol: float = COST_TOL,
) -> Decision:
    """Commit min-noisy-cost config clearing q*+margin, abstaining if a strictly
    cheaper config is plausibly feasible (noisy_q ≥ q*−band).

    Scored against TRUTH exactly as `Outcome.decide`: feasible (true quality ≥ q*) and
    min_sufficient (true cost ≤ (1+cost_tol)·true min-cost-feasible).
    """
    eligible = [m for m in MODELS if o.noisy_quality[m] >= o.q_star + margin]
    if not eligible:
        return Decision(committed=False, feasible=False, min_sufficient=False)
    committed = min(eligible, key=lambda m: o.noisy_cost[m])
    cc = o.noisy_cost[committed]
    # two-sided guard: a strictly cheaper, plausibly-feasible config ⇒ we cannot be
    # sure `committed` is minimum-sufficient ⇒ abstain.
    for m in MODELS:
        if o.noisy_cost[m] < cc - 1e-12 and o.noisy_quality[m] >= o.q_star - band:
            return Decision(committed=False, feasible=False, min_sufficient=False)
    feasible = o.truth_quality[committed] >= o.q_star
    min_sufficient = feasible and (
        o.truth_cost[committed] <= o.truth_min_cost * (1.0 + cost_tol) + 1e-12
    )
    return Decision(committed=True, feasible=feasible, min_sufficient=min_sufficient)


@dataclass(frozen=True)
class BandCurvePoint:
    margin: float
    band: float
    coverage: float
    risk_feasible: float        # P(commit not feasible | commit)
    risk_min_sufficient: float  # P(commit not min-sufficient | commit) — the W4-residual target
    n_queries: int
    n_commit: int
    n_feasible: int
    n_min_sufficient: int


@dataclass(frozen=True)
class BandCalibration:
    alpha: float
    margin: float | None
    band: float | None
    calib_coverage: float
    calib_risk_min_sufficient: float
    test_coverage: float
    test_risk_feasible: float
    test_risk_min_sufficient: float   # the guaranteed quantity on held-out TEST
    test_n_queries: int
    test_n_commit: int
    test_n_min_sufficient: int


class MinSuffGuarantee(GTCoverageGuarantee):
    """Two-sided-band min-sufficiency guarantee (W4 residual) on real GT."""

    @staticmethod
    def band_point(outcomes: list[Outcome], margin: float, band: float) -> BandCurvePoint:
        n_commit = n_feasible = n_min_sufficient = 0
        for o in outcomes:
            d = decide_two_sided(o, margin, band)
            if d.committed:
                n_commit += 1
                n_feasible += int(d.feasible)
                n_min_sufficient += int(d.min_sufficient)
        n = len(outcomes)
        return BandCurvePoint(
            margin=margin, band=band,
            coverage=(n_commit / n if n else 0.0),
            risk_feasible=((n_commit - n_feasible) / n_commit if n_commit else 0.0),
            risk_min_sufficient=(
                (n_commit - n_min_sufficient) / n_commit if n_commit else 0.0
            ),
            n_queries=n, n_commit=n_commit,
            n_feasible=n_feasible, n_min_sufficient=n_min_sufficient,
        )

    def calibrate_min_sufficient(
        self,
        calib: list[Outcome],
        test: list[Outcome],
        alpha: float,
        margins: tuple[float, ...] = DEFAULT_MARGINS,
        bands: tuple[float, ...] = DEFAULT_BANDS,
    ) -> BandCalibration:
        """Pick the (m, b) with calib MIN-SUFFICIENCY risk ≤ α maximizing calib coverage,
        then report TEST min-sufficiency risk (the held-out guarantee). If none meets the
        bound, report the lowest-min-suff-risk committing point and flag margin/band=None.
        """
        best: BandCurvePoint | None = None
        for m in margins:
            for b in bands:
                cp = self.band_point(calib, m, b)
                if cp.n_commit > 0 and cp.risk_min_sufficient <= alpha:
                    if best is None or cp.coverage > best.coverage:
                        best = cp
        meets = best is not None
        if best is None:
            committing = [
                self.band_point(calib, m, b) for m in margins for b in bands
            ]
            committing = [p for p in committing if p.n_commit > 0]
            best = (
                min(committing, key=lambda p: p.risk_min_sufficient)
                if committing else None
            )
        if best is None:
            return BandCalibration(
                alpha=alpha, margin=None, band=None,
                calib_coverage=0.0, calib_risk_min_sufficient=0.0,
                test_coverage=0.0, test_risk_feasible=0.0,
                test_risk_min_sufficient=0.0, test_n_queries=len(test),
                test_n_commit=0, test_n_min_sufficient=0,
            )
        test_pt = self.band_point(test, best.margin, best.band)
        return BandCalibration(
            alpha=alpha,
            margin=best.margin if meets else None,
            band=best.band if meets else None,
            calib_coverage=best.coverage,
            calib_risk_min_sufficient=best.risk_min_sufficient,
            test_coverage=test_pt.coverage,
            test_risk_feasible=test_pt.risk_feasible,
            test_risk_min_sufficient=test_pt.risk_min_sufficient,
            test_n_queries=test_pt.n_queries,
            test_n_commit=test_pt.n_commit,
            test_n_min_sufficient=test_pt.n_min_sufficient,
        )
