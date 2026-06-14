"""Shared loader utilities."""
from __future__ import annotations
import sqlite3
import sys
from pathlib import Path

# Make sure the src dir is on the path when run as __main__
sys.path.insert(0, str(Path(__file__).parents[3]))

from apt_engine.db import init_db, connect


def _upsert_source(con: sqlite3.Connection, source_id, source_type, name, url, snapshot_date, license_):
    con.execute(
        """INSERT OR IGNORE INTO source
           (source_id, source_type, name, url, snapshot_date, license)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (source_id, source_type, name, url, snapshot_date, license_),
    )


def _upsert_evidence(con, evidence_id, source_id, evidence_type, description, page_ref=None, retrieved_date=None):
    con.execute(
        """INSERT OR IGNORE INTO evidence_item
           (evidence_id, source_id, evidence_type, description, page_ref, retrieved_date)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (evidence_id, source_id, evidence_type, description, page_ref, retrieved_date),
    )


def _upsert_component(con, component_id, name, component_type, provider=None,
                      version=None, params_B=None, license_=None, open_weights=0):
    con.execute(
        """INSERT OR IGNORE INTO component
           (component_id, name, component_type, provider, version, params_B, license, open_weights)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (component_id, name, component_type, provider, version, params_B, license_, open_weights),
    )


def _upsert_composition(con, composition_id, name, composition_pattern,
                        task_archetype=None, evidence_id=None, notes=None):
    con.execute(
        """INSERT OR IGNORE INTO composition
           (composition_id, name, composition_pattern, task_archetype, evidence_id, notes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (composition_id, name, composition_pattern, task_archetype, evidence_id, notes),
    )


def _upsert_run(con, run_id, composition_id, component_id, evidence_id, task,
                hardware_tier=None, quality=None, latency_p95_ms=None,
                cost_per_1k_tokens=None, energy_J=None, memory_GB=None,
                quality_metric=None, source_metric=None, notes=None):
    con.execute(
        """INSERT OR IGNORE INTO benchmark_run
           (run_id, composition_id, component_id, evidence_id, task, hardware_tier,
            quality, latency_p95_ms, cost_per_1k_tokens, energy_J, memory_GB,
            quality_metric, source_metric, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (run_id, composition_id, component_id, evidence_id, task, hardware_tier,
         quality, latency_p95_ms, cost_per_1k_tokens, energy_J, memory_GB,
         quality_metric, source_metric, notes),
    )


def _link_composition_component(con, composition_id, component_id, role, execution_order=None):
    con.execute(
        """INSERT OR IGNORE INTO composition_component
           (composition_id, component_id, role, execution_order)
           VALUES (?, ?, ?, ?)""",
        (composition_id, component_id, role, execution_order),
    )


def loader_main(db_path: str, load_fn):
    """Standard main for all loaders."""
    init_db(db_path)
    con = connect(db_path)
    n = load_fn(con)
    con.commit()
    con.close()
    print(f"[{load_fn.__module__}] inserted/updated {n} record-groups into {db_path}")
