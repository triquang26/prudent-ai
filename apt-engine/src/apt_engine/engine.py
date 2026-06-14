"""Core right-sizing engine: Query, candidates(), cell(), right_size()."""
from __future__ import annotations
import dataclasses
from dataclasses import dataclass, field
from typing import Any, Optional
from .db import connect


# ---------------------------------------------------------------------------
# Query dataclass
# ---------------------------------------------------------------------------

@dataclass
class Query:
    """Declarative deployment constraints. Use float('inf') to omit a bound."""
    task_archetype: Optional[str] = None
    composition_pattern: Optional[str] = None
    quality_min: float = 0.0
    latency_max_ms: float = float("inf")
    cost_max_per_1k: float = float("inf")
    regulatory_regime: Optional[str] = None   # e.g. "HIPAA"
    human_review_required: bool = False
    pii_involved: bool = False
    hardware_tier: Optional[str] = None
    # Extra filters
    extra_filters: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class Candidate:
    composition_id: str
    name: str
    composition_pattern: str
    task_archetype: Optional[str]
    quality: Optional[float]
    latency_p95_ms: Optional[float]
    cost_per_1k_tokens: Optional[float]
    energy_J: Optional[float]
    hardware_tier: Optional[str]
    evidence_id: Optional[str]
    source_url: Optional[str]
    source_name: Optional[str]
    notes: Optional[str]
    # Populated after constraint check
    binding_constraints: list[str] = field(default_factory=list)


@dataclass
class RightSizeResult:
    query: Query
    branch: str   # "feasible" | "infeasible_binding" | "no_data"
    candidates: list[Candidate]
    binding_constraints: list[str]
    closest_feasible: Optional[Candidate] = None
    explanation: str = ""


# ---------------------------------------------------------------------------
# Low-level accessors
# ---------------------------------------------------------------------------

def cell(db_path: str, table: str, row_id_col: str, row_id: str, col: str) -> Any:
    """Return a single cell value from the DB."""
    con = connect(db_path)
    row = con.execute(
        f"SELECT {col} FROM {table} WHERE {row_id_col} = ?", (row_id,)
    ).fetchone()
    con.close()
    return row[col] if row else None


def candidates(db_path: str, q: Optional[Query] = None) -> list[Candidate]:
    """
    Return all Candidate objects that match the Query filters.
    Aggregates quality/latency/cost per composition via AVG over benchmark_run.
    """
    sql = """
        SELECT
            c.composition_id,
            c.name,
            c.composition_pattern,
            c.task_archetype,
            AVG(br.quality)             AS quality,
            AVG(br.latency_p95_ms)      AS latency_p95_ms,
            AVG(br.cost_per_1k_tokens)  AS cost_per_1k_tokens,
            AVG(br.energy_J)            AS energy_J,
            br.hardware_tier,
            c.evidence_id,
            s.url                       AS source_url,
            s.name                      AS source_name,
            c.notes
        FROM composition c
        LEFT JOIN benchmark_run br ON br.composition_id = c.composition_id
        LEFT JOIN evidence_item ei ON ei.evidence_id = c.evidence_id
        LEFT JOIN source s ON s.source_id = ei.source_id
    """
    where = []
    params: list[Any] = []

    if q is not None:
        if q.task_archetype:
            where.append("c.task_archetype = ?")
            params.append(q.task_archetype)
        if q.composition_pattern:
            where.append("c.composition_pattern = ?")
            params.append(q.composition_pattern)
        if q.hardware_tier:
            where.append("br.hardware_tier = ?")
            params.append(q.hardware_tier)

    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " GROUP BY c.composition_id"

    con = connect(db_path)
    rows = con.execute(sql, params).fetchall()
    con.close()

    result = []
    for r in rows:
        result.append(Candidate(
            composition_id=r["composition_id"],
            name=r["name"],
            composition_pattern=r["composition_pattern"],
            task_archetype=r["task_archetype"],
            quality=r["quality"],
            latency_p95_ms=r["latency_p95_ms"],
            cost_per_1k_tokens=r["cost_per_1k_tokens"],
            energy_J=r["energy_J"],
            hardware_tier=r["hardware_tier"],
            evidence_id=r["evidence_id"],
            source_url=r["source_url"],
            source_name=r["source_name"],
            notes=r["notes"],
        ))
    return result


