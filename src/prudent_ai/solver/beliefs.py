"""Belief derivation — Agg_φ(O_E(x,a) | κ).

Implements §3.2 of the P0 formalism: the substrate stores raw observations;
the *belief* is a derived object computed at solve time by an aggregation
operator φ the solver chooses, under a confidence filter κ.

This module is **solver-side** (C7). It never touches the database — it only
transforms the observation lists that `Substrate.cell()` returns.

Two aggregation modes are provided (the solver picks one):
  φ = interval : B_E = [min val, max val] over κ-filtered observations.
  φ = point    : B_E = median val over κ-filtered observations.

Missingness is *derived and relative to κ* (§3.2):
  B_E(x,a) = ⊥  ⇔  the κ-filtered observation set is empty.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from statistics import median
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prudent_ai.substrate import Observation

# Default confidence policy (C4): high + medium; low is opt-in.
DEFAULT_KAPPA: tuple[str, ...] = ("H", "M")


class Phi(StrEnum):
    """Aggregation mode chosen by the solver."""

    INTERVAL = "interval"
    POINT = "point"


@dataclass(frozen=True)
class Belief:
    """A derived belief about cell (x, a).

    is_bottom=True  → ⊥ (no κ-qualifying evidence). lo/hi/point are None.
    is_bottom=False → numeric belief with [lo, hi] interval and a point estimate.
    n_obs           → number of κ-qualifying observations it was derived from.
    """

    is_bottom: bool
    lo: float | None = None
    hi: float | None = None
    point: float | None = None
    n_obs: int = 0

    @property
    def is_present(self) -> bool:
        return not self.is_bottom


BOTTOM = Belief(is_bottom=True)


def kappa_filter(
    observations: list[Observation], kappa: tuple[str, ...]
) -> list[Observation]:
    """Keep only observations whose confidence tier is in κ.

    This *is* constraint C4 realized as a filter (§3.2), not a stored flag.
    """
    return [o for o in observations if o.confidence in kappa]


def aggregate(
    observations: list[Observation],
    kappa: tuple[str, ...] = DEFAULT_KAPPA,
    phi: Phi = Phi.INTERVAL,
) -> Belief:
    """Derive B_E(x,a) = Agg_φ(O_E(x,a) | κ).

    Args:
        observations: the raw observation list from Substrate.cell(x, a).
        kappa: confidence tiers the solver accepts (default H+M).
        phi: aggregation mode (interval or point).

    Returns:
        Belief — BOTTOM if the κ-filtered set is empty, else a numeric belief.
    """
    kept = kappa_filter(observations, kappa)
    # Only numeric observations participate (value_num present).
    vals = [o.value_num for o in kept if o.value_num is not None]
    if not vals:
        return BOTTOM

    lo, hi = min(vals), max(vals)
    if phi is Phi.POINT:
        pt = median(vals)
    else:  # INTERVAL — point estimate is the interval midpoint, kept for ranking
        pt = (lo + hi) / 2.0
    return Belief(is_bottom=False, lo=lo, hi=hi, point=pt, n_obs=len(vals))
