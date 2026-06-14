"""Three-valued verdict: decidable / underdetermined / infeasible."""
from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
from .interface import cell, required_fields
from .belief import Belief

class Verdict(Enum):
    DECIDABLE = "decidable"
    UNDERDETERMINED = "underdetermined"
    INFEASIBLE = "infeasible"

@dataclass
class VerdictResult:
    verdict: Verdict
    composition_id: str
    binding_axes: list[str] = field(default_factory=list)
    missing_axes: list[str] = field(default_factory=list)
    quality: Optional[float] = None
    latency_ms: Optional[float] = None
    cost_per_1k: Optional[float] = None

def assess(composition_id: str, quality_min: float = 0.0,
           latency_max: float = float("inf"),
           cost_max: float = float("inf"),
           pattern: Optional[str] = None, db_path=None) -> VerdictResult:
    """Assess a composition against constraints. Returns three-valued verdict."""
    req = required_fields(pattern or "bare_llm")
    missing, binding = [], []

    q_b = cell(composition_id, "quality", db_path=db_path)
    l_b = cell(composition_id, "latency_p95_ms", db_path=db_path)
    c_b = cell(composition_id, "cost_per_1k_tokens", db_path=db_path)

    if q_b.is_bot and "quality" in req: missing.append("quality")
    if l_b.is_bot and "latency_p95_ms" in req: missing.append("latency_p95_ms")
    if c_b.is_bot and "cost_per_1k_tokens" in req: missing.append("cost_per_1k_tokens")

    if missing:
        return VerdictResult(Verdict.UNDERDETERMINED, composition_id, missing_axes=missing)

    # Check binding constraints (use worst-case interval endpoint)
    q_val = q_b.lo  # pessimistic quality = lower bound
    l_val = l_b.hi  # pessimistic latency = upper bound
    c_val = c_b.hi  # pessimistic cost = upper bound

    if q_val is not None and q_val < quality_min:
        binding.append("quality")
    if l_val is not None and l_val > latency_max:
        binding.append("latency_p95_ms")
    if c_val is not None and c_val > cost_max:
        binding.append("cost_per_1k_tokens")

    if binding:
        return VerdictResult(Verdict.INFEASIBLE, composition_id,
                             binding_axes=binding,
                             quality=q_val, latency_ms=l_val, cost_per_1k=c_val)

    return VerdictResult(Verdict.DECIDABLE, composition_id,
                         quality=q_val, latency_ms=l_val, cost_per_1k=c_val)
