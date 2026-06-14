"""Test Q1-Q4 return ≥1 row each with correct structure."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "src"))
from apt_engine.db import init_db
from apt_engine.queries import Q1_missing, Q2_feasible, Q3_borderline, Q4_binding

def make_db(tmp_path):
    db = str(tmp_path / "q.db")
    con = init_db(db)
    con.execute(
        "INSERT INTO source VALUES('s1','benchmark','T','http://x','2024-01-01','MIT')"
    )
    con.execute(
        "INSERT INTO evidence_item VALUES('e1','s1','metric','test evidence',NULL,NULL)"
    )
    con.execute(
        "INSERT INTO component VALUES('c1','LLM','llm','Co','1',7.0,'MIT',1)"
    )
    # comp1: has quality/latency/cost evidence (feasible for low threshold)
    con.execute(
        "INSERT INTO composition VALUES('comp1','A','bare_llm','qa','e1',NULL)"
    )
    con.execute(
        "INSERT INTO benchmark_run "
        "VALUES('r1','comp1','c1','e1','qa','A100',0.90,200.0,0.005,50.0,10.0,'accuracy','acc',NULL)"
    )
    # comp2: missing quality (→ Q1); has latency only
    con.execute(
        "INSERT INTO composition VALUES('comp2','B','bare_llm','qa','e1',NULL)"
    )
    con.execute(
        "INSERT INTO benchmark_run "
        "VALUES('r2','comp2','c1','e1','qa','A100',NULL,800.0,0.05,NULL,NULL,NULL,'latency',NULL)"
    )
    con.commit()
    con.close()
    return db

def test_Q1_missing(tmp_path):
    db = make_db(tmp_path)
    rows = Q1_missing(db_path=db)
    assert len(rows) >= 1
    assert "missing_axes" in rows[0]

def test_Q2_feasible(tmp_path):
    db = make_db(tmp_path)
    rows = Q2_feasible(quality_min=0.5, latency_max=500.0, cost_max=0.1, db_path=db)
    assert len(rows) >= 1

def test_Q3_borderline(tmp_path):
    db = make_db(tmp_path)
    rows = Q3_borderline(quality_min=0.88, latency_max=210.0, cost_max=0.006, margin=0.20, db_path=db)
    assert len(rows) >= 1

def test_Q4_binding(tmp_path):
    db = make_db(tmp_path)
    # comp2 has latency 800ms > 300ms max → binding
    rows = Q4_binding(quality_min=0.95, latency_max=300.0, cost_max=0.01, db_path=db)
    assert len(rows) >= 1
    assert "binding_constraints" in rows[0]
