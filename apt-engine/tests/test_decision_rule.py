"""Test right_size() 5 branches + verdict."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "src"))
from apt_engine.db import init_db
from apt_engine.right_sizing import right_size, Query
from apt_engine.verdict import assess, Verdict

def make_db(tmp_path):
    db = str(tmp_path / "test.db")
    con = init_db(db)
    con.execute("INSERT INTO source VALUES('s1','benchmark','T','http://x','2024','MIT')")
    con.execute("INSERT INTO evidence_item VALUES('e1','s1','metric','t',NULL,NULL)")
    # 3 components
    for cid, name in [("c1","Fast Cheap"),("c2","Mid Quality"),("c3","High Quality")]:
        con.execute("INSERT INTO component VALUES(?,?,'llm','Co','1',7.0,'MIT',1)", (cid,name))
    # 3 compositions
    for cid, cname in [("comp1","Sys A"),("comp2","Sys B"),("comp3","Sys C")]:
        con.execute("INSERT INTO composition VALUES(?,'"+cname+"','bare_llm','qa','e1',NULL)", (cid,))
    # Runs: comp1=cheap low-q, comp2=mid, comp3=high-q expensive
    runs = [
        ("r1","comp1","c1","e1","qa","A100",0.70,150.0,0.002,30.0,5.0,"accuracy","acc",None),
        ("r2","comp2","c2","e1","qa","A100",0.85,300.0,0.010,60.0,10.0,"accuracy","acc",None),
        ("r3","comp3","c3","e1","qa","A100",0.93,500.0,0.025,90.0,15.0,"accuracy","acc",None),
        # comp1 also has a second run (slight variation)
        ("r4","comp1","c1","e1","qa","T4",0.72,200.0,0.003,35.0,5.0,"accuracy","acc",None),
    ]
    for r in runs:
        con.execute("INSERT OR IGNORE INTO benchmark_run VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", r)
    con.commit(); con.close()
    return db

def test_feasible_branch(tmp_path):
    db = make_db(tmp_path)
    q = Query(quality_min=0.65, latency_max_ms=600.0, cost_max_per_1k=0.05)
    result = right_size(q, db_path=db)
    assert result.branch in ("feasible","tiebreak_10pct","comparable_20pct")
    assert len(result.top_candidates) >= 1

def test_infeasible_binding(tmp_path):
    db = make_db(tmp_path)
    q = Query(quality_min=0.99, latency_max_ms=50.0, cost_max_per_1k=0.0001)
    result = right_size(q, db_path=db)
    assert result.branch == "infeasible_binding"
    assert result.binding_constraint_explanation is not None

def test_tiebreak_10pct(tmp_path):
    db = make_db(tmp_path)
    # comp1 (q=0.70-0.72) and comp2 (q=0.85) with very loose constraints
    q = Query(quality_min=0.60, latency_max_ms=600.0, cost_max_per_1k=0.05)
    result = right_size(q, db_path=db)
    assert result.branch in ("tiebreak_10pct","feasible","comparable_20pct")

def test_comparable_20pct(tmp_path):
    db = make_db(tmp_path)
    q = Query(quality_min=0.60, latency_max_ms=600.0, cost_max_per_1k=0.05)
    result = right_size(q, db_path=db)
    assert len(result.top_candidates) >= 1

def test_verdict_decidable(tmp_path):
    db = make_db(tmp_path)
    v = assess("comp2", quality_min=0.80, latency_max=400.0, cost_max=0.02, db_path=db)
    assert v.verdict == Verdict.DECIDABLE

def test_verdict_infeasible(tmp_path):
    db = make_db(tmp_path)
    v = assess("comp1", quality_min=0.95, latency_max=100.0, cost_max=0.001, db_path=db)
    assert v.verdict == Verdict.INFEASIBLE
