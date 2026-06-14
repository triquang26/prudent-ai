#!/usr/bin/env python3
"""make show-w2: HELM load + Q1-Q4 + interface invariance."""
import sys, subprocess
sys.path.insert(0, "src")
from apt_engine.db import init_db, connect, DB_PATH
from apt_engine.loaders.helm_lite import HelmLiteLoader
from apt_engine.queries import Q1_missing, Q2_feasible, Q3_borderline, Q4_binding

db = sys.argv[1] if len(sys.argv)>1 else str(DB_PATH)
init_db(db)
print("="*60); print("SHOW W2: Loader + Queries + Interface"); print("="*60)

# Load HELM Lite
n = HelmLiteLoader(db).load()
con = connect(db)
src_n = con.execute("SELECT COUNT(*) FROM source").fetchone()[0]
run_n = con.execute("SELECT COUNT(*) FROM benchmark_run").fetchone()[0]
con.close()
print(f"\nHELM Lite loaded: {n} new benchmark_run rows (total={run_n}, sources={src_n})")

# Q1-Q4
print("\nQ1 — Missingness (compositions missing required axes):")
q1 = Q1_missing(db_path=db)[:3]
for r in q1: print(f"  {r['composition_id']}: missing={r['missing_axes']}")
print(f"  ({len(Q1_missing(db_path=db))} total missing)")

print("\nQ2 — Feasible (quality≥0.7, lat≤800ms, cost≤0.02):")
q2 = Q2_feasible(0.7, 800.0, 0.02, db_path=db)[:3]
for r in q2: print(f"  {r['name']}: q={r['quality_lo']:.2f} lat={r['latency_hi']:.0f}ms cost={r['cost_hi']:.4f}")
print(f"  ({len(Q2_feasible(0.7,800.0,0.02,db_path=db))} total feasible)")

print("\nQ3 — Borderline (near quality=0.80, lat=500ms, cost=0.012):")
q3 = Q3_borderline(0.80, 500.0, 0.012, db_path=db)[:3]
for r in q3: print(f"  {r['name']}: borderline_axes={r['borderline_axes']}")
print(f"  ({len(Q3_borderline(0.80,500.0,0.012,db_path=db))} total borderline)")

print("\nQ4 — Binding (quality≥0.95, lat≤100ms, cost≤0.001):")
q4 = Q4_binding(0.95, 100.0, 0.001, db_path=db)[:3]
for r in q4: print(f"  {r['name']}: {r['binding_constraints']}")
print(f"  ({len(Q4_binding(0.95,100.0,0.001,db_path=db))} total binding)")

# Run invariance tests
print("\nRunning tests/test_interface_invariance.py ...")
r = subprocess.run(["python3","-m","pytest","tests/test_interface_invariance.py",
                    "tests/test_queries.py","-v","--tb=short"], capture_output=True, text=True)
print(r.stdout[-2000:])
tests_pass = r.returncode == 0

gate_pass = n>0 and len(q1)>=0 and len(q2)>=1 and tests_pass
print("\n" + "="*60)
print(f"GATE W2: {'PASS ✅' if gate_pass else 'FAIL ❌'}")
print(f"  HELM Lite loaded: {'✅' if n>0 else '❌'} ({n} rows)")
print(f"  Q2 ≥1 row: {'✅' if len(Q2_feasible(0.7,800.0,0.02,db_path=db))>=1 else '❌'}")
print(f"  Interface invariance: {'✅' if tests_pass else '❌'}")
sys.exit(0 if gate_pass else 1)