# ---------------------------------------------------------------------------
# Constraint evaluation helpers
# ---------------------------------------------------------------------------

def _check_constraints(cand: Candidate, q: Query) -> list[str]:
    """Return list of binding constraints violated by this candidate."""
    binding = []
    if cand.quality is not None and cand.quality < q.quality_min:
        binding.append(
            f"quality {cand.quality:.3f} < required {q.quality_min:.3f}"
        )
    if cand.latency_p95_ms is not None and q.latency_max_ms < float("inf"):
        if cand.latency_p95_ms > q.latency_max_ms:
            binding.append(
                f"latency {cand.latency_p95_ms:.0f}ms > max {q.latency_max_ms:.0f}ms"
            )
    if cand.cost_per_1k_tokens is not None and q.cost_max_per_1k < float("inf"):
        if cand.cost_per_1k_tokens > q.cost_max_per_1k:
            binding.append(
                f"cost ${cand.cost_per_1k_tokens:.5f} > max ${q.cost_max_per_1k:.5f}"
            )
    return binding


def _score(cand: Candidate) -> float:
    """Score for ranking: higher quality, lower latency, lower cost = better."""
    q_score = cand.quality if cand.quality is not None else 0.0
    l_score = -((cand.latency_p95_ms or 0) / 10000.0)
    c_score = -((cand.cost_per_1k_tokens or 0) * 10)
    return q_score + 0.5 * l_score + 0.3 * c_score


# ---------------------------------------------------------------------------
# Main API
# ---------------------------------------------------------------------------

def right_size(q: Query, db_path: str) -> RightSizeResult:
    """
    Run the right-sizing algorithm against the DB.

    Returns a RightSizeResult with branch:
      - "feasible"          : ≥1 candidate satisfies all constraints
      - "infeasible_binding": no candidate satisfies all constraints;
                              binding constraints explained
      - "no_data"           : no relevant evidence in DB at all
    """
    all_cands = candidates(db_path, q)

    if not all_cands:
        return RightSizeResult(
            query=q,
            branch="no_data",
            candidates=[],
            binding_constraints=[],
            explanation="No compositions found matching the query filters.",
        )

    # Evaluate constraints for every candidate
    feasible = []
    infeasible = []
    for cand in all_cands:
        violations = _check_constraints(cand, q)
        cand.binding_constraints = violations
        if violations:
            infeasible.append(cand)
        else:
            feasible.append(cand)

    # Sort feasible by composite score
    feasible.sort(key=_score, reverse=True)
    infeasible.sort(key=_score, reverse=True)

    if feasible:
        # Collect what constraints were binding across ALL infeasible ones
        all_binding: set[str] = set()
        for c in infeasible:
            all_binding.update(c.binding_constraints)
        return RightSizeResult(
            query=q,
            branch="feasible",
            candidates=feasible,
            binding_constraints=[],
            closest_feasible=feasible[0],
            explanation=f"Found {len(feasible)} feasible composition(s).",
        )
    else:
        # Aggregate which constraints are most commonly violated
        constraint_counts: dict[str, int] = {}
        for c in infeasible:
            for v in c.binding_constraints:
                # Bucket by constraint type
                key = v.split(" ")[0]  # "quality", "latency", "cost"
                constraint_counts[key] = constraint_counts.get(key, 0) + 1
        binding_summary = [
            f"{k} violated by {v}/{len(infeasible)} candidate(s)"
            for k, v in sorted(constraint_counts.items(), key=lambda x: -x[1])
        ]
        # Closest feasible = infeasible candidate with fewest violations
        closest = min(infeasible, key=lambda c: (len(c.binding_constraints), -_score(c)))
        return RightSizeResult(
            query=q,
            branch="infeasible_binding",
            candidates=infeasible,
            binding_constraints=binding_summary,
            closest_feasible=closest,
            explanation=(
                "No composition satisfies all constraints. "
                f"Binding: {'; '.join(binding_summary)}. "
                f"Closest option: {closest.name}."
            ),
        )
