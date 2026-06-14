#!/usr/bin/env python3
"""make show-w9: right_size() canonical scenario + profiles + tests."""
import sys, subprocess
sys.path.insert(0, "src")
from apt_engine.db import DB_PATH, init_db
from apt_engine.right_sizing import right_size, Query
from apt_engine.profiles import load_profiles

db = sys.argv[1] if len(sys.argv)>1 else str(DB_PATH)
init_db(db)
print("="*60); print("SHOW W9: Right-Sizing Decision Rule"); print("="*60)

# Canonical scenario: clinical-note summarization, HIPAA, p95<2000ms, ROUGE-L≥0.30
q = Query(
    task_archetype="summarization",
    quality_min=0.30,
    latency_max_ms=2000.0,
    cost_max_per_1k=0.05,
    regulatory_regime="HIPAA",
    human_review_required=True,
    pii_involved=True,
)
print(f"\nCanonical query: clinical-note summarization, HIPAA, lat≤2000ms, ROUGE-L≥0.30")
result = right_size(q, db_path=db)
print(f"Branch: {result.branch}")
print(f"Top candidates ({len(result.top_candidates)}):")
for c in result.top_candidates:
    print(f"  [{c.verdict_label}] {c.name}")
    print(f"    quality={c.quality}  latency={c.latency_ms}ms  cost={c.cost_per_1k}/1k  {c.notes}")
    if c.binding_constraints:
        print(f"    ⚠ binding: {c.binding_constraints}")
    if c.missing_axes:
        print(f"    ⊥ missing: {c.missing_axes}")
if result.closest_feasible:
    print(f"  Closest-feasible: {result.closest_feasible.name} ({result.closest_feasible.notes})")
if result.binding_constraint_explanation:
    print(f"  Explanation: {result.binding_constraint_explanation}")

print("\nRight-sizing profiles (4+ patterns):")
profiles = load_profiles(db_path=db)
seen_patterns = set()
for p in profiles:
    if p.composition_pattern not in seen_patterns:
        seen_patterns.add(p.composition_pattern)
        print(f"  [{p.composition_pattern:<15}] {p.task_archetype} q≥{p.quality_min} lat≤{p.latency_max_ms}ms {p.regulatory_regime or ''}")

print("\nRunning tests/test_decision_rule.py ...")
r = subprocess.run(["python3","-m","pytest","tests/test_decision_rule.py","-v","--tb=short"],
                   capture_output=True, text=True)
print(r.stdout[-2000:])
tests_pass = r.returncode == 0

n_patterns = len(seen_patterns)
gate_pass = n_patterns>=4 and tests_pass
print("\n" + "="*60); print("GATE W9:")
print(f"  ≥4 profile patterns: {'✅' if n_patterns>=4 else '❌'} ({n_patterns}: {sorted(seen_patterns)})")
print(f"  right_size() works:  {'✅' if result is not None else '❌'}")
print(f"  tests pass:          {'✅' if tests_pass else '❌'}")
print(f"\nGATE W9: {'PASS ✅' if gate_pass else 'FAIL ❌'}")
sys.exit(0 if gate_pass else 1)
