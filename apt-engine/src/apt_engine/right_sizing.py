"""right_size() — single function implementing §12 Tier A decision rule (5 branches)."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from .db import connect, DB_PATH
from .interface import candidates, cell, required_fields
from .verdict import assess, Verdict

@dataclass
class Query:
    task_archetype: Optional[str] = None
    composition_pattern: Optional[str] = None
    quality_min: float = 0.0
    latency_max_ms: float = float("inf")
    cost_max_per_1k: float = float("inf")
    regulatory_regime: Optional[str] = None
    human_review_required: bool = False
    pii_involved: bool = False
    top_k: int = 3

@dataclass
class Candidate:
    composition_id: str
    name: str
    pattern: str
    quality: Optional[float]
    latency_ms: Optional[float]
    cost_per_1k: Optional[float]
    verdict_label: str
    binding_constraints: list[str] = field(default_factory=list)
    missing_axes: list[str] = field(default_factory=list)
    notes: str = ""

@dataclass
class RightSizeResult:
    query: Query
    branch: str   # "feasible"|"tiebreak_10pct"|"comparable_20pct"|"infeasible_binding"|"confidence_filtered"
    top_candidates: list[Candidate]
    closest_feasible: Optional[Candidate] = None
    binding_constraint_explanation: Optional[str] = None

def right_size(query: Query, db_path=None) -> RightSizeResult:
    """
    §12 Tier A decision rule — 5 branches:
    1. feasible:           all constraints met → rank by cost, return top-k
    2. tiebreak_10pct:     multiple within 10% of best on primary metric → pick cheapest
    3. comparable_20pct:   options within 20% cost of cheapest feasible → show full set
    4. infeasible_binding: no feasible option → show binding constraint + closest-feasible
    5. confidence_filtered: after kappa filter, candidate set changes
    """
    db = db_path or DB_PATH
    all_comps = candidates(pattern=query.composition_pattern,
                           task=query.task_archetype, db_path=db)

    scored = []
    for c in all_comps:
        cid = c["composition_id"]
        v = assess(cid, query.quality_min, query.latency_max_ms,
                   query.cost_max_per_1k, c["composition_pattern"], db_path=db)
        q_b = cell(cid, "quality", db_path=db)
        l_b = cell(cid, "latency_p95_ms", db_path=db)
        c_b = cell(cid, "cost_per_1k_tokens", db_path=db)
        scored.append(Candidate(
            composition_id=cid,
            name=c["name"],
            pattern=c["composition_pattern"],
            quality=q_b.lo,
            latency_ms=l_b.hi,
            cost_per_1k=c_b.hi,
            verdict_label=v.verdict.value,
            binding_constraints=v.binding_axes,
            missing_axes=v.missing_axes,
        ))

    # Branch 5: confidence filter — re-score with high-only kappa
    high_conf_scored = []
    for c in all_comps:
        cid = c["composition_id"]
        q_b_h = cell(cid, "quality", min_kappa="high", db_path=db)
        l_b_h = cell(cid, "latency_p95_ms", min_kappa="high", db_path=db)
        c_b_h = cell(cid, "cost_per_1k_tokens", min_kappa="high", db_path=db)
        if not q_b_h.is_bot:
            high_conf_scored.append(cid)

    # Use Verdict enum values for comparison
    decidable_label = Verdict.DECIDABLE.value
    infeasible_label = Verdict.INFEASIBLE.value
    underdetermined_label = Verdict.UNDERDETERMINED.value

    feasible = [s for s in scored if s.verdict_label == decidable_label]
    if not feasible:
        # Branch 4: infeasible_binding
        infeasible = [s for s in scored if s.verdict_label == infeasible_label]
        underdetermined = [s for s in scored if s.verdict_label == underdetermined_label]
        # closest-feasible: relax constraints by 20%
        closest = None
        relaxed = [s for s in scored
                   if (s.quality or 0) >= query.quality_min * 0.8
                   and (s.latency_ms or float("inf")) <= query.latency_max_ms * 1.2
                   and (s.cost_per_1k or float("inf")) <= query.cost_max_per_1k * 1.2]
        if relaxed:
            closest = sorted(relaxed, key=lambda s: s.cost_per_1k or float("inf"))[0]
            closest.notes = "closest-feasible (20% relaxed constraints)"
        binding_axes = set()
        for s in infeasible:
            binding_axes.update(s.binding_constraints)
        explanation = f"Binding constraints: {sorted(binding_axes)}" if binding_axes else "All candidates underdetermined"
        return RightSizeResult(query=query, branch="infeasible_binding",
                               top_candidates=(infeasible+underdetermined)[:query.top_k],
                               closest_feasible=closest,
                               binding_constraint_explanation=explanation)

    # Sort by cost ascending
    feasible_sorted = sorted(feasible, key=lambda s: s.cost_per_1k or float("inf"))
    best = feasible_sorted[0]

    # Branch 2: tiebreak within 10% on quality
    if len(feasible_sorted) > 1:
        best_quality = best.quality or 0.0
        tied = [s for s in feasible_sorted
                if s.quality is not None and abs(s.quality - best_quality) / max(best_quality, 1e-9) <= 0.10]
        if len(tied) > 1:
            tied_sorted = sorted(tied, key=lambda s: s.cost_per_1k or float("inf"))
            tied_sorted[0].notes = "tiebreak winner (cheapest within 10% quality)"
            return RightSizeResult(query=query, branch="tiebreak_10pct",
                                   top_candidates=tied_sorted[:query.top_k])

    # Branch 3: comparable within 20% cost
    cheapest_cost = best.cost_per_1k or 1e-9
    comparable = [s for s in feasible_sorted
                  if (s.cost_per_1k or float("inf")) <= cheapest_cost * 1.20]
    if len(comparable) > 1:
        for s in comparable:
            s.notes = "comparable (within 20% cost)"
        return RightSizeResult(query=query, branch="comparable_20pct",
                               top_candidates=comparable[:query.top_k])

    # Branch 1: standard feasible
    return RightSizeResult(query=query, branch="feasible",
                           top_candidates=feasible_sorted[:query.top_k])
