#!/usr/bin/env python3
"""make show-w6: totals + component breakdown + 1 composition expanded."""
import sys
sys.path.insert(0, "src")
from apt_engine.db import connect, DB_PATH, init_db

db = sys.argv[1] if len(sys.argv)>1 else str(DB_PATH)
init_db(db); con = connect(db)
print("="*60); print("SHOW W6: RAG/Retriever/Tool-Use + Compositions"); print("="*60)

total_runs = con.execute("SELECT COUNT(*) FROM benchmark_run").fetchone()[0]
total_comp = con.execute("SELECT COUNT(*) FROM composition").fetchone()[0]
print(f"\nTotal benchmark_run: {total_runs}")
print(f"Total compositions:  {total_comp}")

print("\nComponent types present:")
for row in con.execute("SELECT component_type, COUNT(*) as n FROM component GROUP BY component_type ORDER BY n DESC").fetchall():
    print(f"  {row['component_type']:<20} {row['n']:>4}")

print("\nComposition patterns:")
for row in con.execute("SELECT composition_pattern, COUNT(*) as n FROM composition GROUP BY composition_pattern ORDER BY n DESC").fetchall():
    print(f"  {row['composition_pattern']:<20} {row['n']:>4}")

# Expand 1 composition graph
ex = con.execute(
    "SELECT c.composition_id, c.name, c.composition_pattern FROM composition c "
    "WHERE c.composition_id IN (SELECT DISTINCT composition_id FROM composition_component) LIMIT 1"
).fetchone()
if ex:
    print(f"\nExpanded composition: {ex['name']} ({ex['composition_id']}, pattern={ex['composition_pattern']})")
    parts = con.execute(
        "SELECT cc.role, cc.execution_order, cmp.name, cmp.component_type "
        "FROM composition_component cc JOIN component cmp ON cc.component_id=cmp.component_id "
        "WHERE cc.composition_id=? ORDER BY cc.execution_order", (ex['composition_id'],)
    ).fetchall()
    for p in parts:
        print(f"  [{p['execution_order']}] {p['role']:<12} → {p['name']} ({p['component_type']})")

has_retriever = con.execute("SELECT COUNT(*) FROM component WHERE component_type='retriever'").fetchone()[0]>0
has_rag = con.execute("SELECT COUNT(*) FROM composition WHERE composition_pattern='rag'").fetchone()[0]>0
has_tool = con.execute("SELECT COUNT(*) FROM component WHERE component_type='tool' OR component_type='agent'").fetchone()[0]>0
has_tool_comp = con.execute("SELECT COUNT(*) FROM composition WHERE composition_pattern='tool_agent'").fetchone()[0]>0
con.close()

gate_pass = total_runs>=400 and total_comp>=30 and has_retriever and (has_rag or has_tool_comp)
print("\n" + "="*60); print("GATE W6:")
print(f"  ≥400 benchmark_run:  {'✅' if total_runs>=400 else '❌'} ({total_runs})")
print(f"  ≥30 compositions:    {'✅' if total_comp>=30 else '❌'} ({total_comp})")
print(f"  retriever present:   {'✅' if has_retriever else '❌'}")
print(f"  RAG present:         {'✅' if has_rag else '❌'}")
print(f"  tool_agent present:  {'✅' if has_tool_comp else '❌'}")
print(f"\nGATE W6: {'PASS ✅' if gate_pass else 'FAIL ❌'}")
sys.exit(0 if gate_pass else 1)
