#!/usr/bin/env python3
"""make show-w4: coverage by source, ≥200 rows ≥4/5 cols."""
import sys
sys.path.insert(0, "src")
from apt_engine.db import connect, DB_PATH, init_db

db = sys.argv[1] if len(sys.argv)>1 else str(DB_PATH)
init_db(db)
con = connect(db)
print("="*60); print("SHOW W4: Dense Benchmark Coverage"); print("="*60)

rows = con.execute(
    "SELECT s.source_id, s.name, COUNT(br.run_id) as cnt FROM benchmark_run br "
    "JOIN evidence_item e ON br.evidence_id=e.evidence_id "
    "JOIN source s ON e.source_id=s.source_id GROUP BY s.source_id ORDER BY cnt DESC"
).fetchall()
print(f"\n{'Source':<35} {'Rows':>6}")
print("-"*42)
total = 0
mlperf_n = helm_n = 0
for r in rows:
    print(f"  {r['name']:<33} {r['cnt']:>6}")
    total += r['cnt']
    if 'mlperf' in r['source_id'].lower() or 'MLPerf' in r['name']: mlperf_n += r['cnt']
    if 'helm' in r['source_id'].lower() or 'HELM' in r['name']: helm_n += r['cnt']
print(f"{'TOTAL':<35} {total:>6}")

ge4 = con.execute(
    "SELECT COUNT(*) FROM benchmark_run WHERE "
    "(quality IS NOT NULL)+(latency_p95_ms IS NOT NULL)+(cost_per_1k_tokens IS NOT NULL)+"
    "(energy_J IS NOT NULL)+(memory_GB IS NOT NULL) >= 4"
).fetchone()[0]
print(f"\nRows with ≥4/5 core columns: {ge4}")

# Sample provenance
print("\nSample rows with provenance:")
samples = con.execute(
    "SELECT br.run_id, s.source_id, e.evidence_id, br.task, br.quality, br.latency_p95_ms "
    "FROM benchmark_run br JOIN evidence_item e ON br.evidence_id=e.evidence_id "
    "JOIN source s ON e.source_id=s.source_id LIMIT 5"
).fetchall()
for s in samples:
    print(f"  run={s['run_id']} src={s['source_id']} ev={s['evidence_id']} task={s['task']} q={s['quality']} lat={s['latency_p95_ms']}")

con.close()
gate_pass = total>=200 and ge4>=200 and mlperf_n>=50 and helm_n>=50
print("\n" + "="*60); print("GATE W4:")
print(f"  ≥200 benchmark_run:   {'✅' if total>=200 else '❌'} ({total})")
print(f"  ≥200 rows ≥4/5 cols:  {'✅' if ge4>=200 else '❌'} ({ge4})")
print(f"  ≥50 MLPerf rows:      {'✅' if mlperf_n>=50 else '❌'} ({mlperf_n})")
print(f"  ≥50 HELM rows:        {'✅' if helm_n>=50 else '❌'} ({helm_n})")
print(f"\nGATE W4: {'PASS ✅' if gate_pass else 'FAIL ❌'}")
sys.exit(0 if gate_pass else 1)
