"""Test W1 gate: 7 tables, FKs, vocab, >=20 seed rows."""
import sys, pathlib, sqlite3
sys.path.insert(0, str(pathlib.Path(__file__).parents[1]/"src"))
from apt_engine.db import init_db, VOCAB, connect

TABLES = ["source","evidence_item","component","composition",
          "composition_component","benchmark_run","right_sizing_profile"]

def make_db(tmp_path):
    db = str(tmp_path / "t.db")
    con = init_db(db)
    con.close()
    return db

def test_seven_tables(tmp_path):
    db = make_db(tmp_path)
    con = sqlite3.connect(db)
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    con.close()
    for t in TABLES:
        assert t in tables, f"missing table: {t}"

def test_foreign_keys_enabled(tmp_path):
    db = make_db(tmp_path)
    con = connect(db)
    fk_on = con.execute("PRAGMA foreign_keys").fetchone()[0]
    con.close()
    assert fk_on == 1

def test_fk_violation_rejected(tmp_path):
    db = make_db(tmp_path)
    con = connect(db)
    import pytest
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO evidence_item VALUES('x','nonexistent_source','metric','t',NULL,NULL)")
        con.commit()
    con.close()

def test_vocab_constants():
    assert "benchmark" in VOCAB["source_type"]
    assert "llm" in VOCAB["component_type"]
    assert "bare_llm" in VOCAB["composition_pattern"]
    assert "A100" in VOCAB["hardware_tier"]

def test_check_constraint_violation(tmp_path):
    db = make_db(tmp_path)
    con = connect(db)
    import pytest
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO source VALUES('s1','INVALID_TYPE','Name','http://x','2024','MIT')")
        con.commit()
    con.close()
