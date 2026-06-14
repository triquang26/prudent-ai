#!/usr/bin/env python3
"""make show-w8: 5 deployment_context + missing-field report + totals."""
import sys
sys.path.insert(0, "src")
from apt_engine.db import connect, DB_PATH, init_db
from apt_engine.missingness import generate_report, coverage_stats

db = sys.argv[1] if len(sys.argv)>1 else str(DB_PATH)
init_db(db); con = connect(db)
print("="*60); print("SHOW W8: Deployment Context + Missingness Report"); print("="*60)

zenml = con.execute(
    "SELECT profile_id, industry, regulatory_regime, human_review_required, pii_involved, confidence, notes "
    "FROM right_sizing_profile WHERE value_source_type='vendor_claim' LIMIT 10"
).fetchall()
print(f"\nZenML deployment_context rows ({len(zenml)}):")
for z in zenml:
    print(f"  {z['profile_id']:<20} industry={z['industry']} regime={z['regulatory_regime']} "
          f"human_review={z['human_review_required']} pii={z['pii_involved']} conf={z['confidence']}")

total_runs = con.execute("SELECT COUNT(*) FROM benchmark_run").fetchone()[0]
total_comp = con.execute("SELECT COUNT(*) FROM composition").fetchone()[0]
print(f"\nTotals: benchmark_run={total_runs}, compositions={total_comp}")
con.close()

print("\nMissingness report:")
report = generate_report(db_path=db, out_path="reports/coverage_report.md")
for line in report.split("\n")[:30]:
    print(" ", line)
print("  [... see reports/coverage_report.md for full report]")

stats = coverage_stats(db_path=db)
gate_pass = (total_runs>=500 and total_comp>=50 and
             stats["zenml_vendor_claim_profiles"]>=5)
print("\n" + "="*60); print("GATE W8:")
print(f"  ≥500 benchmark_run:  {'✅' if total_runs>=500 else '❌'} ({total_runs})")
print(f"  ≥50 compositions:    {'✅' if total_comp>=50 else '❌'} ({total_comp})")
print(f"  ≥5 ZenML profiles:   {'✅' if stats['zenml_vendor_claim_profiles']>=5 else '❌'} ({stats['zenml_vendor_claim_profiles']})")
print(f"  report generated:    ✅ (reports/coverage_report.md)")
print(f"\nGATE W8: {'PASS ✅' if gate_pass else 'FAIL ❌'}")
sys.exit(0 if gate_pass else 1)
