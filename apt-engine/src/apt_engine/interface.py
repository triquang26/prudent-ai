"""Read-interface: candidates(), cell(), required_fields().
C7 invariant: substrate is read-only; missing evidence stays ⊥, never imputed.
"""
from __future__ import annotations
import sqlite3
from typing import Optional
from .db import connect, DB_PATH
from .belief import Belief, aggregate_belief

AXES = ["quality", "latency_p95_ms", "cost_per_1k_tokens", "energy_J", "memory_GB"]

REQUIRED_BY_PATTERN = {
    "bare_llm":     ["quality", "latency_p95_ms", "cost_per_1k_tokens"],
    "rag":          ["quality", "latency_p95_ms", "cost_per_1k_tokens"],
    "rag_reasoning":["quality", "latency_p95_ms", "cost_per_1k_tokens"],
    "tool_agent":   ["quality", "latency_p95_ms", "cost_per_1k_tokens"],
    "single_agent": ["quality", "latency_p95_ms", "cost_per_1k_tokens"],
    "multi_agent":  ["quality", "latency_p95_ms", "cost_per_1k_tokens"],
    "web_nav":      ["quality", "latency_p95_ms"],
}


def candidates(pattern: Optional[str] = None, task: Optional[str] = None,
               db_path=None) -> list[dict]:
    """Return compositions matching optional pattern/task filters."""
    con = connect(db_path or DB_PATH)
    q = "SELECT * FROM composition WHERE 1=1"
    params = []
    if pattern:
        q += " AND composition_pattern=?"
        params.append(pattern)
    if task:
        q += " AND task_archetype=?"
        params.append(task)
    rows = [dict(r) for r in con.execute(q, params).fetchall()]
    con.close()
    return rows


def _fetch_axis_rows(con: sqlite3.Connection, id_col: str, id_val: str,
                     axis: str) -> list[dict]:
    """Fetch benchmark_run rows for a given axis, adding a default confidence."""
    # Check if confidence column exists in benchmark_run
    cols = {row[1] for row in con.execute("PRAGMA table_info(benchmark_run)").fetchall()}
    if "confidence" in cols:
        sql = (
            f"SELECT {axis}, confidence FROM benchmark_run "
            f"WHERE {id_col}=? AND {axis} IS NOT NULL"
        )
    else:
        # No confidence column — synthesise "medium" so aggregate_belief works
        sql = (
            f"SELECT {axis}, 'medium' AS confidence FROM benchmark_run "
            f"WHERE {id_col}=? AND {axis} IS NOT NULL"
        )
    return [dict(r) for r in con.execute(sql, (id_val,)).fetchall()]


def cell(composition_id: str, axis: str, min_kappa="medium",
         db_path=None) -> Belief:
    """Return Belief for a composition on a specific axis. Returns ⊥ if no evidence."""
    assert axis in AXES, f"Unknown axis: {axis}"
    con = connect(db_path or DB_PATH)
    rows = _fetch_axis_rows(con, "composition_id", composition_id, axis)
    con.close()
    return aggregate_belief(rows, axis, min_kappa)


def required_fields(pattern: str) -> list[str]:
    """Return required axes for a composition pattern."""
    return REQUIRED_BY_PATTERN.get(pattern, AXES[:3])


def cell_for_component(component_id: str, axis: str, min_kappa="medium",
                       db_path=None) -> Belief:
    """Belief for a component directly (component-level runs)."""
    assert axis in AXES, f"Unknown axis: {axis}"
    con = connect(db_path or DB_PATH)
    rows = _fetch_axis_rows(con, "component_id", component_id, axis)
    con.close()
    return aggregate_belief(rows, axis, min_kappa)
