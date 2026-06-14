#!/usr/bin/env python3
"""APT Evidence Engine — Demo script.

Runs 4 right-sizing scenarios (or 1 in --smoke mode) and prints clean output.
"""
import sys
import pathlib
import argparse
import os

# Add src/ to path
sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "src"))

from apt_engine import DB_PATH
from apt_engine.db import init_db, connect
from apt_engine.right_sizing import right_size, Query
from apt_engine.profiles import load_profiles, seed_default_profiles
from apt_engine.missingness import generate_report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_cand(c, rank: int = 0) -> str:
    q_str = f"quality={c.quality:.3f}" if c.quality is not None else "quality=⊥"
    l_str = f"latency={c.latency_ms:.0f}ms" if c.latency_ms is not None else "latency=⊥"
    c_str = f"cost=${c.cost_per_1k:.5f}/1k" if c.cost_per_1k is not None else "cost=⊥"
    verdict = f"[{c.verdict_label}]"
    prefix = f"  #{rank+1}" if rank >= 0 else "  "
    return f"{prefix} {verdict} {c.name}  |  {q_str}  {l_str}  {c_str}"


def _print_provenance(c, db_path: str):
    """Print evidence provenance for a candidate, looked up from composition_id."""
    cid = getattr(c, "composition_id", None)
    if not cid:
        print("    Provenance: (no composition_id)")
        return
    con = connect(db_path)
    # Get evidence_id from composition
    comp_row = con.execute(
        "SELECT evidence_id FROM composition WHERE composition_id=?", (cid,)
    ).fetchone()
    ev = None
    src = None
    if comp_row and comp_row["evidence_id"]:
        eid = comp_row["evidence_id"]
        ev = con.execute("SELECT * FROM evidence_item WHERE evidence_id=?", (eid,)).fetchone()
        if ev:
            src = con.execute("SELECT * FROM source WHERE source_id=?",
                              (ev["source_id"],)).fetchone()
    con.close()
    if ev:
        print(f"    Evidence: {ev['description']} (type={ev['evidence_type']})")
    if src:
        print(f"    Source:   {src['name']} | {src['url']} | license={src['license']}")
    else:
        print(f"    Provenance: composition={cid} (no source linked)")


