#!/usr/bin/env python3
"""make show-w7: agent comps + cost-quality frontier + web-nav."""
import sys
sys.path.insert(0, "src")
from apt_engine.db import connect, DB_PATH, init_db

db = sys.argv[1] if len(sys.argv)>1 else str(DB_PATH)
init_db(db); con = connect(db)
print("="*60); print("SHOW W7: Agent Compositions + Frontier"); print("="*60)

agents = con.execute(
    "SELECT name, composition_pattern, task_archetype FROM composition "
    "WHERE composition_pattern IN ('single_agent','multi_agent','web_nav') ORDER BY composition_pattern"
).fetchall()
print(f"\nAgent compositions ({len(agents)}):")
for a in agents:
    print(f"  [{a['composition_pattern']:12}] {a['name']} — {a['task_archetype']}")

web_nav = con.execute("SELECT COUNT(*) FROM composition WHERE composition_pattern='web_nav'").fetchone()[0]

# Cost-quality frontier
print("\nCost-quality frontier (summarization task):")
frontier = con.execute(
    "SELECT c.name, AVG(br.quality) as q, AVG(br.latency_p95_ms) as lat, "
    "AVG(br.cost_per_1k_tokens) as cost "
    "FROM benchmark_run br JOIN composition c ON br.composition_id=c.composition_id "
    "WHERE br.quality IS NOT NULL AND br.cost_per_1k_tokens IS NOT NULL "
    "GROUP BY c.composition_id ORDER BY cost ASC LIMIT 8"
).fetchall()
print(f"  {'Name':<35} {'Quality':>8} {'Lat(ms)':>8} {'Cost/1k':>8}")
print("  " + "-"*62)
for r in frontier:
    print(f"  {r['name']:<35} {r['q']:>8.3f} {r['lat']:>8.0f} {r['cost']:>8.4f}")

con.close()
n_agent = len([a for a in agents if a['composition_pattern'] in ('single_agent','multi_agent')])
gate_pass = n_agent>=1 and len(frontier)>=1 and web_nav>=1
print("\n" + "="*60); print("GATE W7:")
print(f"  agent rows:          {'✅' if n_agent>=1 else '❌'} ({n_agent})")
print(f"  ≥1 frontier row:     {'✅' if len(frontier)>=1 else '❌'}")
print(f"  web_nav composition: {'✅' if web_nav>=1 else '❌'}")
print(f"\nGATE W7: {'PASS ✅' if gate_pass else 'FAIL ❌'}")
sys.exit(0 if gate_pass else 1)
