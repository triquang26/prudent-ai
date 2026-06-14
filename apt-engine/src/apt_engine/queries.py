"""Q1-Q4 decision queries (Appendix E semantics)."""
from __future__ import annotations
from typing import Optional
from .db import connect, DB_PATH
from .interface import cell, required_fields, AXES


def Q1_missing(pattern: Optional[str] = None, db_path=None) -> list[dict]:
    """Q1: Missingness — compositions with ⊥ on at least one required axis."""
    con = connect(db_path or DB_PATH)
    q = "SELECT composition_id, name, composition_pattern FROM composition"
    params = []
    if pattern:
        q += " WHERE composition_pattern=?"
        params.append(pattern)
    comps = [dict(r) for r in con.execute(q, params).fetchall()]
    con.close()
    result = []
    for c in comps:
        cid = c["composition_id"]
        pat = c["composition_pattern"]
        missing = [ax for ax in required_fields(pat)
                   if cell(cid, ax, db_path=db_path).is_bot]
        if missing:
            result.append({**c, "missing_axes": missing})
    return result


def Q2_feasible(quality_min: float = 0.0, latency_max: float = float("inf"),
                cost_max: float = float("inf"), db_path=None) -> list[dict]:
    """Q2: Feasibility — compositions that provably satisfy all constraints."""
    con = connect(db_path or DB_PATH)
    comps = [dict(r) for r in con.execute(
        "SELECT composition_id, name, composition_pattern FROM composition"
    ).fetchall()]
    con.close()
    result = []
    for c in comps:
        cid = c["composition_id"]
        q_b = cell(cid, "quality", db_path=db_path)
        l_b = cell(cid, "latency_p95_ms", db_path=db_path)
        c_b = cell(cid, "cost_per_1k_tokens", db_path=db_path)
        # Only count as feasible if evidence confirms (not ⊥, not ambiguous)
        if (not q_b.is_bot and q_b.lo is not None and q_b.lo >= quality_min and
                not l_b.is_bot and l_b.hi is not None and l_b.hi <= latency_max and
                not c_b.is_bot and c_b.hi is not None and c_b.hi <= cost_max):
            result.append({**c,
                "quality_lo": q_b.lo, "latency_hi": l_b.hi, "cost_hi": c_b.hi})
    return result


def Q3_borderline(quality_min: float, latency_max: float,
                  cost_max: float, margin: float = 0.20,
                  db_path=None) -> list[dict]:
    """Q3: Borderline — within margin of any constraint (underdetermined region)."""
    con = connect(db_path or DB_PATH)
    comps = [dict(r) for r in con.execute(
        "SELECT composition_id, name, composition_pattern FROM composition"
    ).fetchall()]
    con.close()
    result = []
    for c in comps:
        cid = c["composition_id"]
        q_b = cell(cid, "quality", db_path=db_path)
        l_b = cell(cid, "latency_p95_ms", db_path=db_path)
        c_b = cell(cid, "cost_per_1k_tokens", db_path=db_path)
        borderline = []
        if not q_b.is_bot and q_b.lo is not None:
            if quality_min * (1 - margin) <= q_b.lo <= quality_min * (1 + margin):
                borderline.append("quality")
        if not l_b.is_bot and l_b.hi is not None:
            if latency_max * (1 - margin) <= l_b.hi <= latency_max * (1 + margin):
                borderline.append("latency_p95_ms")
        if not c_b.is_bot and c_b.hi is not None:
            if cost_max * (1 - margin) <= c_b.hi <= cost_max * (1 + margin):
                borderline.append("cost_per_1k_tokens")
        if borderline:
            result.append({**c, "borderline_axes": borderline})
    return result


def Q4_binding(quality_min: float, latency_max: float,
               cost_max: float, db_path=None) -> list[dict]:
    """Q4: Binding constraint — for infeasible compositions, which axis blocks?"""
    con = connect(db_path or DB_PATH)
    comps = [dict(r) for r in con.execute(
        "SELECT composition_id, name, composition_pattern FROM composition"
    ).fetchall()]
    con.close()
    result = []
    for c in comps:
        cid = c["composition_id"]
        q_b = cell(cid, "quality", db_path=db_path)
        l_b = cell(cid, "latency_p95_ms", db_path=db_path)
        c_b = cell(cid, "cost_per_1k_tokens", db_path=db_path)
        binding = []
        if not q_b.is_bot and q_b.hi is not None and q_b.hi < quality_min:
            binding.append(f"quality<{quality_min} (max={q_b.hi:.3f})")
        if not l_b.is_bot and l_b.lo is not None and l_b.lo > latency_max:
            binding.append(f"latency>{latency_max}ms (min={l_b.lo:.0f}ms)")
        if not c_b.is_bot and c_b.lo is not None and c_b.lo > cost_max:
            binding.append(f"cost_per_1k>{cost_max:.5f} (min={c_b.lo:.4f})")
        if binding:
            result.append({**c, "binding_constraints": binding})
    return result
