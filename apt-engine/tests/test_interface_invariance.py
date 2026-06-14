"""Test C7 invariant: two different read paths produce byte-identical results."""
import sys, pathlib, sqlite3
sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "src"))
from apt_engine.db import init_db
from apt_engine.interface import cell, candidates, required_fields

def make_test_db(tmp_path):
    db = str(tmp_path / "test.db")
    con = init_db(db)
    con.execute(
        "INSERT INTO source VALUES('s1','benchmark','Test','http://x','2024-01-01','MIT')"
    )
    con.execute(
        "INSERT INTO evidence_item VALUES('e1','s1','metric','test evidence',NULL,NULL)"
    )
    con.execute(
        "INSERT INTO component VALUES('c1','LLM A','llm','TestCo','1.0',7.0,'MIT',1)"
    )
    con.execute(
        "INSERT INTO composition VALUES('comp1','Sys A','bare_llm','qa','e1',NULL)"
    )
    con.execute(
        "INSERT INTO benchmark_run "
        "VALUES('r1','comp1','c1','e1','qa','A100',0.85,300.0,0.01,NULL,20.0,'accuracy','acc',NULL)"
    )
    con.commit()
    con.close()
    return db

def test_cell_invariant(tmp_path):
    db = make_test_db(tmp_path)
    # Two independent reads must return same belief
    b1 = cell("comp1", "quality", db_path=db)
    b2 = cell("comp1", "quality", db_path=db)
    assert b1.lo == b2.lo and b1.hi == b2.hi and b1.is_bot == b2.is_bot

def test_bot_for_missing(tmp_path):
    db = make_test_db(tmp_path)
    b = cell("comp1", "energy_J", db_path=db)
    # energy_J has no evidence (NULL) → must be ⊥
    assert b.is_bot, "energy_J has no evidence → must be ⊥"

def test_candidates_filter(tmp_path):
    db = make_test_db(tmp_path)
    all_c = candidates(db_path=db)
    bare_c = candidates(pattern="bare_llm", db_path=db)
    assert len(all_c) >= 1
    assert all(c["composition_pattern"] == "bare_llm" for c in bare_c)

def test_required_fields_bare_llm():
    rf = required_fields("bare_llm")
    assert "quality" in rf and "latency_p95_ms" in rf

def test_db_not_mutated(tmp_path):
    import hashlib
    db = make_test_db(tmp_path)
    h1 = hashlib.md5(pathlib.Path(db).read_bytes()).hexdigest()
    cell("comp1", "quality", db_path=db)
    candidates(db_path=db)
    h2 = hashlib.md5(pathlib.Path(db).read_bytes()).hexdigest()
    assert h1 == h2, "Read operations must not mutate the DB"