def _print_result(result, label: str, top_n: int = 3, show_provenance: bool = True):
    print(f"\n  Branch: {result.branch}")
    cands = result.top_candidates[:top_n]
    if not cands:
        print("  (no candidates)")
        return
    print(f"  Top {len(cands)} candidate(s):")
    for i, c in enumerate(cands):
        print(_fmt_cand(c, i))
        if c.binding_constraints:
            print(f"       binding: {c.binding_constraints}")
        if c.missing_axes:
            print(f"       missing: {c.missing_axes}")

    if show_provenance and cands:
        print(f"\n  Provenance walk for top candidate: {cands[0].name}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="APT Evidence Engine — Demo")
    parser.add_argument("db", nargs="?", default=str(DB_PATH), help="Path to SQLite DB")
    parser.add_argument("--smoke", action="store_true", help="Quick smoke-test mode (1 scenario)")
    args = parser.parse_args()
    db = args.db

    # Ensure DB is initialized and seeded
    init_db(db)
    try:
        seed_default_profiles(db)
    except Exception:
        pass  # profiles already seeded

    print("=" * 65)
    print("APT Evidence Engine — Demo")
    print("=" * 65)

    # DB stats
    con = connect(db)
    total_runs = con.execute("SELECT COUNT(*) FROM benchmark_run").fetchone()[0]
    total_comp = con.execute("SELECT COUNT(*) FROM composition").fetchone()[0]
    total_prof = con.execute("SELECT COUNT(*) FROM right_sizing_profile").fetchone()[0]
    con.close()

    print(f"\nDB stats:")
    print(f"  benchmark_run rows : {total_runs}")
    print(f"  compositions       : {total_comp}")
    print(f"  right-sizing profiles: {total_prof}")

    # ---------------------------------------------------------------------------
    # SCENARIO 1: Clinical note summarization, HIPAA
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 65)
    print("=== SCENARIO 1: Clinical Note Summarization (HIPAA) ===")
    print("=" * 65)
    print("Query: task=summarization, ROUGE-L≥0.30, lat≤2000ms, cost≤$0.05/1k,")
    print("       HIPAA=True, human_review=True, pii=True")

    q1 = Query(
        task_archetype="summarization",
        quality_min=0.30,
        latency_max_ms=2000.0,
        cost_max_per_1k=0.05,
        regulatory_regime="HIPAA",
        human_review_required=True,
        pii_involved=True,
    )
    r1 = right_size(q1, db_path=db)

    # Print results
    print(f"\n  Branch: {r1.branch}")
    top = r1.top_candidates[:3] if not args.smoke else r1.top_candidates[:1]
    for i, c in enumerate(top):
        print(_fmt_cand(c, i))
        if c.binding_constraints:
            print(f"       binding: {c.binding_constraints}")

    if top:
        print(f"\n  Provenance walk for: {top[0].name}")
        _print_provenance(top[0], db)

    if r1.binding_constraint_explanation:
        print(f"\n  Explanation: {r1.binding_constraint_explanation}")

    if args.smoke:
        print("\n[smoke mode: stopping after scenario 1]")
        print("\nSCENARIO 1 complete.")
        print("\n✅ Demo complete.")
        sys.exit(0)

    # ---------------------------------------------------------------------------
    # SCENARIO 2: Web navigation agent
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 65)
    print("=== SCENARIO 2: Web Navigation Agent ===")
    print("=" * 65)
    print("Query: composition_pattern=web_nav, quality≥0.35, lat≤15000ms, cost≤$0.10/1k")

    q2 = Query(
        composition_pattern="web_nav",
        quality_min=0.35,
        latency_max_ms=15000.0,
        cost_max_per_1k=0.10,
    )
    r2 = right_size(q2, db_path=db)

    print(f"\n  Branch: {r2.branch}")
    for i, c in enumerate(r2.top_candidates[:3]):
        print(_fmt_cand(c, i))
        if c.binding_constraints:
            print(f"       binding: {c.binding_constraints}")

    if r2.branch == "infeasible_binding":
        print(f"\n  Infeasible explanation: {r2.binding_constraint_explanation}")
        if r2.closest_feasible:
            print(f"  Closest option: {r2.closest_feasible.name} "
                  f"(quality={r2.closest_feasible.quality})")

    # ---------------------------------------------------------------------------
    # SCENARIO 3: Open-domain QA with RAG
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 65)
    print("=== SCENARIO 3: Open-Domain QA (RAG, no latency constraint) ===")
    print("=" * 65)
    print("Query: task=question_answering, pattern=rag, quality≥0.75, cost≤$0.02/1k")

    q3 = Query(
        task_archetype="question_answering",
        composition_pattern="rag",
        quality_min=0.75,
        latency_max_ms=float("inf"),
        cost_max_per_1k=0.02,
    )
    r3 = right_size(q3, db_path=db)

    print(f"\n  Branch: {r3.branch}")
    for i, c in enumerate(r3.top_candidates[:3]):
        print(_fmt_cand(c, i))

    if r3.branch == "infeasible_binding":
        print(f"\n  Infeasible: {r3.binding_constraint_explanation}")

    # ---------------------------------------------------------------------------
    # SCENARIO 4: Impossible constraints (failure case)
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 65)
    print("=== SCENARIO 4: Failure Case — Impossible Constraints ===")
    print("=" * 65)
    print("Query: quality≥0.99, latency≤10ms, cost≤$0.00001/1k")
    print("  (Demonstrates correct INFEASIBLE detection)")

    q4 = Query(
        quality_min=0.99,
        latency_max_ms=10.0,
        cost_max_per_1k=0.00001,
    )
    r4 = right_size(q4, db_path=db)

    print(f"\n  Branch: {r4.branch}")
    if r4.branch == "infeasible_binding":
        print(f"  INFEASIBLE — binding constraints: {r4.binding_constraint_explanation}")
        if r4.closest_feasible:
            cf = r4.closest_feasible
            print(f"\n  Closest feasible option (relaxed constraints):")
            print(f"    {cf.name}")
            q_s = f"{cf.quality:.3f}" if cf.quality else "⊥"
            l_s = f"{cf.latency_ms:.0f}ms" if cf.latency_ms else "⊥"
            c_s = f"${cf.cost_per_1k:.5f}" if cf.cost_per_1k else "⊥"
            print(f"    quality={q_s}  latency={l_s}  cost={c_s}/1k")
            print(f"    violations: {cf.binding_constraints}")
    elif r4.branch == "no_data":
        print("  No data — DB is empty or filters returned nothing.")
    else:
        print(f"  Unexpectedly feasible (branch={r4.branch}). Check constraints.")

    # ---------------------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 65)
    print("Summary")
    print("=" * 65)
    branches = [r1.branch, r2.branch, r3.branch, r4.branch]
    scenarios = ["Clinical HIPAA", "Web Nav", "RAG QA", "Impossible"]
    for sc, br in zip(scenarios, branches):
        print(f"  {sc:<20} => {br}")

    print("\n✅ Demo complete.")
    sys.exit(0)


if __name__ == "__main__":
    main()
