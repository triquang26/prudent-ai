"""Belief representation: kappa-filter, phi-interval, derived bottom (undefined)."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

KAPPA_LEVELS = {"high": 3, "medium": 2, "low": 1}

@dataclass
class Belief:
    lo: Optional[float] = None
    hi: Optional[float] = None
    is_bot: bool = False  # ⊥ = no evidence at this axis
    confidence: str = "medium"

    @classmethod
    def bot(cls):
        return cls(is_bot=True)

    @classmethod
    def point(cls, v, conf="high"):
        return cls(lo=v, hi=v, confidence=conf)

    @classmethod
    def interval(cls, lo, hi, conf="medium"):
        return cls(lo=lo, hi=hi, confidence=conf)

    def satisfies_ge(self, threshold) -> Optional[bool]:
        if self.is_bot: return None  # underdetermined
        if self.lo is None: return None
        if self.lo >= threshold: return True
        if self.hi is not None and self.hi < threshold: return False
        return None  # interval straddles threshold

    def satisfies_le(self, threshold) -> Optional[bool]:
        if self.is_bot: return None
        if self.hi is None: return None
        if self.hi <= threshold: return True
        if self.lo is not None and self.lo > threshold: return False
        return None


def kappa_filter(rows, min_kappa="medium"):
    """Filter evidence rows by confidence level >= min_kappa."""
    min_level = KAPPA_LEVELS.get(min_kappa, 2)
    return [r for r in rows if KAPPA_LEVELS.get(r.get("confidence", "low"), 1) >= min_level]


def phi_interval(values: list[float]) -> tuple[float, float]:
    """Return [min, max] interval over a set of values."""
    if not values:
        raise ValueError("empty values")
    return (min(values), max(values))


def aggregate_belief(rows, axis, min_kappa="medium") -> Belief:
    """Aggregate benchmark_run rows for a given axis into a Belief."""
    filtered = kappa_filter(rows, min_kappa)
    vals = [r[axis] for r in filtered if r.get(axis) is not None]
    if not vals:
        return Belief.bot()
    lo, hi = phi_interval(vals)
    conf = "high" if len(vals) >= 3 else "medium" if len(vals) >= 1 else "low"
    return Belief.interval(lo, hi, conf)
