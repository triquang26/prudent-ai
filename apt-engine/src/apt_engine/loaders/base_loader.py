"""Base loader interface."""
from __future__ import annotations
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[2]))
from apt_engine.db import connect


class BaseLoader(ABC):
    def __init__(self, db_path):
        self.db_path = db_path

    def load(self) -> int:
        con = connect(self.db_path)
        n = self._load(con)
        con.commit()
        con.close()
        return n

    @abstractmethod
    def _load(self, con: sqlite3.Connection) -> int:
        """Insert rows into DB, return count of benchmark_run rows inserted."""

    def _ins_source(self, con, sid, stype, name, url, date, lic):
        con.execute("INSERT OR IGNORE INTO source VALUES(?,?,?,?,?,?)",
                    (sid, stype, name, url, date, lic))

    def _ins_ev(self, con, eid, sid, etype, desc, page, date):
        con.execute("INSERT OR IGNORE INTO evidence_item VALUES(?,?,?,?,?,?)",
                    (eid, sid, etype, desc, page, date))

    def _ins_comp_item(self, con, cid, name, ctype, provider, ver, params, lic, ow):
        con.execute("INSERT OR IGNORE INTO component VALUES(?,?,?,?,?,?,?,?)",
                    (cid, name, ctype, provider, ver, params, lic, ow))

    def _ins_composition(self, con, cid, name, pattern, task, eid, notes):
        con.execute("INSERT OR IGNORE INTO composition VALUES(?,?,?,?,?,?)",
                    (cid, name, pattern, task, eid, notes))

    def _ins_run(self, con, run_id, comp_id, cmp_id, ev_id, task, hw,
                 quality, lat, cost, energy, mem, qmetric, smetric, notes):
        con.execute("INSERT OR IGNORE INTO benchmark_run VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (run_id, comp_id, cmp_id, ev_id, task, hw,
                     quality, lat, cost, energy, mem, qmetric, smetric, notes))
